"""Shared Composio v3 client wrapper.

Composio retired the v1 SDK (`composio-core`): there is no `ComposioToolSet`
or `Action` anymore. The current `composio` package (>= 0.21) exposes tools as
raw slugs on a modern REST API, and manual execution requires the acting
user's connected account plus an explicit toolkit version. Every publisher in
the daemon funnels through ComposioClient so env wiring, connection
resolution, and version pinning live in one place.
"""

import logging
import os

logger = logging.getLogger("abvorn.deploy.composio_client")

try:
    from composio import Composio
    HAS_COMPOSIO = True
except ImportError:
    HAS_COMPOSIO = False
    Composio = None

LINKEDIN_MY_INFO_TOOL = "LINKEDIN_GET_MY_INFO"


class ComposioConnectionError(RuntimeError):
    """Raised when a toolkit has no usable connected account / version."""


class ComposioClient:
    """Minimal v3 wrapper: resolve connection + version, then execute tools."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.client = None
        self._toolkit_state = {}  # toolkit -> (user_id, connected_account_id, version)
        self._linkedin_urn = ""
        if api_key and HAS_COMPOSIO:
            try:
                os.environ["COMPOSIO_API_KEY"] = api_key
                self.client = Composio()
                logger.info("Composio v3 client initialized")
            except Exception as e:
                logger.warning(f"Composio init failed: {e}")

    @property
    def available(self) -> bool:
        return self.client is not None

    def toolkit_version(self, toolkit: str) -> str | None:
        """Resolve the publishable toolkit version from the Composio API."""
        if toolkit in self._toolkit_state:
            return self._toolkit_state[toolkit][2]
        try:
            raw_tools = self.client.tools.get_raw_composio_tools(toolkits=[toolkit])
        except Exception as e:
            logger.warning(f"composio toolkit {toolkit} unavailable: {e}")
            return None
        if not raw_tools:
            return None
        return getattr(raw_tools[0], "version", None) or None

    def connection(self, toolkit: str):
        """Return (user_id, connected_account_id, version) for a toolkit, cached.

        The connection is resolved from the live list of connected accounts so
        the wrapper survives account rotation without code changes.
        """
        state = self._toolkit_state.get(toolkit)
        if state is not None:
            return state
        state = (None, None, None)
        try:
            accounts = self.client.connected_accounts.list()
            items = getattr(accounts, "items", None) or []
            for acct in items:
                tk = getattr(acct, "toolkit", None)
                if getattr(tk, "slug", None) != toolkit:
                    continue
                if getattr(acct, "status", None) != "ACTIVE":
                    continue
                state = (
                    getattr(acct, "user_id", None) or os.environ.get("COMPOSIO_USER_ID", ""),
                    getattr(acct, "id", None),
                    self.toolkit_version(toolkit),
                )
                break
        except Exception as e:
            logger.warning(f"composio connection lookup failed for {toolkit}: {e}")
        self._toolkit_state[toolkit] = state
        return state

    def resolve_connection(self, toolkit: str):
        """Return (user_id, connected_account_id, version) or raise."""
        uid, caid, version = self.connection(toolkit)
        if not uid or not caid:
            raise ComposioConnectionError(
                f"no ACTIVE composio connected account for '{toolkit}'"
            )
        if not version:
            raise ComposioConnectionError(
                f"no toolkit version available for '{toolkit}'"
            )
        return uid, caid, version

    def execute(self, toolkit: str, slug: str, arguments: dict) -> dict:
        """Execute a tool against the toolkit's connected account.

        Returns the response data on success; raises on execution failure so
        callers keep their own fallback semantics (staged / export / failed).
        """
        uid, caid, version = self.resolve_connection(toolkit)
        try:
            resp = self.client.tools.execute(
                slug=slug,
                arguments=arguments,
                user_id=uid,
                connected_account_id=caid,
                version=version,
            )
        except Exception as e:
            raise RuntimeError(f"composio {slug}: {str(e)[:200]}") from e
        if not (resp and resp.get("successful")):
            raise RuntimeError(
                f"composio {slug}: {str(resp.get('error') or 'unknown failure')[:300]}"
            )
        return resp.get("data") or {}

    def linkedin_author_urn(self) -> str:
        """Resolve the author URN for LinkedIn posts (env override or discovery)."""
        urn = os.environ.get("LINKEDIN_AUTHOR_URN", "").strip()
        if urn:
            return urn
        if self._linkedin_urn:
            return self._linkedin_urn
        uid, caid, version = self.resolve_connection("linkedin")
        try:
            resp = self.client.tools.execute(
                slug=LINKEDIN_MY_INFO_TOOL,
                arguments={},
                user_id=uid,
                connected_account_id=caid,
                version=version,
            )
            profile_id = (resp.get("data") or {}).get("id")
            if not profile_id:
                raise ComposioConnectionError(
                    "linkedin profile id missing from LINKEDIN_GET_MY_INFO"
                )
            self._linkedin_urn = f"urn:li:person:{profile_id}"
            return self._linkedin_urn
        except Exception as e:
            raise ComposioConnectionError(
                f"linkedin author URN lookup failed: {e}"
            ) from e