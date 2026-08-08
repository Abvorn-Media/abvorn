"""Abvorn daemon — runs all agents continuously."""

import asyncio, logging, signal, sys, json, uuid
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger("abvorn.daemon")

from .core.state import AbvornState
from .core.models import ModelRouter, ModelCostTracker
from .core.secrets import load_secrets
from .core.bus import AgentBus
from .sites.registry import SiteRegistry
from .monitor.error_reporter import ErrorReporter, DaemonGuard
from .will import Will
from .drive import Drive
from .content.pipeline import ContentPipeline
from .agents.orchestrator import ResearchAgent, ContentAgent, DeployAgent
from .agents.supervisor import SupervisorAgent
from .agents.platform import PlatformAgent
from .brain.orchestrator import refresh_brain, get_brain_retriever
from .deploy.github import GitHubDeployer
from .brand import check_soul, format_voice_rules
from .discovery.scanner import OpportunityScanner
from .persona.engine import PersonaEngine
from .persona.registry import PersonaRegistry
from .factory.pipeline import PersuasionPipeline
from .deploy.social import SocialDeployer
from .deploy.notifier import TelegramNotifier
from .orchestrator.scheduler import Scheduler
from .orchestrator.health import HealthMonitor
from .platform import adapters, registry  # noqa: F401 — registers all platforms
from .domination import DominationOrchestrator

STATE_DB = Path.home() / ".abvorn" / "state.db"
BUS_DB = Path.home() / ".abvorn" / "bus.db"

class AbvornDaemon:
    """The daemon that keeps Abvorn alive 24/7."""

    def __init__(self, state_db: str = None):
        self.running = False
        self.state_path = Path(state_db) if state_db else STATE_DB
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state = AbvornState(self.state_path)
        self.bus = AgentBus(str(BUS_DB))
        self.secrets = load_secrets()
        self.router = ModelRouter(self.secrets)
        self.agents = []
        self._tasks = []
        self._phase3_inited = False

    def _ensure_phase3(self):
        """Lazy init of Phase 3 subsystems. Only runs once."""
        if self._phase3_inited:
            return
        self._phase3_inited = True
        self._init_phase3()

    def _init_phase3(self):
        """Initialize Phase 3 subsystems."""
        self.scanner = OpportunityScanner(self.state)
        self.persona_engine = PersonaEngine()
        self.persona_registry = PersonaRegistry(str(self.state_path.parent / "personas.db"))
        self.factory = PersuasionPipeline()
        self.social = SocialDeployer(self.secrets.get("COMPOSIO_KEY", ""))
        self.notifier = TelegramNotifier(bus=self.bus)
        self.scheduler = Scheduler(state_db=str(self.state_path))
        self.health = HealthMonitor(state_db=str(self.state_path))
        self._registry = registry
        self.cost_tracker = ModelCostTracker(self.state)
        from .analytics.ga4 import GA4Client
        from .analytics.engine import AnalyticsEngine
        ga4_property_id = self.secrets.get("GA4_PROPERTY_ID", "")
        ga4_creds = self.secrets.get("GA4_CREDENTIALS_JSON", "")
        self.ga4_client = GA4Client(property_id=ga4_property_id, credentials_json=ga4_creds)
        self.analytics = AnalyticsEngine(ga4_client=self.ga4_client, state=self.state)
        self.notifier._analytics_engine = self.analytics
        from .trends.scanner import TrendScanner
        self.trend_scanner = TrendScanner(state=self.state)
        self.notifier._trend_scanner = self.trend_scanner
        self.site_registry = SiteRegistry(self.state)
        self.notifier._site_registry = self.site_registry
        self.error_reporter = ErrorReporter(self.state, notifier=self.notifier)
        self.daemon_guard = DaemonGuard(self.error_reporter)
        self.notifier._error_reporter = self.error_reporter
        from .monitor.backup import BackupManager
        from .monitor.env import EnvMode
        self.backup_manager = BackupManager()
        self.env_mode = EnvMode()
        self.notifier._backup_manager = self.backup_manager
        self.notifier._env_mode = self.env_mode
        self.will = Will(state=self.state, bus=self.bus)
        self.drive = Drive("abvorn_daemon", mission=self.will.mission)
        rss_path = Path(__file__).resolve().parent.parent / "docs" / "feed.xml"
        self.domination = DominationOrchestrator(
            rss_path=str(rss_path) if rss_path.exists() else "",
            pexels_key=self.secrets.get("PEXELS_KEY", ""),
            composio_key=self.secrets.get("COMPOSIO_KEY", ""),
            db_path=str(self.state_path.parent / "domination.db"),
        )
        self._phase3_inited = True

    def is_paused(self) -> bool:
        """Check if the kill switch is engaged."""
        return self.state.get_meta("kill_switch", False)

    async def run_full_cycle(self) -> dict:
        """Run one complete opportunity → content → deploy cycle."""
        self._ensure_phase3()
        if self.is_paused():
            return {"status": "paused"}

        opp = self.scheduler.get_next_opportunity()
        if not opp:
            logger.info("No pending opportunities — running discovery")
            self.scanner.discover_from_keywords(["wireless headphones", "gaming mouse"])
            opp = self.scheduler.get_next_opportunity()
            if not opp:
                return {"status": "nothing_to_do"}

        niche = opp["niche"]
        logger.info(f"Starting cycle for: {niche}")

        personas = self.persona_engine.discover_personas(niche)
        if not personas:
            self.scheduler.mark_failed(opp["id"])
            self.notifier.report_cycle(niche, "failed", "No personas found")
            return {"status": "no_personas"}

        persona = personas[0]
        persona_id = f"{niche}_{persona['name'].lower().replace(' ', '_')}"
        self.persona_registry.register_persona(persona_id, niche, persona)

        soul_check = check_soul(f"content_for_{persona_id}", {
            "niche": niche,
            "persona": persona.get("name", ""),
        })
        if not soul_check["pass"]:
            self.scheduler.mark_failed(opp["id"])
            self.notifier.report_cycle(niche, "soul_blocked", str(soul_check["violations"]))
            logger.warning(f"Soul check blocked: {soul_check['violations']}")
            return {"status": "soul_blocked", "violations": soul_check["violations"]}

        content = self.factory.run(niche, persona, self.router)
        if not content:
            self.scheduler.mark_failed(opp["id"])
            self.notifier.report_error(niche, "Content factory returned None")
            return {"status": "content_failed"}

        from .platform import registry
        from .exploder.email import generate_lead_magnet, generate_sequence

        magnet = generate_lead_magnet(content)
        sequence = generate_sequence(content, persona)

        # Email to matched persona subscribers
        try:
            from .crm.sender import EmailSender
            from .crm.subscriber import SubscriberDB
            crm_db = SubscriberDB(self.state_path.parent / "crm.db")
            sender = EmailSender()
            sender.send_persona_content(
                persona_id=persona_id, niche=niche, content=content,
                subscriber_db=crm_db,
            )
        except Exception as e:
            logger.warning(f"Email send failed (non-fatal): {e}")

        # Deploy to all social platforms via registry
        for platform in registry.list(category="social"):
            if platform in ("facebook", "youtube"):
                logger.info(f"{platform}: stub ready — waiting for API keys")
                continue
            adapted = registry.adapter(platform)(content)
            self.social.post(content, platform)
            logger.info(f"Deployed to {platform}")

        # Deploy content to site
        try:
            from .agents.orchestrator import SiteDeployer
            site_dep = SiteDeployer(GitHubDeployer(
                token=self.secrets.get("GITHUB_TOKEN", ""),
                repo=self.secrets.get("GITHUB_REPO", ""),
            ), self.state)
            site_dep.deploy_content(niche, content)
            all_niches = self.state.get_all_niches()
            all_slugs = [n["slug"] for n in all_niches]
            all_posts = []
            for s in all_slugs:
                all_posts.extend(self.state.get_posts_for_niche(s))
            site_dep.deploy_root_index(niches=all_niches, posts=all_posts)
            for slug in all_slugs:
                niche_posts = [p for p in all_posts if p.get("niche_slug") == slug]
                site_dep.deploy_category_page(slug, posts=niche_posts, all_categories=all_slugs)
            logger.info(f"Deployed {niche} to site")
        except Exception as e:
            logger.warning(f"Site deploy failed (non-fatal): {e}")

        self.scheduler.mark_complete(opp["id"])
        self.health.log_cycle(niche, success=True, duration_s=120)
        self.persona_registry.update_performance(persona_id, converted=False, quality_score=7.0)
        self.notifier.report_cycle(niche, "success", content.get("post_title", ""))

        self.bus.publish("content.drafted", {"niche": niche, "title": content.get("post_title", "")})
        return {"status": "success", "niche": niche, "persona": persona_id}

    async def run_domination_cycle(self) -> dict:
        """Run one social domination cycle — RSS → scripts → assets → publish."""
        self._ensure_phase3()
        if self.is_paused():
            return {"status": "paused"}
        try:
            result = await asyncio.to_thread(self.domination.run_cycle)
            if result.get("status") == "complete":
                title = result.get("title", "")
                niche = result.get("niche", "")
                self.health.log_cycle(niche, success=True, duration_s=60)
                self.notifier.report_cycle(niche, "success", title)
                self.bus.publish("domination.cycle", {"niche": niche, "title": title})
                logger.info(f"Domination cycle complete: {title[:60]}")
            return result
        except Exception as e:
            logger.error(f"Domination cycle failed: {e}")
            self.notifier.report_error("domination", str(e))
            return {"status": "failed", "error": str(e)}

    async def start(self):
        """Start all agents and the brain."""
        self._ensure_phase3()
        self.running = True
        logger.info("Abvorn daemon starting...")

        brain = None
        try:
            brain = get_brain_retriever()
            if brain:
                logger.info("Brain loaded")
        except Exception as e:
            logger.warning(f"Brain init failed (non-fatal): {e}")

        pipeline = ContentPipeline(self.state)
        if brain:
            pipeline.brain = brain

        deployer = GitHubDeployer(
            token=self.secrets.get("GITHUB_TOKEN", ""),
            repo=self.secrets.get("GITHUB_REPO", ""),
        )

        # Deploy site structure on startup
        try:
            from .agents.orchestrator import SiteDeployer
            site_deployer = SiteDeployer(deployer, self.state)
            all_niches = self.state.get_all_niches()
            all_slugs = [n["slug"] for n in all_niches]
            all_posts = []
            for n in all_slugs:
                all_posts.extend(self.state.get_posts_for_niche(n))
            site_deployer.deploy_root_index(niches=all_niches, posts=all_posts)
            for slug in all_slugs:
                niche_posts = [p for p in all_posts if p.get("niche_slug") == slug]
                site_deployer.deploy_category_page(slug, posts=niche_posts, all_categories=all_slugs)
            logger.info("Site structure deployed at startup")
        except Exception as e:
            logger.warning(f"Site deploy at startup failed (non-fatal): {e}")

        self.agents = [
            ResearchAgent(self.bus, self.state, self.router, brain, will=self.will, drive=Drive("ResearchAgent", self.will.mission)),
            ContentAgent(self.bus, self.state, self.router, pipeline, brain, will=self.will, drive=Drive("ContentAgent", self.will.mission)),
            DeployAgent(self.bus, self.state, deployer, will=self.will, drive=Drive("DeployAgent", self.will.mission)),
        ]

        self.supervisor = SupervisorAgent(self.bus, self.state, brain, will=self.will, drive=Drive("SupervisorAgent", self.will.mission))
        self.supervisor.registry.update({
            a.name: {
                "class": a.__class__.__name__,
                "status": "running",
                "instance": a,
                "spawned_at": datetime.now().isoformat(),
            } for a in self.agents
        })
        self.agents.append(self.supervisor)

        active_platforms = [p for p in self._registry.list(category="social")
                            if p not in ("facebook", "youtube")]
        for pname in active_platforms:
            vp = self._registry.voice_profile(pname)
            pagent = PlatformAgent(self.bus, self.state, self.router, pname,
                                    voice_profile=vp, registry=self._registry, brain=brain,
                                    will=self.will)
            self.supervisor.spawn_agent(pagent.name, PlatformAgent,
                                         self.bus, self.state, self.router,
                                         pname, voice_profile=vp,
                                         registry=self._registry, brain=brain,
                                         will=self.will)
            self.agents.append(pagent)

        from .agents.ambassador import SocialAmbassador
        self.ambassador = SocialAmbassador(
            self.bus, self.state, self.router,
            self.social, brain=brain, notifier=self.notifier,
            will=self.will, drive=Drive("SocialAmbassador", self.will.mission),
        )
        self.supervisor.spawn_agent("SocialAmbassador", SocialAmbassador,
                                     self.bus, self.state, self.router,
                                     self.social, brain=brain, notifier=self.notifier,
                                     will=self.will, drive=Drive("SocialAmbassador", self.will.mission))
        self.agents.append(self.ambassador)

        for agent in self.agents:
            logger.info(f"  Starting agent: {agent.name}")

        for agent in self.agents:
            task = asyncio.create_task(agent.run_forever())
            self._tasks.append(task)

        bus_task = asyncio.create_task(self._bus_loop())
        self._tasks.append(bus_task)

        telegram_task = asyncio.create_task(self._telegram_poll_loop())
        self._tasks.append(telegram_task)

        domination_task = asyncio.create_task(self._domination_loop())
        self._tasks.append(domination_task)

        gsc_task = asyncio.create_task(self._gsc_loop())
        self._tasks.append(gsc_task)

        logger.info(f"Daemon running with {len(self.agents)} agents")

    async def _bus_loop(self):
        while self.running:
            events = self.bus.get_recent_events()
            for evt in events:
                topic = evt.get("topic", "")
                payload = evt.get("payload", {})
                if topic == "domination.signal" and not self.is_paused():
                    self._ensure_phase3()
                    asyncio.create_task(self.run_domination_cycle())
                elif topic == "cycle.signal" and not self.is_paused():
                    asyncio.create_task(self.run_full_cycle())
            await asyncio.sleep(10)

    async def _telegram_poll_loop(self):
        while self.running:
            try:
                self.notifier.check_commands(
                    supervisor=self.supervisor,
                    health=self.health,
                    scheduler=self.scheduler,
                    state=self.state,
                )
            except Exception as e:
                logger.debug(f"Telegram poll error (non-fatal): {e}")
            await asyncio.sleep(5)

    async def _gsc_loop(self):
        """Run Google Search Console ingestion every 24 hours."""
        while self.running:
            last_run = self.state.get_meta("gsc_last_run", "")
            if last_run:
                last_time = datetime.fromisoformat(last_run)
                elapsed = datetime.now() - last_time
                if elapsed < timedelta(hours=24):
                    await asyncio.sleep(1800)
                    continue
            try:
                from abvorn.core.gsc_ingestor import GSCIngestor

                result = GSCIngestor().ingest_performance(days=7)
                logger.info("GSC ingestion: %s", result.get("status"))
                if result.get("status") == "success":
                    self.state.set_meta("gsc_last_run", datetime.now().isoformat())
            except Exception as e:
                logger.warning("GSC ingestion error (non-fatal): %s", e)
            await asyncio.sleep(43200)

    async def _domination_loop(self):
        """Run domination cycle every 4 hours (or on bus signal)."""
        while self.running:
            last_run = self.state.get_meta("domination_last_run", "")
            if last_run:
                last_time = datetime.fromisoformat(last_run)
                elapsed = datetime.now() - last_time
                if elapsed < timedelta(hours=4):
                    await asyncio.sleep(600)
                    continue
            result = await self.run_domination_cycle()
            if result.get("status") == "complete":
                self.state.set_meta("domination_last_run", datetime.now().isoformat())
            await asyncio.sleep(14400)

    async def stop(self):
        """Graceful shutdown of all agents."""
        logger.info("Daemon stopping...")
        self.running = False
        for agent in self.agents:
            agent.stop()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("Daemon stopped")


class OptimizationDaemon:
    """Runs periodic optimization cycles for CTAs, hooks, brain freshness, and email dispatch."""

    def __init__(self, state, cta_tracker=None, cta_analyzer=None, cta_optimizer=None,
                 hook_tester=None, hook_optimizer=None, brain_refresher=None,
                 trend_scanner=None, content_planner=None, schedule=None,
                 email_sender=None, subscriber_db=None):
        self.state = state

        if cta_tracker is not None:
            self.cta_tracker = cta_tracker
        else:
            from .cta.tracker import CTATracker
            self.cta_tracker = CTATracker(state)

        if cta_analyzer is not None:
            self.cta_analyzer = cta_analyzer
        else:
            from .cta.analyzer import CTAAnalyzer
            self.cta_analyzer = CTAAnalyzer(state)

        if cta_optimizer is not None:
            self.cta_optimizer = cta_optimizer
        else:
            from .cta.optimizer import CTAOptimizer
            self.cta_optimizer = CTAOptimizer(state)

        if hook_tester is not None:
            self.hook_tester = hook_tester
        else:
            from .hooks.tester import HookTester
            self.hook_tester = HookTester(state)

        if hook_optimizer is not None:
            self.hook_optimizer = hook_optimizer
        else:
            from .hooks.optimizer import HookOptimizer
            self.hook_optimizer = HookOptimizer(tester=self.hook_tester)

        if brain_refresher is not None:
            self.brain_refresher = brain_refresher
        else:
            from .brain.orchestrator import refresh_brain
            self.brain_refresher = refresh_brain

        if trend_scanner is not None:
            self.trend_scanner = trend_scanner
        else:
            from .trends.scanner import TrendScanner
            self.trend_scanner = TrendScanner(state=self.state)

        if content_planner is not None:
            self.content_planner = content_planner
        else:
            from .trends.planner import ContentPlanner
            self.content_planner = ContentPlanner()

        if schedule is not None:
            self.schedule = schedule
        else:
            from .trends.schedule import Schedule
            self.schedule = Schedule(state)

        if email_sender is not None:
            self.email_sender = email_sender
        else:
            from .crm.sender import EmailSender
            self.email_sender = EmailSender()

        if subscriber_db is not None:
            self.subscriber_db = subscriber_db
        else:
            from .crm.subscriber import SubscriberDB
            self.subscriber_db = SubscriberDB(Path.home() / ".abvorn" / "crm.db")

        self.cost_tracker = ModelCostTracker(state)

    def run_cycle(self) -> dict:
        cycle_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()
        actions = []

        try:
            cta_actions = self.optimize_ctas()
            actions.extend(cta_actions)
        except Exception as e:
            logger.warning(f"CTA optimization failed: {e}")

        try:
            hook_actions = self.optimize_hooks()
            actions.extend(hook_actions)
        except Exception as e:
            logger.warning(f"Hook optimization failed: {e}")

        try:
            brain_status = self.refresh_brain_if_needed()
            if brain_status.get("refreshed"):
                actions.append({
                    "type": "brain_refresh",
                    "detail": f"Brain refreshed: {brain_status.get('indexed', 0)} documents"
                })
        except Exception as e:
            logger.warning(f"Brain refresh failed: {e}")

        try:
            trend_actions = self.run_trend_cycle()
            actions.extend(trend_actions)
        except Exception as e:
            logger.warning(f"Trend cycle failed: {e}")

        try:
            email_actions = self.dispatch_scheduled_emails()
            actions.extend(email_actions)
        except Exception as e:
            logger.warning(f"Email dispatch failed: {e}")

        self.state.set_meta("optimization_last_run", timestamp)

        self.cost_tracker.record_call(
            provider="daemon", model="aggregate", task="optimization_cycle",
            tokens=0, time_ms=0, success=True
        )

        return {
            "cycle_id": cycle_id,
            "timestamp": timestamp,
            "actions": actions
        }

    def optimize_ctas(self) -> list:
        actions = []
        niches = set()

        all_stats = self.state.get_cta_stats()
        for s in all_stats:
            if s.get("niche"):
                niches.add(s["niche"])

        if not niches:
            for n in self.state.get_all_niches():
                niches.add(n["slug"])

        for niche in niches:
            suggestions = self.cta_optimizer.get_cta_suggestions(niche)
            for suggestion in suggestions:
                actions.append({
                    "type": "cta_suggestion",
                    "niche": niche,
                    "detail": suggestion.get("suggestion", str(suggestion))
                })

            niche_stats = [s for s in all_stats if s.get("niche") == niche]
            low_performers = [s for s in niche_stats if s["impressions"] > 10 and s["click_rate"] < 0.02]
            for cta in low_performers:
                optimized = self.cta_optimizer.optimize_cta_text(cta.get("cta_text", ""), cta["cta_type"])
                if optimized != cta.get("cta_text", ""):
                    actions.append({
                        "type": "cta_replacement",
                        "niche": niche,
                        "cta_id": cta["cta_id"],
                        "old_text": cta.get("cta_text", ""),
                        "new_text": optimized,
                        "detail": f"Replaced low-performing CTA '{cta.get('cta_text', '')}' with '{optimized}'"
                    })

        return actions

    def optimize_hooks(self) -> list:
        actions = []

        for niche_info in self.state.get_all_niches():
            niche = niche_info["slug"]
            for platform in ["blog", "x", "facebook", "linkedin"]:
                best = self.hook_tester.get_best_hooks(niche, platform, limit=3)
                if best:
                    self.state.set_meta(f"hook_benchmark:{niche}:{platform}", {
                        "best_hooks": best,
                        "recorded_at": datetime.now().isoformat()
                    })
                    actions.append({
                        "type": "hook_benchmark",
                        "niche": niche,
                        "platform": platform,
                        "detail": f"Recorded {len(best)} top hooks for {niche}/{platform}"
                    })

        if not actions:
            actions.append({
                "type": "hook_benchmark",
                "detail": "No hook data available yet"
            })

        return actions

    def refresh_brain_if_needed(self) -> dict:
        last_refresh = self.state.get_meta("brain_last_refresh")

        if last_refresh:
            last_time = datetime.fromisoformat(last_refresh)
            elapsed = datetime.now() - last_time
            if elapsed < timedelta(hours=1):
                return {"refreshed": False, "reason": f"Last refresh {elapsed.total_seconds() / 60:.0f}m ago"}

        result = self.brain_refresher()
        self.state.set_meta("brain_last_refresh", datetime.now().isoformat())
        return {"refreshed": True, **result}

    def run_trend_cycle(self) -> list:
        """Scan trends, plan content, fill schedule. Returns actions taken."""
        actions = []
        try:
            trends = self.trend_scanner.scan()
            if trends:
                planned = self.content_planner.plan(trends)
                if planned:
                    self.schedule.fill_queue(planned)
                    self.schedule.assign_slots()
                    am = self.schedule.get_am_post()
                    pm = self.schedule.get_pm_post()
                    actions.append({
                        "type": "trend_scan",
                        "trends_found": len(trends),
                        "planned": len(planned),
                        "am_post": am["product_name"] if am else None,
                        "pm_post": pm["product_name"] if pm else None,
                    })
                    self.state.set_meta("trend_last_scan", datetime.now().isoformat())
                else:
                    actions.append({"type": "trend_scan", "trends_found": len(trends), "planned": 0})
            else:
                actions.append({"type": "trend_scan", "trends_found": 0, "planned": 0})
        except Exception as e:
            logger.warning(f"Trend cycle failed: {e}")
            actions.append({"type": "trend_scan", "error": str(e)})
        return actions

    def dispatch_scheduled_emails(self) -> list:
        """Send new content to subscribers for niches with recent posts (last 24h)."""
        actions = []
        niches = self.state.get_all_niches()

        for niche_info in niches:
            niche = niche_info["slug"]
            posts = self.state.get_posts_for_niche(niche)
            recent = [p for p in posts if self._is_recent(p, hours=24)]
            if not recent:
                continue

            latest = recent[0]
            content = {
                "post_title": latest.get("title", "New guide"),
                "post_url": latest.get("url", "#"),
                "persona_name": niche,
            }
            recipients = self.subscriber_db.get_subscribers(niche=niche)
            if not recipients:
                continue

            result = self.email_sender.send_persona_content(
                persona_id=f"persona_{niche}",
                niche=niche,
                content=content,
                recipients=recipients,
            )
            actions.append({
                "type": "email_dispatch",
                "niche": niche,
                "sent": result.get("sent", 0),
                "total": result.get("total", 0),
                "detail": f"Sent {result.get('sent', 0)}/{result.get('total', 0)} emails for {niche}",
            })
            dispatch_count = self.state.get_meta("emails_dispatched_total", 0)
            self.state.set_meta("emails_dispatched_total", dispatch_count + result.get("sent", 0))

        self.state.set_meta("last_cycle_email_actions", actions)

        return actions

    def _is_recent(self, post: dict, hours: int = 24) -> bool:
        """Check if a post was created within the last `hours`."""
        created = post.get("created_at") or post.get("date") or ""
        if not created:
            return False
        try:
            post_time = datetime.fromisoformat(created)
            return datetime.now() - post_time < timedelta(hours=hours)
        except (ValueError, TypeError):
            return False

    def generate_report(self) -> str:
        lines = []
        lines.append("# Abvorn Optimization Report")
        lines.append("")

        last_run = self.state.get_meta("optimization_last_run", "never")
        lines.append(f"**Last optimization cycle:** {last_run}")
        lines.append("")

        lines.append("## CTA Performance")
        cta_summary = self.state.get_cta_summary()
        lines.append(f"- **Total CTAs tracked:** {cta_summary.get('total_ctas', 0)}")
        lines.append(f"- **Overall click rate:** {cta_summary.get('overall_click_rate', 0) * 100:.1f}%")
        lines.append(f"- **Total conversions:** {cta_summary.get('total_conversions', 0)}")

        all_stats = self.state.get_cta_stats()
        low_performers = [s for s in all_stats if s["impressions"] > 10 and s["click_rate"] < 0.02]
        if low_performers:
            lines.append(f"- **CTAs needing attention:** {len(low_performers)}")
            for cta in low_performers[:5]:
                lines.append(f"  - `{cta['cta_id']}` ({cta.get('cta_text', '')}): {cta['click_rate']*100:.1f}% CTR")
        lines.append("")

        lines.append("## Hook Recommendations")
        hook_data = self.state.get_all_intel_patterns()
        hook_patterns = [p for p in hook_data if "hook" in p.get("pattern_type", "").lower()]
        if hook_patterns:
            for p in hook_patterns[:5]:
                lines.append(f"- **{p['content'][:60]}** — confidence: {p['confidence']:.0%}")
        else:
            lines.append("- No hook patterns available yet.")
        lines.append("")

        lines.append("## Brain Status")
        last_brain = self.state.get_meta("brain_last_refresh", "never")
        lines.append(f"- **Last refresh:** {last_brain}")
        if last_brain != "never":
            elapsed = datetime.now() - datetime.fromisoformat(last_brain)
            lines.append(f"- **Freshness:** {elapsed.total_seconds() / 60:.0f} minutes ago")
        lines.append("")

        lines.append("## Model Cost Tracking")
        cost_stats = self.cost_tracker.get_stats()
        lines.append(f"- **Total calls:** {cost_stats['total_calls']}")
        lines.append(f"- **Successful:** {cost_stats['successful']}")
        lines.append(f"- **Failed:** {cost_stats['failed']}")
        lines.append(f"- **Total tokens:** {cost_stats['total_tokens']}")
        lines.append(f"- **Estimated cost:** ${cost_stats['estimated_cost_usd']:.4f}")
        lines.append("")

        lines.append("## Engagement Summary")
        lines.append("- *(Post-level engagement available per-post via state.get_engagement_summary())*")
        lines.append("")

        lines.append("## Email Dispatch")
        emails_total = self.state.get_meta("emails_dispatched_total", 0)
        lines.append(f"- **Total emails dispatched:** {emails_total}")
        last_cycle_actions = self.state.get_meta("last_cycle_email_actions", [])
        for a in last_cycle_actions[-3:]:
            lines.append(f"  - {a.get('detail', '')}")
        lines.append("")

        lines.append("## Content Schedule")
        am_post = self.schedule.get_am_post()
        pm_post = self.schedule.get_pm_post()
        if am_post:
            lines.append(f"- **AM:** [{am_post['content_type']}] {am_post['product_name']} \u2192 {am_post['primary_platform']}")
        else:
            lines.append("- **AM:** No post scheduled")
        if pm_post:
            lines.append(f"- **PM:** [{pm_post['content_type']}] {pm_post['product_name']} \u2192 {pm_post['primary_platform']}")
        else:
            lines.append("- **PM:** No post scheduled")
        lines.append(f"- **Queue:** {self.schedule.queue_size()} items waiting")

        last_trend = self.state.get_meta("trend_last_scan", "never")
        lines.append(f"- **Last trend scan:** {last_trend}")
        lines.append("")

        return "\n".join(lines)

    def should_run(self, interval: int = 3600) -> bool:
        last_run = self.state.get_meta("optimization_last_run")
        if not last_run:
            return True
        last_time = datetime.fromisoformat(last_run)
        elapsed = datetime.now() - last_time
        return elapsed.total_seconds() >= interval


def run_once(state) -> str:
    daemon = OptimizationDaemon(state)
    daemon.run_cycle()
    return daemon.generate_report()