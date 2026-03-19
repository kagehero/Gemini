"""
Microsoft Graph API authentication.

Supports three flows:
  1. Client Credentials  – Azure App with client secret (production)
  2. Device Code Flow    – Interactive browser login (easy PoC setup)
  3. Username/Password   – ROPC flow (PoC with provided credentials)
"""

import json
import logging
from pathlib import Path

import msal

from config import settings

logger = logging.getLogger(__name__)


class GraphAuth:
    """Manages Microsoft Graph API token acquisition with caching."""

    def __init__(self):
        self._token_cache = msal.SerializableTokenCache()
        self._cache_path = settings.TOKEN_CACHE_PATH
        self._load_cache()
        self._app = self._build_app()

    def _load_cache(self):
        if self._cache_path.exists():
            self._token_cache.deserialize(self._cache_path.read_text())

    def _save_cache(self):
        if self._token_cache.has_state_changed:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(self._token_cache.serialize())

    def _build_app(self) -> msal.ClientApplication:
        authority = f"https://login.microsoftonline.com/{settings.TENANT_ID}"

        if settings.CLIENT_SECRET:
            return msal.ConfidentialClientApplication(
                client_id=settings.CLIENT_ID,
                client_credential=settings.CLIENT_SECRET,
                authority=authority,
                token_cache=self._token_cache,
            )
        return msal.PublicClientApplication(
            client_id=settings.CLIENT_ID,
            authority=authority,
            token_cache=self._token_cache,
        )

    def get_token(self) -> str:
        """Return a valid access token, refreshing if necessary."""
        scopes = settings.GRAPH_SCOPES

        # Try silent (cached) first
        accounts = self._app.get_accounts()
        if accounts:
            result = self._app.acquire_token_silent(scopes, account=accounts[0])
            if result and "access_token" in result:
                self._save_cache()
                return result["access_token"]

        # Client credentials flow (app-only)
        if isinstance(self._app, msal.ConfidentialClientApplication):
            result = self._app.acquire_token_for_client(scopes=scopes)
            if result and "access_token" in result:
                self._save_cache()
                return result["access_token"]
            raise RuntimeError(f"Client credentials failed: {result.get('error_description')}")

        # Username / password (ROPC) flow
        if settings.SP_USERNAME and settings.SP_PASSWORD:
            user_scopes = [
                "https://graph.microsoft.com/Sites.Read.All",
                "https://graph.microsoft.com/Files.Read.All",
                "offline_access",
            ]
            result = self._app.acquire_token_by_username_password(
                username=settings.SP_USERNAME,
                password=settings.SP_PASSWORD,
                scopes=user_scopes,
            )
            if result and "access_token" in result:
                self._save_cache()
                logger.info("Authenticated via username/password flow")
                return result["access_token"]
            logger.warning(
                "Username/password failed: %s – falling back to device code",
                result.get("error_description"),
            )

        # Device code flow (interactive fallback)
        return self._device_code_flow()

    def _device_code_flow(self) -> str:
        user_scopes = [
            "https://graph.microsoft.com/Sites.Read.All",
            "https://graph.microsoft.com/Files.Read.All",
            "offline_access",
        ]
        flow = self._app.initiate_device_flow(scopes=user_scopes)
        if "user_code" not in flow:
            raise RuntimeError("Failed to initiate device code flow")

        print("\n" + "=" * 60)
        print("ブラウザで以下のURLにアクセスしてコードを入力してください:")
        print(f"  URL : {flow['verification_uri']}")
        print(f"  Code: {flow['user_code']}")
        print("=" * 60 + "\n")

        result = self._app.acquire_token_by_device_flow(flow)
        if "access_token" in result:
            self._save_cache()
            logger.info("Authenticated via device code flow")
            return result["access_token"]
        raise RuntimeError(f"Device code flow failed: {result.get('error_description')}")


_auth_instance: GraphAuth | None = None


def get_auth() -> GraphAuth:
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = GraphAuth()
    return _auth_instance


def get_access_token() -> str:
    return get_auth().get_token()
