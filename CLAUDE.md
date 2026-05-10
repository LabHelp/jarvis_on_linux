# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Jarvis on Linux is a PTT (Push-to-Talk) desktop app built with Python/tkinter. Hold the button, speak a prompt, and it transcribes via **Whisper API** then passes the text to **ShellGPT (sgpt)** to generate shell commands. Generated commands are shown in the GUI and can be executed in a new `xfce4-terminal` window.

The app targets **Debian 13 Trixie (XFCE)**. The single-file application is `main.py` (~480 lines).

## Development commands

There is no test suite, linter, or type checker configured. The project has a single Python file with no formal dev tooling.

```bash
# Activate the virtual environment and run the app
source venv/bin/activate
python main.py

# Install/update Python dependencies
pip install -r requirements.txt
```

## Architecture

`main.py` — Single-class tkinter application (~480 lines):

```
SpeechRecognitionApp
├── __init__            — Builds GUI: PTT+Cancel buttons, LED volume meter canvas,
│                         transcription label, scrollable command output area
├── start_recognition   — Button press: opens sounddevice InputStream (16kHz mono int16),
│                         starts meter polling via root.after()
├── audio_callback      — Appends audio chunks, computes and stores current_rms
├── stop_recognition    — Button release: stops stream, stops meter, checks silence
│                         (RMS < SILENCE_THRESHOLD → skip API call), spawns transcribe_audio thread
├── _update_meter       — Redraws LED bar on main thread every 50ms; color = green/yellow/red,
│                         shows dB value centered on bar
├── cancel_transcription — Sets threading.Event; checked at multiple points in transcribe_audio
├── transcribe_audio    — Concatenates audio → temp WAV → base64 → POST to WHISPER_URL,
│                         then calls `sgpt sh "<text>"` via subprocess.
│                         All GUI updates go through root.after(0) for thread safety
├── show_commands       — Parses sgpt output; each command gets Execute/Edit buttons,
│                         dangerous commands shown in red with risk labels
├── edit_command        — Opens Toplevel dialog to edit command text before running
├── execute_command     — If dangerous: askyesno confirmation, then runs in xfce4-terminal --hold
└── _classify_danger    — Static method: tests command against 27 compiled regex patterns
```

**Data flow:** Microphone → sounddevice → numpy audio buffer (with real-time RMS meter) → silence check → temp WAV file → base64 JSON POST to Whisper API → transcribed text → `sgpt sh "<text>"` subprocess → command strings displayed in GUI → danger classification → optional edit → (confirmation if dangerous) → xfce4-terminal.

**Two-provider API design:** Transcription and command generation use independent environment variables so each can use a different provider:
- `WHISPER_API_KEY` / `WHISPER_API_BASE` — for audio transcription (model: `openai/whisper-1`)
- `OPENAI_API_KEY` / `OPENAI_API_BASE` — consumed by ShellGPT for command generation

**ShellGPT config:** `config.yaml` is copied by `setup.sh` to `~/.config/sgpt/config.yaml`. Default model: `openai/gpt-4o-mini`.

**Thread safety:** `audio_callback` runs in sounddevice's thread (numpy-only, no GUI). `transcribe_audio` runs in a daemon thread — all GUI updates are scheduled via `_schedule(fn)` which calls `root.after(0, fn)`. The meter uses a timer on the main thread that reads `current_rms` (set by the audio thread, acceptable for visual use).

## Dependencies

- **Python**: `sounddevice`, `numpy`, `requests` — audio capture, array math, HTTP to Whisper API
- **External binary**: `sgpt` (ShellGPT, Go binary) — installed by `setup.sh` via `go install`
- **Desktop**: `xfce4-terminal` — for executing generated commands
- **Audio**: PulseAudio + PortAudio (system packages, installed by `setup.sh`)

## setup.sh

One-shot setup script for Debian 13 Trixie. Installs system packages (Python 3.13, portaudio, ffmpeg, xfce4-terminal, pulseaudio), Go 1.23.4, ShellGPT via `go install`, creates a Python venv, installs pip deps, and copies `config.yaml` to `~/.config/sgpt/`. Requires sudo.
