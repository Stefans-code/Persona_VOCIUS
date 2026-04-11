#!/bin/bash

# Script di build per macOS - Vocius Persona
# Da eseguire su un Mac con Python 3.x installato

echo "🚀 Avvio procedura di build per macOS..."

# 1. Installazione dipendenze necessarie per la build
pip install pyinstaller Cython setuptools customtkinter faster-whisper Pillow ffpyplayer pyjwt torch

# 2. Pulizia cartelle precedenti
rm -rf build dist

# 3. COMPILAZIONE BINARIA (Protezione Codice)
echo "🔒 Compilazione binaria dei core modules per macOS..."
python3 setup_cython.py build_ext --inplace

# 4. Esecuzione PyInstaller
# Usiamo lo spec file specifico per macOS
echo "📦 Generazione pacchetto .app..."
python3 -m PyInstaller vocius_persona_macos.spec --noconfirm

echo "✅ Build completata!"
echo "📂 Troverai il pacchetto .app nella cartella dist/Vocius Persona.app"
echo "💡 Nota: GitHub Actions genererà automaticamente anche uno ZIP scaricabile."
