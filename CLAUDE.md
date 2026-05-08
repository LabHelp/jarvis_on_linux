# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Jarvis on Linux is a PTT (Push-to-Talk) desktop app built with Python/tkinter. Hold the button, speak a prompt, and it transcribes via **Whisper API** then passes the text to **ShellGPT (sgpt)** to generate shell commands. Generated commands are shown in the GUI and can be executed in a new `xfce4-terminal` window.

The app targets **Debian 13 Trixie (XFCE)**. The single-file application is `main.py` (~220 lines).

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

`main.py` — Single-class tkinter application:

```
SpeechRecognitionApp
├── __init__          — Builds GUI (PTT button, transcription label, command output frame)
├── start_recognition — Button press: opens sounddevice InputStream (16kHz mono int16)
├── audio_callback    — Appends audio chunks to self.audio_data
├── stop_recognition  — Button release: stops stream, spawns transcribe_audio thread
├── transcribe_audio  — Concatenates audio → temp WAV → base64 → POST to WHISPER_URL
│                       Then calls `sgpt sh "<text>"` via subprocess
├── show_commands     — Renders sgpt output as labeled Entry widgets with execute buttons
└── execute_command   — Runs command in `xfce4-terminal --hold`
```

**Data flow:** Microphone → sounddevice → numpy audio buffer → temp WAV file → base64 JSON POST to Whisper API → transcribed text → `sgpt sh "<text>"` subprocess → command strings displayed in GUI → click to run in xfce4-terminal.

**Two-provider API design:** Transcription and command generation use independent environment variables so each can use a different provider:
- `WHISPER_API_KEY` / `WHISPER_API_BASE` — for audio transcription (model: `openai/whisper-1`)
- `OPENAI_API_KEY` / `OPENAI_API_BASE` — consumed by ShellGPT for command generation

**ShellGPT config:** `config.yaml` is copied by `setup.sh` to `~/.config/sgpt/config.yaml`. Default model: `openai/gpt-4o-mini`.

## Dependencies

- **Python**: `sounddevice`, `numpy`, `requests` — audio capture, array math, HTTP to Whisper API
- **External binary**: `sgpt` (ShellGPT, Go binary) — installed by `setup.sh` via `go install`
- **Desktop**: `xfce4-terminal` — for executing generated commands
- **Audio**: PulseAudio + PortAudio (system packages, installed by `setup.sh`)

## setup.sh

One-shot setup script for Debian 13 Trixie. Installs system packages (Python 3.13, portaudio, ffmpeg, xfce4-terminal, pulseaudio), Go 1.23.4, ShellGPT via `go install`, creates a Python venv, installs pip deps, and copies `config.yaml` to `~/.config/sgpt/`. Requires sudo.
