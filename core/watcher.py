import os
import time
import threading
from datetime import datetime

class VociusWatcher:
    def __init__(self, db, transcriber, on_file_detected_cb=None):
        self.db = db
        self.transcriber = transcriber
        self.on_file_detected = on_file_detected_cb
        self.is_running = False
        self._thread = None
        self.supported_extensions = ('.mp4', '.mp3', '.wav', '.m4a', '.mov', '.avi', '.mkv')
        self._processed = set()   # path già dispacciati (evita doppioni)
        self._pending = {}        # path -> ultima dimensione vista (debounce copia in corso)

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        self.is_running = False

    def _run(self):
        while self.is_running:
            watch_path = self.db.get_setting("watch_folder_path", "upload")
            if os.path.exists(watch_path):
                for filename in os.listdir(watch_path):
                    if not filename.lower().endswith(self.supported_extensions):
                        continue
                    full_path = os.path.join(watch_path, filename)

                    # Già dispacciato in questa sessione o già presente nel DB
                    if full_path in self._processed or self.db.check_file_exists(full_path):
                        continue

                    # Debounce: processa solo se la dimensione è stabile tra due poll
                    # (il file potrebbe essere ancora in fase di copia/scrittura)
                    try:
                        size = os.path.getsize(full_path)
                    except OSError:
                        continue
                    if self._pending.get(full_path) != size:
                        self._pending[full_path] = size
                        continue
                    self._pending.pop(full_path, None)

                    # Marca PRIMA di dispacciare per evitare doppioni mentre il job
                    # viene inserito nel DB in modo asincrono.
                    self._processed.add(full_path)
                    if self.on_file_detected:
                        self.on_file_detected(full_path)

            time.sleep(5) # Poll every 5 seconds

    def process_file_sync(self, path, progress_cb=None):
        # Helper sincrono: richiede un transcriber valido (può essere None se il
        # watcher è stato costruito senza, come nell'uso via callback dell'app).
        if self.transcriber is None:
            raise RuntimeError("Transcriber non inizializzato per il watcher.")

        name = os.path.basename(path)
        fid = self.db.add_file(name, path, "", "", os.path.splitext(path)[1][1:], 0, "it")

        results, info = self.transcriber.transcribe(path, progress_cb=progress_cb)

        out_dir = self.db.get_setting("output_path", "transcriptions")
        os.makedirs(out_dir, exist_ok=True)
        # Prefisso con l'id per evitare collisioni tra file con lo stesso nome
        safe_base = f"{fid}_{name}"
        txt_path = os.path.join(out_dir, f"{safe_base}.txt")
        srt_path = os.path.join(out_dir, f"{safe_base}.srt")

        self.transcriber.export_txt(results, txt_path)
        self.transcriber.export_srt(results, srt_path)

        self.db.update_file_status(fid, "completed", txt_path, srt_path, duration=info.duration)
        return True
