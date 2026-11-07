import os
import time
import json
import subprocess
# No top-level import of faster_whisper to avoid startup delay

class VociusTranscriber:
    def __init__(self, model_size="zeus", device="cuda", compute_type="float16"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        
        # --- BUNDLE-SAFE CACHE DETECTION ---
        import sys
        if getattr(sys, 'frozen', False):
            # 1. Try inside the bundle (sys._MEIPASS)
            base_path = sys._MEIPASS
            self.cache_dir = os.path.join(base_path, "model_cache")
            
            # 2. If not found or if we want external large cache, look next to the EXE
            if not os.path.exists(self.cache_dir):
                exe_dir = os.path.dirname(sys.executable)
                self.cache_dir = os.path.join(exe_dir, "model_cache")
        else:
            # Running as a script (Development) - Progetto pulito: model_cache è in root
            current_dir = os.path.dirname(os.path.abspath(__file__))
            vocius_root = os.path.dirname(current_dir)
            self.cache_dir = os.path.join(vocius_root, "model_cache")
        
        # Cartella dei modelli vocali Vocius ("Olympus")
        self.engine_cache = os.path.join(self.cache_dir, "olympus")
        if not os.path.exists(self.engine_cache):
            # Fallback for some bundle structures
            self.engine_cache = self.cache_dir

    MODEL_REPO = "Stegeno/Nexflamma_Models"   # cartelle olympus/hermes e olympus/zeus

    @staticmethod
    def user_models_dir():
        """Cartella utente scrivibile per i modelli scaricati (non serve essere amministratore)."""
        import sys
        if sys.platform == "win32":
            base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
            return os.path.join(base, "VociusPersona", "model_cache")
        if sys.platform == "darwin":
            return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "VociusPersona", "model_cache")
        return os.path.join(os.path.expanduser("~"), ".vocius_persona", "model_cache")

    def _find_local_model(self):
        """Cerca il modello: cache inclusa nell'app, accanto all'eseguibile, cartella utente."""
        import sys
        candidates = [os.path.join(self.engine_cache, self.model_size),
                      os.path.join(self.cache_dir, "olympus", self.model_size)]
        if getattr(sys, "frozen", False):
            candidates.append(os.path.join(os.path.dirname(sys.executable), "model_cache", "olympus", self.model_size))
        candidates.append(os.path.join(self.user_models_dir(), "olympus", self.model_size))
        for c in candidates:
            if os.path.isfile(os.path.join(c, "model.bin")):
                return c
        return None

    def _download_model(self, progress_cb=None):
        # Nell'app senza console sys.stderr e' None: le barre tqdm di huggingface_hub andrebbero in errore
        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
        from huggingface_hub import snapshot_download
        dest = self.user_models_dir()
        os.makedirs(dest, exist_ok=True)
        peso = {"zeus": "circa 3 GB", "hermes": "circa 1,5 GB"}.get(self.model_size, "")
        if progress_cb:
            progress_cb(0.12, f"Primo avvio: scarico il modello {self.model_size} ({peso}). Serve solo questa volta...")
        snapshot_download(repo_id=self.MODEL_REPO, allow_patterns=[f"olympus/{self.model_size}/*"], local_dir=dest)
        path = os.path.join(dest, "olympus", self.model_size)
        if not os.path.isfile(os.path.join(path, "model.bin")):
            raise RuntimeError(f"Download del modello {self.model_size} non riuscito: controlla la connessione e riprova.")
        return path

    def load_model(self, progress_cb=None):
        from faster_whisper import WhisperModel
        if progress_cb: progress_cb(0.1, f"Caricamento modello {self.model_size}...")
        
        model_path = self._find_local_model()
        if model_path:
            if progress_cb: progress_cb(0.15, "Modello trovato in cache locale (Offline OK)")
        else:
            # I modelli Olympus non sono dentro l'installer (pesano 1,5-3 GB): al primo uso si
            # scaricano una volta sola da Hugging Face nella cartella utente, poi l'app lavora offline.
            model_path = self._download_model(progress_cb)

        self.model = WhisperModel(model_path, device=self.device, compute_type=self.compute_type)
        if progress_cb: progress_cb(0.3, "Modello caricato.")

    def transcribe(self, audio_path, language=None, progress_cb=None, diarize=False):
        if not self.model:
            self.load_model(progress_cb)

        if progress_cb: progress_cb(0.3, "Analisi file audio...")
        
        # Faster whisper transcription supports returning a generator
        segments, info = self.model.transcribe(audio_path, beam_size=5, language=language)
        total_duration = info.duration
        
        results = []
        for segment in segments:
            results.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
                "speaker": "Speaker 1"
            })
            if progress_cb and total_duration > 0:
                # Progress ranges from 0.3 to 0.9 during transcription
                pct = 0.3 + (segment.end / total_duration) * 0.6
                progress_cb(min(pct, 0.9), f"Trascrizione in corso ({int(pct*100)}%)...")

        if diarize:
            if progress_cb: progress_cb(0.92, "Riconoscimento interlocutori...")
            try:
                from core.diarizer import VociusDiarizer
                diarizer = VociusDiarizer(cache_dir=self.cache_dir)
                turns = diarizer.diarize(audio_path, progress_cb=progress_cb)
                VociusDiarizer.assign_speakers(results, turns)
            except Exception as e:
                # La diarizzazione è opzionale: se fallisce non blocchiamo la trascrizione
                if progress_cb: progress_cb(0.97, f"Diarizzazione non disponibile ({type(e).__name__})")

        if progress_cb: progress_cb(1.0, "Trascrizione completata!")
        return results, info

    def export_txt(self, results, output_path):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for r in results:
                f.write(f"[{self.format_time(r['start'])}] {r['speaker']}: {r['text']}\n")

    def export_srt(self, results, output_path):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for i, r in enumerate(results):
                f.write(f"{i+1}\n")
                f.write(f"{self.format_time_srt(r['start'])} --> {self.format_time_srt(r['end'])}\n")
                f.write(f"{r['text']}\n\n")

    @staticmethod
    def format_time(seconds):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{int(h):02}:{int(m):02}:{int(s):02}"

    @staticmethod
    def format_time_srt(seconds):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        ms = int((s - int(s)) * 1000)
        return f"{int(h):02}:{int(m):02}:{int(s):02},{ms:03}"
