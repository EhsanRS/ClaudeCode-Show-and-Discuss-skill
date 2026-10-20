# Voice: speaking, listening and interruptions

`scripts/voice.py` speaks narration and listens *while* it speaks. When the user
starts talking, playback stops, their words are recorded until they pause, and
the transcript comes back to Claude as JSON. That's how barge-in works without
Claude Code having built-in voice output.

Run it with `uv run "${CLAUDE_SKILL_DIR}/scripts/voice.py" …`. `uv` installs the
dependencies (numpy, sounddevice, faster-whisper) automatically on first run.
Without `uv`, run `pip install -r scripts/requirements.txt` and use `python3`.

## Commands and results

| Command | Result JSON |
|---|---|
| `voice.py doctor` | `{"ok", "mode": "voice"\|"text", "tts", "stt", "problems": [...]}`. Exit 0 if voice works, 2 if not. |
| `voice.py say "text"` (or `--file f`, or stdin) | `{"status": "finished"\|"interrupted"\|"question"\|"error", "transcript", "remaining_text"?, "spoken_seconds", "backend"}` |
| `voice.py listen --timeout 6` | `{"status": "heard"\|"silence"\|"error", "transcript"}` |
| `voice.py calibrate` | `{"noise_floor", "threshold", "hint"}` |

Useful flags: `say --linger 1.5` (seconds to keep listening after speaking,
which catches "wait, …" at a slide boundary), `--max-question 60`, and global
`--no-barge-in`.

Bash calls that speak should use a generous timeout (`timeout: 300000`). A
slide's narration plus a question can easily exceed the 2-minute default.

## Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `ELEVENLABS_API_KEY` | (unset) | Enables ElevenLabs voices (and Scribe if chosen). |
| `SHOW_DISCUSS_TTS` | `auto` | `auto` = ElevenLabs if a key is set, else system voice. Also `elevenlabs`, `system`, `off`. |
| `SHOW_DISCUSS_STT` | `whisper` | `whisper` (local, private) or `scribe` (ElevenLabs, needs key) or `off`. |
| `ELEVENLABS_VOICE_ID` | `JBFqnCBsd6RMkjVDRZzb` | Any voice ID from your ElevenLabs voice library. |
| `ELEVENLABS_MODEL_ID` | `eleven_flash_v2_5` | Fast, lowest-cost model. Use `eleven_multilingual_v2` for higher quality. |
| `SHOW_DISCUSS_WHISPER_MODEL` | `base.en` | `tiny.en` is faster; `small.en` is more accurate; drop `.en` for other languages. |
| `SHOW_DISCUSS_LANGUAGE` | (auto) | Language code passed to TTS/STT, e.g. `en`, `de`. |
| `SHOW_DISCUSS_SYSTEM_VOICE` | (default) | e.g. `Samantha` (macOS `say -v`), `en-us` (espeak). |
| `PIPER_MODEL` | (unset) | Path to a Piper `.onnx` voice; enables Piper as the system voice. |
| `SHOW_DISCUSS_SENSITIVITY` | `1.0` | Higher = picks up quieter speech; lower = fewer false interruptions. |
| `SHOW_DISCUSS_BARGE_IN` | `on` | `off` disables listening during narration. |

Set them in your shell profile, or for Claude Code only in
`~/.claude/settings.json` under `"env"`. Never commit an API key.

## Which voice gets used

1. **ElevenLabs**, when `ELEVENLABS_API_KEY` is set. It's natural-sounding but uses
   credits; the free tier is roughly 10 minutes of speech a month, and
   non-commercial. Check the current numbers on ElevenLabs' pricing page. If a
   request fails (quota, network), the helper switches to the system voice for
   the rest of the call and reports a `warnings` entry.
2. **System voice**: macOS `say`; Piper if `PIPER_MODEL` is set; `espeak-ng`/`espeak`
   on Linux; Windows SAPI. Free, offline, and more robotic (Piper is the best of them).

## Troubleshooting

| Symptom | Fix |
|---|---|
| Narration interrupts itself | The mic hears the speakers. Use headphones (best), or lower `SHOW_DISCUSS_SENSITIVITY` to `0.6`. |
| User's question is missed | Raise `SHOW_DISCUSS_SENSITIVITY` to `1.5`, or run `voice.py calibrate` in the actual room. |
| `PortAudio library not found` (Linux) | `sudo apt install libportaudio2` (Debian/Ubuntu). |
| `no text-to-speech engine found` | Set `ELEVENLABS_API_KEY`, or install `espeak-ng` / Piper. |
| First question takes long | The Whisper model downloads once (~150 MB for `base.en`). Later runs are fast. |
| macOS asks for microphone access | Grant it to your terminal app (System Settings → Privacy & Security → Microphone). |
| Cloud session (claude.ai/code) | No audio device exists. The skill uses Show/Share mode automatically. |

## Privacy

- Default setup (system voice + local Whisper): **nothing leaves the machine**.
- With an ElevenLabs key: narration and answer *text* is sent to ElevenLabs.
- With `SHOW_DISCUSS_STT=scribe`: the user's recorded *audio* is sent to
  ElevenLabs.
- Audio is held in memory only; nothing is written to disk except a
  temporary WAV for system voices, which is deleted immediately.
