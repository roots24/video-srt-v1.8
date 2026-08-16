import customtkinter as ctk
from tkinter import filedialog, messagebox, Listbox
from datetime import datetime
import subprocess
import sys
import threading
import os
import tempfile
import config

# Importiamo la logica di business e le configurazioni
from logic import VideoTranslatorLogic, ProcessingGuard
from video_downloader_pro import YoutubeDownloaderGUI

# Drag-and-drop opzionale: senza tkinterdnd2 la GUI resta funzionante
# (senza DnD), con un avviso nel log.
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _HAS_DND = True
except ImportError:
    DND_FILES = None
    _HAS_DND = False

# I metodi Python del DnD (drop_target_register/dnd_bind) sono forniti dal
# mixin DnDWrapper: senza ereditarietà `_require()` carica solo la parte Tcl
# e i metodi non esistono sulla finestra
_APP_BASES = (ctk.CTk, TkinterDnD.DnDWrapper) if _HAS_DND else (ctk.CTk,)

# ==============================================================================
# INTERFACCIA GRAFICA (GUI)
# ==============================================================================

class App(*_APP_BASES):
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
        # Guardia condivisa tra produzione singola e batch: impedisce due
        # pipeline parallele che usano FFmpeg/TTS e potrebbero scrivere
        # sugli stessi output (file corrotti o crash)
        self._processing_active = ProcessingGuard()

        # Configurazione finestra principale (versione da config.APP_VERSION)
        self.title(f"ꑭ Ultimate Video Translator AI PRO v{config.APP_VERSION} - Neural Edition by Banderivez ꑭ")
        self.geometry("850x950")
        
        # Inizializzazione del backend (VideoTranslatorLogic)
        # Passiamo i metodi della GUI come callback per log e progresso
        self.logic = VideoTranslatorLogic(self.update_log, progress_callback=self.update_progress)

        self._init_state_vars()
        self._init_layout()
        self._build_title()
        self._build_input_frame()
        self._build_language_frame()
        self._build_mode_frame()
        self._build_sync_frame()
        self._build_volumes_frame()
        self._build_batch_frame()
        self._build_progress_section()
        self._build_log_area()
        self._init_dnd()

    def _init_state_vars(self):
        """Variabili di stato (binding dei dati)."""
        self.src_lang = ctk.StringVar(value="uk")      # Lingua sorgente predefinita: Ucraino
        self.tgt_lang = ctk.StringVar(value="it")      # Lingua target predefinita: Italiano
        self.gender = ctk.StringVar(value="male")      # Selezione voce maschile/femminile
        self.output_mode = ctk.StringVar(value="video") # Modalità di export (video o solo audio)
        self.vol_orig = ctk.DoubleVar(value=0.4)       # Volume audio originale (background)
        self.vol_trans = ctk.DoubleVar(value=1.0)      # Volume audio tradotto (foreground)
        self.force_sync = ctk.BooleanVar(value=False)  # Se True, ignora i limiti di velocità audio
        self.max_speed_val = ctk.DoubleVar(value=1.5)  # Limite massimo di accelerazione audio
        self.embed_srt = ctk.BooleanVar(value=False)   # Embed SRT nel video finale

    def _init_layout(self):
        """Layout principale."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(10, weight=1)

    def _build_title(self):
        """Titolo Applicazione."""
        self.label_title = ctk.CTkLabel(self, text=f"ꑭ AI VIDEO TRANSLATOR PRO v{config.APP_VERSION} ꑭ",
                                        font=("Roboto", 24, "bold"), text_color="#3b8ed0")
        self.label_title.grid(row=0, column=0, padx=20, pady=30)

    def _build_input_frame(self):
        """FRAME INPUT (Selezione File)."""
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

    def _build_language_frame(self):
        """FRAME LINGUE (Selezione AI)."""
        self.lang_frame = ctk.CTkFrame(self)
        self.lang_frame.grid(row=2, column=0, padx=20, pady=15, sticky="ew")
        ctk.CTkLabel(self.lang_frame, text="SINTESI NEURALE:", font=("Roboto", 14, "bold")).pack(side="left", padx=20, pady=10)
        
        langs = config.SUPPORTED_LANGS
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
        ctk.CTkButton(self.lang_frame, text="📝 SRT Multi-Lingua", width=120, fg_color="#7a5c00",
                      hover_color="#8f6d00", command=self.export_multilang_srt).pack(side="left", padx=5, pady=10)
        ctk.CTkButton(self.lang_frame, text="🎧 Preview", width=80, fg_color="#3b2d6a",
                      hover_color="#4b3d7a", command=self.open_preview_window).pack(side="left", padx=5, pady=10)

    def _build_mode_frame(self):
        """FRAME MODALITÀ EXPORT."""
        self.mode_frame = ctk.CTkFrame(self)
        self.mode_frame.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        ctk.CTkLabel(self.mode_frame, text="Modalità Esportazione:", font=("Roboto", 14, "bold")).pack(side="left", padx=20, pady=10)
        self.rb_video = ctk.CTkRadioButton(self.mode_frame, text="Video Completo (Mix Neural)", variable=self.output_mode, value="video",
                                           command=self._on_mode_changed)
        self.rb_video.pack(side="left", padx=10, pady=10)
        self.rb_audio = ctk.CTkRadioButton(self.mode_frame, text="Solo Audio Tradotto", variable=self.output_mode, value="audio",
                                           command=self._on_mode_changed)
        self.rb_audio.pack(side="left", padx=10, pady=10)

    def _build_sync_frame(self):
        """FRAME SINCRONIZZAZIONE E VELOCITÀ."""
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
        self._on_mode_changed()

    def _build_volumes_frame(self):
        """FRAME VOLUMI (Mixaggio Audio)."""
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

    def _build_batch_frame(self):
        """BATCH MODE."""
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

    def _build_progress_section(self):
        """PULSANTE AVVIO E PROGRESSO."""
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

    def _build_log_area(self):
        """Filtro Log e Console di output."""
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

    def _init_dnd(self):
        """Inizializzazione drag-and-drop: _require() DEVE precedere bind_dnd(),
        altrimenti i metodi drop_target_register/dnd_bind non esistono ancora."""
        if _HAS_DND:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
            except Exception as e:
                self.update_log(f"⚠️ Inizializzazione drag-and-drop fallita: {e}")
        self.bind_dnd()

    # ----------------------------------------------------------------------
    # METODI DI SUPPORTO GUI
    # ----------------------------------------------------------------------
    def update_log(self, message):
        """
        Aggiunge un messaggio al log con timestamp e livello.

        THREAD-SAFE: il backend (logic.py) chiama `self.log` dai propri worker
        thread, quindi la scrittura sui widget Tk viene schedulata sul main
        thread tramite `self.after(0, ...)`.
        """
        self.after(0, lambda: self._append_log(message))

    def _append_log(self, message):
        """Scrittura effettiva del log (eseguita solo sul main thread)."""
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

        # Rilevamento dello stadio in base al testo del progresso
        # (il backend non conosce gli stadi della GUI)
        text_lower = (text or '').lower()
        if 'parsing' in text_lower or 'analisi srt' in text_lower:
            stage = 'parsing'
        elif 'traduzion' in text_lower:
            stage = 'translation'
        elif 'neurale' in text_lower or 'tts' in text_lower or 'sintesi' in text_lower or 'elaborazione' in text_lower:
            stage = 'tts'
        elif 'stretch' in text_lower or 'sincronizzazion' in text_lower:
            stage = 'stretching'
        elif 'mixaggi' in text_lower or 'video finale' in text_lower:
            stage = 'mixing'
        elif 'batch' in text_lower:
            # Tra un item e l'altro del batch nessuno stadio è attivo
            stage = 'idle'
        else:
            stage = self.current_stage.get()

        stage_idx = stage_map.get(stage, -1)
        for i, lbl in enumerate(self.stage_labels):
            if i == stage_idx:
                lbl.configure(text_color="#3b8ed0")
            else:
                lbl.configure(text_color="gray")

    def drop_file(self, event):
        """Gestisce drag-and-drop di file, routing automatico per estensione."""
        try:
            raw = event.data
            # tk.splitlist gestisce correttamente i path con spazi
            # (es. {C:/My Folder/a.srt}) che shlex non sa decodificare
            files = self.tk.splitlist(raw) if isinstance(raw, str) else list(raw)
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
        """Inizializza drag-and-drop: reale con tkinterdnd2, altrimenti disabilitato."""
        if not _HAS_DND or not hasattr(self, 'drop_target_register'):
            self.update_log("ℹ️ Drag-and-drop disabilitato: installa tkinterdnd2 (pip install tkinterdnd2)")
            return
        try:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', lambda e: self.drop_file(e))
            self.update_log("✅ Drag-and-drop attivo: trascina file SRT/video sull'app")
        except Exception as e:
            self.update_log(f"❌ Drag-and-drop non disponibile: {e}")

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

    def _on_mode_changed(self):
        """In modalità solo-audio l'embed SRT non ha effetto: disabilita la checkbox."""
        if hasattr(self, 'cb_embed_srt'):
            if self.output_mode.get() == "video":
                self.cb_embed_srt.configure(state="normal")
            else:
                self.cb_embed_srt.configure(state="disabled")
                self.embed_srt.set(False)

    def _open_with_system(self, path):
        """Apre un file con l'applicazione di default del sistema (cross-platform:
        os.startfile esiste solo su Windows)."""
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])

    def open_downloader(self):
        """Apre il modulo Multi-Video Downloader in una finestra separata."""
        YoutubeDownloaderGUI()

    def open_preview_window(self):
        """Preview Before/After (#8): ascolta l'audio del segmento originale
        (estratto dal video) e quello tradotto con la voce neurale corrente,
        prima di lanciare l'export completo."""
        srt = self.entry_srt.get().strip()
        if not srt:
            messagebox.showerror("Errore", "Seleziona prima un file SRT")
            return

        segments, invalid = self.logic.parse_srt_file(srt)
        if not segments:
            messagebox.showerror("Errore", "Nessun segmento SRT valido nel file selezionato")
            return

        vid = self.entry_vid.get().strip()
        win = ctk.CTkToplevel(self)
        win.title("🎧 Preview Before / After")
        win.geometry("820x600")
        win.attributes("-topmost", True)

        info_text = (f"SRT: {os.path.basename(srt)}  |  {len(segments)} segmenti"
                     + (f"  |  Video: {os.path.basename(vid)}" if vid else "  |  Nessun video: Preview Originale disattivata"))
        ctk.CTkLabel(win, text=info_text, font=("Roboto", 12)).pack(pady=(14, 4))
        ctk.CTkLabel(win, text=f"Seleziona un segmento e confronta l'audio (trad: {self.tgt_lang.get().upper()}, {self.gender.get()})",
                     font=("Roboto", 11), text_color="gray").pack(pady=(0, 8))

        # Area testi (originale | traduzione)
        text_frame = ctk.CTkFrame(win)
        text_frame.pack(fill="x", padx=15, pady=4)
        text_frame.grid_columnconfigure(0, weight=1)
        text_frame.grid_columnconfigure(1, weight=1)
        text_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(text_frame, text="Testo Originale:", font=("Roboto", 12, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=(6, 2))
        ctk.CTkLabel(text_frame, text="Traduzione:", font=("Roboto", 12, "bold")).grid(row=0, column=1, sticky="w", padx=8, pady=(6, 2))
        orig_txt = ctk.CTkTextbox(text_frame, height=90, font=("Consolas", 12))
        orig_txt.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        transl_txt = ctk.CTkTextbox(text_frame, height=90, font=("Consolas", 12))
        transl_txt.grid(row=1, column=1, sticky="nsew", padx=8, pady=(0, 8))

        # Lista segmenti
        list_frame = ctk.CTkFrame(win)
        list_frame.pack(fill="both", expand=True, padx=15, pady=6)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)
        lb = Listbox(list_frame, font=("Consolas", 11), bg="#1e1e1e", fg="#e0e0e0",
                     selectbackground="#3b8ed0", selectforeground="white",
                     highlightthickness=0, activestyle="none", borderwidth=0)
        lb.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        scroll = ctk.CTkScrollbar(list_frame, command=lb.yview)
        scroll.grid(row=0, column=1, sticky="ns", pady=6)
        lb.configure(yscrollcommand=scroll.set)

        state = {"current": 0}

        def show_segment(event=None):
            sel = lb.curselection()
            idx = sel[0] if sel else state["current"]
            state["current"] = idx
            seg = segments[idx]
            orig_txt.delete("1.0", "end")
            orig_txt.insert("1.0", seg["text"])
            transl_txt.delete("1.0", "end")
            transl_txt.insert("1.0", "⏳ Traduzione in corso...")

            def do_translate():
                translated = self.logic.translate_text(seg["text"], self.src_lang.get(), self.tgt_lang.get())
                self.after(0, lambda t=translated: self._set_preview_translation(transl_txt, t))

            threading.Thread(target=do_translate, daemon=True).start()

        for i, seg in enumerate(segments):
            time_str = f"{self.logic.ms_to_srt_time(seg['start'])} → {self.logic.ms_to_srt_time(seg['start'] + seg['limit'])}"
            preview_text = seg["text"].replace("\n", " ")[:55]
            lb.insert("end", f"{i + 1:>4}. [{time_str}] {preview_text}")
        lb.bind("<<ListboxSelect>>", show_segment)
        lb.selection_set(0)
        show_segment()

        def play_original():
            if not vid:
                messagebox.showinfo("Preview", "Seleziona il Video Originale nell'app principale per ascoltare l'originale")
                return
            seg = segments[state["current"]]
            out = os.path.join(tempfile.gettempdir(), f"preview_orig_{seg['start']}.mp3")
            self.update_log(f"🎬 Estrazione audio originale segmento {state['current'] + 1}...")
            if not self.logic.extract_video_audio_segment(vid, out, seg["start"], seg["start"] + seg["limit"]):
                messagebox.showerror("Errore", "Estrazione audio originale fallita (verifica il video e FFmpeg)")
                return
            self._open_with_system(out)
            self.update_log(f"▶️ Preview ORIGINALE in riproduzione (segmento {state['current'] + 1})")

        def play_translated():
            seg = segments[state["current"]]
            tgt = self.tgt_lang.get()
            gender = self.gender.get()
            out = os.path.join(tempfile.gettempdir(), f"preview_tts_{seg['start']}_{tgt}_{gender}.mp3")
            self.update_log(f"⏳ Generazione voce neurale ({tgt.upper()}, {gender}) per preview...")

            def task():
                translated = self.logic.translate_text(seg["text"], self.src_lang.get(), tgt)
                if not translated:
                    self.update_log("❌ Preview: traduzione non disponibile")
                    self.after(0, lambda: messagebox.showerror("Errore", "Traduzione non disponibile per il segmento selezionato"))
                    return
                if not self.logic.preview_translated_audio(translated, tgt, gender, out):
                    self.update_log("❌ Preview: generazione TTS fallita")
                    self.after(0, lambda: messagebox.showerror("Errore", "Generazione TTS preview fallita (verifica connessione)"))
                    return
                self.after(0, lambda: (self._open_with_system(out),
                                       self.update_log(f"▶️ Preview TRADOTTA in riproduzione (segmento {state['current'] + 1})")))

            threading.Thread(target=task, daemon=True).start()

        btn_frame = ctk.CTkFrame(win)
        btn_frame.pack(fill="x", padx=15, pady=(4, 12))
        ctk.CTkButton(btn_frame, text="🔊 Play Originale", width=160, fg_color="#0a6e0a",
                      hover_color="#0c8c0c", command=play_original).pack(side="left", padx=6, pady=6)
        ctk.CTkButton(btn_frame, text="🔊 Play Tradotto", width=160, fg_color="#0919ff",
                      hover_color="#090b72", command=play_translated).pack(side="left", padx=6, pady=6)
        ctk.CTkButton(btn_frame, text="Chiudi", width=100, fg_color="#555555",
                      command=win.destroy).pack(side="right", padx=6, pady=6)

    def _set_preview_translation(self, textbox, translated):
        """Imposta il testo tradotto nella preview (main thread)."""
        textbox.delete("1.0", "end")
        textbox.insert("1.0", translated or "(traduzione non disponibile)")

    def export_multilang_srt(self):
        """Export dell'SRT tradotto in più lingue (#7): dialog con checkbox delle lingue."""
        srt = self.entry_srt.get().strip()
        if not srt:
            messagebox.showerror("Errore", "Seleziona prima un file SRT")
            return

        # Dialog di selezione delle lingue di destinazione
        win = ctk.CTkToplevel(self)
        win.title("Export SRT Multi-Lingua")
        win.geometry("320x430")
        win.attributes("-topmost", True)

        ctk.CTkLabel(win, text="Lingue di destinazione:", font=("Roboto", 13, "bold")).pack(pady=10)
        check_vars = {}
        for lang in config.SUPPORTED_LANGS:
            var = ctk.BooleanVar(value=False)
            check_vars[lang] = var
            ctk.CTkCheckBox(win, text=lang.upper(), variable=var).pack(anchor="w", padx=20, pady=2)

        def start():
            target_langs = [lang for lang, var in check_vars.items() if var.get()]
            if not target_langs:
                messagebox.showinfo("Export SRT", "Seleziona almeno una lingua")
                return
            win.destroy()

            # Template: cartella di destinazione (o cartella dell'SRT) + nome base del file
            out_dir = os.path.dirname(self.entry_out.get().strip()) or os.path.dirname(srt)
            base = os.path.splitext(os.path.basename(srt))[0]
            template = os.path.join(out_dir, base)

            def task():
                self.update_log(f"📝 Export SRT multi-lingua: {', '.join(l.upper() for l in target_langs)}")
                files = self.logic.export_translated_srt(
                    srt, template, self.src_lang.get(), target_langs,
                    progress_callback=self.update_progress)
                if files:
                    self.update_log(f"✅ {len(files)} file SRT generati: {', '.join(os.path.basename(f) for f in files)}")
                else:
                    self.update_log("❌ Export SRT multi-lingua fallito (vedi log)")

            threading.Thread(target=task, daemon=True).start()

        ctk.CTkButton(win, text="Esporta", fg_color="#0a6e0a", hover_color="#0c8c0c", command=start).pack(pady=15)
        ctk.CTkButton(win, text="Annulla", fg_color="#555555", command=win.destroy).pack(pady=5)

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
                config.set_ffmpeg_bin(path)
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
                text_sample = self.logic.extract_srt_text_sample(srt)
                if text_sample:
                    detected = self.logic.detect_language(text_sample)
                    if detected:
                        self.after(0, lambda: self._set_detected_lang(detected))
                    else:
                        self.update_log("⚠️ Rilevamento lingua non riuscito (verifica: pip install langdetect)")
                else:
                    self.update_log("⚠️ Nessun testo valido trovato nell'SRT")
            except Exception as e:
                self.update_log(f"❌ Errore rilevamento: {e}")

        threading.Thread(target=detect_task, daemon=True).start()

    def _set_detected_lang(self, lang):
        """Imposta la lingua rilevata nel menu a tendina."""
        langs = config.SUPPORTED_LANGS
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
            messagebox.showerror("Errore", "Seleziona il Video Originale per la modalità video!")
            return

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

        # Guardia condivisa: nessuna produzione singola può correre in parallelo
        # (due pipeline = FFmpeg/TTS concorrenti sullo stesso output)
        if not self._processing_active.try_begin():
            messagebox.showinfo("Batch", "Elaborazione già in corso, attendi il completamento")
            return

        if self._batch_processor.is_running:
            self._processing_active.end()
            messagebox.showinfo("Batch", "Elaborazione batch già in corso")
            return

        def batch_task():
            # Aggiornamenti UI schedulati sul main thread (thread-safety Tkinter)
            self.after(0, lambda: self.btn_batch_start.configure(state="disabled", text="⏳ In corso..."))
            self.after(0, lambda: self.btn_start.configure(state="disabled", text="Batch in corso..."))
            # Durante il batch si blocca anche la gestione della coda
            self.after(0, lambda: self.btn_batch_add.configure(state="disabled"))
            self.after(0, lambda: self.btn_batch_clear.configure(state="disabled"))
            try:
                success, total = self._batch_processor.process_all(self.logic)
                self._batch_processor.queue.clear()
                self.after(0, self._refresh_batch_list)
                # Riepilogo esito reale (prima diceva "completata" anche se tutti falliti)
                self.after(0, lambda: messagebox.showinfo(
                    "Batch",
                    f"Elaborazione batch completata: {success}/{total} successi."
                    + ("" if success == total else "\nVedi il log per i dettagli degli errori.")))
            except Exception as e:
                self.update_log(f"❌ Errore imprevisto nel batch: {e}")
            finally:
                # Sempre (successo, errore o eccezione): reabilita i pulsanti
                # e libera il flag condiviso
                self.after(0, lambda: self.btn_batch_start.configure(state="normal", text="▶ Avvia Batch"))
                self.after(0, lambda: self.btn_start.configure(state="normal", text="AVVIA TRADUZIONE NEURALE"))
                self.after(0, lambda: self.btn_batch_add.configure(state="normal"))
                self.after(0, lambda: self.btn_batch_clear.configure(state="normal"))
                self._processing_active.end()

        threading.Thread(target=batch_task, daemon=True).start()

    def start_production(self):
        """
        Orchestratore del processo di produzione neurale.

        FLUSSO TECNICO:
        1. Validazione degli input (controlla che i path obbligatori siano presenti).
        2. Avvio di un Thread separato: questo è fondamentale per evitare il 'freeze' 
           della GUI durante le chiamate API (Traduzione e TTS) e l'elaborazione FFmpeg.
        3. Esecuzione della pipeline unificata `logic.process()` (generazione audio + mixaggio).
        """
        # Lettura di TUTTI i valori GUI sul main thread prima dell'avvio del thread
        srt = self.entry_srt.get().strip()
        vid = self.entry_vid.get().strip()
        out = self.entry_out.get().strip()
        src = self.src_lang.get()
        tgt = self.tgt_lang.get()
        gender = self.gender.get()
        mode = self.output_mode.get()
        f_sync = self.force_sync.get()
        m_speed = self.max_speed_val.get()
        v_orig = self.vol_orig.get()
        v_trans = self.vol_trans.get()
        e_srt = self.embed_srt.get()

        # Validazione minima input
        if not srt or not out:
            messagebox.showerror("Errore", "Inserisci almeno il file SRT e la destinazione!")
            return
        if mode == "video" and not vid:
            messagebox.showerror("Errore", "Seleziona il Video Originale per il mixaggio!")
            return

        # UX: se l'SRT contiene segmenti non validi, avvisa prima di partire
        # (prima l'utente scopriva gli scarti solo nel log, a lavoro finito)
        if self._warn_invalid_segments(srt):
            return

        # Guardia condivisa: nessun batch può correre in parallelo alla produzione
        if not self._processing_active.try_begin():
            messagebox.showinfo("Info", "Elaborazione già in corso, attendi il completamento")
            return

        def task():
            # Disabilita i pulsanti di entrambe le modalità (UI sul main thread)
            self.after(0, lambda: self.btn_start.configure(state="disabled", text="Sintesi Neurale in corso..."))
            self.after(0, lambda: self.btn_batch_start.configure(state="disabled"))
            self.after(0, lambda: self.progress_bar.set(0))
            self.after(0, lambda: self.progress_label.configure(text="Inizio elaborazione neurale..."))

            try:
                self.after(0, lambda: self.current_stage.set("parsing"))
                self.update_progress(0.1, "Parsing SRT...")

                # Pipeline unificata (genera audio + mixaggio opzionale)
                ok, msg = self.logic.process(
                    srt, out, video_file=vid, src_lang=src, tgt_lang=tgt, gender=gender,
                    force_sync=f_sync, max_speed=m_speed,
                    vol_orig=v_orig, vol_trans=v_trans, mode=mode, embed_srt=e_srt
                )
                if ok:
                    success_msg = (f"Video Tradotto con Voci Neurali ({src} -> {tgt})!"
                                   if mode == "video" else "Audio Neurale esportato correttamente!")
                    self.after(0, lambda: messagebox.showinfo("Successo", success_msg))
                else:
                    self.after(0, lambda m=msg: messagebox.showerror("Errore", f"{m}. Controlla il log per i dettagli."))
            except Exception as e:
                self.update_log(f"❌ Errore imprevisto nel task: {e}")
                self.after(0, lambda: messagebox.showerror("Errore", f"Errore imprevisto: {e}"))
            finally:
                self.after(0, lambda: self.current_stage.set("idle"))
                self.after(0, lambda: self.progress_bar.set(0))
                self.after(0, lambda: self.progress_label.configure(text="Pronto per l'elaborazione neurale"))
                # Testo originale del pulsante (coerente con _build_progress_section)
                self.after(0, lambda: self.btn_start.configure(state="normal", text="AVVIA TRADUZIONE NEURALE"))
                self.after(0, lambda: self.btn_batch_start.configure(state="normal"))
                self._processing_active.end()

        # Esecuzione in Thread separato
        threading.Thread(target=task, daemon=True).start()

    def _warn_invalid_segments(self, srt_file):
        """Pre-check SRT: se ci sono segmenti non validi mostra askyesno.
        Ritorna True se l'utente annulla (la produzione non deve partire)."""
        try:
            _, invalid_count = self.logic.parse_srt_file(srt_file)
        except Exception as e:
            # Errore di lettura: la pipeline lo ri-segnalirà in modo esplicito
            self.update_log(f"⚠️ Pre-check SRT non riuscito: {e}")
            return False
        if invalid_count > 0:
            return not messagebox.askyesno(
                "SRT parziale",
                f"⚠️ {invalid_count} segmenti SRT ignorati (formato non valido). Continuare?")
        return False