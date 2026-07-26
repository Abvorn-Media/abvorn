"""CLI entry point: python -m abvorn <command>"""

import asyncio, logging, sys, os

from .brain.orchestrator import refresh_brain

_DAEMON = None

def _get_daemon():
    global _DAEMON
    if _DAEMON is None:
        from .daemon import AbvornDaemon
        _DAEMON = AbvornDaemon
    return _DAEMON

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    logger = logging.getLogger("abvorn")

    if len(sys.argv) < 2:
        print("Usage: python -m abvorn <command>")
        print("Commands:")
        print("  daemon         Run all agents continuously")
        print("  cycle          Run one full discovery → content → deploy cycle")
        print("  brain-refresh  Scan and index the knowledge brain")
        print("  once           Run one cycle of the pipeline")
        print("  pause          Pause the autonomous system (kill switch)")
        print("  resume         Resume the autonomous system")
        print("  status         Show system status and kill switch state")
        print("  health         Run health check and report stats")
        print("  migrate        Bootstrap initial site from existing content")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "daemon":
        DaemonCls = _get_daemon()
        async def run():
            d = DaemonCls()
            await d.start()
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                await d.stop()
        asyncio.run(run())

    elif cmd == "cycle":
        DaemonCls = _get_daemon()
        async def run_cycle():
            d = DaemonCls()
            result = await d.run_full_cycle()
            print(f"Cycle result: {result.get('status')}")
            if result.get('niche'):
                print(f"  Niche: {result['niche']}")
        asyncio.run(run_cycle())

    elif cmd == "brain-refresh":
        result = refresh_brain()
        summary = result.get("summary", {})
        domains = summary.get("domains", [])
        print(f"Brain refresh complete: {summary.get('total_documents', 0)} documents, {summary.get('total_chunks', 0)} chunks")
        for d in domains:
            print(f"  {d['domain']}: {d['documents']} documents, {d['chunks']} chunks")

    elif cmd == "once":
        from .core.secrets import load_secrets
        from .core.models import ModelRouter
        from .content.pipeline import ContentPipeline
        secrets = load_secrets()
        router = ModelRouter(secrets)
        pipeline = ContentPipeline()
        niche = sys.argv[2] if len(sys.argv) > 2 else "wireless headphones"
        result = pipeline.run(niche, router)
        if result:
            print(f"Generated: {result.get('post_title')}")
            print(f"Quality: {result.get('quality_score')}")
        else:
            print("Pipeline failed")

    elif cmd == "pause":
        d = _get_daemon()()
        d.state.set_meta("kill_switch", True)
        print("[PAUSED] System paused - kill switch engaged")

    elif cmd == "resume":
        d = _get_daemon()()
        d.state.set_meta("kill_switch", False)
        print("[ACTIVE] System resumed - kill switch disengaged")

    elif cmd == "status":
        d = _get_daemon()()
        paused = d.state.get_meta("kill_switch", False)
        niches = d.state.get_all_niches()
        print(f"Status: {'[PAUSED]' if paused else '[ACTIVE]'}")
        print(f"  Tracked niches: {len(niches)}")
        if niches:
            print(f"  Top niche: {niches[0].get('slug', 'N/A')} (score: {niches[0].get('ga4_score', 0)})")

    elif cmd == "health":
        d = _get_daemon()()
        from .orchestrator.health import HealthMonitor
        monitor = HealthMonitor(state_db=str(d.state_path))
        status = monitor.check()
        stats = monitor.get_stats()
        opps = len(d.state.get_all_niches())
        print(f"Health: {'[OK]' if status['healthy'] else '[ISSUES]'}")
        print(f"  Cycles: {stats.get('total_cycles', 0)}")
        print(f"  Success rate: {stats.get('success_rate', 0):.0%}")
        print(f"  Avg duration: {stats.get('avg_duration_s', 0):.0f}s")
        print(f"  Tracked niches: {opps}")

    elif cmd == "migrate":
        from .deploy.github import GitHubDeployer
        from .core.secrets import load_secrets
        from .sites.migration import BootstrapMigration
        d = _get_daemon()()
        secrets = load_secrets()
        deployer = GitHubDeployer(
            token=secrets.get("GITHUB_TOKEN", ""),
            repo=secrets.get("GITHUB_REPO", ""),
        )
        migration = BootstrapMigration(d.state, deployer)
        results = migration.run()
        for r in results:
            print(f"  {r}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()