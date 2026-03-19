"""
Thin wrapper around Microsoft Graph API REST calls.
All requests are token-refreshed automatically.
"""

import logging
import time
from typing import Any, Generator

import requests

from auth.graph_auth import get_access_token
from config import settings

logger = logging.getLogger(__name__)

BASE = settings.GRAPH_BASE_URL
_RETRY_CODES = {429, 503}
_MAX_RETRIES = 5


def _headers() -> dict:
    return {"Authorization": f"Bearer {get_access_token()}"}


def _get(url: str, params: dict | None = None, retry: int = 0) -> dict:
    """GET with automatic retry on throttle."""
    resp = requests.get(url, headers=_headers(), params=params, timeout=30)

    if resp.status_code in _RETRY_CODES and retry < _MAX_RETRIES:
        wait = int(resp.headers.get("Retry-After", 2 ** retry))
        logger.warning("Throttled – waiting %ds (retry %d)", wait, retry + 1)
        time.sleep(wait)
        return _get(url, params, retry + 1)

    resp.raise_for_status()
    return resp.json()


def _get_bytes(url: str, retry: int = 0) -> bytes:
    """Download binary content with retry."""
    resp = requests.get(url, headers=_headers(), timeout=60)

    if resp.status_code in _RETRY_CODES and retry < _MAX_RETRIES:
        wait = int(resp.headers.get("Retry-After", 2 ** retry))
        time.sleep(wait)
        return _get_bytes(url, retry + 1)

    resp.raise_for_status()
    return resp.content


def _paginate(url: str, params: dict | None = None) -> Generator[dict, None, None]:
    """Walk through all @odata.nextLink pages."""
    while url:
        data = _get(url, params)
        yield from data.get("value", [])
        url = data.get("@odata.nextLink")
        params = None  # nextLink already includes query params


# ── Site operations ──────────────────────────────────────────

def list_sites() -> list[dict]:
    """Return all SharePoint sites in the tenant."""
    url = f"{BASE}/sites?search=*"
    return list(_paginate(url))


def get_site(site_name: str) -> dict | None:
    """Lookup a site by display name or relative path."""
    hostname = settings.SHAREPOINT_HOSTNAME
    url = f"{BASE}/sites/{hostname}:/sites/{site_name}"
    try:
        return _get(url)
    except requests.HTTPError as exc:
        if exc.response.status_code == 404:
            return None
        raise


def list_drives(site_id: str) -> list[dict]:
    """List document libraries (drives) for a site."""
    url = f"{BASE}/sites/{site_id}/drives"
    return list(_paginate(url))


# ── File / item operations ───────────────────────────────────

def list_children(drive_id: str, item_id: str = "root") -> list[dict]:
    url = f"{BASE}/drives/{drive_id}/items/{item_id}/children"
    return list(_paginate(url, {"$select": "id,name,size,lastModifiedDateTime,file,folder,parentReference"}))


def get_delta(drive_id: str, delta_token: str | None = None) -> tuple[list[dict], str]:
    """
    Fetch changed items since last delta token.
    Returns (items, new_delta_token).
    """
    if delta_token:
        url = f"{BASE}/drives/{drive_id}/root/delta(token='{delta_token}')"
    else:
        url = f"{BASE}/drives/{drive_id}/root/delta"

    items: list[dict] = []
    new_token = ""

    while url:
        data = _get(url)
        items.extend(data.get("value", []))
        url = data.get("@odata.nextLink")
        if not url:
            new_token = data.get("@odata.deltaLink", "").split("token='")[-1].rstrip("'")

    return items, new_token


def download_item(drive_id: str, item_id: str) -> bytes:
    """Download the raw bytes of a drive item."""
    url = f"{BASE}/drives/{drive_id}/items/{item_id}/content"
    return _get_bytes(url)


# ── Search ───────────────────────────────────────────────────

def search_documents(query: str, site_id: str | None = None, top: int = 10) -> list[dict]:
    """
    Use Graph Search API to retrieve most-relevant documents.
    Falls back to site-scoped search when site_id is given.
    """
    url = f"{BASE}/search/query"
    payload: dict[str, Any] = {
        "requests": [
            {
                "entityTypes": ["driveItem"],
                "query": {"queryString": query},
                "size": top,
                "fields": ["id", "name", "webUrl", "parentReference", "lastModifiedDateTime"],
            }
        ]
    }
    if site_id:
        payload["requests"][0]["contentSources"] = [f"/sites/{site_id}"]

    resp = requests.post(url, headers={**_headers(), "Content-Type": "application/json"}, json=payload, timeout=30)
    resp.raise_for_status()
    hits = resp.json().get("value", [{}])[0].get("hitsContainers", [{}])[0].get("hits", [])
    return [h.get("resource", {}) for h in hits]
