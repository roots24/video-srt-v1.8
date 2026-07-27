import customtkinter as ctk
from tkinter import filedialog, messagebox, dnd
from datetime import datetime
import threading
import tempfile
import os
import shutil
import config

# Importiamo la logica di business e le configurazioni
from logic import VideoTranslatorLogic
from video_downloader_pro import YoutubeDownloaderGUI

# ==============================================================================
# INTERFACCIA GRAFICA (GUI)
# ==============================================================================

class App(ctk.CTk):
    """
    Classe principale dell'interfaccia grafica (GUI) basata su CustomTkinter.

    RUOLO TECNICO:
    - Gestisce l'albero dei widget e il layout della finestra principale.
    - Implementa il binding tra gli input utente (StringVar, DoubleVar) e la logica di business.
    - Fornisce i metodi di callback (`update_log`, `update_progress`) che permettono al 
      backend (`VideoTranslatorLogic`) di comunicare con l'interfaccia in modo asincrono.
    """
    def __init__(self):
        super().__init__()
        self._log_history = []

        # Configurazione finestra principale
        self.title("ꑭ Ultimate Video Translator AI PRO v1.8 - Neural Edition by Banderivez ꑭ")
        self.geometry("850x950")
        
        # Inizializzazione del backend (VideoTranslatorLogic)
        # Passiamo i metodi della GUI come callback per log e progresso
        self.logic = VideoTranslatorLogic(self.update_log, progress_callback=self.update_progress)

        # ----------------------------------------------------------------------
        # VARIABILI DI STATO (Binding dei dati)
        # ----------------------------------------------------------------------
        self.src_lang = ctk.StringVar(value="uk")      # Lingua sorgente predefinita: Ucraino
        self.tgt_lang = ctk.StringVar(value="it")      # Lingua target predefinita: Italiano
        self.gender = ctk.StringVar(value="male")      # Selezione voce maschile/femminile
        self.output_mode = ctk.StringVar(value="video") # Modalità di export (video o solo audio)
        self.vol_orig = ctk.DoubleVar(value=0.4)       # Volume audio originale (background)
        self.vol_trans = ctk.DoubleVar(value=1.0)      # Volume audio tradotto (foreground)
        self.force_sync = ctk.BooleanVar(value=False)  # Se True, ignora i limiti di velocità audio
        self.max_speed_val = ctk.DoubleVar(value=1.5)  # Limite massimo di accelerazione audio
        self.embed_srt = ctk.BooleanVar(value=False)   # Embed SRT nel video finale

        # Layout principale
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(10, weight=1)

        # Titolo Applicazione
        self.label_title = ctk.CTkLabel(self, text="ꑭ AI VIDEO TRANSLATOR PRO v1.8 ꑭ",
                                        font=("Roboto", 24, "bold"), text_color="#3b8ed0")
        self.label_title.grid(row=0, column=0, padx=20, pady=30)

        # ----------------------------------------------------------------------
        # FRAME INPUT (Selezione File)
        # ----------------------------------------------------------------------
        self.input_frame = ctk.CTkFrame(self)
        self.input_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.input_frame.grid_columnconfigure(1, weight=1)

        # Campo File SRT
        ctk.CTkLabel(self.input_frame, text="File SRT:", width=120).grid(row=0, column=0, padx=10, pady=15)
        self.entry_srt = ctk.CTkEntry(self.input_frame)
        self.entry_srt.grid(row=0, column=1, padx=10, pady=15, sticky="ew")
        ctk.CTkButton(self.input_frame, text="Sfoglia", width=80, 
                      command=lambda: self.browse_file(self.entry_srt, "*.srt")).grid(row=0, column=2, padx=10)

        # Campo Video Originale
        ctk.CTkLabel(self.input_frame, text="Video Orig:", width=120).grid(row=1, column=0, padx=10, pady=15)
        self.entry_vid = ctk.CTkEntry(self.input_frame)
        self.entry_vid.grid(row=1, column=1, padx=10, pady=15, sticky="ew")
        ctk.CTkButton(self.input_frame, text="Sfoglia", width=80, 
                      command=lambda: self.browse_file(self.entry_vid, "*.mp4")).grid(row=1, column=2, padx=10)

        # Campo Destinazione Salvataggio
        ctk.CTkLabel(self.input_frame, text="Salva In:", width=120).grid(row=2, column=0, padx=10, pady=15)
        self.entry_out = ctk.CTkEntry(self.input_frame)
        self.entry_out.grid(row=2, column=1, padx=10, pady=15, sticky="ew")
        ctk.CTkButton(self.input_frame, text="Sfoglia", width=80, command=self.browse_save).grid(row=2, column=2, padx=10)

        # ----------------------------------------------------------------------
        # FRAME LINGUE (Selezione AI)
        # ----------------------------------------------------------------------
        self.lang_frame = ctk.CTkFrame(self)
        self.lang_frame.grid(row=2, column=0, padx=20, pady=15, sticky="ew")
        ctk.CTkLabel(self.lang_frame, text="SINTESI NEURALE:", font=("Roboto", 14, "bold")).pack(side="left", padx=20, pady=10)
        
        langs = ["en", "it", "es", "fr", "de", "zh", "uk", "sv", "nl"]
        self.src_menu = ctk.CTkOptionMenu(self.lang_frame, values=langs, variable=self.src_lang, width=70)
        self.src_menu.pack(side="left", padx=5, pady=10)
        self.btn_detect = ctk.CTkButton(self.lang_frame, text="🔍", width=30, command=self.auto_detect_language)
        self.btn_detect.pack(side="left", padx=(0, 5), pady=10)
        ctk.CTkLabel(self.lang_frame, text="➔").pack(side="left", padx=5)
        self.tgt_menu = ctk.CTkOptionMenu(self.lang_frame, values=langs, variable=self.tgt_lang, width=70)
        self.tgt_menu.pack(side="left", padx=5, pady=10)
        
        ctk.CTkLabel(self.lang_frame, text="Voce:", font=("Roboto", 12)).pack(side="left", padx=(20, 5))
        self.gender_menu = ctk.CTkOptionMenu(self.lang_frame, values=["male", "female"], variable=self.gender, width=70)
        self.gender_menu.pack(side="left", padx=5, pady=10)
        ctk.CTkButton(self.lang_frame, text="🚀 Download Video", width=120, fg_color="#0919ff", hover_color="#090b72", command=self.open_downloader).pack(side="left", padx=5, pady=10)
        ctk.CTkButton(self.lang_frame, text="⚙️ FFmpeg", width=80, command=self.set_ffmpeg).pack(side="left", padx=20)

        # ----------------------------------------------------------------------
        # FRAME MODALITÀ EXPORT
        # ----------------------------------------------------------------------
        self.mode_frame = ctk.CTkFrame(self)
        self.mode_frame.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        ctk.CTkLabel(self.mode_frame, text="Modalità Esportazione:", font=("Roboto", 14, "bold")).pack(side="left", padx=20, pady=10)
        self.rb_video = ctk.CTkRadioButton(self.mode_frame, text="Video Completo (Mix Neural)", variable=self.output_mode, value="video")
        self.rb_video.pack(side="left", padx=10, pady=10)
        self.rb_audio = ctk.CTkRadioButton(self.mode_frame, text="Solo Audio Tradotto", variable=self.output_mode, value="audio")
        self.rb_audio.pack(side="left", padx=10, pady=10)

        # ----------------------------------------------------------------------
        # FRAME SINCRONIZZAZIONE E VELOCITÀ
        # ----------------------------------------------------------------------
        self.sync_frame = ctk.CTkFrame(self)
        self.sync_frame.grid(row=4, column=0, padx=20, pady=5, sticky="ew")

        self.cb_force_sync = ctk.CTkCheckBox(self.sync_frame, text="Forza Sincronizzazione (Ignora Limite)", 
                                              variable=self.force_sync, font=("Roboto", 12))
        self.cb_force_sync.pack(side="left", padx=20, pady=10)

        self.speed_label = ctk.CTkLabel(self.sync_frame, text=f"Limite Velocità: {self.max_speed_val.get():.1f}x", font=("Roboto", 12))
        self.speed_label.pack(side="left", padx=(20, 5), pady=10)
        self.slider_speed = ctk.CTkSlider(self.sync_frame, from_=1.0, to=3.0, variable=self.max_speed_val, 
                                           command=lambda v: self.speed_label.configure(text=f"Limite Velocità: {float(v):.1f}x"))
        self.slider_speed.pack(side="left", padx=5, pady=10)

        self.cb_embed_srt = ctk.CTkCheckBox(self.sync_frame, text="Embed SRT nel video", 
                                              variable=self.embed_srt, font=("Roboto", 12))
        self.cb_embed_srt.pack(side="left", padx=20, pady=10)

        # ----------------------------------------------------------------------
        # FRAME VOLUMI (Mixaggio Audio)
        # ----------------------------------------------------------------------
        self.vol_frame = ctk.CTkFrame(self)
        self.vol_frame.grid(row=5, column=0, padx=20, pady=5, sticky="ew")
        
        # Volume Originale
        self.vol_orig_label = ctk.CTkLabel(self.vol_frame, text=f"Volume Originale: {self.vol_orig.get():.1f}", font=("Roboto", 12))
        self.vol_orig_label.pack(side="left", padx=(20, 5), pady=10)
        self.slider_orig = ctk.CTkSlider(self.vol_frame, from_=0, to=1, variable=self.vol_orig, 
                                          command=lambda v: self.vol_orig_label.configure(text=f"Volume Originale: {float(v):.1f}"))
        self.slider_orig.pack(side="left", padx=5, pady=10)

        # Volume Tradotto
        self.vol_trans_label = ctk.CTkLabel(self.vol_frame, text=f"Volume Tradotto: {self.vol_trans.get():.1f}", font=("Roboto", 12))
        self.vol_trans_label.pack(side="left", padx=(20, 5), pady=10)
        self.slider_trans = ctk.CTkSlider(self.vol_frame, from_=0, to=2, variable=self.vol_trans, 
                                           command=lambda v: self.vol_trans_label.configure(text=f"Volume Tradotto: {float(v):.1f}"))
        self.slider_trans.pack(side="left", padx=5, pady=10)

        # ----------------------------------------------------------------------
        # BATCH MODE
        # ----------------------------------------------------------------------
        self.batch_frame = ctk.CTkFrame(self)
        self.batch_frame.grid(row=6, column=0, padx=20, pady=5, sticky="ew")
        self.batch_frame.grid_columnconfigure(0, weight=1)

        self.batch_label = ctk.CTkLabel(self.batch_frame, text="BATCH MODE:", font=("Roboto", 14, "bold"))
        self.batch_label.pack(side="left", padx=20, pady=10)

        self.batch_list = ctk.CTkTextbox(self.batch_frame, height=50, font=("Consolas", 11))
        self.batch_list.pack(side="left", fill="x", expand=True, padx=5, pady=10)
        self.batch_list.insert("end", "File in coda...\n")
        self.batch_list.configure(state="disabled")

        self.btn_batch_add = ctk.CTkButton(self.batch_frame, text="+ Aggiungi", width=90,
                                            command=self.batch_add_current)
        self.btn_batch_add.pack(side="left", padx=2, pady=10)

        self.btn_batch_clear = ctk.CTkButton(self.batch_frame, text="X Svuota", width=80,
                                              fg_color="#555555", command=self.batch_clear)
        self.btn_batch_clear.pack(side="left", padx=2, pady=10)

        self.btn_batch_start = ctk.CTkButton(self.batch_frame, text="▶ Avvia Batch", width=100,
                                               fg_color="#0a6e0a", hover_color="#0c8c0c",
                                               command=self.start_batch)
        self.btn_batch_start.pack(side="left", padx=2, pady=10)

        # ----------------------------------------------------------------------
        # PULSANTE AVVIO E PROGRESSO
        # ----------------------------------------------------------------------
        self.btn_start = ctk.CTkButton(self, text="AVVIA TRADUZIONE NEURALE", 
                                        fg_color="#042eeb", hover_color="#1f2eff", 
                                        font=("Roboto", 18, "bold"), command=self.start_production)
        self.btn_start.grid(row=7, column=0, padx=20, pady=25, sticky="ew")

        self.progress_frame = ctk.CTkFrame(self)
        self.progress_frame.grid(row=8, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.progress_frame.grid_columnconfigure(0, weight=1)

        self.stage_labels = []
        stages = ["Parsing SRT", "Traduzione", "TTS Neurale", "Stretching Audio", "Mixaggio"]
        for i, stage in enumerate(stages):
            lbl = ctk.CTkLabel(self.progress_frame, text=f"● {stage}", font=("Roboto", 11), text_color="gray")
            lbl.grid(row=0, column=i, padx=5, pady=(15, 5))
            self.stage_labels.append(lbl)

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.grid(row=1, column=0, columnspan=5, padx=20, pady=(5, 5), sticky="ew")
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(self.progress_frame, text="Pronto per l'elaborazione neurale", font=("Roboto", 12))
        self.progress_label.grid(row=2, column=0, columnspan=5, padx=20, pady=(0, 15))

        self.current_stage = ctk.StringVar(value="idle")

        # Log Filter
        self.log_filter_frame = ctk.CTkFrame(self)
        self.log_filter_frame.grid(row=9, column=0, padx=20, pady=(0, 2), sticky="ew")
        ctk.CTkLabel(self.log_filter_frame, text="Filtro Log:", font=("Roboto", 11)).pack(side="left", padx=10, pady=5)
        self.log_filter_var = ctk.StringVar(value="All")
        self.log_filter_btn = ctk.CTkSegmentedButton(
            self.log_filter_frame,
            values=["All", "Info", "Warn", "Error"],
            variable=self.log_filter_var,
            command=self.filter_logs,
            font=("Roboto", 11)
        )
        self.log_filter_btn.pack(side="left", padx=5, pady=5)

        # Log Console (Output testuale)
        self.log_text = ctk.CTkTextbox(self, font=("Consolas", 12))
        self.log_text.grid(row=10, column=0, padx=20, pady=(0, 20), sticky="nsew")

        self.bind_dnd()

    # ----------------------------------------------------------------------
    # METODI DI SUPPORTO GUI
    # ----------------------------------------------------------------------
    def update_log(self, message):
        """
        Aggiunge un messaggio al log con timestamp e livello.
        Mantiene una cronologia completa per supportare il filtro visivo.
        """
        if '❌' in message or 'Errore' in message or 'errore' in message:
            level = "ERROR"
        elif '⚠️' in message or 'Attenzione' in message or 'tentativo' in message.lower():
            level = "WARN"
        else:
            level = "INFO"

        timestamp = datetime.now().strftime('%H:%M:%S')
        entry = (timestamp, level, message)
        self._log_history.append(entry)

        current_filter = self.log_filter_var.get()
        if current_filter == "All" or current_filter == level:
            self.log_text.insert("end", f"[{timestamp}] {message}\n")
            self.log_text.see("end")

    def filter_logs(self, level):
        """Filtra i messaggi di log per livello."""
        self.log_text.delete("1.0", "end")
        for timestamp, msg_level, message in self._log_history:
            if level == "All" or msg_level == level:
                self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")

    def update_progress(self, value, text):
        """
        Aggiorna la barra di progresso e il testo associato.
        IMPLEMENTAZIONE THREAD-SAFE: 
        Poiché Tkinter non è thread-safe, utilizziamo `self.after(0, ...)` per schedulare 
        l'aggiornamento della UI sul thread principale (Main Thread), evitando crash o comportamenti instabili.
        """
        self.after(0, lambda: self._set_progress(value, text))

    def _set_progress(self, value, text):
        self.progress_bar.set(value)
        self.progress_label.configure(text=text)
        
        stage_map = {
            "idle": -1,
            "parsing": 0,
            "translation": 1,
            "tts": 2,
            "stretching": 3,
            "mixing": 4
        }
        stage_idx = stage_map.get(self.current_stage.get(), -1)
        for i, lbl in enumerate(self.stage_labels):
            if i == stage_idx:
                lbl.configure(text_color="#3b8ed0")
            else:
                lbl.configure(text_color="gray")

    def drop_file(self, event):
        """Gestisce drag-and-drop di file, routing automatico per estensione."""
        try:
            files = event.data
            if isinstance(files, str):
                files = files.split()
            for f in files:
                if os.path.isfile(f):
                    ext = os.path.splitext(f)[1].lower()
                    if ext == ".srt":
                        self.entry_srt.delete(0, "end")
                        self.entry_srt.insert(0, f)
                    elif ext in (".mp4", ".avi", ".mkv", ".webm"):
                        self.entry_vid.delete(0, "end")
                        self.entry_vid.insert(0, f)
                    else:
                        self.entry_out.delete(0, "end")
                        self.entry_out.insert(0, f)
                    self.update_log(f"📥 File drag-and-drop: {f}")
                    break
        except Exception as e:
            self.update_log(f"❌ Drag-and-drop error: {e}")

    def bind_dnd(self):
        """Inizializza drag-and-drop support."""
        try:
            self.event_add("<DND>", "<Drop>")
            self.bind("<DND>", lambda e: self.drop_file(e))
        except Exception:
            pass

    def browse_file(self, entry, ext):
        """Apre una finestra di dialogo per selezionare un file."""
        path = filedialog.askopenfilename(filetypes=[(f"Files {ext}", ext)])
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)

    def browse_save(self):
        """Apre una finestra di dialogo per scegliere dove salvare il file finale."""
        ext = ".mp4" if self.output_mode.get() == "video" else ".mp3"
        path = filedialog.asksaveasfilename(defaultextension=ext, 
                                               filetypes=[("Video File", "*.mp4"), ("Audio File", "*.mp3")])
        if path:
            self.entry_out.delete(0, "end")
            self.entry_out.insert(0, path)

    def open_downloader(self):
        """Apre il modulo Multi-Video Downloader in una finestra separata."""
        YoutubeDownloaderGUI()

    def set_ffmpeg(self):
        """Apre una finestra di impostazioni per la configurazione di FFmpeg."""
        settings_win = ctk.CTkToplevel(self)
        settings_win.title("Configurazione FFmpeg")
        settings_win.geometry("400x200")
        settings_win.attributes("-topmost", True) # Mantiene la finestra sopra l'app principale

        ctk.CTkLabel(settings_win, text="Come desideri configurare FFmpeg?", font=("Roboto", 14)).pack(pady=20)

        # Opzione 1: Seleziona file manualmente
        def select_exe():
            path = filedialog.askopenfilename(filetypes=[("Executable", "*.exe"), ("All Files", "*.*")])
            if path:
                config.FFMPEG_BIN = path
                config.save_ffmpeg_path(path)
                messagebox.showinfo("Configurazione", f"Percorso FFmpeg aggiornato:\n{path}")
                settings_win.destroy()

        # Opzione 2: Scarica e installa in una cartella specifica
        def download_and_install():
            path = filedialog.askdirectory(title="Scegli la cartella per l'installazione di FFmpeg")
            if path:
                config.save_ffmpeg_install_dir(path)
                messagebox.showinfo("Download", "L'operazione verrà avviata in background.\nControlla il log principale.")
                settings_win.destroy()

                def run_download():
                    self.update_log(f"Avvio download/aggiornamento FFmpeg in: {path}...")
                    success, msg = config.check_and_update_ffmpeg(custom_install_dir=path)
                    if success:
                        self.update_log(f"✅ {msg}")
                    else:
                        self.update_log(f"❌ {msg}")

                threading.Thread(target=run_download, daemon=True).start()

        ctk.CTkButton(settings_win, text="Scegli Esguibile (.exe)", command=select_exe).pack(pady=10)
        ctk.CTkButton(settings_win, text="Scarica e Installa in Cartella", command=download_and_install).pack(pady=10)

    def auto_detect_language(self):
        """Rileva automaticamente la lingua dal file SRT."""
        srt = self.entry_srt.get().strip()
        if not srt:
            messagebox.showinfo("Auto-Detect", "Seleziona prima un file SRT")
            return

        def detect_task():
            self.update_log("🔍 Rilevamento lingua in corso...")
            try:
                text_sample = ""
                with open(srt, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    blocks = content.split('\n\n')
                    for block in blocks:
                        lines = block.split('\n')
                        if len(lines) >= 3 and ' --> ' in lines[1]:
                            text_sample = ' '.join(lines[2:]).strip()
                            if len(text_sample) > 50:
                                break

                if text_sample:
                    detected = self.logic.detect_language(text_sample)
                    if detected:
                        self.after(0, lambda: self._set_detected_lang(detected))
                    else:
                        self.update_log("⚠️ Installare 'pip install langdetect' per il rilevamento automatico")
                else:
                    self.update_log("⚠️ Nessun testo valido trovato nell'SRT")
            except Exception as e:
                self.update_log(f"❌ Errore rilevamento: {e}")

        threading.Thread(target=detect_task, daemon=True).start()

    def _set_detected_lang(self, lang):
        """Imposta la lingua rilevata nel menu a tendina."""
        langs = ["en", "it", "es", "fr", "de", "zh", "uk", "sv", "nl"]
        if lang in langs:
            self.src_lang.set(lang)
            self.update_log(f"✅ Lingua sorgente impostata a: {lang.upper()}")
        else:
            self.update_log(f"⚠️ Lingua '{lang}' non supportata, impostazione manuale richiesta")

    def batch_add_current(self):
        """Aggiunge la configurazione corrente alla coda batch."""
        srt = self.entry_srt.get().strip()
        vid = self.entry_vid.get().strip()
        out = self.entry_out.get().strip()
        if not srt or not out:
            messagebox.showerror("Errore", "Inserisci almeno SRT e destinazione per aggiungere alla coda")
            return

        if not hasattr(self, '_batch_processor') or self._batch_processor is None:
            from logic import BatchProcessor
            self._batch_processor = BatchProcessor(self.update_log, progress_callback=self.update_progress)
            self._batch_processor.clear_queue()

        mode = self.output_mode.get()
        if mode == "video" and not vid:
            self._batch_processor.add_to_queue(
                srt, "", out, self.src_lang.get(), self.tgt_lang.get(),
                self.gender.get(), self.force_sync.get(), self.max_speed_val.get(),
                self.vol_orig.get(), self.vol_trans.get(), "audio", self.embed_srt.get()
            )
        else:
            self._batch_processor.add_to_queue(
                srt, vid, out, self.src_lang.get(), self.tgt_lang.get(),
                self.gender.get(), self.force_sync.get(), self.max_speed_val.get(),
                self.vol_orig.get(), self.vol_trans.get(), mode, self.embed_srt.get()
            )

        self._refresh_batch_list()

    def _refresh_batch_list(self):
        """Aggiorna la visualizzazione della coda batch."""
        self.batch_list.configure(state="normal")
        self.batch_list.delete("1.0", "end")
        if hasattr(self, '_batch_processor') and self._batch_processor and self._batch_processor.queue:
            for i, item in enumerate(self._batch_processor.queue):
                self.batch_list.insert("end", f"{i+1}. {os.path.basename(item['srt'])} → {os.path.basename(item['output'])}\n")
        else:
            self.batch_list.insert("end", "Nessun file in coda.\n")
        self.batch_list.configure(state="disabled")

    def batch_clear(self):
        """Svuota la coda batch."""
        if hasattr(self, '_batch_processor') and self._batch_processor:
            self._batch_processor.clear_queue()
        self._refresh_batch_list()
        self.update_log("🗑️ Coda batch svuotata")

    def start_batch(self):
        """Avvia l'elaborazione batch."""
        if not hasattr(self, '_batch_processor') or not self._batch_processor or not self._batch_processor.queue:
            messagebox.showinfo("Batch", "Nessun file in coda. Aggiungi file con '+ Aggiungi'")
            return

        if self._batch_processor.is_running:
            messagebox.showinfo("Batch", "Elaborazione batch già in corso")
            return

        def batch_task():
            self.btn_batch_start.configure(state="disabled", text="⏳ In corso...")
            self.btn_start.configure(state="disabled", text="Batch in corso...")
            self._batch_processor.process_all(self.logic)
            self.btn_batch_start.configure(state="normal", text="▶ Avvia Batch")
            self.btn_start.configure(state="normal", text="AVVIA PRODUZIONE NEURALE")
            self._batch_processor.queue.clear()
            self._refresh_batch_list()
            messagebox.showinfo("Batch", "Elaborazione batch completata!")

        threading.Thread(target=batch_task, daemon=True).start()

    def start_production(self):
        """
        Orchestratore del processo di produzione neurale.

        FLUSSO TECNICO:
        1. Validazione degli input (controlla che i path obbligatori siano presenti).
        2. Creazione di un file temporaneo per l'audio tradotto (`tempfile`).
        3. Avvio di un Thread separato: questo è fondamentale per evitare il 'freeze' 
           della GUI durante le chiamate API (Traduzione e TTS) e l'elaborazione FFmpeg.
        4. Gestione della pipeline: Generazione Audio -> Mixaggio Video (opzionale) -> Pulizia Temporanei.
        """
        srt = self.entry_srt.get().strip()
        vid = self.entry_vid.get().strip()
        out = self.entry_out.get().strip()
        src = self.src_lang.get()
        tgt = self.tgt_lang.get()
        gender = self.gender.get()
        mode = self.output_mode.get()

        # Validazione minima input
        if not srt or not out:
            messagebox.showerror("Errore", "Inserisci almeno il file SRT e la destinazione!")
            return
        if mode == "video" and not vid:
            messagebox.showerror("Errore", "Seleziona il Video Originale per il mixaggio!")
            return

        def task():
            # Disabilita pulsante durante l'elaborazione
            self.btn_start.configure(state="disabled", text="Sintesi Neurale in corso...")
            self.progress_bar.set(0)
            self.progress_label.configure(text="Inizio elaborazione neurale...")

            # Creazione file audio temporaneo per la traccia tradotta
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf_final:
                audio_tmp = tf_final.name
            
            try:
                f_sync = self.force_sync.get()
                m_speed = self.max_speed_val.get()

                self.current_stage.set("parsing")
                self.update_progress(0.1, "Parsing SRT...")
                
                if self.logic.generate_synced_audio(srt, audio_tmp, src_lang=src, tgt_lang=tgt, gender=gender, force_sync=f_sync, max_speed=m_speed):
                    if mode == "video":
                        self.current_stage.set("mixing")
                        self.update_progress(0.9, "Mixaggio video...")
                        # 2. Mixaggio con video originale se richiesto
                        v_orig = self.vol_orig.get()
                        v_trans = self.vol_trans.get()
                        e_srt = self.embed_srt.get()
                        self.logic.merge_audio_video_mixed(vid, audio_tmp, out, vol_orig=v_orig, vol_trans=v_trans, embed_srt=e_srt)
                        messagebox.showinfo("Successo", f"Video Tradotto con Voci Neurali ({src} -> {tgt})!")
                    else:
                        # Esporta solo l'audio finale
                        shutil.copy(audio_tmp, out)
                        messagebox.showinfo("Successo", f"Audio Neurale esportato correttamente!")
                else:
                    messagebox.showerror("Errore", "Si è verificato un errore critico durante la generazione dell'audio neurale.")
            except Exception as e:
                self.update_log(f"❌ Errore imprevisto nel task: {e}")
                messagebox.showerror("Errore", f"Errore imprevisto: {e}")
            finally:
                # Pulizia file temporaneo audio finale
                if os.path.exists(audio_tmp): 
                    os.remove(audio_tmp)
                self.current_stage.set("idle")
                self.progress_bar.set(0)
                self.progress_label.configure(text="Pronto per l'elaborazione neurale")
                self.btn_start.configure(state="normal", text="AVVIA PRODUZIONE NEURALE")

        # Esecuzione in Thread separato
        threading.Thread(target=task, daemon=True).start()