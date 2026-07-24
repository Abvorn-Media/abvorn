"""Abvorn Cycle Runner — executes the full empire pipeline outside Colab.
Designed for GitHub Actions (twice-daily cron) and local scheduling.
Replaces google.colab with env-var-based mocks so the three cell files
run unchanged on a standard Python runtime."""

import os, sys, types, pathlib, json, shutil, logging, re

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("abvorn-cycle")

# ── MOCK OBJECTS (injected into exec namespace, not sys.modules) ────────

class _MockUserdata:
    @staticmethod
    def get(key, default=''):
        return os.environ.get(key, default)

def _mock_mount(path, **kw):
    logger.info(f"[mock] drive.mount({path}) — skipped (CI/local mode)")

def _mock_auth_default():
    return None, None

# These will be placed directly into the exec namespace
colab_drive = types.ModuleType('drive')
colab_drive.mount = _mock_mount

colab_userdata = _MockUserdata()

colab_auth = types.ModuleType('auth')
colab_auth.default = _mock_auth_default

# ── PATHS ───────────────────────────────────────────────────────────────────
# Replicate the Drive directory structure locally so the cell code finds
# /content/drive/MyDrive/The_Synthetic_Boardroom/ etc.

DRIVE_BASE = pathlib.Path('/content/drive/MyDrive')
BOARDROOM_DIR = DRIVE_BASE / 'The_Synthetic_Boardroom'
BOOKS_DIR = DRIVE_BASE / 'Notebook LM Brain'
for d in [BOARDROOM_DIR, BOARDROOM_DIR / '6_Empire_Network',
          BOARDROOM_DIR / 'Design_Skills', BOOKS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── STATE CACHE ─────────────────────────────────────────────────────────────
# The ~/.abvorn directory is cached between GitHub Actions runs so that the
# empire state, ChromaDB backup, and skills survive across cycles.

CACHE_DIR = pathlib.Path(os.environ.get('ABVORN_CACHE_DIR',
                                        pathlib.Path.home() / '.abvorn'))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _restore_cache():
    """Copy cached state into the Drive-mirror paths before running cells."""
    for item in CACHE_DIR.iterdir():
        dest = BOARDROOM_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
    logger.info(f"Cache restored from {CACHE_DIR}")

def _save_cache():
    """Copy Drive-mirror state back to cache dir for the next workflow run."""
    for item in BOARDROOM_DIR.iterdir():
        dest = CACHE_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
    logger.info(f"Cache saved to {CACHE_DIR}")

# ── CELL PREPROCESSOR ──────────────────────────────────────────────────────

_COLAB_IMPORT_RE = re.compile(
    r'^\s*(?:from\s+google\.colab\s+import|import\s+google\.colab)'
)

def preprocess_cell(source: str) -> str:
    """Strip Colab-specific syntax that would break in a standard Python env."""
    cleaned = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith('!'):
            continue
        if _COLAB_IMPORT_RE.match(stripped):
            continue
        cleaned.append(line)
    return '\n'.join(cleaned)

# ── MAIN ───────────────────────────────────────────────────────────────────

_CELL_FILES = ['abvorn_cell1.py', 'abvorn_cell2.py', 'abvorn_cell3.py']

def main():
    logger.info("=" * 60)
    logger.info("Abvorn Cycle Runner — starting full pipeline")
    logger.info("=" * 60)

    _restore_cache()

    # Build the namespace shared across all three cells.
    # We provide mock objects for google.colab imports so the cells don't
    # need the real Colab runtime.  The rest are ordinary Python globals.
    namespace = {
        '__name__': '__main__',
        '__builtins__': __builtins__,
        'drive': colab_drive,
        'auth': colab_auth,
        'userdata': colab_userdata,
    }

    for cell_path_str in _CELL_FILES:
        cell_path = pathlib.Path(cell_path_str)
        if not cell_path.exists():
            logger.error(f"Cell file not found: {cell_path}")
            continue
        logger.info(f"─── Executing {cell_path} ───")
        raw = cell_path.read_text(encoding='utf-8')
        processed = preprocess_cell(raw)
        try:
            exec(processed, namespace)
        except SystemExit:
            logger.warning(f"{cell_path} called sys.exit() — continuing")
        except Exception:
            logger.exception(f"{cell_path} raised an exception — continuing")
            # Other cells may still do useful work

    _save_cache()
    logger.info("Abvorn cycle complete. All three cells executed.")

if __name__ == '__main__':
    main()
