# Suggerimenti di Miglioramento — Ultimate Video Translator AI PRO v1.8

## ✅ Completati

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

- ✅ **Embed SRT nel video finale** — `logic.py:517` `merge_audio_video_mixed()`
  - Parametro `embed_srt=False` (default)
  - Crea file SRT temporaneo e lo passa a FFmpeg con `-c:s mov_text -map 2:s:0`
  - Attivabile via checkbox in `gui.py:138` `self.cb_embed_srt`

- ✅ **Auto-detect lingua sorgente** — `logic.py:332` `detect_language()`
  - Utilizza `langdetect` (opzionale: `pip install langdetect`)
  - Pulsante 🔍 in `gui.py:99` accanto al menu lingua sorgente
  - Estrae un campione di testo dal file SRT e lo analizza
  - Fallback graceful senza crash se libreria non installata

- ✅ **Batch mode** — `logic.py:544` classe `BatchProcessor`
  - Coda di file SRT con configurazione individuale
  - UI in `gui.py:162-188`: textbox coda, pulsanti +Aggiungi / X Svuota / ▶ Avvia Batch
  - Elaborazione sequenziale con progresso globale

- ✅ **Progress indicator mixaggio video** — `logic.py:540-541`
  - Sostituito `subprocess.run` con `subprocess.Popen` in `merge_audio_video_mixed()`
  - Parsing progressivo di `time=` dallo stderr di FFmpeg
  - Aggiornamento barra da 90% a 100%

- ✅ **Log filter per livello** — `gui.py:218-230`
  - `CTkSegmentedButton` con valori: All / Info / Warn / Error
  - Storico cronologico (`self._log_history`) per refiltering
  - Rilevamento automatico livello: ❌=ERROR, ⚠️=WARN, altri=INFO

### Robustness (da ai-sugerimenti.md)

- ✅ **Timeout API calls** — `logic.py:158` `execute_with_retry()`
  - Wrapper con `ThreadPoolExecutor(max_workers=1)` + `future.result(timeout=...)`
  - Timeout predefiniti in `config.py:156-157`: `API_TIMEOUT=30`, `API_TIMEOUT_TTS=60`
  - Retry con exponential backoff: 2s, 4s, 8s...

- ✅ **Retry FFmpeg configurabile** — `logic.py:184` `ffmpeg_execute_with_retry()`
  - Parametri `max_retries=None` e `initial_delay=None` → default da `config.py:159-160`
  - Costanti: `FFMPEG_MAX_RETRIES=3`, `FFMPEG_RETRY_DELAY=2`

- ✅ **Controllo spazio disco** — `logic.py:203` `check_disk_space()`
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
