"""Speech in/out via the ElevenLabs API (Hebrew speech-to-text and text-to-speech)."""
import logging
import os
import re

import requests

logger = logging.getLogger(__name__)

API = "https://api.elevenlabs.io/v1"
KEY = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "")
TTS_MODEL = os.environ.get("ELEVENLABS_TTS_MODEL", "eleven_v3")   # Hebrew-capable model
STT_MODEL = os.environ.get("ELEVENLABS_STT_MODEL", "scribe_v3")
LANG = os.environ.get("COACH_LANG", "he")


def is_configured() -> bool:
    return bool(KEY and VOICE_ID)


def transcribe(pcm16k: bytes) -> str:
    """Raw PCM (signed 16-bit little-endian, 16kHz, mono) -> text."""
    r = requests.post(
        f"{API}/speech-to-text",
        headers={"xi-api-key": KEY},
        data={"model_id": STT_MODEL, "language_code": LANG, "file_format": "pcm_s16le_16",
              "tag_audio_events": "false"},
        files={"file": ("speech.pcm", pcm16k, "application/octet-stream")},
        timeout=60,
    )
    r.raise_for_status()
    return (r.json().get("text") or "").strip()


_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")


def speak(text: str) -> bytes:
    """Text -> raw PCM 16kHz (what the device speaker plays)."""
    text = _EMOJI.sub("", re.sub(r"[*_#`]", "", text)).strip()
    if not text:
        return b""
    r = requests.post(
        f"{API}/text-to-speech/{VOICE_ID}",
        params={"output_format": "pcm_16000"},
        headers={"xi-api-key": KEY, "Content-Type": "application/json"},
        json={"text": text[:4500], "model_id": TTS_MODEL, "language_code": LANG},
        timeout=90,
    )
    r.raise_for_status()
    return r.content
