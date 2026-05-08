# Jarvis on Linux

Applicazione Python con GUI (tkinter) per il riconoscimento vocale di un prompt descrittivo, la sua trascrizione e l'esecuzione di comandi forniti in risposta da ShellGPT. Testato su Debian 13 Trixie (XFCE).

## Descrizione

L'app dispone di un bottone **PTT (Push-to-Talk)**: tenendolo premuto si registra l'audio tramite il microfono, che viene trascritto usando l'API **Whisper** (tramite provider configurabile), quindi passato a **ShellGPT (sgpt)** per generare comandi shell eseguibili. I comandi generati appaiono nella GUI e, cliccando il pulsante accanto, vengono eseguiti in un nuovo terminale `xfce4-terminal`.

La trascrizione e la generazione dei comandi usano **due provider e chiavi indipendenti**, per permettere cost tracking separato e massima flessibilita' nell'eventuale cambio di provider.

### Novità versione 0.3.0

- **Barra volume LED**: durante la registrazione, una barra orizzontale mostra in tempo reale il livello audio con gradazione di colore (verde → giallo → rosso) e valore in dB.
- **Rilevamento silenzio**: se il volume registrato e' sotto una soglia minima, la chiamata API Whisper viene saltata, evitando consumi inutili.
- **Pulsante Cancel**: durante la trascrizione appare un pulsante rosso per annullare l'operazione in corso.
- **Sicurezza comandi**: 27 pattern pericolosi predefiniti (`rm`, `sudo`, `chmod`, `mkfs`, `dd`, fork bomb, `curl | sh`, `git push --force`, ecc.). I comandi riconosciuti appaiono in **rosso** con l'etichetta del rischio e richiedono una **conferma esplicita** prima dell'esecuzione.
- **Pulsante Edit**: ogni comando ha un tasto `Edit` che apre una finestra di modifica prima dell'esecuzione, utile per correggere o adattare il comando generato.

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
- La barra volume mostra il livello RMS in dB, aggiornato ogni 50ms. Registrazioni con RMS inferiore a 0.005 sono considerate silenti e non inviate all'API
- La trascrizione usa `WHISPER_API_BASE` con modello `openai/whisper-1`
- I comandi sono generati da `sgpt sh "prompt"` configurato tramite `~/.config/sgpt/config.yaml` con modello di default: `openai/gpt-4o-mini`
- I comandi generati vengono eseguiti in un terminale XFCE separato (`xfce4-terminal --hold`)
- Il formato audio inviato all'API e' **WAV con encoding base64** in JSON
- Prima dell'esecuzione, ogni comando viene analizzato tramite regex per individuare pattern pericolosi (es. `rm`, `sudo`, `chmod`, `mkfs`, `dd`, fork bomb, `curl | sh`, `git push --force`, `iptables`, `fdisk`, ecc.). In caso di match il comando appare in rosso e viene richiesta conferma esplicita
  

## Licenza e Note (anche Legali si sa mai...)

- Trattandosi di un progetto a scopo didattico non c'e' nessuna pretesa di reale utilizzo. 
  Proprio in ottica educativa si e' studiato i pro e contro del refactoring tramite un agente IA via console, semi-integrato con IDE VSCode based e utilizzo di modelli LLM gratuiti tramite router AI provider.
- Come ben chiarito dall'autore iniziale https://morrolinux.it a cui devo (tanto) delle mie (poche) conoscenze riguardo ai sistemi Linux non deve essere usato come un oracolo, ma come una sorta di help evoluto che parte dai concetti per arrivare alla sintassi. 
Fate sempre attenzione a cosa eseguite via terminale, lo consigli un LLM (o vostro cugino) e' sempre sotto la vostra responsabilita' !
- Questo progetto e' un fork di https://github.com/morrolinux/jarvis_linux 
L'originale non presentava alcuna restrizione di licenza al momento del fork.
Le modifiche da me effettuate sono rilasciate sotto licenza MIT. 
Il codice originale appartiene all'autore [morrolinux · GitHub](https://github.com/morrolinux)
