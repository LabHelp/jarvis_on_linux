#!/usr/bin/env python3

import base64
import json
import math
import os
import re
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import messagebox
import wave
import numpy as np
import requests
import sounddevice as sd

WHISPER_API_KEY = os.environ.get("WHISPER_API_KEY", "")
WHISPER_API_BASE = os.environ.get("WHISPER_API_BASE", "https://openrouter.ai/api/v1")
WHISPER_URL = f"{WHISPER_API_BASE}/audio/transcriptions"
SITE_URL = "https://jarvix.com"
SITE_TITLE = "Jarvis on Linux"

# --- Dangerous command patterns (compiled once) ---
# Each tuple: (regex, label shown to the user)
_DANGEROUS_PATTERNS = [
    (r"\brm\b", "rm — file deletion"),
    (r"\bsudo\b", "sudo — superuser privileges"),
    (r"\bchmod\b", "chmod — permission change"),
    (r"\bchown\b", "chown — ownership change"),
    (r"\bmkfs\b", "mkfs — filesystem format"),
    (r"\bdd\b", "dd — raw device write"),
    (r"\bshutdown\b", "shutdown — system shutdown"),
    (r"\breboot\b", "reboot — system reboot"),
    (r"\bpoweroff\b", "poweroff — power off"),
    (r"\bhalt\b", "halt — system halt"),
    (r"\binit\s+[06]\b", "init runlevel — system state change"),
    (r"\bmv\b.*/dev/null", "mv to /dev/null — data destruction"),
    (r">\s*/dev/sd", "redirect to block device — data destruction"),
    (r">\s*/dev/nvme", "redirect to NVMe device — data destruction"),
    (r"\bcurl\b.*\|\s*(?:ba)?sh\b", "curl piped to shell — unsafe download"),
    (r"\bwget\b.*\|\s*(?:ba)?sh\b", "wget piped to shell — unsafe download"),
    (r":\(\)\s*\{", "fork bomb pattern"),
    (r"\bgit\s+push\s+.*--force", "git push --force — overwrite remote"),
    (r"\bgpg\b.*--decrypt", "gpg decrypt — sensitive operation"),
    (r"\bpasswd\b", "passwd — password change"),
    (r"\biptables\b", "iptables — firewall modification"),
    (r"\bufw\b", "ufw — firewall modification"),
    (r"\bsystemctl\b", "systemctl — service management"),
    (r"\bfdisk\b", "fdisk — partition table modification"),
    (r"\bparted\b", "parted — partition modification"),
    (r"\bmount\b", "mount — filesystem mount"),
    (r"\bumount\b", "umount — filesystem unmount"),
]
DANGEROUS_REGEX = [(re.compile(pattern, re.IGNORECASE), label) for pattern, label in _DANGEROUS_PATTERNS]

# Raw int16 RMS threshold — below this the audio is considered silent.
# Int16 samples range ±32767; a quiet room typically lands at RMS 1–10,
# soft speech around 50–200.  20 rejects pure background noise reliably.
SILENCE_RMS_THRESHOLD = 20

# Meter update interval in ms
METER_INTERVAL_MS = 50


class SpeechRecognitionApp:
    def __init__(self, root):
        self.root = root

        # --- Row 0: PTT + Cancel buttons ---
        self.ptt_frame = tk.Frame(root, bg="black")
        self.ptt_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")

        self.button = tk.Button(
            self.ptt_frame, text="Push to Talk", bg="blue",
            fg="white", highlightbackground="black", font=("sans", 12),
        )
        self.button.bind("<Button-1>", self.start_recognition)
        self.button.bind("<ButtonRelease-1>", self.stop_recognition)
        self.button.pack(side=tk.LEFT, fill="both", expand=True)

        self.cancel_button = tk.Button(
            self.ptt_frame, text="Cancel", bg="red",
            fg="white", highlightbackground="black", font=("sans", 10),
            command=self.cancel_transcription,
        )

        # --- Row 1: Volume meter bar ---
        self.meter_canvas = tk.Canvas(root, height=50, bg="black", highlightthickness=0, bd=0)
        self.meter_canvas.grid(row=1, column=0, columnspan=2, sticky="nsew")

        # --- Row 2: STT output ---
        self.label = tk.Label(root, text="", bg="black", fg="white", font=("sans", 11))
        self.label.grid(row=2, column=0, columnspan=2, sticky="nsew")

        # --- Row 3: Command output area ---
        self.output_canvas = tk.Canvas(root, bg="black", highlightthickness=0)
        self.output_scrollbar = tk.Scrollbar(root, orient="vertical", command=self.output_canvas.yview)
        self.output_text_frame = tk.Frame(self.output_canvas, bg="black")
        self.output_text_frame.bind(
            "<Configure>",
            lambda e: self.output_canvas.configure(scrollregion=self.output_canvas.bbox("all")),
        )
        self.output_canvas.create_window((0, 0), window=self.output_text_frame, anchor="nw")
        self.output_canvas.configure(yscrollcommand=self.output_scrollbar.set)

        self.output_canvas.grid(row=3, column=0, sticky="nsew")
        self.output_scrollbar.grid(row=3, column=1, sticky="ns")

        # --- Grid weights ---
        root.grid_rowconfigure(0, weight=0)
        root.grid_rowconfigure(1, weight=0)
        root.grid_rowconfigure(2, weight=0)
        root.grid_rowconfigure(3, weight=1)
        root.grid_columnconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=0)

        # --- Audio state ---
        self.recording = False
        self.audio_data = []
        self.stream = None
        self.current_rms = 0.0          # set from audio callback, read by meter timer
        self._meter_job = None          # after() job id for meter updates

        # --- Transcription cancellation ---
        self.cancel_event = threading.Event()

        # --- API key check ---
        if not WHISPER_API_KEY:
            messagebox.showwarning(
                "API Key not found",
                "WHISPER_API_KEY not set.\n\nbye bye",
            )

    # ==================================================================
    #  Recording
    # ==================================================================

    def start_recognition(self, event):
        self.button.config(text="Speaking...", bg="darkgreen")
        self.audio_data = []
        self.current_rms = 0.0
        self.recording = True

        self.stream = sd.InputStream(
            channels=1, samplerate=16000, dtype="int16", callback=self.audio_callback,
        )
        self.stream.start()
        self._start_meter()

    def audio_callback(self, indata, frames, time, status):
        if status:
            print(f"Audio status: {status}")
        if self.recording:
            data = indata.copy().flatten()
            self.audio_data.append(data)
            # Compute RMS on this chunk (avoid sqrt on every sample by
            # checking against squared threshold first — faster path).
            rms = math.sqrt(float(np.mean(data.astype(np.float64) ** 2)))
            self.current_rms = rms

    def stop_recognition(self, event):
        self.button.config(text="Push to Talk", bg="blue")
        self.recording = False
        self._stop_meter()
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        # Check for silence before spawning the transcription thread
        if not self.audio_data:
            self.label.config(text="(no audio captured)")
            return

        full_audio = np.concatenate(self.audio_data)
        rms = math.sqrt(float(np.mean(full_audio.astype(np.float64) ** 2)))
        if rms < SILENCE_RMS_THRESHOLD:
            self.label.config(text=f"(silent — RMS {rms:.4f} < {SILENCE_RMS_THRESHOLD})")
            self.audio_data = []
            return

        self.cancel_event.clear()
        self.cancel_button.pack(side=tk.RIGHT, fill="y")
        threading.Thread(target=self.transcribe_audio, args=(full_audio,), daemon=True).start()

    # ==================================================================
    #  Volume meter
    # ==================================================================

    def _start_meter(self):
        self._meter_job = self.root.after(METER_INTERVAL_MS, self._update_meter)

    def _stop_meter(self):
        if self._meter_job is not None:
            self.root.after_cancel(self._meter_job)
            self._meter_job = None
        self.meter_canvas.delete("all")

    def _update_meter(self):
        if not self.recording:
            return

        canvas_w = self.meter_canvas.winfo_width()
        canvas_h = self.meter_canvas.winfo_height()

        self.meter_canvas.delete("all")
        if canvas_w < 10 or canvas_h < 4:
            self._meter_job = self.root.after(METER_INTERVAL_MS, self._update_meter)
            return

        # Convert raw RMS to a dB-like value (0–100 scale)
        if self.current_rms > 1e-9:
            raw_db = 20 * math.log10(self.current_rms)
        else:
            raw_db = -99
        display_db = max(0.0, min(raw_db, 100.0))

        # dB scale: 0–100, step 10 → 10 LEDs
        led_on = int(display_db / 10)       # 0..9 when display_db < 100, 9 at 100
        led_on = max(0, min(led_on, 9))

        n_leds = 10
        margin_x = 8
        margin_y_top = 8
        label_h = 14          # room for dB text at the bottom
        gap = 4

        usable_w = canvas_w - 2 * margin_x
        led_w = (usable_w - (n_leds - 1) * gap) / n_leds
        led_h = canvas_h - margin_y_top - label_h

        # Color tables: green 0-4, yellow 5-7, red 8-9
        _LED_COLORS_LIT   = ["#00ee00"] * 5 + ["#eeee00"] * 3 + ["#ee0000"] * 2
        _LED_COLORS_DIM   = ["#003300"] * 5 + ["#333300"] * 3 + ["#330000"] * 2
        _LED_COLORS_GLOW  = ["#88ff88"] * 5 + ["#ffff88"] * 3 + ["#ff8888"] * 2

        for i in range(n_leds):
            x0 = margin_x + i * (led_w + gap)
            y0 = margin_y_top
            x1 = x0 + led_w
            y1 = y0 + led_h

            if i <= led_on:
                # Lit LED
                self.meter_canvas.create_rectangle(
                    x0, y0, x1, y1, fill=_LED_COLORS_LIT[i], outline="#666666", width=1,
                )
                # Top highlight to simulate LED dome
                hl_h = max(led_h * 0.35, 2)
                self.meter_canvas.create_rectangle(
                    x0 + 1, y0 + 1, x1 - 1, y0 + hl_h,
                    fill=_LED_COLORS_GLOW[i], outline="",
                )
            else:
                # Unlit LED — dark, barely visible
                self.meter_canvas.create_rectangle(
                    x0, y0, x1, y1, fill=_LED_COLORS_DIM[i], outline="#1a1a1a", width=1,
                )

        # dB label
        self.meter_canvas.create_text(
            canvas_w // 2, canvas_h - 6,
            text=f"{display_db:.0f} dB", fill="#aaaaaa", font=("sans", 8),
        )

        self._meter_job = self.root.after(METER_INTERVAL_MS, self._update_meter)

    # ==================================================================
    #  Cancel
    # ==================================================================

    def cancel_transcription(self):
        self.cancel_event.set()
        self.label.config(text="Transcription cancelled")
        self._hide_cancel_button()

    def _hide_cancel_button(self):
        self.cancel_button.pack_forget()

    # ==================================================================
    #  Transcription
    # ==================================================================

    def transcribe_audio(self, full_audio):
        self._set_label("Transcribing...")
        temp_wav = None

        try:
            # Save to temp WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_wav = f.name

            with wave.open(temp_wav, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(full_audio.tobytes())

            if self.cancel_event.is_set():
                return

            # Encode and send to API
            with open(temp_wav, "rb") as f:
                base64_audio = base64.b64encode(f.read()).decode("utf-8")

            response = requests.post(
                url=WHISPER_URL,
                headers={
                    "Authorization": f"Bearer {WHISPER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": SITE_URL,
                    "X-OpenRouter-Title": SITE_TITLE,
                },
                data=json.dumps({
                    "model": "openai/whisper-1",
                    "input_audio": {
                        "data": base64_audio,
                        "format": "wav",
                    },
                }),
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            text = result.get("text", "").strip()

        except requests.RequestException as e:
            self._schedule(lambda: messagebox.showerror(
                "API Error", f"Error with API service:\n{e}"))
            self._set_label("Transcription error")
            return
        except Exception as e:
            if self.cancel_event.is_set():
                return
            self._schedule(lambda: messagebox.showerror(
                "Whisper Error", f"Error during transcription:\n{e}"))
            self._set_label("Transcription error")
            return
        finally:
            if temp_wav:
                try:
                    os.unlink(temp_wav)
                except OSError:
                    pass

        display_text = f"You: {text}"
        print(display_text)
        self._set_label(display_text)

        # ShellGPT
        try:
            process = subprocess.Popen(
                ["sgpt", "sh", text],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            output, stderr = process.communicate()
        except FileNotFoundError:
            self._schedule(lambda: messagebox.showerror(
                "Error", "ShellGPT (sgpt) not found.\n"
                         "Install with: go install github.com/tbckr/sgpt/v2/cmd/sgpt@latest"))
            self._schedule(self._hide_cancel_button)
            return

        if self.cancel_event.is_set():
            self._schedule(self._hide_cancel_button)
            return

        if stderr:
            print(f"sgpt stderr: {stderr.decode()}")

        if output:
            response_text = output.decode().strip()
            print("sgpt:", response_text)
            self._schedule(lambda: self.show_commands(response_text))

        self.audio_data = []
        self._schedule(self._hide_cancel_button)

    # ==================================================================
    #  Display commands
    # ==================================================================

    def show_commands(self, response):
        for widget in self.output_text_frame.winfo_children():
            widget.destroy()

        lines = response.split("\n")
        for line in lines:
            if not line.strip():
                continue

            is_dangerous, danger_labels = self._classify_danger(line)

            frame = tk.Frame(self.output_text_frame, bg="black")
            frame.pack(side=tk.TOP, fill="x")

            # Execute button
            exec_btn = tk.Button(
                frame, text="⮞", font=("sans", 10),
                command=lambda l=line: self.execute_command(l),
                fg="white", bg="black", highlightbackground="black",
            )
            exec_btn.pack(side=tk.LEFT)

            # Edit button
            edit_btn = tk.Button(
                frame, text="Edit", font=("sans", 9),
                command=lambda l=line: self.edit_command(l),
                fg="white", bg="#333333", highlightbackground="black",
            )
            edit_btn.pack(side=tk.LEFT)

            # Command text
            fg_color = "#ff4444" if is_dangerous else "white"
            entry = tk.Entry(frame, bg="black", fg=fg_color, bd=0, highlightthickness=0,
                             font=("sans", 10))
            entry.insert(tk.END, f" {line}")
            entry.pack(side=tk.LEFT, fill="x", expand=True)

            # Dangerous label
            if is_dangerous:
                warning = tk.Label(
                    frame, text=f" [{', '.join(danger_labels)}]",
                    bg="black", fg="#ff4444", font=("sans", 8),
                )
                warning.pack(side=tk.RIGHT)

    @staticmethod
    def _classify_danger(line):
        """Return (is_dangerous, [label, ...]) for matched patterns."""
        matched = []
        for regex, label in DANGEROUS_REGEX:
            if regex.search(line):
                matched.append(label)
        return bool(matched), matched

    # ==================================================================
    #  Edit command
    # ==================================================================

    def edit_command(self, original_command):
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit command")
        dialog.configure(bg="black")
        dialog.geometry("700x120")

        tk.Label(dialog, text="Edit the command below then press Execute:",
                 bg="black", fg="white", font=("sans", 10)).pack(pady=(10, 5))

        entry = tk.Entry(dialog, bg="#1a1a1a", fg="white", insertbackground="white",
                         font=("sans", 10), bd=1, relief="solid")
        entry.insert(0, original_command)
        entry.pack(fill="x", padx=10, pady=5)
        entry.select_range(0, tk.END)
        entry.focus_set()

        btn_frame = tk.Frame(dialog, bg="black")
        btn_frame.pack(pady=(0, 10))

        tk.Button(btn_frame, text="Execute", bg="darkgreen", fg="white",
                  command=lambda: [dialog.destroy(), self.execute_command(entry.get())],
                  font=("sans", 10)).pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="Cancel", bg="#333333", fg="white",
                  command=dialog.destroy, font=("sans", 10)).pack(side=tk.LEFT, padx=5)

    # ==================================================================
    #  Execute command
    # ==================================================================

    def execute_command(self, command):
        is_dangerous, danger_labels = self._classify_danger(command)

        if is_dangerous:
            msg = (
                f"This command may be dangerous:\n\n"
                f"  {command}\n\n"
                f"Matched: {', '.join(danger_labels)}\n\n"
                f"Do you want to execute it anyway?"
            )
            if not messagebox.askyesno("Dangerous command", msg, parent=self.root):
                return

        safe_command = command.replace("'", "'\"'\"'")
        subprocess.Popen(
            ["xfce4-terminal", "--hold", "--command",
             f"bash -c '{safe_command}; exec bash'"]
        )

    # ==================================================================
    #  Helpers
    # ==================================================================

    def _set_label(self, text):
        """Thread-safe label update."""
        self._schedule(lambda: self.label.config(text=text))

    def _schedule(self, fn):
        """Schedule fn to run on the main (tkinter) thread."""
        self.root.after(0, fn)


def main():
    root = tk.Tk()
    root.title("Jarvis on Linux")
    root.geometry("960x540")
    root.configure(bg="black")
    SpeechRecognitionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
