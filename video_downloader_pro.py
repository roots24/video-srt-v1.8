import os
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox

import config
from downloader_config import FORMAT_CONFIG
from downloader_logic import is_valid_url, run_download_process

class DownloadJobRow(ctk.CTkFrame):
    """
    Componente UI per la rappresentazione di un singolo job di download.

    RUOLO TECNICO:
    - Incapsula l'estetica della riga di download (Nome, Barra Progresso, Stato).
    - Gestisce l'animazione a 'impulso' durante la fase di merge (unione audio/video), 
      fornendo un feedback visivo all'utente mentre FFmpeg elabora i file.
    """
    def __init__(self, master, filename="Download in corso..."):
        super().__init__(master)
        self.pack(fill="x", padx=10, pady=5)
        self.is_merging = False
        self.pulse_val = 0
        self.pulse_dir = 1
        self.lbl_name = ctk.CTkLabel(self, text=filename, font=("Roboto", 12), width=200, anchor="w")
        self.lbl_name.pack(side="left", padx=10, pady=5)
        self.progress_bar = ctk.CTkProgressBar(self, width=200)
        self.progress_bar.set(0)
        self.progress_bar.pack(side="left", padx=10, pady=5)
        self.lbl_status = ctk.CTkLabel(self, text="0%", font=("Roboto", 12), width=100)
        self.lbl_status.pack(side="left", padx=10, pady=5)

    def update_progress(self, percent, text):
        self.after(0, lambda: self.progress_bar.set(percent))
        self.after(0, lambda: self.lbl_status.configure(text=text))

    def start_merge_animation(self):
        self.is_merging = True
        self.after(0, lambda: self.lbl_status.configure(text="⚙️ Merging...", text_color="#3498db"))
        self._animate_pulse()

    def _animate_pulse(self):
        if not self.is_merging: return
        self.pulse_val += 0.05 * self.pulse_dir
        if self.pulse_val >= 0.9 or self.pulse_val <= 0.1: self.pulse_dir *= -1
        self.progress_bar.set(self.pulse_val)
        self.after(50, self._animate_pulse)

    def stop_merge_animation(self):
        self.is_merging = False
        self.after(0, lambda: self.progress_bar.set(1.0))

    def set_final_status(self, text, color="green"):
        self.stop_merge_animation()
        self.after(0, lambda: self.lbl_status.configure(text=text, text_color=color))

class YoutubeDownloaderGUI(ctk.CTkToplevel):
    """
    Interfaccia per il modulo di download multi-video.

    ARCHITETTURA TECNICA:
    - Gestisce la configurazione dei parametri di download (Browser, Qualità, Preset FFmpeg).
    - Implementa una coda di download asincrona: ogni URL inserito avvia un nuovo Thread 
      che esegue `run_download_process`, permettendo download multipli paralleli senza bloccare l'UI.
    - Integrazione con `config.py` per l'aggiornamento dinamico del motore FFmpeg.
    """
    def __init__(self):
        super().__init__()
        self.title("ꑭ 🚀 MULTI-VIDEO DOWNLOADER ULTRA PRO v1.9.1 By Banderivez ꑭ")
        # Dimensione ottimizzata per la maggior parte degli schermi
        self.geometry("750x900") 
        ctk.set_appearance_mode("dark") 
        ctk.set_default_color_theme("blue")

        self.browser_var = ctk.StringVar(value="chrome")
        self.selected_category = ctk.StringVar(value="Risoluzione")
        self.selected_format = ctk.StringVar(value="") 
        self.preset_var = ctk.StringVar(value="medium")

        self.setup_ui()
        threading.Thread(target=self.check_ffmpeg_on_startup, daemon=True).start()

    def setup_ui(self):
        # Usiamo un frame principale per gestire meglio i pesi e l'espansione
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=10)

        # --- HEADER (Più compatto) ---
        self.header_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.header_frame.pack(pady=(10, 15), fill="x")
        ctk.CTkLabel(self.header_frame, text="ꑭ 🚀 MULTI-VIDEO DOWNLOADER\nULTRA PRO v1.9.1 By Banderivez ꑭ", font=("Roboto", 24, "bold"), justify="center").pack()

        # --- PANEL IMPOSTAZIONI (Grid) ---
        self.settings_panel = ctk.CTkFrame(self.main_container)
        self.settings_panel.pack(fill="x", pady=5)
        ctk.CTkLabel(self.settings_panel, text="⚙️ CONFIGURAZIONE", font=("Roboto", 13, "bold"), text_color="gray").grid(row=0, column=0, columnspan=2, pady=(10, 5), padx=20, sticky="w")

        ctk.CTkLabel(self.settings_panel, text="🌐 Browser:", font=("Roboto", 13)).grid(row=1, column=0, padx=20, pady=5, sticky="e")
        self.browser_menu = ctk.CTkOptionMenu(self.settings_panel, values=["chrome", "firefox", "edge", "brave", "safari", "None"], variable=self.browser_var, width=250)
        self.browser_menu.grid(row=1, column=1, padx=20, pady=5, sticky="w")

        ctk.CTkLabel(self.settings_panel, text="📂 Categoria:", font=("Roboto", 13)).grid(row=2, column=0, padx=20, pady=5, sticky="e")
        categories = list(FORMAT_CONFIG.keys())
        self.category_menu = ctk.CTkOptionMenu(self.settings_panel, values=categories, command=self.update_format_list, variable=self.selected_category, width=250)
        self.category_menu.grid(row=2, column=1, padx=20, pady=5, sticky="w")

        ctk.CTkLabel(self.settings_panel, text="🎨 Formato:", font=("Roboto", 13)).grid(row=3, column=0, padx=20, pady=5, sticky="e")
        self.sub_format_menu = ctk.CTkOptionMenu(self.settings_panel, values=[], command=self.on_format_selected, variable=self.selected_format, width=250)
        self.sub_format_menu.grid(row=3, column=1, padx=20, pady=5, sticky="w")

        ctk.CTkLabel(self.settings_panel, text="⚡ Preset FFmpeg:", font=("Roboto", 13)).grid(row=4, column=0, padx=20, pady=5, sticky="e")
        self.preset_menu = ctk.CTkOptionMenu(self.settings_panel, values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"], variable=self.preset_var, width=250)
        self.preset_menu.grid(row=4, column=1, padx=20, pady=5, sticky="w")

        self.update_format_list("Risoluzione")

        # --- INPUT PANEL (Più compatto) ---
        self.input_panel = ctk.CTkFrame(self.main_container)
        self.input_panel.pack(fill="x", pady=5)
        
        self.url_frame = ctk.CTkFrame(self.input_panel, fg_color="transparent")
        self.url_frame.pack(padx=20, pady=(15, 5), fill="x")
        ctk.CTkLabel(self.url_frame, text="🔗 URL Video o Playlist:", font=("Roboto", 13, "bold")).pack(anchor="w")
        self.entry_url_container = ctk.CTkFrame(self.url_frame, fg_color="transparent")
        self.entry_url_container.pack(fill="x", pady=5)
        self.entry_url = ctk.CTkEntry(self.entry_url_container, placeholder_text="https://...", height=32)
        self.entry_url.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(self.entry_url_container, text="Incolla", width=80, height=32, command=self.paste_url).pack(side="right")

        self.path_frame = ctk.CTkFrame(self.input_panel, fg_color="transparent")
        self.path_frame.pack(padx=20, pady=(5, 15), fill="x")
        ctk.CTkLabel(self.path_frame, text="📁 Cartella di salvataggio:", font=("Roboto", 13, "bold")).pack(anchor="w")
        self.entry_path_container = ctk.CTkFrame(self.path_frame, fg_color="transparent")
        self.entry_path_container.pack(fill="x", pady=5)
        self.entry_path = ctk.CTkEntry(self.entry_path_container, height=32)
        self.entry_path.insert(0, os.getcwd())
        self.entry_path.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(self.entry_path_container, text="Scegli Cartella...", width=120, height=32, command=self.browse_folder).pack(side="right")

        # --- AZIONE PRINCIPALE ---
        self.btn_download = ctk.CTkButton(self.main_container, text="START DOWNLOAD", font=("Roboto", 18, "bold"), height=50, width=300, fg_color="#2ecc71", hover_color="#27ae60", command=self.start_download_thread)
        self.btn_download.pack(pady=15)

        # --- CODA DOWNLOADS (L'unica area che si espande e contrae) ---
        ctk.CTkLabel(self.main_container, text="📥 CODA DOWNLOAD ATTIVI", font=("Roboto", 15, "bold"), text_color="gray").pack(pady=(10, 0))
        self.downloads_frame = ctk.CTkScrollableFrame(self.main_container, width=650, height=280)
        self.downloads_frame.pack(padx=30, pady=10, fill="both", expand=True)

        # --- FOOTER (Sempre in fondo) ---
        self.btn_update_ffmpeg = ctk.CTkButton(self.main_container, text="Update FFmpeg Engine", font=("Roboto", 12), fg_color="transparent", border_width=1, command=self.check_and_update_ffmpeg)
        self.btn_update_ffmpeg.pack(pady=(0, 10))

    def update_format_list(self, category):
        formats = list(FORMAT_CONFIG[category].keys())
        self.sub_format_menu.configure(values=formats)
        self.sub_format_menu.set(formats[0])
        self.selected_format.set(formats[0])
        self.on_format_selected(formats[0])

    def on_format_selected(self, choice):
        self.selected_format.set(choice)
        category = self.selected_category.get()
        config = FORMAT_CONFIG[category][choice]
        self.preset_menu.configure(state="normal" if config.get("preset_support", False) else "disabled")

    def start_download_thread(self):
        """
        Avvia l'esecuzione del download in un thread separato.

        FLUSSO TECNICO:
        1. Validazione URL tramite regex (`is_valid_url`).
        2. Istanziazione di `DownloadJobRow` per aggiungere visivamente il task alla coda UI.
        3. Mapping dei parametri della GUI (selettori, variabili di stato) in un dizionario 
           da passare a `run_download_process`.
        4. Esecuzione via `threading.Thread` con flag `daemon=True` per assicurare che 
           il thread termini se la finestra principale viene chiusa.
        """
        url = self.entry_url.get().strip()
        if not is_valid_url(url): return messagebox.showerror("Errore", "Inserisci un URL valido!")
        
        job_row = DownloadJobRow(self.downloads_frame, filename="Inizializzazione...")
        
        # Raccolta parametri dalla GUI per passarli alla logica esterna
        params = {
            "url": url,
            "job_row": job_row,
            "category": self.selected_category.get(),
            "fmt_choice": self.selected_format.get(),
            "save_path": self.entry_path.get().strip(),
            "browser_choice": None if self.browser_var.get() == "None" else self.browser_var.get(),
            "preset_var": self.preset_var
        }

        threading.Thread(target=run_download_process, kwargs=params, daemon=True).start()

    def paste_url(self):
        try: self.entry_url.delete(0, "end"); self.entry_url.insert(0, self.clipboard_get())
        except Exception as e: messagebox.showerror("Errore", f"Impossibile incollare: {e}")

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder: self.entry_path.delete(0, "end"); self.entry_path.insert(0, folder)

    def check_ffmpeg_on_startup(self):
        """Verifica l'aggiornamento di FFmpeg all'avvio senza mostrare alert se già aggiornato."""
        success, message = config.check_and_update_ffmpeg()
        if success:
            self.after(0, lambda: messagebox.showinfo("FFmpeg", message))
        elif "già aggiornato" not in message:
            self.after(0, lambda: messagebox.showerror("Errore", message))

    def check_and_update_ffmpeg(self):
        """Wrapper per il pulsante della GUI che richiama la logica unificata."""
        # Riutilizza la stessa logica ma mostra sempre il risultato (anche se già aggiornato)
        success, message = config.check_and_update_ffmpeg()
        msg_type = "Successo" if success else "Info"
        messagebox.showinfo(msg_type, message)


