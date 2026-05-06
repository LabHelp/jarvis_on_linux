#!/usr/bin/env python3

import base64
import json
import os
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import messagebox
import wave
import numpy as np
import requests
import sounddevice as sd

# futura modifica metterle in .env ed usare os.getenv()
# from dotenv import load_dotenv
# load_dotenv() # Carica il file .env
# per ora i parametri vengono passati tramite variabili d'ambiente os
# al momento non ha senso perchè sgt go usa variabili d'ambiente os
# quindi tocca tenersele

WHISPER_API_KEY = os.environ.get("WHISPER_API_KEY", "")
WHISPER_API_BASE = os.environ.get("WHISPER_API_BASE", "https://openrouter.ai/api/v1")
WHISPER_URL = f"{WHISPER_API_BASE}/audio/transcriptions"
SITE_URL = "https://jarvix.com"
SITE_TITLE = "Jarvis on Linux"


class SpeechRecognitionApp:
    def __init__(self, root):
        self.root = root
        # PTT button
        self.button = tk.Button(
            root, text="Push to Talk", bg="blue", highlightbackground="black"
        )
        self.button.bind("<Button-1>", self.start_recognition)
        self.button.bind("<ButtonRelease-1>", self.stop_recognition)
        self.button.grid(row=0, column=0, columnspan=2, sticky="nsew")
        # STT output
        self.label = tk.Label(root, text="", bg="black", fg="white")
        self.label.grid(row=1, column=0, columnspan=2, sticky="nsew")
        # Model output
        self.output_text_frame = tk.Frame(root, bg="black")
        self.output_text_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")

        # Configure grid
        root.grid_rowconfigure(0, weight=0)
        root.grid_rowconfigure(1, weight=0)
        root.grid_rowconfigure(2, weight=1)
        root.grid_columnconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=1)

        # Audio setup
        self.recording = False
        self.audio_data = []
        self.stream = None

        # Check API key
        if not WHISPER_API_KEY:
            messagebox.showwarning(
                "API Key not found",
                "WHISPER_API_KEY.\n\n"
                "\n"
                "bye bye",
            )

    def start_recognition(self, event):
        self.button.config(text="Speaking...")
        self.audio_data = []
        self.recording = True
        self.stream = sd.InputStream(
            channels=1, samplerate=16000, dtype="int16", callback=self.audio_callback
        )
        self.stream.start()

    def audio_callback(self, indata, frames, time, status):
        if status:
            print(f"Audio status: {status}")
        if self.recording:
            self.audio_data.append(indata.copy().flatten())

    def stop_recognition(self, event):
        self.button.config(text="PTT")
        self.recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        threading.Thread(target=self.transcribe_audio, daemon=True).start()

    def transcribe_audio(self):
        if not self.audio_data:
            return

        self.label.config(text="Transcribing...")
        self.root.update_idletasks()

        audio = np.concatenate(self.audio_data)
        temp_wav = None

        try:
            # Save to temp WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_wav = f.name

            with wave.open(temp_wav, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(audio.tobytes())

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
            messagebox.showerror("Errore API service", f"Error with API service:\n{e}")
            self.label.config(text="Trascript error")
            return
        except Exception as e:
            messagebox.showerror("Errore Whisper", f"Errore during transcription:\n{e}")
            self.label.config(text="Transcript error")
            return
        finally:
            if temp_wav:
                try:
                    os.unlink(temp_wav)
                except OSError:
                    pass

        display_text = f"Tu: {text}"
        print(display_text)
        self.label.config(text=display_text)

        # ShellGPT
        try:
            process = subprocess.Popen(
                ["sgpt", "sh",text],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            output, stderr = process.communicate()
        except FileNotFoundError:
            messagebox.showerror(
                "Error:", "ShellGPT (sgpt) not found.\nInstall with: go install github.com/tbckr/sgpt/v2/cmd/sgpt@latest"
            )
            return

        if stderr:
            print(f"sgpt stderr: {stderr.decode()}")

        if output:
            response = output.decode().strip()
            print("sgpt:", response)
            self.show_commands(response)

        self.audio_data = []

    def show_commands(self, response):
        # Clear previous results
        for widget in self.output_text_frame.winfo_children():
            widget.destroy()

        lines = response.split("\n")
        for line in lines:
            if not line.strip():
                continue
            frame = tk.Frame(self.output_text_frame, bg="black")
            frame.pack(side=tk.TOP, fill="x")
            button = tk.Button(
                frame,
                text="⮞",
                command=lambda l=line: self.execute_command(l),
                fg="white",
                bg="black",
                highlightbackground="black",
            )
            button.pack(side=tk.LEFT)
            entry = tk.Entry(frame, bg="black", fg="white", bd=0, highlightthickness=0)
            entry.insert(tk.END, f" {line}")
            entry.pack(side=tk.LEFT, fill="x", expand=True)

    def execute_command(self, command):
        # Run in xfce4-terminal
        safe_command = command.replace("'", "'\"'\"'")
        subprocess.Popen(
            ["xfce4-terminal", "--hold", "--command", f"bash -c '{safe_command}; exec bash'"]
        )


def main():
    root = tk.Tk()
    root.title("Jarvis on Linux")
    root.geometry("960x540")
    root.configure(bg="black")
    app = SpeechRecognitionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
