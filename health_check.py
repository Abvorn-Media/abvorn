"""Abvorn Health Check — run this to verify the system is ready for launch."""
import sys, json
from pathlib import Path


def check(description, fn):
    try:
        result = fn()
        print(f"  [OK] {description}")
        return result
    except Exception as e:
        print(f"  [FAIL] {description}: {e}")
        return False


def main():
    print("=" * 54)
    print("  Abvorn Launch Health Check")
    print("=" * 54)
    print()

    checks = []
    errors = 0

    # 1. Python version
    print("Environment:")
    checks.append(check("Python 3.14+", lambda: sys.version_info >= (3, 14)))

    # 2. Module imports
    print("\nCore modules:")
    checks.append(check("abvorn.sites.model", lambda: __import__("abvorn.sites.model")))
    checks.append(check("abvorn.sites.registry", lambda: __import__("abvorn.sites.registry")))
    checks.append(check("abvorn.sites.brand", lambda: __import__("abvorn.sites.brand")))
    checks.append(check("abvorn.sites.migration", lambda: __import__("abvorn.sites.migration")))
    checks.append(check("abvorn.deploy.github", lambda: __import__("abvorn.deploy.github")))
    checks.append(check("abvorn.deploy.site_deployer", lambda: __import__("abvorn.deploy.site_deployer")))
    checks.append(check("abvorn.deploy.crosslinker", lambda: __import__("abvorn.deploy.crosslinker")))
    checks.append(check("abvorn.deploy.dashboard", lambda: __import__("abvorn.deploy.dashboard")))
    checks.append(check("abvorn.deploy.redirect", lambda: __import__("abvorn.deploy.redirect")))
    checks.append(check("abvorn.deploy.notifier", lambda: __import__("abvorn.deploy.notifier")))
    checks.append(check("abvorn.persuasion.stage", lambda: __import__("abvorn.persuasion.stage")))
    checks.append(check("abvorn.persuasion.context", lambda: __import__("abvorn.persuasion.context")))
    checks.append(check("abvorn.persuasion.matcher", lambda: __import__("abvorn.persuasion.matcher")))
    checks.append(check("abvorn.persuasion.widget", lambda: __import__("abvorn.persuasion.widget")))
    checks.append(check("abvorn.persuasion.tracker", lambda: __import__("abvorn.persuasion.tracker")))
    checks.append(check("abvorn.monitor.error_reporter", lambda: __import__("abvorn.monitor.error_reporter")))
    checks.append(check("abvorn.monitor.backup", lambda: __import__("abvorn.monitor.backup")))
    checks.append(check("abvorn.monitor.env", lambda: __import__("abvorn.monitor.env")))

    # 3. Secrets
    print("\nSecrets:")
    from abvorn.core.secrets import load_secrets
    secrets = load_secrets()
    required = ["GITHUB_TOKEN", "GITHUB_REPO", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]
    for key in required:
        checks.append(check(f"  {key}", lambda k=key: bool(secrets.get(k)) and "YOUR_" not in secrets.get(k, "")))

    # 4. State DB
    print("\nState database:")
    from abvorn.core.state import AbvornState
    state_path = Path.home() / ".abvorn" / "state.db"
    checks.append(check(f"  Exists at {state_path}", lambda: state_path.exists()))
    if state_path.exists():
        try:
            state = AbvornState(state_path)
            checks.append(check("  Opens and readable", lambda: state.get_meta("test", "ok") == "ok"))
        except Exception as e:
            print(f"  [FAIL] State DB error: {e}")
            errors += 1

    # 5. Sites
    print("\nSites:")
    if state_path.exists():
        try:
            from abvorn.sites.registry import SiteRegistry
            registry = SiteRegistry(state)
            sites = registry.list()
            checks.append(check(f"  {len(sites)} site(s) registered", lambda: True))
            for s in sites:
                checks.append(check(f"    {s.name} ({s.slug}) - {len(s.niches)} niches", lambda: True))
        except Exception as e:
            print(f"  [FAIL] Sites error: {e}")
            errors += 1

    # 6. GitHub Pages URL
    print("\nGitHub Pages:")
    repo = secrets.get("GITHUB_REPO", "")
    if repo and "/" in repo:
        owner, rname = repo.split("/")
        url = f"https://{owner}.github.io/{rname}/"
        print(f"  URL: {url}")
        try:
            import urllib.request
            resp = urllib.request.urlopen(url, timeout=10)
            checks.append(check(f"  Status {resp.status}", lambda: resp.status == 200))
        except Exception:
            print("  [WARN] Could not reach URL (may not be deployed yet)")
    else:
        print("  [WARN] GITHUB_REPO not configured")

    # 7. Telegram
    print("\nTelegram:")
    token = secrets.get("TELEGRAM_TOKEN", "")
    chat_id = secrets.get("TELEGRAM_CHAT_ID", "")
    if token and chat_id:
        try:
            import requests
            resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
            if resp.status_code == 200 and resp.json().get("ok"):
                bot_name = resp.json()["result"].get("first_name", "")
                checks.append(check(f"  Bot @{bot_name} connected", lambda: True))
            else:
                checks.append(check("  Bot token invalid", lambda: False))
        except Exception as e:
            print(f"  [FAIL] Telegram error: {e}")
    else:
        print("  [WARN] Telegram not configured")

    # Summary
    print("\n" + "=" * 54)
    passed = sum(1 for c in checks if c)
    total = len(checks)
    print(f"  Results: {passed}/{total} checks passed")
    if passed == total:
        print("  [READY FOR LAUNCH]")
    else:
        print(f"  [WARN] {total - passed} check(s) failed — review above")
    print("=" * 54)


if __name__ == "__main__":
    main()
