import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import customtkinter as ctk
import os
import threading
import time
from datetime import datetime
from PIL import Image, ImageTk

import sys
from core.licensing import verify_license, get_hwid
from core.hardware import detect_hardware
from core.transcriber import VociusTranscriber
from core.database import VociusDatabase
from core.watcher import VociusWatcher

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- BRANDING VOCIUS ---
COLORS = {
    "primary": "#6159E1",
    "bg_main": ("#F8F9FA", "#1A1B1E"),      # Light grey, Darker grey
    "bg_sidebar": ("#FFFFFF", "#25262B"),
    "card_bg": ("#FFFFFF", "#25262B"),
    "text": ("#292D32", "#C1C2C5"),
    "text_sec": ("#697077", "#909296"),
    "border": ("#EBEDF2", "#373A40"),
    "status_ok": "#10B981",
    "status_ok_light": ("#E6F6F1", "#102F26"),
    "danger": "#EF4444",
    "danger_light": ("#FEE2E2", "#3E1616")
}

ctk.set_appearance_mode("Light")

class VociusPersonaApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Vocius Persona")
        self.geometry("1100x755")
        self.configure(fg_color=COLORS["bg_main"])
        
        # Icona - Cross-platform
        system = platform.system()
        if system == "Darwin":
            icon_name = "icon.icns"
        else:
            icon_name = "icon.ico"
            
        icon_path = get_resource_path(os.path.join("assets", icon_name))
        
        if os.path.exists(icon_path):
            if system == "Windows":
                try: self.iconbitmap(icon_path)
                except: pass
            # Su Mac l'icona è gestita dal bundle .app tramite lo spec file

        # --- STATE ---
        self.db = VociusDatabase()
        self.is_licensed = False
        self.lic_msg = ""
        self.lic_details = None
        self.hw_info = None
        self.transcriber = None
        self.nav_btns = {}
        self.active_folder_id = None 
        self.selected_file_ids = set() 
        self.jobs_progress = {} # {file_id: (percent, status_text)}
        
        # --- UI LAYOUT ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.setup_sidebar()
        self.setup_main()

        # --- DEFERRED HEAVY INIT ---
        self.after(100, self.deferred_init)

    def deferred_init(self):
        self.hw_info = detect_hardware()
        self.update_license_state()
        
        # --- AUTOMATION WATCHER ---
        self.watcher = VociusWatcher(self.db, None, on_file_detected_cb=self.on_watcher_event)
        self.watcher.start()
        
        self.select_view("dashboard")

    def update_license_state(self):
        self.is_licensed, self.lic_msg, self.lic_details = verify_license()
        self.setup_sidebar()

    def setup_sidebar(self):
        if hasattr(self, "sidebar"): self.sidebar.destroy()
        
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=COLORS["bg_sidebar"], border_width=1, border_color=COLORS["border"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)

        # 1. Licenza (Pallino sopra logo)
        header_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        header_frame.pack(anchor="w", padx=30, pady=(35, 10))
        
        dot_color = COLORS["status_ok"] if self.is_licensed else COLORS["danger"]
        ctk.CTkFrame(header_frame, width=8, height=8, corner_radius=4, fg_color=dot_color).pack(anchor="w", pady=(0, 5))
        ctk.CTkLabel(header_frame, text="Vocius", font=("Inter", 26, "bold"), text_color=COLORS["primary"]).pack(anchor="w")

        # Menu Items
        self.nav_btns = {}
        self.add_nav_item("dashboard", "I miei File", id="root")

        # Section Cartelle
        folder_header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        folder_header.pack(fill="x", padx=30, pady=(25, 5))
        ctk.CTkLabel(folder_header, text="CARTELLE", font=("Inter", 10, "bold"), text_color=COLORS["text_sec"]).pack(side="left")
        
        btn_new_folder = ctk.CTkButton(folder_header, text="+", width=20, height=20, fg_color="transparent", text_color=COLORS["primary"],
                                      hover_color="#F3F4F6", font=("Inter", 14, "bold"), command=self.create_folder_dialog)
        btn_new_folder.pack(side="right")

        # Dynamic Folders
        folders = self.db.get_all_folders()
        for fid, fname in folders:
            self.add_nav_item(f"folder_{fid}", fname, id=f"folder_{fid}")

        # Footer
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=15, pady=20)
        
        self.btn_theme = ctk.CTkButton(footer, text="Dark Mode", font=("Inter", 13), fg_color="transparent", text_color=COLORS["text"],
                                      hover_color="#F3F4F6", anchor="w", command=self.toggle_theme)
        self.btn_theme.pack(fill="x", pady=2)
        
        # IMPOSTAZIONI va al posto di esci
        self.add_nav_item("settings", "Impostazioni", parent=footer, id="settings")

    def add_nav_item(self, view_id, label, parent=None, id=None):
        target = parent if parent else self.sidebar
        btn = ctk.CTkButton(target, text=label, font=("Inter", 14), height=42, corner_radius=10,
                           fg_color="transparent", text_color=COLORS["text"], hover_color="#F3F4F6", anchor="w",
                           command=lambda: self.select_view(view_id))
        btn.pack(fill="x", padx=15, pady=2)
        self.nav_btns[id if id else view_id] = btn

    def setup_main(self):
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=1, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

    def select_view(self, view_id):
        for widget in self.container.winfo_children(): widget.destroy()
        
        # Update State
        self.active_folder_id = None
        if view_id.startswith("folder_"):
            self.active_folder_id = int(view_id.split("_")[1])
            target_nav_id = view_id
        else:
            target_nav_id = "root" if view_id == "dashboard" else view_id

        self._current_view_id = view_id

        # Update Nav
        for nid, btn in self.nav_btns.items():
            if nid == target_nav_id: 
                btn.configure(fg_color="#EEEDFD", text_color=COLORS["primary"], font=("Inter", 14, "bold"))
            else: 
                btn.configure(fg_color="transparent", text_color=COLORS["text"], font=("Inter", 14))

        if view_id == "dashboard" or view_id.startswith("folder_"): self.view_dashboard()
        elif view_id == "settings": self.view_settings()
        elif view_id.startswith("detail_"): self.view_detail(view_id.split("_")[1])

    def view_dashboard(self):
        view = ctk.CTkFrame(self.container, fg_color="transparent")
        view.grid(row=0, column=0, sticky="nsew", padx=45, pady=40)
        view.grid_columnconfigure(0, weight=1)

        title = "I miei File"
        if self.active_folder_id:
            folders = self.db.get_all_folders()
            title = next((f[1] for f in folders if f[0] == self.active_folder_id), "Cartella")

        ctk.CTkLabel(view, text=title, font=("Inter", 34, "bold"), text_color=COLORS["text"]).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(view, text="Bentornato, utente", font=("Inter", 15), text_color=COLORS["text_sec"]).grid(row=1, column=0, sticky="w", pady=(2, 25))

        btn_bar = ctk.CTkFrame(view, fg_color="transparent")
        btn_bar.grid(row=2, column=0, sticky="ew", pady=(0, 30))

        btn_upload = ctk.CTkButton(btn_bar, text="Carica nuovo file", font=("Inter", 14, "bold"), height=48, width=200,
                                  fg_color=COLORS["primary"], corner_radius=24, hover_color="#4F46E5",
                                  command=self.show_upload_modal)
        btn_upload.pack(side="left")

        if self.selected_file_ids:
            btn_move = ctk.CTkButton(btn_bar, text=f"Sposta Selezionati ({len(self.selected_file_ids)})", font=("Inter", 13), 
                                    height=38, fg_color="transparent", border_width=1, border_color=COLORS["border"], 
                                    text_color=COLORS["text"], command=self.show_bulk_move_modal)
            btn_move.pack(side="left", padx=20)
            
            btn_bulk_del = ctk.CTkButton(btn_bar, text="Elimina", font=("Inter", 13), height=38, fg_color="#FEE2E2", text_color=COLORS["danger"],
                                        command=self.bulk_delete)
            btn_bulk_del.pack(side="left")

        # Table
        table_card = ctk.CTkFrame(view, fg_color=COLORS["card_bg"], corner_radius=16, border_width=1, border_color=COLORS["border"])
        table_card.grid(row=3, column=0, sticky="nsew")
        table_card.grid_columnconfigure((0, 1, 2, 3), weight=1)

        headers = ["", "NOME", "CARICATO IL", "TIPO", ""]
        for i, h in enumerate(headers):
            ctk.CTkLabel(table_card, text=h, font=("Inter", 11, "bold"), text_color=COLORS["text_sec"]).grid(row=0, column=i, padx=20, pady=18, sticky="w")
        
        table_card.grid_columnconfigure(1, weight=3) # Name column

        # Load filtered files
        files = self.db.get_files_by_folder(self.active_folder_id) if self.active_folder_id else self.db.get_all_files()
        
        if not files:
            ctk.CTkLabel(table_card, text="Nessun file presente in questa sezione.", font=("Inter", 13)).grid(row=1, column=0, columnspan=4, pady=30)
        
        for i, row_data in enumerate(files):
            name, date, ftype, fid = row_data[0], row_data[1], row_data[2], row_data[3]
            row_idx = i + 1
            ctk.CTkFrame(table_card, height=1, fg_color=COLORS["border"]).grid(row=row_idx, column=0, columnspan=5, sticky="ew")
            
            # Checkbox
            cb = ctk.CTkCheckBox(table_card, text="", width=20, height=20, command=lambda f=fid: self.toggle_selection(f))
            if fid in self.selected_file_ids: cb.select()
            cb.grid(row=row_idx, column=0, padx=20, pady=16)

            lbl_name = ctk.CTkLabel(table_card, text=name, font=("Inter", 13, "bold"), text_color=COLORS["text"], cursor="hand2")
            lbl_name.grid(row=row_idx, column=1, padx=20, pady=16, sticky="w")
            lbl_name.bind("<Button-1>", lambda e, f=fid: self.select_view(f"detail_{f}"))
            
            ctk.CTkLabel(table_card, text=date, font=("Inter", 13), text_color=COLORS["text_sec"]).grid(row=row_idx, column=2, padx=20, sticky="w")
            ctk.CTkLabel(table_card, text=ftype.upper(), font=("Inter", 11, "bold"), fg_color="#F3F4F6", text_color=COLORS["text_sec"], corner_radius=6).grid(row=row_idx, column=3, padx=20, sticky="w")
            
            btn_del = ctk.CTkButton(table_card, text="🗑", width=35, height=35, fg_color="transparent", text_color=COLORS["danger"], hover_color="#FEE2E2", 
                                   command=lambda f=fid: self.delete_file(f))
            btn_del.grid(row=row_idx, column=4, padx=20, sticky="e")

    def toggle_selection(self, fid):
        if fid in self.selected_file_ids: self.selected_file_ids.remove(fid)
        else: self.selected_file_ids.add(fid)
        self.view_dashboard()

    def bulk_delete(self):
        if messagebox.askyesno("Elimina", f"Eliminare {len(self.selected_file_ids)} file?"):
            for fid in self.selected_file_ids: self.db.delete_file(fid)
            self.selected_file_ids.clear()
            self.view_dashboard()

    def create_folder_dialog(self):
        # High fidelity modal for new folder
        modal = ctk.CTkToplevel(self)
        modal.title("Nuova Cartella")
        modal.geometry("400x250")
        modal.attributes("-topmost", True)
        
        ctk.CTkLabel(modal, text="Nuova Cartella", font=("Inter", 20, "bold")).pack(pady=20)
        entry = ctk.CTkEntry(modal, width=300, height=40, placeholder_text="Nome cartella...")
        entry.pack(pady=10)
        entry.focus()
        
        def save():
            name = entry.get().strip()
            if name:
                self.db.add_folder(name)
                self.setup_sidebar()
                modal.destroy()
        
        btn_save = ctk.CTkButton(modal, text="Crea Cartella", fg_color=COLORS["primary"], height=40, command=save)
        btn_save.pack(pady=10)
        
    def show_bulk_move_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Sposta Files")
        modal.geometry("400x300")
        modal.attributes("-topmost", True)
        
        ctk.CTkLabel(modal, text="Sposta in...", font=("Inter", 18, "bold")).pack(pady=20)
        
        folders = self.db.get_all_folders()
        folder_names = ["I miei File (Root)"] + [f[1] for f in folders]
        choice = ctk.CTkOptionMenu(modal, values=folder_names, width=300, height=40)
        choice.pack(pady=10)
        
        def confirm():
            fname = choice.get()
            fid = next((f[0] for f in folders if f[1] == fname), None)
            for file_id in self.selected_file_ids:
                self.db.move_file_to_folder(file_id, fid)
            self.selected_file_ids.clear()
            modal.destroy()
            self.view_dashboard()
            self.setup_sidebar()

        ctk.CTkButton(modal, text="Conferma Spostamento", fg_color=COLORS["primary"], height=40, command=confirm).pack(pady=20)

    def show_upload_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Carica Media")
        modal.geometry("580x600")
        modal.configure(fg_color="#FFFFFF")
        modal.attributes("-topmost", True)
        
        # Header
        ctk.CTkLabel(modal, text="Carica Media", font=("Inter", 24, "bold")).pack(pady=(30, 10))
        self.selected_file_path = None

        def pick_file(event=None):
            p = filedialog.askopenfilename(filetypes=[("Media Files", "*.mp4 *.mp3 *.wav *.m4a *.mov *.mxf *.avi *.mkv")])
            if p:
                self.selected_file_path = p
                lbl_drag.configure(text=f"Pronto: {os.path.basename(p)}", text_color=COLORS["primary"])

        # 1. Drop Zone (Mirror Web)
        drop_zone_container = ctk.CTkFrame(modal, fg_color="transparent")
        drop_zone_container.pack(fill="x", padx=40, pady=10)
        
        drop_zone = ctk.CTkFrame(drop_zone_container, height=200, border_width=1, border_color=COLORS["border"], fg_color="#FFFFFF", corner_radius=12)
        drop_zone.pack(fill="x")
        drop_zone.pack_propagate(False)
        drop_zone.bind("<Button-1>", pick_file)
        
        # Icon & Text
        ctk.CTkLabel(drop_zone, text="↑", font=("Inter", 42), text_color=COLORS["border"]).pack(pady=(35, 5))
        lbl_drag = ctk.CTkLabel(drop_zone, text="Trascina file qui", font=("Inter", 15), text_color=COLORS["text"])
        lbl_drag.pack()
        ctk.CTkLabel(drop_zone, text="Supporta MP3, MP4, WAV, M4A, MOV, MXF...", font=("Inter", 11), text_color=COLORS["text_sec"]).pack(pady=2)
        
        btn_browse_inner = ctk.CTkButton(drop_zone, text="Sfoglia File", font=("Inter", 13), fg_color="white", border_width=1, border_color=COLORS["border"], 
                                         text_color=COLORS["text"], height=34, width=120, command=pick_file)
        btn_browse_inner.pack(pady=15)

        # 2. Options (Side-by-side like Web)
        opt_frame = ctk.CTkFrame(modal, fg_color="transparent")
        opt_frame.pack(fill="x", padx=40, pady=20)
        opt_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(opt_frame, text="Lingua Audio", font=("Inter", 12)).grid(row=0, column=0, sticky="w")
        lang_menu = ctk.CTkOptionMenu(opt_frame, values=["Italiano IT", "English EN"], fg_color="#F8F9FA", text_color=COLORS["text"], button_color="#F8F9FA", height=38)
        lang_menu.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=5)
        
        ctk.CTkLabel(opt_frame, text="Modello", font=("Inter", 12)).grid(row=0, column=1, sticky="w")
        model_menu = ctk.CTkOptionMenu(opt_frame, values=["Large v3 (Migliore)", "Medium", "Base"], fg_color="#F8F9FA", text_color=COLORS["text"], button_color="#F8F9FA", height=38)
        model_menu.grid(row=1, column=1, sticky="ew", pady=5)

        # Folder Selection (Keep it but styled)
        ctk.CTkLabel(modal, text="Sposta in cartella (Opzionale)", font=("Inter", 12)).pack(anchor="w", padx=40)
        folders = self.db.get_all_folders()
        folder_names = ["Nessuna (I miei File)"] + [f[1] for f in folders]
        self.folder_choice = ctk.CTkOptionMenu(modal, values=folder_names, fg_color="#F8F9FA", text_color=COLORS["text"], button_color="#F8F9FA", height=38)
        self.folder_choice.pack(fill="x", padx=40, pady=(5, 20))
        if self.active_folder_id:
            current_name = next((f[1] for f in folders if f[0] == self.active_folder_id), "Nessuna")
            self.folder_choice.set(current_name)

        # 3. Action Buttons (Bottom Right like Web)
        actions = ctk.CTkFrame(modal, fg_color="transparent")
        actions.pack(fill="x", padx=40, pady=(10, 30))
        
        def start():
            if not self.is_licensed:
                messagebox.showwarning("Vocius", "Licenza richiesta."); return
            if not self.selected_file_path:
                messagebox.showwarning("Vocius", "Scegli un file."); return
            
            fname = self.folder_choice.get()
            fid = next((f[0] for f in folders if f[1] == fname), None)
            path = self.selected_file_path
            modal.destroy()
            self.selected_file_path = None
            job_id = self.start_transcription_job(path, folder_id=fid)
            self.select_view(f"detail_{job_id}")

        btn_start = ctk.CTkButton(actions, text="Avvia Trascrizione", font=("Inter", 14, "bold"), fg_color=COLORS["primary"], height=44, corner_radius=8, command=start)
        btn_start.pack(side="right")
        
        btn_cancel = ctk.CTkButton(actions, text="Annulla", font=("Inter", 13), fg_color="transparent", text_color=COLORS["text"], width=100, command=modal.destroy)
        btn_cancel.pack(side="right", padx=15)

    def view_settings(self):
        view = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        view.grid(row=0, column=0, sticky="nsew", padx=45, pady=40)
        view.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(view, text="Impostazioni", font=("Inter", 34, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 30))

        # Paths
        block_save = self.create_block_empty(view, "SALVATAGGIO / AUTOMAZIONE", row=1)
        self.create_path_row(block_save, "Cartella Trascrizioni (Output)", "output_path")
        self.create_path_row(block_save, "Cartella Monitorata (Upload)", "watch_folder_path")

        # License
        lic_card = ctk.CTkFrame(view, fg_color=COLORS["card_bg"], corner_radius=16, border_width=1, border_color=COLORS["border"])
        lic_card.grid(row=2, column=0, sticky="ew", pady=10)
        ctk.CTkLabel(lic_card, text="LICENZA", font=("Inter", 11, "bold"), text_color=COLORS["text_sec"]).pack(anchor="w", padx=20, pady=(20, 10))
        ctk.CTkLabel(lic_card, text=f"Stato: {self.lic_msg}", font=("Inter", 14, "bold"), text_color=COLORS["status_ok"] if self.is_licensed else COLORS["danger"]).pack(anchor="w", padx=20)
        ctk.CTkLabel(lic_card, text=f"Scadenza: {self.lic_details['expiry']}", font=("Inter", 12)).pack(anchor="w", padx=20, pady=5)
        ctk.CTkLabel(lic_card, text=f"HWID: {self.lic_details['hwid']}", font=("Inter", 10), text_color=COLORS["text_sec"]).pack(anchor="w", padx=20)

        ctk.CTkButton(lic_card, text="Carica File Licenza (.vocius)", command=self.save_license_file).pack(fill="x", padx=20, pady=20)

        # Aggiornamenti
        upd_card = ctk.CTkFrame(view, fg_color=COLORS["card_bg"], corner_radius=16, border_width=1, border_color=COLORS["border"])
        upd_card.grid(row=3, column=0, sticky="ew", pady=10)
        ctk.CTkLabel(upd_card, text="AGGIORNAMENTI", font=("Inter", 11, "bold"), text_color=COLORS["text_sec"]).pack(anchor="w", padx=20, pady=(20, 10))
        ctk.CTkLabel(upd_card, text="Versione corrente: v1.0.0", font=("Inter", 13)).pack(anchor="w", padx=20)
        self.btn_check_upd = ctk.CTkButton(upd_card, text="Verifica Aggiornamenti", font=("Inter", 13, "bold"), fg_color=COLORS["primary"], command=self.check_software_updates)
        self.btn_check_upd.pack(fill="x", padx=20, pady=20)

    def check_software_updates(self):
        import urllib.request
        import json
        import webbrowser
        self.btn_check_upd.configure(state="disabled", text="Verifica in corso...")
        
        def check_upd_bg():
            current_version = "1.0.0"
            try:
                url = "https://nexflamma.net/vocius_version.json"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    remote_version = data.get("version", "1.0.0")
                    download_url = data.get("download_url", "")
                    changelog = data.get("changelog", "Miglioramenti generali.")

                    self.after(0, lambda: self.btn_check_upd.configure(state="normal", text="Verifica Aggiornamenti"))
                    
                    if remote_version > current_version:
                        msg = f"Una nuova versione di Vocius è disponibile: v{remote_version}!\n\nChangelog:\n{changelog}\n\nVuoi scaricarla ora?"
                        if messagebox.askyesno("Nuovo Aggiornamento Disponibile", msg):
                            webbrowser.open(download_url)
                    else:
                        self.after(0, lambda: messagebox.showinfo("Aggiornamenti", f"Il software è aggiornato alla versione più recente (v{current_version})!"))
            except Exception as e:
                self.after(0, lambda: self.btn_check_upd.configure(state="normal", text="Verifica Aggiornamenti"))
                self.after(0, lambda: messagebox.showerror("Errore", f"Impossibile verificare gli aggiornamenti: {e}"))

        threading.Thread(target=check_upd_bg, daemon=True).start()

    def save_license_file(self):
        path = filedialog.askopenfilename(filetypes=[("Vocius License", "*.vocius")])
        if path:
            import shutil
            shutil.copy(path, "license.vocius")
            self.update_license_state()
            self.setup_sidebar()
            self.view_settings()
            messagebox.showinfo("Vocius", "Licenza attiva!")

    def create_block_empty(self, parent, title, row):
        card = ctk.CTkFrame(parent, fg_color=COLORS["card_bg"], corner_radius=16, border_width=1, border_color=COLORS["border"])
        card.grid(row=row, column=0, sticky="ew", pady=10)
        ctk.CTkLabel(card, text=title, font=("Inter", 11, "bold"), text_color=COLORS["text_sec"]).pack(anchor="w", padx=20, pady=(20, 10))
        return card

    def create_path_row(self, parent, label, db_key):
        ctk.CTkLabel(parent, text=label, font=("Inter", 12, "bold")).pack(anchor="w", padx=20)
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(5, 15))
        path = self.db.get_setting(db_key)
        entry = ctk.CTkEntry(row, height=38, border_color=COLORS["border"])
        entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        entry.insert(0, path)
        def b():
            p = filedialog.askdirectory()
            if p: entry.delete(0, "end"); entry.insert(0, p); self.db.set_setting(db_key, p)
        ctk.CTkButton(row, text="Sfoglia", width=80, command=b).pack(side="right")

    def view_detail(self, file_id):
        data = self.db.get_file_detail(file_id)
        if not data: return
        
        # Use a scrollable frame for the whole detail page like web
        view = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        view.grid(row=0, column=0, sticky="nsew", padx=45, pady=40)
        view.grid_columnconfigure(0, weight=3) # Main col (Player + Trans)
        view.grid_columnconfigure(1, weight=1) # Side col (Export)

        # 1. Header (Title + Badge + Back Button)
        header = ctk.CTkFrame(view, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 25))
        
        ctk.CTkLabel(header, text=data['name'], font=("Inter", 26, "bold"), text_color=COLORS["text"]).pack(side="left")
        
        status_color = COLORS["status_ok"] if data['status'] == 'completed' else COLORS["primary"]
        status_badge = ctk.CTkFrame(header, fg_color=COLORS["status_ok_light"] if data['status'] == 'completed' else "#EEEDFD", corner_radius=6)
        status_badge.pack(side="left", padx=20)
        ctk.CTkLabel(status_badge, text=f"Stato: {data['status'].upper()}", font=("Inter", 11, "bold"), text_color=status_color).pack(padx=10, pady=2)
        
        ctk.CTkButton(header, text="← Torna ai File", font=("Inter", 13), fg_color="white", border_width=1, border_color=COLORS["border"], 
                     text_color=COLORS["text"], width=130, command=lambda: self.select_view("dashboard")).pack(side="right")

        # 2. Main Column (Left)
        main_col = ctk.CTkFrame(view, fg_color="transparent")
        main_col.grid(row=1, column=0, sticky="nsew", padx=(0, 25))
        main_col.grid_columnconfigure(0, weight=1)

        # Media Player (Mirror Web)
        player_card = ctk.CTkFrame(main_col, fg_color="black", corner_radius=12, height=450)
        player_card.grid(row=0, column=0, sticky="ew")
        player_card.pack_propagate(False)
        ctk.CTkLabel(player_card, text="▶️ Player Media Vocius", font=("Inter", 16), text_color="white").pack(expand=True)

        # Transcription Block (Mirror Web - Under Player)
        trans_card = ctk.CTkFrame(main_col, fg_color=COLORS["card_bg"], corner_radius=16, border_width=1, border_color=COLORS["border"])
        trans_card.grid(row=1, column=0, sticky="ew", pady=(25, 0))
        
        ctk.CTkLabel(trans_card, text="Trascrizione", font=("Inter", 14, "bold"), text_color=COLORS["text_sec"]).pack(anchor="w", padx=20, pady=15)
        
        # Segments list or Progress
        if data['status'] == 'processing':
            prog_val, prog_text = self.jobs_progress.get(int(file_id), (0.1, "Inizializzazione..."))
            
            ctk.CTkLabel(trans_card, text=prog_text, font=("Inter", 13)).pack(pady=(20, 5))
            bar = ctk.CTkProgressBar(trans_card, height=12, corner_radius=6, fg_color=COLORS["border"], progress_color=COLORS["primary"])
            bar.pack(fill="x", padx=40, pady=10)
            bar.set(prog_val)
            
            ctk.CTkLabel(trans_card, text="Il file è in fase di trascrizione. Rimarrai su questa pagina fino al completamento.", font=("Inter", 11), text_color=COLORS["text_sec"]).pack(pady=(0, 30))
        
        elif data['transcription_path_txt'] and os.path.exists(data['transcription_path_txt']):
            with open(data['transcription_path_txt'], 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines:
                    if line.strip():
                        seg = ctk.CTkFrame(trans_card, fg_color="transparent")
                        seg.pack(fill="x", padx=10, pady=10)
                        
                        # Timecode column
                        ctk.CTkLabel(seg, text="00:00:02,165", font=("Inter", 11), text_color=COLORS["text_sec"], width=100).pack(side="left")
                        # Text column
                        ctk.CTkLabel(seg, text=line.strip(), font=("Inter", 13), wraplength=550, justify="left", text_color=COLORS["text"]).pack(side="left", fill="x", expand=True, padx=20)
                        ctk.CTkFrame(trans_card, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=20)
        else:
            ctk.CTkLabel(trans_card, text="Nessuna trascrizione trovata.", font=("Inter", 13, "italic"), text_color=COLORS["text_sec"]).pack(pady=40)

        # 3. Side Column (Right: Export Panel)
        export_card = ctk.CTkFrame(view, fg_color=COLORS["card_bg"], corner_radius=16, border_width=1, border_color=COLORS["border"])
        export_card.grid(row=1, column=1, sticky="ne")
        export_card.configure(width=280)
        
        ctk.CTkLabel(export_card, text="Esporta", font=("Inter", 18, "bold")).pack(anchor="w", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(export_card, text="Formato", font=("Inter", 12), text_color=COLORS["text_sec"]).pack(anchor="w", padx=20)
        fmt_menu = ctk.CTkOptionMenu(export_card, values=["Sottotitoli (.srt)", "Testo (.txt)", "JSON"], fg_color="#F8F9FA", text_color=COLORS["text"], button_color="#F8F9FA", height=38)
        fmt_menu.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(export_card, text="Fonti", font=("Inter", 12), text_color=COLORS["text_sec"]).pack(anchor="w", padx=20, pady=(15, 0))
        src_box = ctk.CTkFrame(export_card, fg_color="#F8F9FA", corner_radius=8)
        src_box.pack(fill="x", padx=20, pady=10)
        ctk.CTkCheckBox(src_box, text="Tutte le fonti", font=("Inter", 12), border_width=2).pack(padx=15, pady=15, anchor="w")
        
        btn_dl = ctk.CTkButton(export_card, text="Scarica", font=("Inter", 14, "bold"), fg_color=COLORS["primary"], height=42, command=lambda: messagebox.showinfo("Esporta", f"Download avviato: {fmt_menu.get()}"))
        btn_dl.pack(fill="x", padx=20, pady=(10, 20))

    def start_transcription_job(self, path, folder_id=None):
        name = os.path.basename(path)
        fid = self.db.add_file(name, path, "", "", os.path.splitext(path)[1][1:], 0, "it")
        if folder_id: self.db.move_file_to_folder(fid, folder_id)
        
        def run_task():
            def update_ui_prog(pct, msg):
                self.jobs_progress[fid] = (pct, msg)
                # If we are on the detail page for THIS file, refresh it
                self.after(0, self.refresh_if_active, fid)

            try:
                if not self.transcriber: self.transcriber = VociusTranscriber(device=self.hw_info["device"], compute_type=self.hw_info["compute_type"])
                results, info = self.transcriber.transcribe(path, progress_cb=update_ui_prog)
                out_dir = self.db.get_setting("output_path", "transcriptions")
                if not os.path.exists(out_dir): os.makedirs(out_dir)
                
                txt_p = os.path.join(out_dir, f"{name}.txt"); srt_p = os.path.join(out_dir, f"{name}.srt")
                self.transcriber.export_txt(results, txt_p); self.transcriber.export_srt(results, srt_p)
                
                self.db.update_file_status(fid, "completed", txt_p, srt_p)
                if fid in self.jobs_progress: del self.jobs_progress[fid]
                
                self.after(0, lambda: messagebox.showinfo("Vocius", f"Completato: {name}"))
                self.after(0, lambda: self.select_view(f"detail_{fid}")) # Final refresh
            except Exception as e: 
                self.db.update_file_status(fid, "error")
                if fid in self.jobs_progress: del self.jobs_progress[fid]
                self.after(0, lambda: messagebox.showerror("Errore", str(e)))
                
        threading.Thread(target=run_task, daemon=True).start()
        return fid

    def refresh_if_active(self, fid):
        # We refresh the view ONLY if the current view 'detail_{fid}' is matches
        # For simplicity, we trigger a selective update or just call select_view
        # To avoid flicker, we'll only update if it is a processing file
        if hasattr(self, "_current_view_id") and self._current_view_id == f"detail_{fid}":
             self.select_view(self._current_view_id)

    def on_watcher_event(self, path):
        self.after(0, lambda: self.start_transcription_job(path))

    def delete_file(self, fid):
        if messagebox.askyesno("Elimina", "Confermi?"): self.db.delete_file(fid); self.view_dashboard()

    def toggle_theme(self):
        mode = "Dark" if ctk.get_appearance_mode() == "Light" else "Light"
        ctk.set_appearance_mode(mode)
        self.btn_theme.configure(text="Light Mode" if mode == "Dark" else "Dark Mode")

if __name__ == "__main__":
    app = VociusPersonaApp()
    app.mainloop()
