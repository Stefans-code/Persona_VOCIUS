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
                    if filename.lower().endswith(self.supported_extensions):
                        full_path = os.path.join(watch_path, filename)
                        
                        # Check if already in DB using the safe centralized method
                        if not self.db.check_file_exists(full_path):
                            if self.on_file_detected:
                                self.on_file_detected(full_path)
                                # Note: the processing itself should happen in a way that doesn't block the watcher
                                # but usually we want one at a time for Whisper.
            
            time.sleep(5) # Poll every 5 seconds

    def process_file_sync(self, path, progress_cb=None):
        # This is a helper for the main app to call when watcher finds a file
        name = os.path.basename(path)
        results, info = self.transcriber.transcribe(path, progress_cb=progress_cb)
        
        out_dir = self.db.get_setting("output_path", "transcriptions")
        txt_path = os.path.join(out_dir, f"{name}.txt")
        srt_path = os.path.join(out_dir, f"{name}.srt")
        
        self.transcriber.export_txt(results, txt_path)
        self.transcriber.export_srt(results, srt_path)
        
        self.db.add_file(name, path, txt_path, srt_path, os.path.splitext(path)[1][1:], info.duration, "it")
        return True
