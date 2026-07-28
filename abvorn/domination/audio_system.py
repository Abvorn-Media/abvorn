"""Audio System — voiceover generation and brand jingle synthesis.
Uses TTS fallbacks since pydub/librosa are not installed in this environment.
Outputs WAV files or generates script files for external processing."""

import logging, json
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("abvorn.domination.audio")

AUDIO_DIR = Path.home() / ".abvorn" / "audio"


class AudioSystem:
    """Manages voiceover scripts and audio asset metadata.

    Full voice synthesis requires pydub + TTS engine (not installed).
    This module generates script files ready for external TTS processing
    and manages the audio asset inventory.
    """

    def __init__(self):
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        self._manifest = AUDIO_DIR / "manifest.json"
        self._assets = self._load_manifest()

    def _load_manifest(self) -> dict:
        if self._manifest.exists():
            try:
                return json.loads(self._manifest.read_text())
            except Exception:
                pass
        return {"jingles": [], "voiceovers": [], "generated_at": ""}

    def _save_manifest(self):
        self._manifest.write_text(json.dumps(self._assets, indent=2))

    def generate_voiceover_script(self, text: str, niche: str,
                                  platform: str = "tiktok",
                                  duration_s: int = 30) -> dict:
        """Generate a voiceover script file for external TTS processing."""
        slug = f"vo_{niche}_{platform}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        script_path = AUDIO_DIR / f"{slug}.txt"
        script_path.write_text(text, encoding="utf-8")

        entry = {
            "id": slug,
            "niche": niche,
            "platform": platform,
            "duration_s": duration_s,
            "text_length": len(text),
            "words": len(text.split()),
            "estimated_duration_s": max(duration_s, len(text.split()) // 3),
            "script_path": str(script_path),
            "created_at": datetime.now().isoformat(),
        }
        self._assets.setdefault("voiceovers", []).append(entry)
        self._save_manifest()
        logger.info(f"Voiceover script saved: {slug}")
        return entry

    def generate_jingle(self, niche: str, mood: str = "energetic") -> dict:
        """Generate a jingle specification for external audio production."""
        slug = f"jingle_{niche}_{mood}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        spec_path = AUDIO_DIR / f"{slug}.json"

        spec = {
            "jingle_id": slug,
            "niche": niche,
            "mood": mood,
            "bpm": 120 if mood == "energetic" else 90 if mood == "calm" else 100,
            "duration_s": 5,
            "instruments": ["synth_pad", "bass", "percussion"],
            "brand_colors": {"primary": "#1a1a1a", "accent": "#0066cc"},
            "notes": f"Short {mood} brand jingle for {niche} content",
        }
        spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

        entry = {**spec, "spec_path": str(spec_path), "created_at": datetime.now().isoformat()}
        self._assets.setdefault("jingles", []).append(entry)
        self._save_manifest()
        logger.info(f"Jingle spec saved: {slug}")
        return entry

    def get_voiceover_for_post(self, post_title: str) -> dict | None:
        """Get a cached voiceover matching a post title."""
        for vo in self._assets.get("voiceovers", []):
            if post_title[:30] in vo.get("id", ""):
                return vo
        return None

    def count_assets(self) -> dict:
        return {
            "voiceovers": len(self._assets.get("voiceovers", [])),
            "jingles": len(self._assets.get("jingles", [])),
        }
