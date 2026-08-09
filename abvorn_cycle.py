"""Abvorn Cycle Runner — executes the full empire pipeline outside Colab.
Designed for GitHub Actions (twice-daily cron) and local scheduling.
Uses the abvorn/ package directly instead of exec-injecting mocks into cell files."""

import os, sys, types, pathlib, json, shutil, logging, re

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("abvorn-cycle")

# ── MOCK OBJECTS (for optional cell file execution) ──────────────────────

class _MockUserdata:
    @staticmethod
    def get(key, default=''):
        return os.environ.get(key, default)

def _mock_mount(path, **kw):
    logger.info(f"[mock] drive.mount({path}) — skipped (CI/local mode)")

def _mock_auth_default():
    return None, None

colab_drive = types.ModuleType('drive')
colab_drive.mount = _mock_mount

colab_userdata = _MockUserdata()

colab_auth = types.ModuleType('auth')
colab_auth.default = _mock_auth_default

# ── PATHS ───────────────────────────────────────────────────────────────────

DRIVE_BASE = pathlib.Path('/content/drive/MyDrive')
BOARDROOM_DIR = DRIVE_BASE / 'The_Synthetic_Boardroom'
BOOKS_DIR = DRIVE_BASE / 'Notebook LM Brain'
for d in [BOARDROOM_DIR, BOARDROOM_DIR / '6_Empire_Network',
          BOARDROOM_DIR / 'Design_Skills', BOOKS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── STATE CACHE ─────────────────────────────────────────────────────────────

CACHE_DIR = pathlib.Path(os.environ.get('ABVORN_CACHE_DIR',
                                        pathlib.Path.home() / '.abvorn'))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _restore_cache():
    for item in CACHE_DIR.iterdir():
        dest = BOARDROOM_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
    logger.info(f"Cache restored from {CACHE_DIR}")

def _save_cache():
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
    cleaned = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith('!'):
            continue
        if _COLAB_IMPORT_RE.match(stripped):
            continue
        cleaned.append(line)
    return '\n'.join(cleaned)

# ── ABVORN PIPELINE (direct, no exec) ─────────────────────────────────────

def run_pipeline_direct():
    """Execute the full Abvorn pipeline using the abvorn package directly."""
    from abvorn.core.secrets import load_secrets
    from abvorn.core.state import AbvornState
    from abvorn.core.models import ModelRouter
    from abvorn.content.pipeline import ContentPipeline
    from abvorn.deploy.analytics import pull_ga4_analytics, apply_analytics_feedback

    secrets = load_secrets()
    if not secrets:
        logger.warning("No secrets found — running in mock/demo mode")
        secrets = {"AMAZON_TAG": "abvorn-20"}

    db_path = BOARDROOM_DIR / "empire_state.db"
    state = AbvornState(db_path)

    # Migrate legacy JSON state if present
    legacy_json = BOARDROOM_DIR / "empire_state.json"
    if legacy_json.exists():
        state.import_legacy_json(legacy_json)

    router = ModelRouter(secrets)
    pipeline = ContentPipeline(state=state, router=router)

    # Process queued niches
    while True:
        task = state.dequeue()
        if not task:
            logger.info("No queued tasks — pipeline idle")
            break
        niche_slug = task["niche_slug"]
        niche_name = niche_slug.replace("_", " ").title()
        logger.info(f"Processing task: {niche_slug} ({task['stage']})")

        try:
            result = pipeline.run(niche_name, router)
            if result:
                state.add_post(niche_slug, result.get("post_title", ""),
                               filename=result.get("post_title", "").lower().replace(" ", "-")[:50] + ".html",
                               quality_score=result.get("quality_score", 7.0))
                state.upsert_niche(niche_slug, niche_name)
                logger.info(f"  Done: {niche_slug}")
            state.complete_queue_item(task["id"])
        except Exception as e:
            logger.exception(f"Pipeline failed for {niche_slug}")
            state.fail_queue_item(task["id"])

    # GA4 analytics feedback loop
    analytics = pull_ga4_analytics(secrets)
    if analytics:
        apply_analytics_feedback(state, analytics)
        logger.info(f"GA4 feedback applied for {len(analytics)} niches")

    return state

# ── MAIN ───────────────────────────────────────────────────────────────────

_CELL_FILES = ['abvorn_cell1.py', 'abvorn_cell2.py', 'abvorn_cell3.py']

def main():
    logger.info("=" * 60)
    logger.info("Abvorn Cycle Runner — starting full pipeline")
    logger.info("=" * 60)

    _restore_cache()

    # Run the abvorn pipeline directly
    run_pipeline_direct()

    # Legacy cell files (abvorn_cell1/2/3.py) still contain the full old
    # pipeline and auto-run it at module level (run_swarm, deploy_and_ping,
    # poll_ceo_commands, etc.). Exec'ing them here ran the entire legacy
    # pipeline on top of run_pipeline_direct() every cycle — double AI spend,
    # double scraping, double deploys. They are now DISABLED by default.
    # Set ABVORN_RUN_LEGACY_CELLS=1 to opt back in (advanced use only).
    if os.environ.get('ABVORN_RUN_LEGACY_CELLS') == '1':
        namespace = {
            # Do NOT set '__main__': cell files guard their auto-run blocks
            # with `if __name__ == "__main__"`, and exec'ing with that name
            # would re-trigger the full legacy pipeline.
            '__name__': 'abvorn_legacy_cells',
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
            logger.info(f"─── Executing {cell_path} (environment setup) ───")
            raw = cell_path.read_text(encoding='utf-8')
            processed = preprocess_cell(raw)
            try:
                exec(processed, namespace)
            except SystemExit:
                logger.warning(f"{cell_path} called sys.exit() — continuing")
            except Exception:
                logger.exception(f"{cell_path} raised an exception — continuing")

    _save_cache()
    logger.info("Abvorn cycle complete.")

if __name__ == '__main__':
    main()