"""CLI entry point: python -m abvorn <command>"""

import asyncio, logging, sys
from .daemon import AbvornDaemon
from .brain.orchestrator import refresh_brain

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    logger = logging.getLogger("abvorn")

    if len(sys.argv) < 2:
        print("Usage: python -m abvorn <command>")
        print("Commands:")
        print("  daemon        Run all agents continuously")
        print("  brain-refresh  Scan and index the knowledge brain")
        print("  once          Run one cycle of the pipeline")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "daemon":
        async def run():
            d = AbvornDaemon()
            await d.start()
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                await d.stop()
        asyncio.run(run())

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

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()