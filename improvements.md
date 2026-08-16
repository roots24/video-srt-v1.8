# Suggerimenti di Miglioramento — Ultimate Video Translator AI PRO v1.8.1

## ✅ Completati (v1.8.1 — Manutenzione)

### Refactoring
- ✅ **Retry unificato** — `logic.py:230` `_retry_with_backoff()` (backoff 2s/4s/8s, nessuno sleep dopo l'ultimo tentativo)
- ✅ **Pipeline unificata** — `logic.py:834` `VideoTranslatorLogic.process()` usata da GUI singola e batch
- ✅ **Parsing SRT centralizzato** — `logic.py:436` `extract_srt_text_sample()` (niente parser duplicato in gui.py)
- ✅ **Pattern `NamedTemporaryFile`** → helper `_temp_file()` (5→1 occorrenze)
- ✅ **Pattern `CREATE_NO_WINDOW`** → costante `NO_WINDOW` (4→1 occorrenze)
- ✅ **Titolo downloader unificato** — costante `DOWNLOADER_TITLE` (`video_downloader_pro.py`)
- ✅ **Import morti rimossi** — `threading`/`messagebox` in downloader_logic, `tempfile`/`shutil` in gui.py, `shlex` (sostituito da `tk.splitlist`)
- ✅ **Metodo morto rimosso** — `BatchProcessor.remove_from_queue()`

### Bug fix
- ✅ **Warning pydub all'avvio** — PATH prima dell'import + sync `AudioSegment.converter`/`ffprobe`
- ✅ **Timeout TTS** — usa `API_TIMEOUT_TTS` (60s) non il default 30s
- ✅ **Barra downloader** — non più 100% su errore
- ✅ **Timestamp SRT 4 cifre** millis e `-->` senza spazi
- ✅ **Cache TTS memoria limitata** — `MAX_TTS_MEMORY_ENTRIES=200`
- ✅ **Anti-drift** — taglio audio oltre l'inizio della frase successiva
- ✅ **`embed_srt` in modalità audio** — checkbox disabilitata automaticamente
- ✅ **Update FFmpeg senza bloccare la UI** — background + timeout 120s
- ✅ **Riepilogo batch reale** — `process_all()` ritorna `(successi, totali)`
- ✅ **Timeout download FFmpeg** — `urlopen(timeout=120)` al posto di `urlretrieve`

### Test
- ✅ **Suite pytest** — `tests/` (41 test): parsing, tempo, cache, retry, stretch, anti-drift, process, batch

## ✅ Completati (v1.8)

### Bug / Typo
- ✅ Creato directory persistente `ffmpeg_persistent/`
- Vecchia cartella `ffempeg/` spostata in `ffmpeg_old/`
- ✅ Corretto typo `ffempeg/` → `ffmpeg_persistent/`
- ✅ Rimossa duplicazione codice `stretch_audio()` (logic.py)

### Performance
- ✅ Cache persistente su disco per traduzioni e TTS
  - Traduzioni: `.cache/translation_cache.json`
  - Audio: `.cache/tts_[hash].pkl`
- ✅ Auto-caricamento cache all'avvio
- ✅ Controllo dimensione cache (max 500MB)
- ✅ Aumento worker paralleli da 8 a `min(cpu*2, 16)`

### Robustness
- ✅ Parsing SRT robusto con validazione completa:
  - Gestione timestamp con virgola o punto
  - Validazione durata positiva
  - Controllo testo vuoto
  - Log dettagliato per ogni errore

### UX / UI
- ✅ Selezione voce female/male per ogni lingua (VOICE_MAP)
- ✅ Progress bar multi-stage (Parsing → Translation → TTS → Stretching → Mixing)
- ✅ Drag-and-drop file support nella GUI

### Nuove Features (da ai-sugerimenti.md)

- ✅ **Embed SRT nel video finale** — `logic.py:622` `merge_audio_video_mixed()`
  - Parametro `embed_srt=False` (default)
  - Crea file SRT temporaneo e lo passa a FFmpeg con `-c:s mov_text -map 2:s:0`
  - Attivabile via checkbox in `gui.py:138` `self.cb_embed_srt`

- ✅ **Auto-detect lingua sorgente** — `logic.py:360` `detect_language()`
  - Utilizza `langdetect` (opzionale: `pip install langdetect`)
  - Pulsante 🔍 in `gui.py:99` accanto al menu lingua sorgente
  - Estrae un campione di testo dal file SRT e lo analizza
  - Fallback graceful senza crash se libreria non installata

- ✅ **Batch mode** — `logic.py:716` classe `BatchProcessor`
  - Coda di file SRT con configurazione individuale
  - UI in `gui.py:165-188`: textbox coda, pulsanti +Aggiungi / X Svuota / ▶ Avvia Batch
  - Elaborazione sequenziale con progresso globale

- ✅ **Progress indicator mixaggio video** — `logic.py:678-698`
  - Sostituito `subprocess.run` con `subprocess.Popen` in `merge_audio_video_mixed()`
  - Parsing progressivo di `time=` dallo stderr di FFmpeg
  - Aggiornamento barra da 90% a 100%

- ✅ **Log filter per livello** — `gui.py:219-230`
  - `CTkSegmentedButton` con valori: All / Info / Warn / Error
  - Storico cronologico (`self._log_history`) per refiltering
  - Rilevamento automatico livello: ❌=ERROR, ⚠️=WARN, altri=INFO

### Robustness (da ai-sugerimenti.md)

- ✅ **Timeout API calls** — `logic.py:172` `execute_with_retry()`
  - Wrapper con `ThreadPoolExecutor(max_workers=1)` + `future.result(timeout=...)`
  - Timeout predefiniti in `config.py:165-166`: `API_TIMEOUT=30`, `API_TIMEOUT_TTS=60`
  - Retry con exponential backoff: 2s, 4s, 8s...

- ✅ **Retry FFmpeg configurabile** — `logic.py:205` `ffmpeg_execute_with_retry()`
  - Parametri `max_retries=None` e `initial_delay=None` → default da `config.py:169-170`
  - Costanti: `FFMPEG_MAX_RETRIES=3`, `FFMPEG_RETRY_DELAY=2`

- ✅ **Controllo spazio disco** — `logic.py:224` `check_disk_space()`
  - Usa `shutil.disk_usage()` per calcolare spazio disponibile
  - Chiamato in `generate_synced_audio()` prima dell'elaborazione
  - Stima spazio richiesto: `srt_size * 10 + n_segmenti * 0.5 + 200` MB

### Build / Setup
- ✅ Rimosso `package.json` e `node_modules/` (conteneva solo dipendenza `npm` irrilevante)
- ✅ Creato `build_app.spec` per compilazione PyInstaller
  - `datas`: include `ffmpeg_persistent/*` e `ffmpeg_settings.txt`
  - `hiddenimports`: tutti i moduli Python necessari
  - `console=True` per finestra log visibile

### Bug Fix
- ✅ **Cache serialization** — Separata cache TTS (`_tts_memory_cache`) dalla cache testuale (`_cache`) per evitare `TypeError: Object of type AudioSegment is not JSON serializable` in `_save_persistent_cache()`
- ✅ **FFmpeg encoding** — Aggiunto `encoding='utf-8'` e `errors='replace'` in `merge_audio_video_mixed()` per evitare errore `'charmap' codec can't decode byte` su Windows

## Da Implementare

- **Export multi-language** (ai-sugerimenti #7): generare versioni in più lingue in una passata
- **Previews before/after** (ai-sugerimenti #8): anteprima audio originale vs tradotto
- **Playlist/downloader**: profili H.264 su YouTube ricadono su `best[ext=mp4]` (spesso bassa risoluzione)

## Setup

```bash
pip install -r requirements.txt
```

## Note tecniche

### Cache System
```python
# Directory: .cache/
translation_cache.json  # Traduzioni testuali
tts_[sha256].pkl       # Audio TTS serializzati

# Configurazione in config.py:
CACHE_DIR = os.path.join(PROJECT_ROOT, '.cache')
MAX_CACHE_SIZE_MB = 500
PERSISTENT_CACHE_ENABLED = True
```

### Performance
```python
# Worker paralleli (configurabile):
MAX_WORKERS = min(os.cpu_count() or 4 * 2, 16)

# Retry logic:
max_retries = 3
initial_delay = 2  # seconds
```
