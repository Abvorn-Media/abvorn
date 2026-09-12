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

from pathlib import Path

logger = logging.getLogger("abvorn.deploy.composio_client")

try:
    from composio import Composio
    HAS_COMPOSIO = True
except ImportError:
    HAS_COMPOSIO = False
    Composio = None

LINKEDIN_MY_INFO_TOOL = "LINKEDIN_GET_MY_INFO"

INSTAGRAM_TOOLKIT = "instagram"
INSTAGRAM_GET_USER_INFO_TOOL = "INSTAGRAM_GET_USER_INFO"
INSTAGRAM_CAROUSEL_CONTAINER_TOOL = "INSTAGRAM_CREATE_CAROUSEL_CONTAINER"
INSTAGRAM_CREATE_POST_TOOL = "INSTAGRAM_CREATE_POST"

PINTEREST_TOOLKIT = "pinterest"
PINTEREST_CREATE_PIN_TOOL = "PINTEREST_CREATE_PIN"
PINTEREST_LIST_BOARDS_TOOL = "PINTEREST_LIST_BOARDS"
PINTEREST_CREATE_BOARD_TOOL = "PINTEREST_CREATE_BOARD"
PINTEREST_DEFAULT_BOARD = "Abvorn Finds"


class ComposioConnectionError(RuntimeError):
    """Raised when a toolkit has no usable connected account / version."""


class ComposioClient:
    """Minimal v3 wrapper: resolve connection + version, then execute tools."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.client = None
        self._toolkit_state = {}  # toolkit -> (user_id, connected_account_id, version)
        self._linkedin_urn = ""
        self._instagram_user_id = ""
        self._pinterest_board_id = ""
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

    def instagram_user_id(self) -> str:
        """Resolve the numeric Instagram Business/Creator account ID.

        Env override (INSTAGRAM_USER_ID) wins, then a cached discovery result,
        then live discovery via INSTAGRAM_GET_USER_INFO. The numeric ID is
        required by INSTAGRAM_CREATE_POST (the literal "me" is rejected).
        """
        env_id = os.environ.get("INSTAGRAM_USER_ID", "").strip()
        if env_id:
            return env_id
        if self._instagram_user_id:
            return self._instagram_user_id
        uid, caid, version = self.resolve_connection(INSTAGRAM_TOOLKIT)
        try:
            resp = self.client.tools.execute(
                slug=INSTAGRAM_GET_USER_INFO_TOOL,
                arguments={},
                user_id=uid,
                connected_account_id=caid,
                version=version,
            )
            user_id = (resp.get("data") or {}).get("id")
            if not user_id:
                raise ComposioConnectionError(
                    "instagram user id missing from INSTAGRAM_GET_USER_INFO"
                )
            self._instagram_user_id = str(user_id)
            return self._instagram_user_id
        except Exception as e:
            raise ComposioConnectionError(
                f"instagram user id lookup failed: {e}"
            ) from e

    def instagram_publish_carousel(self, caption: str,
                                   image_paths: list[str]) -> dict:
        """Publish a carousel from local image files.

        Uploads each image through Composio's file-upload pipeline
        (FileUploadable), creates a carousel container with the uploaded
        children, then publishes it with INSTAGRAM_CREATE_POST. Returns the
        create-post response data on success; raises on any step failure so
        the caller can keep its export fallback.
        """
        uid, caid, version = self.resolve_connection(INSTAGRAM_TOOLKIT)
        user_id = self.instagram_user_id()

        try:
            from composio.core.models._files import FileUploadable
        except ImportError as e:
            raise RuntimeError(
                f"composio FileUploadable unavailable: {e}"
            ) from e

        children = []
        for path in image_paths[:10]:
            fu = FileUploadable.from_path(
                client=self.client.client,
                file=path,
                tool=INSTAGRAM_CAROUSEL_CONTAINER_TOOL,
                toolkit=INSTAGRAM_TOOLKIT,
                sensitive_file_upload_protection=False,
            )
            children.append(fu.model_dump())

        container = self.execute(
            INSTAGRAM_TOOLKIT,
            INSTAGRAM_CAROUSEL_CONTAINER_TOOL,
            {
                "ig_user_id": user_id,
                "caption": caption[:2200],
                "child_image_files": children,
            },
        )
        creation_id = (container or {}).get("id") or ""
        if not creation_id:
            raise RuntimeError(
                "instagram carousel container returned no creation id"
            )

        return self.execute(
            INSTAGRAM_TOOLKIT,
            INSTAGRAM_CREATE_POST_TOOL,
            {"ig_user_id": user_id, "creation_id": creation_id},
        )

    # ------------------------------------------------------------------
    # Pinterest
    # ------------------------------------------------------------------

    def pinterest_board_id(self) -> str:
        """Resolve the destination Pinterest board (numeric ID).

        Priority: env PINTEREST_BOARD_ID, then the first existing board,
        then auto-create PINTEREST_DEFAULT_BOARD. Cached in-memory so the
        daemon posts to one stable board per process.
        """
        env_id = os.environ.get("PINTEREST_BOARD_ID", "").strip()
        if env_id:
            return env_id
        if self._pinterest_board_id:
            return self._pinterest_board_id
        cached = self._pinterest_cached_board()
        if cached:
            self._pinterest_board_id = cached
            return cached
        self.resolve_connection(PINTEREST_TOOLKIT)
        board = self.execute(
            PINTEREST_TOOLKIT,
            PINTEREST_CREATE_BOARD_TOOL,
            {"name": PINTEREST_DEFAULT_BOARD,
             "description": "Real specs, prices, and owner feedback across the products we compare."},
        )
        board_id = (board or {}).get("id") or (board or {}).get("board_id") or ""
        if not board_id:
            raise ComposioConnectionError(
                "pinterest board auto-create returned no board id"
            )
        self._pinterest_board_id = str(board_id)
        self._pinterest_persist_board(str(board_id))
        logger.info(f"pinterest: using auto-created board '{PINTEREST_DEFAULT_BOARD}' ({board_id})")
        return self._pinterest_board_id

    def _pinterest_cached_board(self) -> str:
        """First existing board id, or a previously persisted id."""
        persist = Path.home() / ".abvorn" / "pinterest_board_id.txt"
        if persist.exists():
            existing = persist.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        if self._pinterest_board_id:
            return self._pinterest_board_id
        try:
            self.resolve_connection(PINTEREST_TOOLKIT)
            resp = self.execute(PINTEREST_TOOLKIT, PINTEREST_LIST_BOARDS_TOOL, {})
            items = (resp or {}).get("items") or []
            for b in items:
                bid = b.get("id")
                if bid:
                    return str(bid)
        except Exception as e:
            logger.warning(f"pinterest: board discovery failed ({e}) — will auto-create")
        return ""

    def _pinterest_persist_board(self, board_id: str):
        try:
            persist = Path.home() / ".abvorn"
            persist.mkdir(parents=True, exist_ok=True)
            (persist / "pinterest_board_id.txt").write_text(board_id, encoding="utf-8")
        except OSError:
            pass

    def pinterest_publish_pin(self, board_id: str, image_paths: list[str],
                              title: str = "", description: str = "",
                              link: str = "", alt_text: str = "") -> dict:
        """Create a pin from local image files.

        A single image uses the image_base64 source; 2-5 images become a
        carousel via multiple_image_base64 (Pinterest carousels hold up to
        five). The first pin image is the primary when index is omitted.
        """
        from pathlib import Path
        from base64 import b64encode
        import mimetypes

        imgs = []
        for path in image_paths[:5]:
            p = Path(path)
            if not p.is_file():
                continue
            data = p.read_bytes()
            ctype = mimetypes.guess_type(p.name)[0] or "image/jpeg"
            imgs.append({
                "content_type": ctype,
                "data": b64encode(data).decode("ascii"),
            })
        if not imgs:
            raise RuntimeError("pinterest pin: no readable image files")

        if len(imgs) == 1:
            media_source = {
                "source_type": "image_base64",
                "content_type": imgs[0]["content_type"],
                "data": imgs[0]["data"],
            }
        else:
            media_source = {
                "source_type": "multiple_image_base64",
                "items": imgs,
            }

        args = {
            "board_id": str(board_id),
            "media_source": media_source,
            "title": (title or "")[:100],
            "description": (description or "")[:800],
            "link": (link or "")[:2048],
            "alt_text": (alt_text or "")[:500],
        }
        return self.execute(PINTEREST_TOOLKIT, PINTEREST_CREATE_PIN_TOOL, args)