import os
import time
import json
import subprocess
# No top-level import of faster_whisper to avoid startup delay

class VociusTranscriber:
    def __init__(self, model_size="large-v3", device="cuda", compute_type="float16"):
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
        
        self.whisper_cache = os.path.join(self.cache_dir, "whisper")
        if not os.path.exists(self.whisper_cache):
            # Fallback for some bundle structures
            self.whisper_cache = self.cache_dir 

    def load_model(self, progress_cb=None):
        from faster_whisper import WhisperModel
        if progress_cb: progress_cb(0.1, f"Caricamento modello {self.model_size}...")
        
        # Use local path if found in cache
        model_path = self.model_size
        if self.whisper_cache:
            potential_path = os.path.join(self.whisper_cache, self.model_size)
            if os.path.exists(potential_path):
                model_path = potential_path
                if progress_cb: progress_cb(0.15, "Modello trovato in cache locale (Offline OK)")

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
            if progress_cb: progress_cb(0.92, "Diarizzazione in corso...")
            pass

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
