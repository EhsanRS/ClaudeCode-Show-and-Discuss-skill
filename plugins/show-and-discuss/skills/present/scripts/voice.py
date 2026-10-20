#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "numpy>=1.24",
#   "sounddevice>=0.4.6",
#   "faster-whisper>=1.0",
# ]
# ///
"""Voice helper for the show-and-discuss skill.

Speaks narration aloud and listens for the user while it speaks. As soon as
the user starts talking, playback stops ("barge-in"), their question is
recorded until they pause, transcribed, and returned to Claude.

Every command prints exactly one JSON object on stdout; diagnostics go to
stderr. Run with ``uv run voice.py <command>`` so dependencies install
automatically, or ``python3 voice.py`` after ``pip install -r requirements.txt``.

Commands
--------
  doctor            Report which speech backends and audio devices are usable.
  say TEXT          Speak TEXT; stop and transcribe if the user interrupts.
  listen            Wait for the user to speak, record until they pause, transcribe.
  calibrate         Measure ambient noise and suggest a sensitivity.

Backends (chosen automatically, overridable with environment variables)
-------------------------------------------------------------------
  Text-to-speech  SHOW_DISCUSS_TTS = auto | elevenlabs | system | off
                  auto → ElevenLabs when ELEVENLABS_API_KEY is set, else the
                  system voice (macOS `say`, `piper`, `espeak-ng`/`espeak`,
                  Windows SAPI).
  Speech-to-text  SHOW_DISCUSS_STT = whisper | scribe | off   (default whisper)
                  whisper → local faster-whisper (private, offline after the
                  first model download); scribe → ElevenLabs Scribe API.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import platform
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
import wave
from collections import deque
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

__version__ = "0.1.0"

ELEVENLABS_API = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # "George" — a stock ElevenLabs voice
DEFAULT_TTS_MODEL = "eleven_flash_v2_5"  # lowest credit cost per character
DEFAULT_STT_MODEL = "scribe_v1"
DEFAULT_WHISPER_MODEL = "base.en"
STT_RATE = 16_000  # Whisper and Scribe both work well at 16 kHz mono
FRAME_MS = 30
MAX_CHUNK_CHARS = 600


def log(*parts: object) -> None:
    print("[voice]", *parts, file=sys.stderr, flush=True)


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


# ── Configuration ────────────────────────────────────────────────────────────


@dataclass
class Config:
    tts: str = "auto"
    stt: str = "whisper"
    api_key: str | None = None
    voice_id: str = DEFAULT_VOICE_ID
    tts_model: str = DEFAULT_TTS_MODEL
    stt_model: str = DEFAULT_STT_MODEL
    whisper_model: str = DEFAULT_WHISPER_MODEL
    system_voice: str | None = None
    piper_model: str | None = None
    barge_in: bool = True
    sensitivity: float = 1.0  # >1 = more sensitive, <1 = less sensitive
    language: str | None = None

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Config:
        env = dict(os.environ if env is None else env)

        def flag(name: str, default: bool) -> bool:
            raw = env.get(name)
            if raw is None or raw == "":
                return default
            return raw.strip().lower() not in {"0", "false", "no", "off"}

        def number(name: str, default: float) -> float:
            try:
                return float(env[name])
            except (KeyError, ValueError):
                return default

        return cls(
            tts=env.get("SHOW_DISCUSS_TTS", "auto").strip().lower() or "auto",
            stt=env.get("SHOW_DISCUSS_STT", "whisper").strip().lower() or "whisper",
            api_key=env.get("ELEVENLABS_API_KEY") or None,
            voice_id=env.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE_ID,
            tts_model=env.get("ELEVENLABS_MODEL_ID") or DEFAULT_TTS_MODEL,
            stt_model=env.get("ELEVENLABS_STT_MODEL_ID") or DEFAULT_STT_MODEL,
            whisper_model=env.get("SHOW_DISCUSS_WHISPER_MODEL") or DEFAULT_WHISPER_MODEL,
            system_voice=env.get("SHOW_DISCUSS_SYSTEM_VOICE") or None,
            piper_model=env.get("PIPER_MODEL") or None,
            barge_in=flag("SHOW_DISCUSS_BARGE_IN", True),
            sensitivity=max(0.1, number("SHOW_DISCUSS_SENSITIVITY", 1.0)),
            language=env.get("SHOW_DISCUSS_LANGUAGE") or None,
        )


def system_tts_engine(
    which: Callable[[str], str | None] = shutil.which,
    system: str | None = None,
    piper_model: str | None = None,
) -> str | None:
    """Return the best offline TTS engine available on this machine."""
    system = system or platform.system()
    if system == "Darwin" and which("say"):
        return "say"
    if piper_model and which("piper"):
        return "piper"
    for name in ("espeak-ng", "espeak"):
        if which(name):
            return name
    if system == "Windows" and (which("powershell") or which("pwsh")):
        return "sapi"
    return None


def resolve_tts(cfg: Config, which: Callable[[str], str | None] = shutil.which) -> str:
    """Pick the TTS backend: 'elevenlabs', a system engine name, or 'off'."""
    if cfg.tts == "off":
        return "off"
    if cfg.tts in ("auto", "elevenlabs") and cfg.api_key:
        return "elevenlabs"
    if cfg.tts == "elevenlabs":
        log("SHOW_DISCUSS_TTS=elevenlabs but ELEVENLABS_API_KEY is not set; using the system voice.")
    return system_tts_engine(which, piper_model=cfg.piper_model) or "off"


def resolve_stt(cfg: Config) -> str:
    """Pick the STT backend: 'whisper', 'scribe' or 'off'."""
    if cfg.stt == "off":
        return "off"
    if cfg.stt == "scribe":
        if cfg.api_key:
            return "scribe"
        log("SHOW_DISCUSS_STT=scribe but ELEVENLABS_API_KEY is not set; using local Whisper.")
    return "whisper"


# ── Pure helpers (unit-tested) ───────────────────────────────────────────────


def chunk_text(text: str, limit: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split narration at sentence boundaries into chunks of at most ``limit`` chars.

    Short chunks let speech start quickly and give natural points to check for
    an interruption between synthesis calls.
    """
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        while len(sentence) > limit:  # very long sentence: split on whitespace
            cut = sentence.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            if current:
                chunks.append(current)
                current = ""
            chunks.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if not sentence:
            continue
        if current and len(current) + 1 + len(sentence) > limit:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


def resample(samples, src_rate: int, dst_rate: int):
    """Linear-interpolation resample of a mono float32 numpy array."""
    import numpy as np

    if src_rate == dst_rate or len(samples) == 0:
        return samples.astype(np.float32, copy=False)
    duration = len(samples) / src_rate
    n_out = max(1, int(round(duration * dst_rate)))
    x_old = np.linspace(0.0, duration, num=len(samples), endpoint=False)
    x_new = np.linspace(0.0, duration, num=n_out, endpoint=False)
    return np.interp(x_new, x_old, samples).astype(np.float32)


def pcm16_to_float(data: bytes):
    import numpy as np

    return np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0


def float_to_wav_bytes(samples, rate: int) -> bytes:
    """Encode a mono float32 array in [-1, 1] as 16-bit PCM WAV."""
    import numpy as np

    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def read_wav(path: str):
    """Read a PCM WAV file into (mono float32 array, sample rate)."""
    import numpy as np

    with wave.open(path, "rb") as w:
        rate, channels, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif width == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"unsupported WAV sample width: {width}")
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data.astype(np.float32), rate


def multipart_body(fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]) -> tuple[bytes, str]:
    """Build a multipart/form-data body. ``files`` maps name → (filename, data, mime)."""
    boundary = f"----show-and-discuss-{uuid.uuid4().hex}"
    out = io.BytesIO()
    for name, value in fields.items():
        out.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    for name, (filename, data, mime) in files.items():
        out.write(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {mime}\r\n\r\n".encode()
        )
        out.write(data)
        out.write(b"\r\n")
    out.write(f"--{boundary}--\r\n".encode())
    return out.getvalue(), f"multipart/form-data; boundary={boundary}"


@dataclass
class SpeechDetector:
    """Energy-based voice-activity detector working on fixed-size frames.

    The noise floor adapts slowly while nobody is speaking. Speech "starts" after
    ``start_frames`` consecutive loud frames and "ends" after ``end_frames``
    consecutive quiet frames. ``boost`` raises the threshold while our own
    narration is playing, so speaker bleed into the mic is less likely to count
    as the user talking (headphones remove the problem entirely).
    """

    sensitivity: float = 1.0
    start_frames: int = 8  # 8 × 30 ms ≈ 240 ms of sustained speech
    end_frames: int = 40  # 40 × 30 ms ≈ 1.2 s of silence ends an utterance
    min_level: float = 0.012  # absolute RMS floor, so a silent room never triggers
    ratio: float = 3.0  # speech must be this many times louder than the noise floor
    boost: float = 1.0
    noise_floor: float = 0.004
    _loud: int = field(default=0, repr=False)
    _quiet: int = field(default=0, repr=False)
    speaking: bool = field(default=False, repr=False)

    def threshold(self) -> float:
        base = max(self.min_level, self.noise_floor * self.ratio)
        return base * self.boost / self.sensitivity

    def update(self, level: float) -> str | None:
        """Feed one frame's RMS level. Returns 'start', 'end' or None."""
        loud = level > self.threshold()
        if not self.speaking and not loud:
            self.noise_floor = 0.95 * self.noise_floor + 0.05 * level
        if loud:
            self._loud += 1
            self._quiet = 0
        else:
            self._quiet += 1
            self._loud = 0
        if not self.speaking and self._loud >= self.start_frames:
            self.speaking = True
            return "start"
        if self.speaking and self._quiet >= self.end_frames:
            self.speaking = False
            return "end"
        return None


def rms(frame) -> float:
    import numpy as np

    if len(frame) == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(frame, dtype=np.float64))))


# ── Text-to-speech backends ─────────────────────────────────────────────────


class TTSError(RuntimeError):
    pass


def http_post(url: str, body: bytes, headers: dict[str, str], timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise TTSError(f"HTTP {exc.code} from {url.split('?')[0]}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise TTSError(f"network error contacting {url.split('?')[0]}: {exc.reason}") from exc


def synth_elevenlabs(text: str, cfg: Config, rate: int = 22_050):
    """Synthesize with ElevenLabs as raw PCM so no audio decoder is needed."""
    url = f"{ELEVENLABS_API}/text-to-speech/{cfg.voice_id}?output_format=pcm_{rate}"
    payload: dict[str, object] = {"text": text, "model_id": cfg.tts_model}
    if cfg.language:
        payload["language_code"] = cfg.language
    data = http_post(
        url,
        json.dumps(payload).encode(),
        {"xi-api-key": cfg.api_key or "", "Content-Type": "application/json", "Accept": "audio/pcm"},
    )
    return pcm16_to_float(data), rate


def synth_system(text: str, engine: str, cfg: Config):
    """Render text to a temporary WAV with an offline engine, then load it."""
    fd, path = tempfile.mkstemp(suffix=".wav", prefix="show-discuss-")
    os.close(fd)
    try:
        if engine == "say":
            cmd = ["say", "-o", path, "--data-format=LEI16@22050"]
            if cfg.system_voice:
                cmd += ["-v", cfg.system_voice]
            subprocess.run([*cmd, text], check=True, capture_output=True, timeout=120)
        elif engine == "piper":
            subprocess.run(
                ["piper", "--model", cfg.piper_model or "", "--output_file", path],
                input=text.encode(),
                check=True,
                capture_output=True,
                timeout=120,
            )
        elif engine in ("espeak-ng", "espeak"):
            cmd = [engine, "-w", path]
            if cfg.system_voice:
                cmd += ["-v", cfg.system_voice]
            subprocess.run([*cmd, text], check=True, capture_output=True, timeout=120)
        elif engine == "sapi":
            shell = shutil.which("powershell") or shutil.which("pwsh") or "powershell"
            script = (
                "Add-Type -AssemblyName System.Speech;"
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                + (f"$s.SelectVoice('{cfg.system_voice}');" if cfg.system_voice else "")
                + f"$s.SetOutputToWaveFile('{path}');"
                "$s.Speak([Console]::In.ReadToEnd()); $s.Dispose()"
            )
            subprocess.run(
                [shell, "-NoProfile", "-Command", script],
                input=text.encode(),
                check=True,
                capture_output=True,
                timeout=120,
            )
        else:
            raise TTSError(f"unknown system TTS engine: {engine}")
        return read_wav(path)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raise TTSError(f"{engine} failed: {exc}") from exc
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


class Synthesizer:
    """Wraps the chosen backend; falls back to the system voice if ElevenLabs fails."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.backend = resolve_tts(cfg)
        self.fallback = system_tts_engine(piper_model=cfg.piper_model)
        self.warnings: list[str] = []

    def __call__(self, text: str):
        if self.backend == "elevenlabs":
            try:
                return synth_elevenlabs(text, self.cfg)
            except TTSError as exc:
                if not self.fallback:
                    raise
                msg = f"ElevenLabs failed ({exc}); switched to system voice '{self.fallback}'."
                log(msg)
                self.warnings.append(msg)
                self.backend = self.fallback
        if self.backend == "off":
            raise TTSError("no text-to-speech backend is available")
        return synth_system(text, self.backend, self.cfg)


# ── Speech-to-text backends ─────────────────────────────────────────────────

_WHISPER = None


def transcribe(samples, cfg: Config) -> str:
    """Transcribe 16 kHz mono float32 audio with the configured backend."""
    backend = resolve_stt(cfg)
    if backend == "off" or len(samples) == 0:
        return ""
    if backend == "scribe":
        body, ctype = multipart_body(
            {"model_id": cfg.stt_model, **({"language_code": cfg.language} if cfg.language else {})},
            {"file": ("question.wav", float_to_wav_bytes(samples, STT_RATE), "audio/wav")},
        )
        try:
            data = http_post(
                f"{ELEVENLABS_API}/speech-to-text", body, {"xi-api-key": cfg.api_key or "", "Content-Type": ctype}
            )
            return str(json.loads(data).get("text", "")).strip()
        except (TTSError, ValueError) as exc:
            log(f"Scribe failed ({exc}); falling back to local Whisper.")
    global _WHISPER
    from faster_whisper import WhisperModel

    if _WHISPER is None:
        log(f"loading Whisper model '{cfg.whisper_model}' (first run downloads it)…")
        _WHISPER = WhisperModel(cfg.whisper_model, device="auto", compute_type="int8")
    segments, _info = _WHISPER.transcribe(samples, language=cfg.language, beam_size=1, vad_filter=True)
    return " ".join(seg.text.strip() for seg in segments).strip()


# ── Audio I/O ────────────────────────────────────────────────────────────────


class Mic:
    """Background microphone capture delivering fixed-size mono float32 frames."""

    def __init__(self) -> None:
        import sounddevice as sd

        info = sd.query_devices(kind="input")
        self.rate = int(info["default_samplerate"]) or 48_000
        self.frame = int(self.rate * FRAME_MS / 1000)
        self.frames: queue.Queue = queue.Queue()
        self.stream = sd.InputStream(
            samplerate=self.rate, channels=1, dtype="float32", blocksize=self.frame, callback=self._callback
        )

    def _callback(self, indata, _frames, _time, _status) -> None:
        self.frames.put(indata[:, 0].copy())

    def __enter__(self) -> Mic:
        self.stream.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.stream.stop()
        self.stream.close()

    def read(self, timeout: float = 0.5):
        try:
            return self.frames.get(timeout=timeout)
        except queue.Empty:
            return None


class Player:
    """Non-blocking playback of a float32 array that can be stopped mid-way."""

    def __init__(self, samples, rate: int) -> None:
        import sounddevice as sd

        self.samples, self.rate, self.pos = samples, rate, 0
        self.done = threading.Event()
        self.stream = sd.OutputStream(
            samplerate=rate, channels=1, dtype="float32", callback=self._callback, finished_callback=self.done.set
        )

    def _callback(self, outdata, frames, _time, _status) -> None:
        import sounddevice as sd

        chunk = self.samples[self.pos : self.pos + frames]
        outdata[: len(chunk), 0] = chunk
        outdata[len(chunk) :, 0] = 0
        self.pos += len(chunk)
        if len(chunk) < frames:
            raise sd.CallbackStop

    def start(self) -> Player:
        self.stream.start()
        return self

    def stop(self) -> None:
        self.stream.abort()
        self.done.set()

    def close(self) -> None:
        self.stream.close()

    @property
    def seconds(self) -> float:
        return self.pos / self.rate


def record_utterance(mic: Mic, detector: SpeechDetector, preroll: Iterable, max_seconds: float):
    """Record until the detector reports the end of speech; returns 16 kHz audio."""
    import numpy as np

    frames = list(preroll)
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        frame = mic.read()
        if frame is None:
            continue
        frames.append(frame)
        if detector.update(rms(frame)) == "end":
            break
    audio = np.concatenate(frames) if frames else np.zeros(0, dtype=np.float32)
    return resample(audio, mic.rate, STT_RATE)


def calibrate_floor(mic: Mic, seconds: float = 0.4) -> float:
    levels = []
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        frame = mic.read(timeout=seconds)
        if frame is not None:
            levels.append(rms(frame))
    levels.sort()
    return levels[len(levels) // 2] if levels else 0.004


# ── Commands ─────────────────────────────────────────────────────────────────


def cmd_doctor(cfg: Config) -> int:
    report: dict[str, object] = {
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.system(),
        "tts": resolve_tts(cfg),
        "stt": resolve_stt(cfg),
        "elevenlabs_key": bool(cfg.api_key),
        "barge_in": cfg.barge_in,
        "problems": [],
    }
    problems: list[str] = report["problems"]  # type: ignore[assignment]
    try:
        import numpy  # noqa: F401
    except ImportError:
        problems.append("numpy is not installed")
    try:
        import sounddevice as sd

        try:
            report["input_device"] = sd.query_devices(kind="input")["name"]
        except Exception as exc:  # noqa: BLE001 — PortAudio raises various types
            problems.append(f"no microphone available: {exc}")
        try:
            report["output_device"] = sd.query_devices(kind="output")["name"]
        except Exception as exc:  # noqa: BLE001
            problems.append(f"no audio output available: {exc}")
    except (ImportError, OSError) as exc:
        problems.append(f"sounddevice/PortAudio unavailable: {exc}")
    if report["tts"] == "off" and cfg.tts != "off":
        problems.append("no text-to-speech engine found (set ELEVENLABS_API_KEY or install espeak-ng/piper)")
    if report["stt"] == "whisper":
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            problems.append("faster-whisper is not installed (needed for local transcription)")
    report["ok"] = not problems
    report["mode"] = "voice" if report["ok"] else "text"
    emit(report)
    return 0 if report["ok"] else 2


def cmd_say(cfg: Config, text: str, linger: float, max_question: float) -> int:
    chunks = chunk_text(text)
    if not chunks:
        emit({"status": "finished", "spoken_seconds": 0.0, "transcript": ""})
        return 0
    synth = Synthesizer(cfg)
    if synth.backend == "off":
        emit({"status": "error", "error": "no text-to-speech backend available", "text": text})
        return 2

    result: dict[str, object] = {"status": "finished", "backend": synth.backend, "transcript": ""}
    spoken = 0.0
    pool = ThreadPoolExecutor(max_workers=1)
    pending = pool.submit(synth, chunks[0])
    mic_ctx: Mic | None = None
    try:
        if cfg.barge_in:
            mic_ctx = Mic().__enter__()
            detector = SpeechDetector(
                sensitivity=cfg.sensitivity, boost=2.0, noise_floor=calibrate_floor(mic_ctx, 0.25)
            )
            preroll: deque = deque(maxlen=int(600 / FRAME_MS))
        for i in range(len(chunks)):
            samples, rate = pending.result()
            if i + 1 < len(chunks):
                pending = pool.submit(synth, chunks[i + 1])  # synthesize ahead while this plays
            player = Player(samples, rate).start()
            interrupted = False
            while not player.done.is_set():
                if not mic_ctx:
                    player.done.wait(0.1)
                    continue
                frame = mic_ctx.read(timeout=0.1)
                if frame is None:
                    continue
                preroll.append(frame)
                if detector.update(rms(frame)) == "start":
                    interrupted = True
                    break
            if interrupted:
                player.stop()
            spoken += player.seconds
            player.close()
            if interrupted:
                detector.boost = 1.0  # narration stopped; listen at normal sensitivity
                audio = record_utterance(mic_ctx, detector, preroll, max_question)
                result.update(
                    status="interrupted",
                    interrupted_at_chunk=i,
                    remaining_text=" ".join(chunks[i:]),
                    transcript=transcribe(audio, cfg),
                )
                break
        else:
            if mic_ctx and linger > 0:  # brief window to catch a question right after the slide
                detector.boost = 1.0
                end = time.monotonic() + linger
                while time.monotonic() < end:
                    frame = mic_ctx.read(timeout=0.1)
                    if frame is None:
                        continue
                    preroll.append(frame)
                    if detector.update(rms(frame)) == "start":
                        audio = record_utterance(mic_ctx, detector, preroll, max_question)
                        result.update(status="question", transcript=transcribe(audio, cfg))
                        break
    except Exception as exc:  # noqa: BLE001 — always report back as JSON
        result.update(status="error", error=f"{type(exc).__name__}: {exc}")
    finally:
        if mic_ctx:
            mic_ctx.__exit__(None, None, None)
        pool.shutdown(wait=False, cancel_futures=True)
    result["spoken_seconds"] = round(spoken, 2)
    if synth.warnings:
        result["warnings"] = synth.warnings
    emit(result)
    return 0 if result["status"] != "error" else 1


def cmd_listen(cfg: Config, timeout: float, max_question: float) -> int:
    result: dict[str, object] = {"status": "silence", "transcript": ""}
    try:
        with Mic() as mic:
            detector = SpeechDetector(sensitivity=cfg.sensitivity, noise_floor=calibrate_floor(mic, 0.25))
            preroll: deque = deque(maxlen=int(600 / FRAME_MS))
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                frame = mic.read(timeout=0.1)
                if frame is None:
                    continue
                preroll.append(frame)
                if detector.update(rms(frame)) == "start":
                    audio = record_utterance(mic, detector, preroll, max_question)
                    result.update(status="heard", transcript=transcribe(audio, cfg))
                    break
    except Exception as exc:  # noqa: BLE001
        result.update(status="error", error=f"{type(exc).__name__}: {exc}")
    emit(result)
    return 0 if result["status"] != "error" else 1


def cmd_calibrate(cfg: Config, seconds: float) -> int:
    try:
        with Mic() as mic:
            floor = calibrate_floor(mic, seconds)
    except Exception as exc:  # noqa: BLE001
        emit({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
        return 1
    detector = SpeechDetector(sensitivity=cfg.sensitivity, noise_floor=floor)
    emit(
        {
            "status": "ok",
            "noise_floor": round(floor, 5),
            "threshold": round(detector.threshold(), 5),
            "hint": "If quiet speech is missed, raise SHOW_DISCUSS_SENSITIVITY (e.g. 1.5); "
            "if narration triggers itself, lower it or use headphones.",
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="voice.py", description=__doc__.split("\n\n")[0])
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--no-barge-in", action="store_true", help="do not listen while speaking")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="report which voice features work on this machine")
    say = sub.add_parser("say", help="speak text; stop and transcribe if the user interrupts")
    say.add_argument("text", nargs="?", help="text to speak (or use --file / stdin)")
    say.add_argument("--file", help="read the text from a file")
    say.add_argument("--linger", type=float, default=1.5, help="seconds to keep listening after speaking")
    say.add_argument("--max-question", type=float, default=60.0, help="maximum seconds to record a question")
    listen = sub.add_parser("listen", help="wait for the user to speak and transcribe it")
    listen.add_argument("--timeout", type=float, default=10.0, help="seconds to wait for speech to start")
    listen.add_argument("--max-question", type=float, default=90.0, help="maximum seconds to record")
    cal = sub.add_parser("calibrate", help="measure background noise")
    cal.add_argument("--seconds", type=float, default=2.0)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config.from_env()
    if args.no_barge_in:
        cfg.barge_in = False
    if args.command == "doctor":
        return cmd_doctor(cfg)
    if args.command == "say":
        if args.file:
            with open(args.file, encoding="utf-8") as fh:
                text = fh.read()
        elif args.text is not None:
            text = args.text
        else:
            text = sys.stdin.read()
        return cmd_say(cfg, text, args.linger, args.max_question)
    if args.command == "listen":
        return cmd_listen(cfg, args.timeout, args.max_question)
    if args.command == "calibrate":
        return cmd_calibrate(cfg, args.seconds)
    return 2


if __name__ == "__main__":
    sys.exit(main())
