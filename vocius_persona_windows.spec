# -*- mode: python ; coding: utf-8 -*-
# Build Windows di Vocius (cartella onedir, poi installer Inno Setup: installer_windows.iss).
# I modelli vocali NON sono inclusi: l'app li scarica al primo uso nella cartella utente.

import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

torch_datas, torch_binaries, torch_hiddenimports = collect_all('torch')
ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all('customtkinter')
whisper_datas, whisper_binaries, whisper_hiddenimports = collect_all('faster_whisper')
ct2_datas, ct2_binaries, ct2_hiddenimports = collect_all('ctranslate2')

# Diarizzazione (opzionale): se i pacchetti mancano il build prosegue senza
diar_datas, diar_binaries, diar_hiddenimports = [], [], []
for _pkg in ('pyannote.audio', 'torchaudio', 'asteroid_filterbanks', 'lightning_fabric', 'pytorch_lightning'):
    try:
        _d, _b, _h = collect_all(_pkg)
        diar_datas += _d; diar_binaries += _b; diar_hiddenimports += _h
    except Exception as _e:
        print(f"[spec] pacchetto diarizzazione non trovato, salto: {_pkg} ({_e})")

added_files = [('assets', 'assets'), ('license.txt', '.')] + torch_datas + ctk_datas + whisper_datas + ct2_datas + diar_datas
if os.path.isdir('model_cache'):
    added_files.append(('model_cache', 'model_cache'))
added_binaries = torch_binaries + ctk_binaries + whisper_binaries + ct2_binaries + diar_binaries

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=added_binaries,
    datas=added_files,
    hiddenimports=[
        'PIL.ImageTk', 'PIL.Image', 'ffpyplayer', 'jwt', 'cryptography', 'timeit', 'shlex',
        'huggingface_hub',
        'core.database', 'core.hardware', 'core.licensing', 'core.transcriber', 'core.watcher', 'core.diarizer',
    ] + torch_hiddenimports + ctk_hiddenimports + whisper_hiddenimports + ct2_hiddenimports + diar_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Vocius',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=['assets/icon.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='Vocius',
)
