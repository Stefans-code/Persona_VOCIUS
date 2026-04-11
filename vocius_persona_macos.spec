# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Raccolta automatica per pacchetti complessi
torch_datas, torch_binaries, torch_hiddenimports = collect_all('torch')
ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all('customtkinter')
whisper_datas, whisper_binaries, whisper_hiddenimports = collect_all('faster_whisper')
ct2_datas, ct2_binaries, ct2_hiddenimports = collect_all('ctranslate2')

added_files = [
    ('assets', 'assets'),
    ('model_cache', 'model_cache'),
] + torch_datas + ctk_datas + whisper_datas + ct2_datas

added_binaries = torch_binaries + ctk_binaries + whisper_binaries + ct2_binaries

# Aggiungiamo il database iniziale vuoto o esistente
if os.path.exists('vocius_persona.db'):
    added_files.append(('vocius_persona.db', '.'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=added_binaries,
    datas=added_files,
    hiddenimports=[
        'PIL.ImageTk', 
        'PIL.Image',
        'ffpyplayer',
        'pygame',
        'jwt',
        'PyJWT',
        'timeit',
        'pkg_resources',
        'shlex',
        'core.database',
        'core.hardware',
        'core.licensing',
        'core.transcriber',
        'core.watcher'
    ] + torch_hiddenimports + ctk_hiddenimports + whisper_hiddenimports + ct2_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Vocius Persona',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.icns'], # Nota: macOS usa .icns
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Vocius Persona',
)

app = BUNDLE(
    coll,
    name='Vocius Persona.app',
    icon='assets/icon.icns',
    bundle_identifier='com.vocius.persona',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'LSBackgroundOnly': 'False',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'NSPrincipalClass': 'NSApplication',
    },
)
