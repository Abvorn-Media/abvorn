"""Persona discovery — derives buyer personas from niches using brain frameworks."""

import logging, random

logger = logging.getLogger("abvorn.persona")

AWARENESS_LEVELS = ["unaware", "problem_aware", "solution_aware", "product_aware", "most_aware"]
LF8_DESIRES = ["survival", "food_enjoyment", "freedom_from_pain", "companionship",
               "comfortable_living", "superiority", "care_for_loved_ones", "social_approval"]
CIALDINI_PRINCIPLES = ["reciprocity", "scarcity", "authority", "liking",
                        "consistency", "social_proof", "unity"]
HOFFELD_REASONS = ["gain", "avoid", "feel", "conform", "identity", "reduce_uncertainty"]

PERSONA_TEMPLATES = {
    "wireless headphones": [
        {"name": "Marcus the Commuter", "age_range": "25-40",
         "psychology": {"awareness_level": "solution_aware", "primary_lf8_desire": "freedom_from_pain",
                        "anxieties": ["battery dying mid-commute", "missing my stop", "tangled wires"],
                        "hopes": ["peaceful commute", "hear every detail"]}},
        {"name": "Gamer Gary", "age_range": "18-35",
         "psychology": {"awareness_level": "product_aware", "primary_lf8_desire": "superiority",
                        "anxieties": ["lag ruining my game", "mic cutting out"],
                        "hopes": ["hear footsteps first", "win more matches"]}},
        {"name": "Audiophile Amy", "age_range": "30-55",
         "psychology": {"awareness_level": "most_aware", "primary_lf8_desire": "comfortable_living",
                        "anxieties": ["compressed audio", "cheap build quality"],
                        "hopes": ["reference-quality sound", "luxury feel"]}},
    ],
    "gaming mice": [
        {"name": "Competitive Calvin", "age_range": "16-30",
         "psychology": {"awareness_level": "most_aware", "primary_lf8_desire": "superiority",
                        "anxieties": ["missed flick shots", "sensor jitter under fast movement", "double-click failure mid-clutch"],
                        "hopes": ["sub-50g wireless", "flawless tracking", "rank up this season"]}},
        {"name": "MMO Mike", "age_range": "22-40",
         "psychology": {"awareness_level": "product_aware", "primary_lf8_desire": "comfortable_living",
                        "anxieties": ["carpal tunnel from endless clicking", "not enough side buttons", "software rebinding my keys"],
                        "hopes": ["12 programmable buttons", "ergonomic grip for 8-hour raids", "one-shot macros"]}},
        {"name": "Budget Buyer Bella", "age_range": "18-25",
         "psychology": {"awareness_level": "problem_aware", "primary_lf8_desire": "freedom_from_pain",
                        "anxieties": ["wasting money on gimmicks", "cheap sensor skipping", "mouse breaking in 3 months"],
                        "hopes": ["pro-level feel under $50", "reliable build", "honest comparison"]}},
    ],
    "4k monitors": [
        {"name": "Creative Director Chloe", "age_range": "28-50",
         "psychology": {"awareness_level": "most_aware", "primary_lf8_desire": "superiority",
                        "anxieties": ["AdobeRGB below 95%", "backlight bleed ruining grading", "USB-C not delivering 90W"],
                        "hopes": ["factory-calibrated Delta-E < 2", "true HDR600+", "seamless Mac integration"]}},
        {"name": "Productivity Pete", "age_range": "30-55",
         "psychology": {"awareness_level": "solution_aware", "primary_lf8_desire": "care_for_loved_ones",
                        "anxieties": ["eye strain after 10-hour days", "tiny text on 1080p", "multi-monitor bezel gap"],
                        "hopes": ["crisp text for spreadsheets", "PIP for两台 computers", "ergonomic height adjust"]}},
        {"name": "Console Gamer Ryan", "age_range": "20-35",
         "psychology": {"awareness_level": "product_aware", "primary_lf8_desire": "superiority",
                        "anxieties": ["HDMI 2.1 not supported", "VRR flicker", "input lag above 10ms"],
                        "hopes": ["true 4K 120Hz", "auto low-latency mode", "HDR that pops"]}},
    ],
    "laptops": [
        {"name": "Digital Nomad Nina", "age_range": "24-38",
         "psychology": {"awareness_level": "solution_aware", "primary_lf8_desire": "freedom_from_pain",
                        "anxieties": ["battery dead before lunch", "laptop too heavy for backpack", "fan noise in coffee shops"],
                        "hopes": ["16-hour real battery", "under 3 lbs", "instant wake from sleep"]}},
        {"name": "Power User Paul", "age_range": "28-50",
         "psychology": {"awareness_level": "most_aware", "primary_lf8_desire": "superiority",
                        "anxieties": ["thermal throttling during renders", "soldered RAM I can't upgrade", "GPU too weak for my workflow"],
                        "hopes": ["32GB+ RAM", "full-fat GPU", "dual NVMe slots"]}},
        {"name": "Student Sarah", "age_range": "18-24",
         "psychology": {"awareness_level": "problem_aware", "primary_lf8_desire": "care_for_loved_ones",
                        "anxieties": ["laptop dying mid-exam", "spilled coffee on keyboard", "budget too tight for mistakes"],
                        "hopes": ["lasts 4 years through college", "spill-resistant keyboard", "best bang for $800"]}},
    ],
    "streaming devices": [
        {"name": "Cord-Cutter Carl", "age_range": "28-50",
         "psychology": {"awareness_level": "solution_aware", "primary_lf8_desire": "freedom_from_pain",
                        "anxieties": ["cable bill too high", "missing live sports", "app ecosystem too limited"],
                        "hopes": ["all streaming services in one", "sports without blackouts", "no monthly fees"]}},
        {"name": "Home Theater Hannah", "age_range": "30-60",
         "psychology": {"awareness_level": "most_aware", "primary_lf8_desire": "comfortable_living",
                        "anxieties": ["Dolby Vision not supported", "audio sync issues", "cheap plastic remote feel"],
                        "hopes": ["Dolby Atmos passthrough", "lossless audio", "premium build that matches my setup"]}},
        {"name": "Budget Mom Maria", "age_range": "30-45",
         "psychology": {"awareness_level": "problem_aware", "primary_lf8_desire": "care_for_loved_ones",
                        "anxieties": ["kids content too hard to find", "subscriptions adding up", "device too complicated for spouse"],
                        "hopes": ["simple kid-friendly UI", "parental controls", "one remote for everything"]}},
    ],
    "mechanical keyboards": [
        {"name": "Typist Tom", "age_range": "25-55",
         "psychology": {"awareness_level": "product_aware", "primary_lf8_desire": "freedom_from_pain",
                        "anxieties": ["RSI from mushy membrane keys", "typing fatigue by 3 PM", "loud switches annoying coworkers"],
                        "hopes": ["silent tactile switches", "perfect ergonomic angle", "wrist rest that works"]}},
        {"name": "Enthusiast Emma", "age_range": "20-35",
         "psychology": {"awareness_level": "most_aware", "primary_lf8_desire": "superiority",
                        "anxieties": ["gasket mount not flexible enough", "PCB not QMK/VIA compatible", "plate material too stiff"],
                        "hopes": ["custom frankenswitch build", "thocky sound profile", "alice layout endgame"]}},
        {"name": "Gamer Greg", "age_range": "16-30",
         "psychology": {"awareness_level": "product_aware", "primary_lf8_desire": "superiority",
                        "anxieties": ["key press latency over 1ms", "N-key rollover missing", "WASD keys wear out too fast"],
                        "hopes": ["hot-swap for linear switches", "PBT doubleshot keycaps", "racing-style cable"]}},
    ],
    "wireless earbuds": [
        {"name": "Gym Rat Jake", "age_range": "20-35",
         "psychology": {"awareness_level": "solution_aware", "primary_lf8_desire": "freedom_from_pain",
                        "anxieties": ["buds falling out during deadlifts", "sweat damaging IP rating", "wind noise on outdoor runs"],
                        "hopes": ["IPX7 waterproof", "wing tips that lock in", "transparency mode for safety"]}},
        {"name": "Remote Worker Wendy", "age_range": "28-50",
         "psychology": {"awareness_level": "product_aware", "primary_lf8_desire": "comfortable_living",
                        "anxieties": ["mic picking up background noise", "battery dies before meetings end", "ear fatigue after 2 hours"],
                        "hopes": ["clear call quality with ANC", "6+ hours talk time", "comfortable all-day wear"]}},
        {"name": "Value Hunter Vince", "age_range": "22-40",
         "psychology": {"awareness_level": "problem_aware", "primary_lf8_desire": "freedom_from_pain",
                        "anxieties": ["losing one bud immediately", "charging case battery degrading", "paying $200 for basic features"],
                        "hopes": ["good ANC under $80", "Find My support", "USB-C everything"]}},
    ],
    "fitness trackers": [
        {"name": "Marathoner Maya", "age_range": "25-45",
         "psychology": {"awareness_level": "most_aware", "primary_lf8_desire": "superiority",
                        "anxieties": ["GPS dropping mid-run", "HR sensor inaccurate at high BPM", "battery can't handle ultra distance"],
                        "hopes": ["dual-band GPS accuracy", "training readiness score", "7-day battery"]}},
        {"name": "Health-Conscious Helen", "age_range": "35-60",
         "psychology": {"awareness_level": "solution_aware", "primary_lf8_desire": "survival",
                        "anxieties": ["heart palpitations going unnoticed", "sleep quality declining", "stress levels too high"],
                        "hopes": ["AFib detection", "sleep staging", "stress management guidance"]}},
        {"name": "New Year Noah", "age_range": "20-35",
         "psychology": {"awareness_level": "problem_aware", "primary_lf8_desire": "social_approval",
                        "anxieties": ["buying a device I won't wear", "subscription fees for basic stats", "data that doesn't motivate me"],
                        "hopes": ["no monthly fees", "step streak challenges", "visible progress that keeps me going"]}},
    ],
    "webcams": [
        {"name": "Streamer Steph", "age_range": "18-30",
         "psychology": {"awareness_level": "product_aware", "primary_lf8_desire": "social_approval",
                        "anxieties": ["grainy image on stream", "auto-focus hunting and blurring", "no background replacement"],
                        "hopes": ["1080p 60fps clean feed", "good low-light for night streams", "plug-and-play OBS setup"]}},
        {"name": "Remote Manager Mark", "age_range": "30-55",
         "psychology": {"awareness_level": "solution_aware", "primary_lf8_desire": "freedom_from_pain",
                        "anxieties": ["looking unprofessional on calls", "fisheye distortion from built-in lens", "disconnected signals"],
                        "hopes": ["DSLR-like quality in one cable", "auto-light correction", "wide enough for team views"]}},
        {"name": "Teacher Tina", "age_range": "28-50",
         "psychology": {"awareness_level": "problem_aware", "primary_lf8_desire": "care_for_loved_ones",
                        "anxieties": ["students can't see my whiteboard", "cheap webcam dies mid-lesson", "driver issues every update"],
                        "hopes": ["built-in ring light", "privacy shutter that works", "multiplatform compatibility"]}},
    ],
    "smart home": [
        {"name": "Tech Tinkerer Troy", "age_range": "25-45",
         "psychology": {"awareness_level": "most_aware", "primary_lf8_desire": "superiority",
                        "anxieties": ["Matter certification delays", "hub compatibility hell", "devices that need proprietary bridges"],
                        "hopes": ["true local control no cloud", "Thread mesh network", "Home Assistant integration"]}},
        {"name": "Security-Minded Sam", "age_range": "30-60",
         "psychology": {"awareness_level": "solution_aware", "primary_lf8_desire": "survival",
                        "anxieties": ["package theft caught too late", "privacy concerns with cloud cams", "false alarms from motion sensors"],
                        "hopes": ["24/7 local recording", "AI package detection", "end-to-end encrypted video"]}},
        {"name": "New Homeowner Nora", "age_range": "25-40",
         "psychology": {"awareness_level": "problem_aware", "primary_lf8_desire": "comfortable_living",
                        "anxieties": ["smart lock failing when locked out", "wife hates complicated setup", "too many brands not talking"],
                        "hopes": ["start simple with three staples", "voice control for daily tasks", "energy bill reduction"]}},
    ],
}


class PersonaEngine:
    """Discovers buyer personas for niches using brain psychology frameworks."""

    def discover_personas(self, niche: str) -> list[dict]:
        """Derive 2-5 candidate personas for a niche."""
        niche_lower = niche.lower()
        templates = PERSONA_TEMPLATES.get(niche_lower, [])
        if not templates:
            templates = self._generate_personas(niche)
        for p in templates:
            if "cialdini_principles" not in p.get("psychology", {}):
                p.setdefault("psychology", {})["cialdini_principles"] = random.sample(CIALDINI_PRINCIPLES, 3)
            if "hoffeld_buying_reason" not in p.get("psychology", {}):
                p["psychology"]["hoffeld_buying_reason"] = random.choice(HOFFELD_REASONS)
        logger.info(f"Discovered {len(templates)} personas for '{niche}'")
        return templates

    def _generate_personas(self, niche: str) -> list[dict]:
        """Fallback: generate generic personas for any niche."""
        return [
            {"name": "The First-Time Buyer", "age_range": "20-40",
             "psychology": {"awareness_level": "problem_aware", "primary_lf8_desire": "freedom_from_pain",
                            "anxieties": ["wasting money", "choosing wrong product"],
                            "hopes": ["get it right first time"]}},
            {"name": "The Enthusiast", "age_range": "25-50",
             "psychology": {"awareness_level": "product_aware", "primary_lf8_desire": "superiority",
                            "anxieties": ["missing features", "outdated tech"],
                            "hopes": ["best-in-class experience"]}},
        ]