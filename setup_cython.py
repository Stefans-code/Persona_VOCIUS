from setuptools import setup
from Cython.Build import cythonize
import os

# Definiamo i moduli da proteggere (tutti quelli nella cartella core)
core_modules = [
    "core/database.py",
    "core/hardware.py",
    "core/licensing.py",
    "core/transcriber.py",
    "core/watcher.py"
]

setup(
    name="Vocius Persona Core Protection",
    ext_modules=cythonize(
        core_modules,
        compiler_directives={'language_level': "3"}
    ),
)

print("\n✅ Compilazione completata!")
print("💡 Ora puoi rimuovere i file .py nella cartella core (tieni solo i .pyd o .so) per la distribuzione.")
