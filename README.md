# JARVIS Linux

Applicazione Python con GUI (tkinter) per il riconoscimento vocale e l'esecuzione di comandi tramite interfaccia grafica su Debian 13 Trixie (XFCE).

## Descrizione

L'app fornisce un bottone **PTT (Push-to-Talk)**: tenendolo premuto si registra l'audio tramite il microfono, che viene trascritto usando l'API **Whisper** (tramite provider configurabile), quindi passato a **ShellGPT (sgpt)** per generare comandi shell eseguibili. I comandi generati appaiono nella GUI e, cliccando il pulsante accanto, vengono eseguiti in un nuovo terminale `xfce4-terminal`.

La trascrizione e la generazione dei comandi usano **due provider e chiavi indipendenti**, per permettere cost tracking separato e massima flessibilita' nel cambio provider.

## Prerequisiti

- **Debian 13 Trixie** con ambiente **XFCE**
- **Python 3.13** (testato con 3.13.5)
- **PulseAudio** (backend audio di sistema)
- Connessione internet (per le API e l'installazione delle dipendenze)
- Account su [OpenRouter](https://openrouter.ai) (o altro provider compatibile) per ottenere le API key

## Installazione

Eseguire una sola volta lo script di setup:

```bash
bash setup.sh
```

Lo script installa automaticamente:

- Pacchetti sistema (Python 3.13, pulseaudio, portaudio, ffmpeg, xfce4-terminal, build-essential)
- **Go** essendo **ShellGPT (sgpt)** nella versione scritta in Go
- Un virtual environment `venv` con le dipendenze Python

## Configurazione

Sono utilizzate **quattro variabili d'ambiente** indipendenti, configurabili in `~/.bashrc` o `~/.profile`:

```bash
# Whisper (trascrizione audio)
export WHISPER_API_KEY='sk-or-v1-...'
export WHISPER_API_BASE='https://openrouter.ai/api/v1'   
# o altro provider API compatibile

# ShellGPT (generazione comandi)
export OPENAI_API_KEY='sk-or-v1-...'
export OPENAI_API_BASE='https://openrouter.ai/api/v1'  
# o altro provider API compatibile
```

Per applicare:

```bash
source ~/.bashrc
```

### Cambiare provider

Le variabili `*_API_BASE` permettono di usare provider diversi da OpenRouter (es. API diretta OpenAI, Groq, ecc.). Esempi:

```bash
# Usa OpenAI diretto per la trascrizione
export WHISPER_API_BASE='https://api.openai.com/v1'

# Usa Groq per i comandi
export OPENAI_API_BASE='https://api.groq.com/openai/v1'
```

## Esecuzione

Attivare il virtual environment ed avviare l'applicazione:

```bash
source venv/bin/activate
python main.py
```

## Dipendenze Python

- `sounddevice` — registrazione audio (PortAudio/PulseAudio)
- `numpy` — gestione array audio
- `requests` — chiamate HTTP alle API

## Note tecniche

- L'audio viene registrato a **16kHz mono** in formato int16
- La trascrizione usa `WHISPER_API_BASE` con modello `openai/whisper-1`
- I comandi sono generati da `sgpt sh "prompt"` configurato tramite `~/.config/sgpt/config.yaml` con modello di default: `openai/gpt-4o-mini`
- I comandi generati vengono eseguiti in un terminale XFCE separato (`xfce4-terminal --hold`)
- Il formato audio inviato all'API e' **WAV con encoding base64** in JSONbash
  

## Licenza e Note (anche Legali si sa mai...)

- Questo progetto è un fork di https://github.com/morrolinux/jarvis_linux
  L'originale non presentava alcuna restrizione di licenza al momento del fork. 
  Trattandosi di un progetto a scopo didattico non c'è nessuna pretesa di reale utilizzo. 
  Proprio in ottica educativa si è studiato i pro e contro del refactoring tramite un agente IA via console, semi-integrato con IDE VSCode based e utilizzo di modelli LLM gratuiti tramite router AI provider.
- Come ben chiarito dall'autore iniziale https://morrolinux.it a cui devo (tanto) delle mie (poche) conoscenze riguardo ai sistemi Linux non deve essere usato come un oracolo, ma come una sorta di help evoluto che parte dai concetti per arrivare alla sintassi. 
Fate sempre attenzione a cosa eseguite via terminale, lo consigli un LLM (o vostro cugino) è sempre sotto la vostra responsabilità !
- Le modifiche da me effettuate sono rilasciate sotto licenza MIT. 
Il codice originale appartiene all'autore [morrolinux · GitHub](https://github.com/morrolinux)
