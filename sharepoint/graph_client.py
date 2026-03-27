"""
Thin wrapper around Microsoft Graph API REST calls.
All requests are token-refreshed automatically.
"""

import logging
import time
import urllib.parse
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
    """
    List children of a drive item. No $select so file/folder facets and size
    are always returned (some tenants omit fields when $select is used).
    """
    url = f"{BASE}/drives/{drive_id}/items/{item_id}/children"
    return list(_paginate(url))


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


def get_site_drive_item(site_id: str, item_id: str) -> dict | None:
    """GET full driveItem metadata (resolves driveId; fixes many Search API quirks)."""
    try:
        enc_site = urllib.parse.quote(site_id, safe="")
        enc_item = urllib.parse.quote(str(item_id), safe="")
        return _get(f"{BASE}/sites/{enc_site}/drive/items/{enc_item}")
    except requests.HTTPError as exc:
        logger.debug("get_site_drive_item failed: %s", exc)
        return None


def search_site_drive_root(site_id: str, query: str, top: int = 25) -> list[dict]:
    """
    Keyword search in the site's document libraries (Graph drive /root/search).

    Returns driveItems with complete parentReference.driveId — more reliable than
    /search/query for downloading content.
    """
    try:
        drives = list_drives(site_id)
    except requests.HTTPError as exc:
        logger.warning("list_drives failed: %s", exc)
        return []

    inner = query.replace("'", "''")
    odata_fn = f"search(q='{inner}')"
    encoded = urllib.parse.quote(odata_fn, safe="()'")
    out: list[dict] = []
    for drive in drives:
        drive_id = drive["id"]
        e_drive = urllib.parse.quote(drive_id, safe="")
        url = f"{BASE}/drives/{e_drive}/root/{encoded}"
        try:
            data = _get(url, {"$top": str(min(200, top - len(out)))})
            out.extend(data.get("value") or [])
        except requests.HTTPError as exc:
            logger.warning("drive root search failed (%s): %s", drive.get("name"), exc)
            continue
        if len(out) >= top:
            break
    return out[:top]


def download_drive_item_content(
    resource: dict,
    fallback_site_id: str | None = None,
) -> bytes:
    """
    Download bytes from a driveItem (e.g. Search hit).

    Resolves metadata via ``GET /sites/{siteId}/drive/items/{id}`` when possible
    so ``driveId`` is always correct for ``/drives/.../items/.../content``.
    """
    item_id = resource.get("id")
    if not item_id:
        raise ValueError("driveItem missing id")

    parent = resource.get("parentReference") or {}
    drive_id = parent.get("driveId")
    site_id = parent.get("siteId") or fallback_site_id

    if site_id:
        meta = get_site_drive_item(site_id, str(item_id))
        if meta:
            drive_id = (meta.get("parentReference") or {}).get("driveId") or drive_id
            item_id = meta.get("id", item_id)

    if drive_id:
        return download_item(drive_id, str(item_id))

    if site_id:
        enc_site = urllib.parse.quote(site_id, safe="")
        enc_item = urllib.parse.quote(str(item_id), safe="")
        url = f"{BASE}/sites/{enc_site}/drive/items/{enc_item}/content"
        return _get_bytes(url)

    raise ValueError("driveItem missing driveId, siteId, and no fallback_site_id")


# ── Search ───────────────────────────────────────────────────

def search_documents(
    query: str,
    site_path: str | None = None,
    top: int = 10,
    from_: int = 0,
) -> list[dict]:
    """
    Use Graph Search API to retrieve drive items.

    ``contentSources`` must **not** be used with ``entityTypes: driveItem`` — it is
    only valid for ``externalItem``. Site scope is applied via KQL ``Path:`` instead.

    Application permissions require ``GRAPH_SEARCH_REGION`` in settings.
    """
    url = f"{BASE}/search/query"
    qs = query.strip()
    if site_path and settings.SHAREPOINT_HOSTNAME:
        host = settings.SHAREPOINT_HOSTNAME.rstrip("/")
        name = site_path.strip().strip("/")
        site_url = f"https://{host}/sites/{name}"
        # KQL: limit results to this site (do not use contentSources for driveItem)
        qs = f'{qs} Path:"{site_url}*"'

    req: dict[str, Any] = {
        "entityTypes": ["driveItem"],
        "query": {"queryString": qs},
        "from": max(0, from_),
        "size": min(top, 500),
    }
    if settings.GRAPH_SEARCH_REGION:
        req["region"] = settings.GRAPH_SEARCH_REGION

    payload: dict[str, Any] = {"requests": [req]}

    resp = requests.post(url, headers={**_headers(), "Content-Type": "application/json"}, json=payload, timeout=60)
    if not resp.ok:
        logger.warning("search/query error %s: %s", resp.status_code, resp.text[:500])
    resp.raise_for_status()
    body = resp.json()
    containers = body.get("value", [{}])[0].get("hitsContainers", [])
    if not containers:
        return []
    hits = containers[0].get("hits", [])
    return [h.get("resource", {}) for h in hits if h.get("resource")]
