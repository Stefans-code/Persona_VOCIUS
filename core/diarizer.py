import os

# Pipeline di diarizzazione (chi parla e quando) basata su pyannote.audio.
# Caricata SOLO dalla cache locale dei modelli (offline), import lazy.

# Pipeline candidate, in ordine di preferenza (pyannote 4.x usa "community-1")
_PIPELINES = (
    "pyannote/speaker-diarization-community-1",
    "pyannote/speaker-diarization-3.1",
)


class VociusDiarizer:
    def __init__(self, cache_dir=None):
        # cache_dir = radice di model_cache (dove stanno le cartelle 'models--pyannote--...')
        self.cache_dir = cache_dir
        self.pipeline = None

    def _force_offline_cache(self):
        """Punta huggingface_hub alla cache locale e vieta connessioni di rete."""
        if self.cache_dir and os.path.isdir(self.cache_dir):
            os.environ.setdefault("HF_HOME", self.cache_dir)
            os.environ.setdefault("HF_HUB_CACHE", self.cache_dir)
            os.environ.setdefault("HUGGINGFACE_HUB_CACHE", self.cache_dir)
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    def load(self, progress_cb=None):
        if self.pipeline is not None:
            return
        self._force_offline_cache()
        from pyannote.audio import Pipeline
        last_err = None
        for repo in _PIPELINES:
            try:
                if progress_cb:
                    progress_cb(0.92, "Caricamento modello interlocutori...")
                self.pipeline = Pipeline.from_pretrained(repo)
                if self.pipeline is not None:
                    return
            except Exception as e:
                last_err = e
        raise RuntimeError(f"Modello di diarizzazione non caricabile dalla cache locale: {last_err}")

    def diarize(self, audio_path, progress_cb=None):
        """Ritorna una lista di tuple (start, end, speaker_label)."""
        self.load(progress_cb)

        # Decodifichiamo l'audio in memoria (16kHz mono) con il decoder di
        # faster-whisper, così evitiamo torchcodec/FFmpeg lato pyannote.
        from faster_whisper.audio import decode_audio
        import torch

        wav = decode_audio(audio_path, sampling_rate=16000)  # float32 mono 1D
        waveform = torch.as_tensor(wav, dtype=torch.float32).unsqueeze(0)  # (1, time)
        output = self.pipeline({"waveform": waveform, "sample_rate": 16000})

        # pyannote.audio 4.x ritorna un DiarizeOutput con .speaker_diarization (Annotation);
        # le versioni 3.x ritornano direttamente l'Annotation.
        annotation = getattr(output, "speaker_diarization", output)

        turns = []
        for segment, _, speaker in annotation.itertracks(yield_label=True):
            turns.append((float(segment.start), float(segment.end), speaker))
        return turns

    @staticmethod
    def assign_speakers(segments, turns):
        """Assegna a ogni segmento di trascrizione lo speaker con massima sovrapposizione temporale."""
        for seg in segments:
            best, best_overlap = None, 0.0
            for (t_start, t_end, spk) in turns:
                overlap = max(0.0, min(seg["end"], t_end) - max(seg["start"], t_start))
                if overlap > best_overlap:
                    best_overlap, best = overlap, spk
            if best is not None:
                seg["speaker"] = _pretty_speaker(best)
        return segments


def _pretty_speaker(label):
    # pyannote usa etichette tipo "SPEAKER_00" -> "Speaker 1"
    try:
        n = int(str(label).split("_")[-1]) + 1
        return f"Speaker {n}"
    except Exception:
        return str(label)
