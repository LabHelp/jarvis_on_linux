#!/usr/bin/env bash
# setup.sh — one-shot setup script for Debian 13 Trixie (XFCE)
# Run with: bash setup.sh

set -e

echo "==> Aggiornamento pacchetti di sistema..."
sudo apt update
sudo apt install -y \
    python3.13 \
    python3.13-venv \
    python3.13-dev \
    python3-tk \
    python3-pip \
    ffmpeg \
    build-essential \
    curl \
    git \
    xfce4-terminal \
    portaudio19-dev \
    pulseaudio \
    libpulse-dev

echo "==> Installazione Go (per sgpt)..."
if ! command -v go &>/dev/null; then
    GO_VERSION="1.23.4"
    wget -q "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz"
    sudo rm -rf /usr/local/go
    sudo tar -C /usr/local -xzf "go${GO_VERSION}.linux-amd64.tar.gz"
    rm "go${GO_VERSION}.linux-amd64.tar.gz"
    export PATH=$PATH:/usr/local/go/bin
    echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
fi

echo "==> Installazione ShellGPT (sgpt) via Go..."
export PATH=$PATH:/usr/local/go/bin:$HOME/go/bin
go install github.com/tbckr/sgpt/v2/cmd/sgpt@latest
echo 'export PATH=$PATH:$HOME/go/bin' >> ~/.bashrc
sudo ln -sf "$HOME/go/bin/sgpt" /usr/local/bin/sgpt

echo "==> Creazione virtual environment..."
if [ ! -d "venv" ]; then
    python3.13 -m venv venv
fi

echo "==> Attivazione virtual environment..."
source venv/bin/activate

echo "==> Upgrade pip..."
pip install --upgrade pip setuptools wheel

echo "==> Installazione dipendenze Python..."
pip install -r requirements.txt

echo ""
echo "==> Configurazione ShellGPT (sgpt)..."
mkdir -p "$HOME/.config/sgpt"
cp -f ./config.yaml "$HOME/.config/sgpt" 

echo ""
echo "==> IMPORTANTE: configura le API key"
echo "   Registrati su https://openrouter.ai e ottieni le chiavi."
echo "   Poi aggiungi a ~/.bashrc:"
echo "     export WHISPER_API_KEY='sk-or-v1-...'  # per trascrizione Whisper"
echo "     export WHISPER_API_BASE='https://openrouter.ai/api/v1'"
echo "     export OPENAI_API_KEY='sk-or-v1-...'   # per generazione comandi sgpt"
echo "     export OPENAI_API_BASE='https://openrouter.ai/api/v1'"
echo ""
echo "   esegui source ~/.bashrc per aggiornare environment"
echo ""
echo "==> Installazione completata!"
echo ""
echo "  usa sgpt config show per vedere la configurazione di shellgpt"
echo "  usa sgpt check per assicurarti che shellgpt sia correttamente configurato"
echo ""
echo "==> Per avviare l'applicazione:"
echo "  source venv/bin/activate"
echo "  python main.py"
