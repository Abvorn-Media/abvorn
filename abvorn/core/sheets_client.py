"""sheets_client.py — Read Abvorn's Google Sheets via a service account.

This is the IAM/service-account path: Python authenticates as a non-interactive
Google Cloud service account (no browser consent screen), so the backend can
pull leads and reactions silently.

Requirements:
  1. A Google Cloud service account key (JSON). It can be referenced two ways:
       - ABVORN_SERVICE_ACCOUNT env var = path to the JSON key file, or
       - secrets["GA4_CREDENTIALS_JSON"] (the same key already used for GA4
         works if that service account is added to the spreadsheet).
  2. The service account email added as EDITOR on the target spreadsheet.

Usage:
    from abvorn.core.sheets_client import AbvornSheets
    sh = AbvornSheets()
    leads = sh.read_leads(SHEET_ID)            # list[dict] from Sheet1
    reactions = sh.read_reactions(SHEET_ID)    # list[dict] from 'reactions' tab
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("abvorn.sheets")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _load_service_account_info() -> Optional[dict]:
    """Return parsed service-account JSON from env file or GA4 secret, else None."""
    env_path = os.environ.get("ABVORN_SERVICE_ACCOUNT", "")
    if env_path:
        p = Path(env_path).expanduser()
        if p.exists():
            try:
                return json.loads(p.read_bytes())
            except Exception as e:
                logger.warning(f"ABVORN_SERVICE_ACCOUNT unreadable: {e}")
    try:
        from abvorn.core.secrets import load_secrets

        ga4_json = load_secrets().get("GA4_CREDENTIALS_JSON", "")
        if ga4_json:
            return json.loads(ga4_json)
    except Exception as e:
        logger.warning(f"Could not load GA4 credentials as service account: {e}")
    return None


class AbvornSheets:
    """Read Abvorn's spreadsheet tabs with a Google service account."""

    def __init__(self, credentials: Optional[dict] = None):
        creds = credentials if credentials is not None else _load_service_account_info()
        if not creds:
            raise RuntimeError(
                "No service-account credentials available. Set ABVORN_SERVICE_ACCOUNT "
                "to the JSON key path, or configure GA4_CREDENTIALS_JSON."
            )
        self._credentials = creds

    def client(self):
        import gspread
        from google.oauth2.service_account import Credentials

        creds = Credentials.from_service_account_info(self._credentials).with_scopes(SCOPES)
        return gspread.authorize(creds)

    def open(self, spreadsheet_id: str):
        return self.client().open_by_key(spreadsheet_id)

    def read_leads(self, spreadsheet_id: str, tab: str = "Sheet1") -> List[Dict]:
        """Read email leads from the given tab (default Sheet1)."""
        sh = self.open(spreadsheet_id)
        ws = sh.worksheet(tab)
        rows = ws.get_all_records(head=1)
        logger.info(f"Read {len(rows)} leads from '{tab}'")
        return rows

    def read_reactions(self, spreadsheet_id: str) -> List[Dict]:
        """Read like/love reaction counts from the 'reactions' tab."""
        sh = self.open(spreadsheet_id)
        try:
            ws = sh.worksheet("reactions")
        except Exception:
            return []
        return ws.get_all_records(head=1)

    def read_tab(self, spreadsheet_id: str, tab: str) -> List[Dict]:
        sh = self.open(spreadsheet_id)
        ws = sh.worksheet(tab)
        return ws.get_all_records(head=1)

    def list_tabs(self, spreadsheet_id: str) -> List[str]:
        sh = self.open(spreadsheet_id)
        return [ws.title for ws in sh.worksheets()]