import sqlite3
import os
import platform
from datetime import datetime

class VociusDatabase:
    def __init__(self, db_path=None):
        if db_path is None:
            # Rilevamento piattaforma per percorsi persistenti
            system = platform.system()
            if system == "Windows":
                app_data = os.environ.get('APPDATA')
                if not app_data:
                    app_data = os.path.expanduser("~\\AppData\\Roaming")
                base_dir = os.path.abspath(os.path.join(app_data, "VociusPersona"))
            elif system == "Darwin": # macOS
                base_dir = os.path.expanduser("~/Library/Application Support/VociusPersona")
            else: # Linux o altro
                base_dir = os.path.expanduser("~/.vociuspersona")
            
            if not os.path.exists(base_dir):
                try:
                    os.makedirs(base_dir, exist_ok=True)
                except Exception as e:
                    print(f"ERROR: Could not create directory {base_dir}: {e}")
            
            self.db_path = os.path.join(base_dir, "vocius_persona.db")
        else:
            self.db_path = os.path.abspath(db_path)
            
        print(f"DATABASE PATH: {self.db_path}")
        self.init_db()

    def init_db(self):
        # Assicuriamoci che la cartella esista prima di connetterci
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            
        try:
            conn = sqlite3.connect(self.db_path)
        except Exception as e:
            print(f"SQLITE CONNECTION ERROR: {e}")
            raise
        cur = conn.cursor()
        
        # Table for processed files
        cur.execute("""
            CREATE TABLE IF NOT EXISTS processed_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                original_path TEXT NOT NULL,
                transcription_path_txt TEXT,
                transcription_path_srt TEXT,
                type TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                duration REAL,
                status TEXT DEFAULT 'processing',
                language TEXT,
                transcription_json TEXT
            )
        """)
        
        # Migrazione per database esistenti
        try:
            cur.execute("ALTER TABLE processed_files ADD COLUMN status TEXT DEFAULT 'processing'")
        except: pass
        try:
            cur.execute("ALTER TABLE processed_files ADD COLUMN language TEXT")
        except: pass
        try:
            cur.execute("ALTER TABLE processed_files ADD COLUMN transcription_json TEXT")
        except: pass
        try:
            cur.execute("ALTER TABLE processed_files ADD COLUMN folder_id INTEGER")
        except: pass

        # Table for Folders [NEW]
        cur.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table for app settings
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # Default settings
        defaults = [
            ("output_path", "transcriptions"),
            ("watch_folder_path", "upload"),
            ("preferred_model", "large-v3"),
            ("theme", "light")
        ]
        for key, val in defaults:
            cur.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)", (key, val))
            
        conn.commit()
        conn.close()

    def get_setting(self, key, default=None):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else default

    def set_setting(self, key, value):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
        conn.close()

    def add_file(self, name, original_path, txt_path, srt_path, file_type, duration, language, transcription_json=None):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO processed_files (name, original_path, transcription_path_txt, transcription_path_srt, type, duration, language, transcription_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, original_path, txt_path, srt_path, file_type, duration, language, transcription_json, 'processing'))
        conn.commit()
        last_id = cur.lastrowid
        conn.close()
        return last_id

    def get_all_files(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT name, processed_at, type, id, status, language FROM processed_files ORDER BY processed_at DESC")
        rows = cur.fetchall()
        conn.close()
        return rows
    
    def check_file_exists(self, original_path):
        """Metodo sicuro per controllare se un file è già nel database senza aprire connessioni esterne"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT id FROM processed_files WHERE original_path = ?", (original_path,))
        exists = cur.fetchone() is not None
        conn.close()
        return exists
    
    def get_file_detail(self, file_id):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM processed_files WHERE id = ?", (file_id,))
        row = cur.fetchone()
        if row:
            columns = [column[0] for column in cur.description]
            res = dict(zip(columns, row))
        else:
            res = None
        conn.close()
        return res

    def delete_file(self, file_id):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("DELETE FROM processed_files WHERE id = ?", (file_id,))
        conn.commit()
        conn.close()

    # --- FOLDER METHODS ---
    def add_folder(self, name):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO folders (name) VALUES (?)", (name,))
            conn.commit()
            fid = cur.lastrowid
        except:
            fid = None
        conn.close()
        return fid

    def get_all_folders(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM folders ORDER BY name ASC")
        rows = cur.fetchall()
        conn.close()
        return rows

    def get_files_by_folder(self, folder_id=None):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        if folder_id is None:
            cur.execute("SELECT name, processed_at, type, id, status, language FROM processed_files WHERE folder_id IS NULL ORDER BY processed_at DESC")
        else:
            cur.execute("SELECT name, processed_at, type, id, status, language FROM processed_files WHERE folder_id = ? ORDER BY processed_at DESC", (folder_id,))
        rows = cur.fetchall()
        conn.close()
        return rows

    def move_file_to_folder(self, file_id, folder_id):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("UPDATE processed_files SET folder_id = ? WHERE id = ?", (folder_id, file_id))
        conn.commit()
        conn.close()

    def update_file_status(self, file_id, status, txt_path=None, srt_path=None):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        if txt_path and srt_path:
            cur.execute("UPDATE processed_files SET status = ?, transcription_path_txt = ?, transcription_path_srt = ? WHERE id = ?", (status, txt_path, srt_path, file_id))
        else:
            cur.execute("UPDATE processed_files SET status = ? WHERE id = ?", (status, file_id))
        conn.commit()
        conn.close()
