"""Speech to text with MLX Whisper (runs on the Apple Silicon GPU)."""
from __future__ import annotations

import re
import threading
import zlib

import numpy as np

from .phrases import fold

# Whisper is very prone to inventing these over silence or noise.
_HALLUCINATIONS = {
    "altyazi m k", "altyazi mk", "altyazi", "abone olmayi unutmayin",
    "izlediginiz icin tesekkurler", "tesekkurler", "altyazi ve ceviri",
    "bu videoda", "altyazilar", "thanks for watching", "thank you",
    "you", "subtitles by the amara org community", "amara org",
    "altyazi m k tarafindan", "beni takip etmeyi unutmayin", "muzik",
    "alkis", "gulme", "iyi seyirler", "devami gelecek",
}
_PUNCT_ONLY = re.compile(r"^[\W_]*$", re.UNICODE)


def _compression_ratio(text: str) -> float:
    """Repeating text compresses extremely well. When Whisper hallucinates
    ("...l'e'l'e'l'e...") this ratio spikes. A normal sentence is ~1.2-1.9."""
    data = text.encode("utf-8")
    if len(data) < 24:
        return 1.0
    return len(data) / max(1, len(zlib.compress(data, 1)))


def _is_garbage(text: str) -> bool:
    f = fold(text).strip(" .,!?-—–…")
    f = re.sub(r"\s+", " ", f)
    if not f or _PUNCT_ONLY.match(text):
        return True
    if f in _HALLUCINATIONS:
        return True
    # Variants such as "Subtitles by M.K."
    if f.startswith("altyazi") or f.startswith("subtitles"):
        return True
    # Known hallucinations matched by their opening words
    for bad in ("izlediginiz icin", "abone olmayi", "beni takip",
                "altyazi", "subtitles", "thanks for watching",
                "ceviri ve altyazi", "ceviri m k", "altyazi ve ceviri",
                "ceviri altyazi"):
        if f.startswith(bad):
            return True
    # Leftovers of a single letter or a lone period
    if len(f) <= 1:
        return True
    # Self-repeating text (the hallucination loop)
    if _compression_ratio(text) > 2.4:
        return True
    return False


class Transcriber:
    def __init__(self, cfg: dict):
        self.model = cfg["model"]
        self.language = cfg.get("language") or None
        self.initial_prompt = cfg.get("initial_prompt") or None
        self.no_speech_threshold = float(cfg.get("no_speech_threshold", 0.6))
        self.min_sec = float(cfg.get("min_segment_sec", 0.35))
        self.normalize = bool(cfg.get("normalize", True))
        self.target_rms = float(cfg.get("target_rms", 0.08))
        self.max_gain = float(cfg.get("max_gain", 12.0))
        self._lock = threading.Lock()   # the mlx model takes one call at a time
        pf = re.sub(r"[^a-z0-9 ]+", " ", fold(self.initial_prompt or ""))
        self._prompt_folded = re.sub(r"\s+", " ", pf).strip()
        self._ready = False
        self.load_error: str | None = None

    def warmup(self) -> bool:
        """Downloads and warms the model so the first real sentence is fast."""
        try:
            silence = np.zeros(16000, dtype=np.float32)
            self._run(silence)
            self._ready = True
            return True
        except Exception as exc:
            self.load_error = str(exc)
            print(f"[stt] model yuklenemedi: {exc}")
            return False

    @property
    def ready(self) -> bool:
        return self._ready

    def _run(self, audio: np.ndarray) -> dict:
        import mlx_whisper
        kwargs = dict(
            path_or_hf_repo=self.model,
            task="transcribe",          # NEVER "translate": transcribe, do not translate
            temperature=0.0,
            condition_on_previous_text=False,   # break the hallucination chain
            no_speech_threshold=self.no_speech_threshold,
            compression_ratio_threshold=2.4,
        )
        if self.language:
            kwargs["language"] = self.language
        if self.initial_prompt:
            kwargs["initial_prompt"] = self.initial_prompt
        with self._lock:
            return mlx_whisper.transcribe(audio, **kwargs)

    def _normalize(self, audio: np.ndarray) -> np.ndarray:
        """Lifts a quiet recording to a target level.

        The built-in microphone records far quieter than a headset, and Whisper
        degrades noticeably on quiet audio ("kes" -> "test"). The gain is
        capped, otherwise background noise is amplified along with the speech.
        """
        if not self.normalize:
            return audio
        rms = float(np.sqrt(np.mean(np.square(audio))))
        if rms < 1e-6:
            return audio
        gain = min(self.target_rms / rms, self.max_gain)
        if gain <= 1.05:
            return audio
        return np.clip(audio * gain, -1.0, 1.0)

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        if audio.size < int(self.min_sec * sample_rate):
            return ""
        audio = self._normalize(audio.astype(np.float32))
        try:
            result = self._run(audio.astype(np.float32))
        except Exception as exc:
            print(f"[stt] cozumleme hatasi: {exc}")
            return ""

        # Drop segments whose no-speech probability is high.
        kept = []
        for seg in result.get("segments", []):
            if seg.get("no_speech_prob", 0.0) > self.no_speech_threshold:
                continue
            txt = (seg.get("text") or "").strip()
            if txt and not _is_garbage(txt):
                kept.append(txt)
        segments = result.get("segments") or []
        if segments:
            # When every segment is filtered out the result is EMPTY. This
            # used to fall back to the raw text, which disabled the filter.
            text = " ".join(kept).strip()
        else:
            text = (result.get("text") or "").strip()
        if not text or _is_garbage(text):
            return ""
        if self._echoes_prompt(text):
            return ""
        return re.sub(r"\s+", " ", text)

    def _echoes_prompt(self, text: str) -> bool:
        """Whisper can read the initial_prompt back on silence; catch that.

        If the FIRST TWO words of a short text appear consecutively in the
        prompt, it is an echo ("API response" -> prompt holds "api response
        payload"). Commands always contain the wake name, which never appears
        in the prompt, so this rule never discards a command.
        """
        if not self._prompt_folded:
            return False
        f = re.sub(r"[^a-z0-9 ]+", " ", fold(text))
        f = re.sub(r"\s+", " ", f).strip()
        if len(f) < 8:
            return False
        if f in self._prompt_folded:
            return True
        toks = f.split()
        if len(toks) == 1:
            # A single word that occurs in the prompt is an echo ("JSON", "API")
            return f" {toks[0]} " in f" {self._prompt_folded} "
        if 2 <= len(toks) <= 5:
            if f"{toks[0]} {toks[1]}" in self._prompt_folded:
                return True
        return False
