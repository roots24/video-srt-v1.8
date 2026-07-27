# Ultimate Video Translator AI PRO v1.8

Applicazione Python avanzata per la traduzione neurale di video tramite file SRT, con download video integrato e caching persistente.

Implementa le funzionalità suggerite in `ai-sugerimenti.md` incluse: Embed SRT, auto-detect lingua, timeout API, batch mode, log filter, controllo spazio disco e progress mixing.

## ✅ Novità versione 1.8 (Attuale)

### Nuove Features (da ai-sugerimenti.md)

- **Embed SRT nel video** (`gui.py:138`, `logic.py:517`)
  - Checkbox "Embed SRT nel video" nella GUI
  - Passa sottotitoli tradotti come traccia `mov_text` nel video finale via FFmpeg
  - Nessun file `.srt` separato da gestire

- **Auto-detect lingua sorgente** (`gui.py:99`, `logic.py:332`)
  - Pulsante 🔍 accanto al menu lingua sorgente
  - Usa `langdetect` (opzionale: `pip install langdetect`)
  - Estrae campione di testo dal SRT e rileva lingua automaticamente
  - Imposta il menu a tendina con la lingua rilevata

- **Batch mode** (`gui.py:162-188`, `logic.py:544`)
  - Coda di file SRT con pulsanti +Aggiungi / X Svuota / ▶ Avvia Batch
  - Elaborazione sequenziale con progresso globale
  - Ogni elemento in coda mantiene la propria configurazione (lingue, volumi, sync)

- **Progress mixing video** (`logic.py:540-541`)
  - Monitoraggio real-time dell'output FFmpeg via `subprocess.Popen`
  - Parsing di `time=` per aggiornare la barra di progresso (90%→100%)

- **Log filter per livello** (`gui.py:218-230`)
  - `CTkSegmentedButton` con filtri: All / Info / Warn / Error
  - Storico cronologico completo per refiltering senza perdita messaggi
  - Rilevamento automatico livello: ❌=ERROR, ⚠️=WARN

### Performance
- **Cache persistente su disco** per traduzioni e TTS
- **Worker paralleli aumentati** a `min(cpu*2, 16)`
- **Doppio livello cache**: memoria + disco

### Robustezza
- **Timeout API configurabile** (`logic.py:158`, `config.py:156-157`)
  - Wrapper con `ThreadPoolExecutor` + timeout: 30s traduzione, 60s TTS
  - Exponential backoff: 2s, 4s, 8s...
- **Retry FFmpeg configurabile** (`logic.py:184`, `config.py:159-160`)
  - Parametri `FFMPEG_MAX_RETRIES=3`, `FFMPEG_RETRY_DELAY=2` in `config.py`
- **Controllo spazio disco** (`logic.py:203`)
  - Verifica spazio disponibile con `shutil.disk_usage()` prima di elaborare
  - Stima spazio richiesto: `srt_size*10 + n_segmenti*0.5 + 200` MB
- **Parsing SRT robusto** con validazione completa
- **Gestione timestamp** con virgola o punto come separatore

### UX/UI
- Progress bar multi-stage (6 fasi)
- Drag-and-drop file support
- Selezione gender voce per ogni lingua

### Moduli Principali

| File | Descrizione |
|------|-------------|
| `main.py` | Entry point dell'applicazione |
| `gui.py` | Interfaccia grafica CustomTkinter (850x950 px) |
| `logic.py` | Core engine: SRT→Traduzione→TTS→Mixaggio audio |
| `config.py` | Configurazioni globali, gestione FFmpeg e cache |
| `downloader_config.py` | Profili di download (yt-dlp) |
| `downloader_logic.py` | Motore di download asincrono |
| `video_downloader_pro.py` | GUI downloader multi-video parallelo |
| `requirements.txt` | Dipendenze Python (installazione con `pip install -r requirements.txt`) |
| `build_app.spec` | Configurazione PyInstaller per compilazione `.exe` |

### Directory

- `ffmpeg_persistent/`: FFmpeg scaricato automaticamente (persistente)
- `ffmpeg_old/`: Backup vecchia cartella (può essere rimosso)
- `.cache/`: Traduzioni e TTS in cache (generato dinamicamente)

### Requisiti

- Python 3.8+
- FFmpeg (scaricamento automatico in `ffmpeg_persistent/`)
- Internet per API traduzione e TTS
- `langdetect` (opzionale) per auto-detect lingua sorgente

### Setup

1. **Clona il repository**
2. **Installa le dipendenze**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Avvia l'applicazione**:

   ```bash
   python main.py
   ```

   FFmpeg verrà scaricato automaticamente al primo avvio.

### Compilazione (.exe)

Per creare un eseguibile standalone:

```bash
pip install pyinstaller
pyinstaller build_app.spec
```

Il file sarà in `dist/UltimateVideoTranslatorAI.exe` (`console=True` — finestra terminale visibile per i log).

Per compilare senza finestra console, modificare `console=True` → `console=False` in `build_app.spec`.

## Note

- Personalizza `config.py` per regolare performance e cache
- La cache persistente è in `.cache/`
