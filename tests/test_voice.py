"""Unit tests for the voice helper. No audio hardware or network is needed."""

import json
import threading

import numpy as np
import pytest
import voice

# ── Configuration & backend selection ───────────────────────────────────────


def test_config_defaults():
    cfg = voice.Config.from_env({})
    assert cfg.tts == "auto"
    assert cfg.stt == "whisper"
    assert cfg.api_key is None
    assert cfg.barge_in is True
    assert cfg.sensitivity == 1.0
    assert cfg.voice_id == voice.DEFAULT_VOICE_ID


def test_config_overrides():
    cfg = voice.Config.from_env(
        {
            "SHOW_DISCUSS_TTS": "System",
            "SHOW_DISCUSS_STT": "scribe",
            "ELEVENLABS_API_KEY": "k",
            "SHOW_DISCUSS_BARGE_IN": "off",
            "SHOW_DISCUSS_SENSITIVITY": "1.5",
            "ELEVENLABS_VOICE_ID": "abc",
        }
    )
    assert (cfg.tts, cfg.stt, cfg.api_key, cfg.barge_in, cfg.sensitivity, cfg.voice_id) == (
        "system",
        "scribe",
        "k",
        False,
        1.5,
        "abc",
    )


def test_config_ignores_bad_sensitivity():
    assert voice.Config.from_env({"SHOW_DISCUSS_SENSITIVITY": "loud"}).sensitivity == 1.0


def which_of(*available):
    return lambda name: f"/usr/bin/{name}" if name in available else None


def test_system_engine_prefers_say_on_macos():
    assert voice.system_tts_engine(which_of("say", "espeak-ng"), system="Darwin") == "say"


def test_system_engine_piper_needs_model():
    assert voice.system_tts_engine(which_of("piper", "espeak"), system="Linux") == "espeak"
    assert voice.system_tts_engine(which_of("piper", "espeak"), system="Linux", piper_model="m.onnx") == "piper"


def test_system_engine_windows_and_none():
    assert voice.system_tts_engine(which_of("powershell"), system="Windows") == "sapi"
    assert voice.system_tts_engine(which_of(), system="Linux") is None


@pytest.mark.parametrize(
    ("env", "available", "expected"),
    [
        ({"ELEVENLABS_API_KEY": "k"}, (), "elevenlabs"),
        ({}, ("espeak-ng",), "espeak-ng"),
        ({"SHOW_DISCUSS_TTS": "elevenlabs"}, ("espeak-ng",), "espeak-ng"),  # no key → fall back
        ({"SHOW_DISCUSS_TTS": "system", "ELEVENLABS_API_KEY": "k"}, ("espeak-ng",), "espeak-ng"),
        ({"SHOW_DISCUSS_TTS": "off", "ELEVENLABS_API_KEY": "k"}, ("espeak-ng",), "off"),
        ({}, (), "off"),
    ],
)
def test_resolve_tts(env, available, expected):
    assert voice.resolve_tts(voice.Config.from_env(env), which_of(*available)) == expected


def test_resolve_stt():
    assert voice.resolve_stt(voice.Config.from_env({})) == "whisper"
    assert voice.resolve_stt(voice.Config.from_env({"SHOW_DISCUSS_STT": "scribe"})) == "whisper"
    assert voice.resolve_stt(voice.Config.from_env({"SHOW_DISCUSS_STT": "scribe", "ELEVENLABS_API_KEY": "k"})) == (
        "scribe"
    )
    assert voice.resolve_stt(voice.Config.from_env({"SHOW_DISCUSS_STT": "off"})) == "off"


# ── Pure helpers ─────────────────────────────────────────────────────────────


def test_chunk_text_keeps_sentences_together():
    text = "One. Two is here!  Three?\nFour."
    assert voice.chunk_text(text, limit=100) == ["One. Two is here! Three? Four."]
    assert voice.chunk_text(text, limit=12) == ["One.", "Two is here!", "Three? Four."]
    assert voice.chunk_text(text, limit=8) == ["One.", "Two is", "here!", "Three?", "Four."]


def test_chunk_text_splits_long_sentences_and_respects_limit():
    long_sentence = " ".join(["word"] * 200) + "."
    chunks = voice.chunk_text(long_sentence, limit=50)
    assert all(len(c) <= 50 for c in chunks)
    assert " ".join(chunks).split() == long_sentence.split()


def test_chunk_text_empty():
    assert voice.chunk_text("   \n ") == []


def test_wav_roundtrip(tmp_path):
    t = np.linspace(0, 1, 16_000, endpoint=False)
    tone = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    path = tmp_path / "tone.wav"
    path.write_bytes(voice.float_to_wav_bytes(tone, 16_000))
    data, rate = voice.read_wav(str(path))
    assert rate == 16_000
    assert np.max(np.abs(data - tone)) < 1e-3


def test_resample_length_and_identity():
    x = np.random.default_rng(0).standard_normal(48_000).astype(np.float32)
    assert len(voice.resample(x, 48_000, 16_000)) == 16_000
    assert voice.resample(x, 16_000, 16_000) is not None


def test_pcm16_to_float():
    raw = np.array([0, 16384, -32768], dtype="<i2").tobytes()
    assert np.allclose(voice.pcm16_to_float(raw), [0.0, 0.5, -1.0])


def test_multipart_body():
    body, ctype = voice.multipart_body({"model_id": "scribe_v1"}, {"file": ("q.wav", b"RIFF", "audio/wav")})
    boundary = ctype.split("boundary=")[1]
    assert ctype.startswith("multipart/form-data")
    assert body.count(f"--{boundary}".encode()) == 3
    assert b'name="model_id"\r\n\r\nscribe_v1' in body
    assert b'filename="q.wav"' in body and b"RIFF" in body


# ── Voice activity detection ────────────────────────────────────────────────


def feed(detector, levels):
    return [e for e in (detector.update(level) for level in levels) if e]


def test_detector_silence_never_triggers():
    assert feed(voice.SpeechDetector(), [0.003] * 500) == []


def test_detector_ignores_short_blip():
    assert feed(voice.SpeechDetector(), [0.003] * 20 + [0.2] * 3 + [0.003] * 50) == []


def test_detector_start_and_end():
    d = voice.SpeechDetector()
    events = feed(d, [0.003] * 20 + [0.2] * 30 + [0.003] * 60)
    assert events == ["start", "end"]


def test_detector_boost_raises_threshold():
    d = voice.SpeechDetector()
    plain = d.threshold()
    d.boost = 2.0
    assert d.threshold() == pytest.approx(plain * 2)
    d.sensitivity = 2.0
    assert d.threshold() == pytest.approx(plain)


def test_detector_calibrated_noise_does_not_trigger():
    # `say`/`listen` calibrate the floor on startup, so a steady noisy room is ignored.
    d = voice.SpeechDetector(noise_floor=0.02)
    assert feed(d, [0.02] * 300) == []
    assert feed(d, [0.2] * 10) == ["start"]


def test_detector_noise_floor_drifts_while_quiet():
    d = voice.SpeechDetector()
    feed(d, [0.008] * 300)  # below threshold: treated as background
    assert d.noise_floor == pytest.approx(0.008, rel=0.01)


# ── Orchestration of `say` with fake audio devices ──────────────────────────


class FakeMic:
    rate = 16_000
    frame = 480

    def __init__(self, levels):
        self.levels = list(levels)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def read(self, timeout=0.5):
        level = self.levels.pop(0) if self.levels else 0.002
        return np.full(self.frame, level, dtype=np.float32)


class FakePlayer:
    def __init__(self, samples, rate):
        self.samples, self.rate = samples, rate
        self.done = threading.Event()
        self.stopped = False

    def start(self):
        threading.Timer(0.3, self.done.set).start()
        return self

    def stop(self):
        self.stopped = True
        self.done.set()

    def close(self):
        pass

    @property
    def seconds(self):
        return 0.3


@pytest.fixture
def fake_audio(monkeypatch):
    calls = {"synth": [], "transcribe": 0}

    class FakeSynth:
        def __init__(self, cfg):
            self.backend, self.fallback, self.warnings = "espeak-ng", None, []

        def __call__(self, text):
            calls["synth"].append(text)
            return np.zeros(100, dtype=np.float32), 16_000

    def fake_transcribe(audio, cfg):
        calls["transcribe"] += 1
        return "why not use cookies"

    monkeypatch.setattr(voice, "Synthesizer", FakeSynth)
    monkeypatch.setattr(voice, "Player", FakePlayer)
    monkeypatch.setattr(voice, "transcribe", fake_transcribe)
    monkeypatch.setattr(voice, "calibrate_floor", lambda mic, seconds=0.4: 0.004)
    return calls


def run_say(monkeypatch, capsys, levels, text="First sentence. Second sentence.", linger=0.2):
    monkeypatch.setattr(voice, "Mic", lambda: FakeMic(levels))
    monkeypatch.setattr(voice, "MAX_CHUNK_CHARS", 20)
    cfg = voice.Config.from_env({})
    code = voice.cmd_say(cfg, text, linger=linger, max_question=5)
    return code, json.loads(capsys.readouterr().out)


def test_say_without_interruption_finishes(fake_audio, monkeypatch, capsys):
    code, out = run_say(monkeypatch, capsys, levels=[])
    assert code == 0
    assert out["status"] == "finished"
    assert out["transcript"] == ""
    assert fake_audio["transcribe"] == 0


def test_say_barge_in_stops_and_transcribes(fake_audio, monkeypatch, capsys):
    code, out = run_say(monkeypatch, capsys, levels=[0.002] * 5 + [0.3] * 30 + [0.002] * 60)
    assert code == 0
    assert out["status"] == "interrupted"
    assert out["transcript"] == "why not use cookies"
    assert out["interrupted_at_chunk"] == 0
    assert out["remaining_text"].startswith("First sentence.")


def test_say_without_barge_in_ignores_mic(fake_audio, monkeypatch, capsys):
    monkeypatch.setattr(voice, "Mic", lambda: pytest.fail("mic must not open"))
    cfg = voice.Config.from_env({"SHOW_DISCUSS_BARGE_IN": "0"})
    assert voice.cmd_say(cfg, "Hello there.", linger=0.5, max_question=5) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "finished"


def test_say_reports_errors_as_json(fake_audio, monkeypatch, capsys):
    def broken_mic():
        raise OSError("no input device")

    monkeypatch.setattr(voice, "Mic", broken_mic)
    code = voice.cmd_say(voice.Config.from_env({}), "Hello.", linger=0, max_question=5)
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out["status"] == "error" and "no input device" in out["error"]


def test_doctor_emits_json(capsys):
    code = voice.cmd_doctor(voice.Config.from_env({"SHOW_DISCUSS_TTS": "off"}))
    out = json.loads(capsys.readouterr().out)
    assert code in (0, 2)
    assert out["mode"] in ("voice", "text")
    assert isinstance(out["problems"], list)
