# Ultimate Video Translator AI PRO v1.8.2


Applicazione Python avanzata per la traduzione neurale di video tramite file SRT, con download video integrato e caching persistente.

Implementa le funzionalità suggerite in `ai-sugerimenti.md` incluse: Embed SRT, auto-detect lingua, timeout API, batch mode, log filter, controllo spazio disco, progress mixing e unit test.

## ✅ v1.8.1 — Manutenzione (Refactoring + Test)

### Refactoring (eliminazione duplicazioni)

- **Retry unificato** (`logic.py:230` `_retry_with_backoff()`): `execute_with_retry()` (API) e `ffmpeg_execute_with_retry()` ora delegano a un unico helper con backoff 2s/4s/8s e **nessuno sleep dopo l'ultimo tentativo**.
- **Pipeline unificata** (`logic.py:834` `VideoTranslatorLogic.process()`): GUI singola e batch condividono lo stesso flusso (generazione audio + mixaggio), gestione temp file centralizzata.
- **Parsing SRT centralizzato** (`logic.py:436` `extract_srt_text_sample()`): il parser duplicato nella GUI (auto-detect) ora delega al backend.
- **Pattern banali**: helper `_temp_file()` (5 occorrenze `NamedTemporaryFile` → 1) e costante `NO_WINDOW` (4 occorrenze `CREATE_NO_WINDOW` → 1).
- **Titolo downloader unificato**: costante `DOWNLOADER_TITLE` usata da finestra e header (`video_downloader_pro.py:11`).

### Correzioni

- **Warning pydub all'avvio** ("Couldn't find ffmpeg or avconv"): PATH preparato PRIMA dell'import di pydub e `AudioSegment.converter`/`ffprobe` sincronizzati su `config.FFMPEG_BIN` (`logic.py:17-36`).
- **TTT timeout TTS corretto**: 60s (`API_TIMEOUT_TTS`) invece del default 30s.
- **Barra progresso downloader**: non più al 100% su errore (`stop_merge_animation(mark_complete=...)`).
- **Timestamp SRT a 4 cifre millis** (es. `00:01:23,4567`) e `-->` senza spazi ora accettati.
- **Cache TTS in memoria limitata** (`MAX_TTS_MEMORY_ENTRIES=200`) per evitare RAM illimitata.
- **Anti-drift**: audio più lungo del gap verso la frase successiva viene tagliato per non spostare la timeline.
- **`embed_srt` ignorato in modalità solo-audio**: la checkbox ora si disabilita automaticamente.
- **Pulsante "Update FFmpeg Engine"** non blocca più la UI (esecuzione in background con timeout 120s sul download).
- **Metodo morto rimosso**: `BatchProcessor.remove_from_queue()` (mai chiamato).
- **Riepilogo batch reale**: la finestra finale mostra `successi/totali` (prima diceva "completata" anche con tutti i fallimenti).

### Unit Test (nuovi)

Suite pytest in `tests/` (41 test): parsing SRT, conversioni tempo, cache traduzione/TTS (memoria+disco), retry/backoff/timeout, stretch via FFmpeg, anti-drift, pipeline `process()` e batch.

```bash
pip install pytest
python -m pytest tests/ -q
```

## ✅ v1.8.2 — Robustezza (piano `fix-plan.md`)

- **🔴 Concorrenza batch ↔ produzione singola**: guardia condivisa `ProcessingGuard` (`logic.py`) usata da `start_batch()`/`start_production()`; pulsanti dell'altra modalità disabilitati durante l'elaborazione e sempre riabilitati in `finally`.
- **🔴 Encoding SRT**: `_read_text_file()` (`logic.py`) rileva UTF-8 (±BOM), cp1252/ANSI e UTF-16 (ordine e sanity-check NUL calibrati su file SRT): nessun `UnicodeDecodeError` su file salvati in codifiche Windows.
- **🟡 Parser SRT**: `_iter_srt_blocks()` normalizza i fine riga e tollera righe vuote multiple/spazi: niente segmenti persi con CRLF o file "sporchi"; parsing unificato (no duplicazione).
- **🟡 Thread zombie su timeout**: `socket.setdefaulttimeout(API_TIMEOUT)` in `config.py` (le librerie che usano `requests` senza timeout esplicito, es. `deep_translator`, ereditano il limite) + `connect_timeout`/`receive_timeout` su `edge_tts.Communicate` dove supportati; il wrapper executor resta come safety net.
- **🔵 Cache JSON atomica**: `_save_persistent_cache()` scrive su `.tmp` + `os.replace` (crash-safe).
- **🔵 Cross-platform**: `_open_with_system()` (win32/darwin/linux) al posto di `os.startfile`; il download automatico FFmpeg (build win64) su altre piattaforme restituisce un messaggio chiaro invece di scaricare un binario inusabile.
- **🔵 UX segmenti invalidi**: pre-check `askyesno` prima di partire se l'SRT ha segmenti non validi + riepilogo (`N segmenti, M ignorati`) nel messaggio di successo di `process()`.
- **🔵 Cache TTS in memoria**: `_trim_tts_memory_cache()` chiamato anche sul ramo "hit da disco" di `translate_and_fetch_tts()`.
- **Test**: suite salita a 68 test (nuovi `tests/test_encoding.py`; estese `test_parsing.py`, `test_retry.py`, `test_cache.py`, `test_batch.py`).
- **Versionamento incrementale**: la versione è una unica costante `config.APP_VERSION` (usata dalla GUI per titolo e header) e si incrementa con `bump_version.py` (patch/minor/major), che aggiorna anche il titolo di questo README.

## 🔢 Versionamento

La versione dell'applicazione vive **solo** in `config.py` (`APP_VERSION`): GUI, script e build la leggono da lì. Per incrementarla in modo incrementale:

```bash
python bump_version.py          # mostra la versione corrente
python bump_version.py patch    # fix/robustezza  (1.8.2 -> 1.8.3)
python bump_version.py minor    # nuova feature   (1.8.2 -> 1.9.0)
python bump_version.py major    # cambio sostanziale (1.8.2 -> 2.0.0)
```

Lo script aggiorna `config.py` e il titolo del `README.md`; il commit resta un passo separato.

## ✅ Novità versione 1.8

### Nuove Features (da ai-sugerimenti.md)

- **Embed SRT nel video** (`gui.py:138`, `logic.py:622`)
  - Checkbox "Embed SRT nel video" nella GUI
  - Passa sottotitoli tradotti come traccia `mov_text` nel video finale via FFmpeg
  - Nessun file `.srt` separato da gestire

- **Auto-detect lingua sorgente** (`gui.py:99`, `logic.py:360`)
  - Pulsante 🔍 accanto al menu lingua sorgente
  - Usa `langdetect` (opzionale: `pip install langdetect`)
  - Estrae campione di testo dal SRT e rileva lingua automaticamente
  - Imposta il menu a tendina con la lingua rilevata

- **Batch mode** (`gui.py:165-188`, `logic.py:716`)
  - Coda di file SRT con pulsanti +Aggiungi / X Svuota / ▶ Avvia Batch
  - Elaborazione sequenziale con progresso globale
  - Ogni elemento in coda mantiene la propria configurazione (lingue, volumi, sync)

- **Progress mixing video** (`logic.py:678-698`)
  - Monitoraggio real-time dell'output FFmpeg via `subprocess.Popen`
  - Parsing di `time=` per aggiornare la barra di progresso (90%→100%)

- **Log filter per livello** (`gui.py:219-230`)
  - `CTkSegmentedButton` con filtri: All / Info / Warn / Error
  - Storico cronologico completo per refiltering senza perdita messaggi
  - Rilevamento automatico livello: ❌=ERROR, ⚠️=WARN

### Performance

- **Cache persistente su disco** per traduzioni e TTS
- **Worker paralleli aumentati** a `min(cpu*2, 16)`
- **Doppio livello cache**: memoria + disco

### Robustezza

- **Timeout API configurabile** (`logic.py:172`, `config.py:165-166`)
  - Wrapper con `ThreadPoolExecutor` + timeout: 30s traduzione, 60s TTS
  - Exponential backoff: 2s, 4s, 8s...
- **Retry FFmpeg configurabile** (`logic.py:205`, `config.py:169-170`)
  - Parametri `FFMPEG_MAX_RETRIES=3`, `FFMPEG_RETRY_DELAY=2` in `config.py`
- **Controllo spazio disco** (`logic.py:224`)
  - Verifica spazio disponibile con `shutil.disk_usage()` prima di elaborare
  - Stima spazio richiesto: `srt_size*10 + n_segmenti*0.5 + 200` MB
- **Parsing SRT robusto** con validazione completa
- **Gestione timestamp** con virgola o punto come separatore

### UX/UI

- Progress bar multi-stage (6 fasi)
- Drag-and-drop file (con `tkinterdnd2`, opzionale)
- Selezione gender voce per ogni lingua
- `embed_srt` disabilitato automaticamente in modalità solo-audio

### Moduli Principali

| File | Descrizione |
| ------ | ------------- |
| `main.py` | Entry point dell'applicazione |
| `gui.py` | Interfaccia grafica CustomTkinter (850x950 px) |
| `logic.py` | Core engine: SRT→Traduzione→TTS→Mixaggio audio |
| `config.py` | Configurazioni globali, gestione FFmpeg e cache |
| `downloader_config.py` | Profili di download (yt-dlp) |
| `downloader_logic.py` | Motore di download asincrono |
| `video_downloader_pro.py` | GUI downloader multi-video parallelo |
| `requirements.txt` | Dipendenze Python (installazione con `pip install -r requirements.txt`) |
| `build_app.spec` | Configurazione PyInstaller per compilazione `.exe` |
| `tests/` | Suite di unit test (pytest, 41 test) |

### Directory

- `ffmpeg_persistent/`: FFmpeg scaricato automaticamente (persistente)
- `.cache/`: Traduzioni e TTS in cache (generato dinamicamente)

### Requisiti

- Python 3.8+
- FFmpeg (scaricamento automatico in `ffmpeg_persistent/`)
- Internet per API traduzione e TTS
- `langdetect` (opzionale) per auto-detect lingua sorgente
- `tkinterdnd2` (opzionale) per drag-and-drop nativo dei file
- `pytest` (solo sviluppo) per gli unit test

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

Per creare l'eseguibile (modalità **onedir**: FFmpeg resta in una cartella separata, l'exe resta piccolo):

```bash
pip install pyinstaller
python -m PyInstaller build_app.spec
```

Il risultato è in `dist/UltimateVideoTranslatorAI/`:

- `UltimateVideoTranslatorAI.exe` (~11 MB, `console=True` — finestra terminale visibile per i log)
- `ffmpeg/` (o `ffmpeg_persistent/`): binari FFmpeg **accanto all'exe**, sostituibili manualmente
- `_internal/`: moduli Python (non toccare)

L'app cerca FFmpeg: cartella accanto all'exe → `ffmpeg_settings.txt` → bundle → PATH di sistema.

Per compilare senza finestra console, modificare `console=True` → `console=False` in `build_app.spec`.

## Note

- Personalizza `config.py` per regolare performance e cache
- La cache persistente è in `.cache/`

## Bug Fixati (v1.8)

| Gravità | Bug | Fix |
| ------ | ---- | -------- |
| Critico | Segmenti SRT saltati: gli ID dei segmenti usavano l'indice del blocco originale. Con un blocco invalido gli ID non erano contigui e i segmenti validi successivi venivano scartati dalla timeline audio | `logic.py`: ID ora contigui (`len(segments_data)`) |
| Critico | Il valore di ritorno di `merge_audio_video_mixed()` era ignorato: si mostrava "Successo" anche quando FFmpeg falliva (es. video senza traccia audio) | Verifica esito in `gui.py` e nel batch (`logic.py`) |
| Alto | `config.FFMPEG_BIN` calcolato una sola volta all'import: dopo "Scarica e Installa" il nuovo percorso FFmpeg non veniva usato fino al riavvio | Nuova `config.set_ffmpeg_bin()` (aggiorna binario + PATH per pydub) |
| Alto | La cache TTS (`tts_*.pkl`) non veniva mai ripulita: `_enforce_cache_limit()` agiva solo su `translation_cache.json` | Nuova `_enforce_tts_cache_limit()`: rimozione file più vecchi oltre il limite |
| Medio | `_save_persistent_cache()` eseguita da più worker senza lock → rischio scritture concorrenti/parziali del JSON | Lock `RLock` su cache testuale e TTS |
| Medio | `ffmpeg -version` senza `encoding`/`creationflags` → possibile `UnicodeDecodeError` su Windows e finestra console lampeggiante | `encoding='utf-8'`, `errors='replace'`, `CREATE_NO_WINDOW` |
| Medio | Rilevamento playlist con `'playlist' in url` (fragile) e doppia estrazione metadati (`extract_info` + `download`) | Rilevamento via `info['_type']`, download con `process_ie_result()` |
| **Critico (download)** | **Download video non funzionante**: `ydl.params['outtmpl']` veniva impostato come stringa, ma yt-dlp moderno richiede un dict `{'default': ...}` → crash `'str' object has no attribute 'get'` su ogni download | `downloader_logic.py`: `ydl.params['outtmpl'] = {'default': outtmpl}` — verificato con download reale |
| Medio | `embed_srt=True` con segmenti vuoti generava un file SRT vuoto → FFmpeg falliva con errore oscuro | `logic.py`: salta i sottotitoli con warning se non ci sono segmenti validi |
| Medio | `drop_file` usava `split()` che rompeva i path con spazi; import `dnd` inutile | `shlex.split()` e import rimosso |
| Basso | In batch, se `mode='video'` ma il campo video era vuoto, l'MP3 veniva copiato sul file `.mp4` | Errore esplicito e conteggio corretto dei successi |
| Critico | `RuntimeWarning: Couldn't find ffmpeg or avconv` all'avvio: pydub risolveva i binari PRIMA dell'aggiornamento del PATH | Preparazione PATH centralizzata in `config.py` (primo modulo importato ovunque) + sync `AudioSegment.converter`/`ffprobe` su `config.FFMPEG_BIN` in `logic.py` |
| Alto | Timeout TTS usava il default 30s invece dei 60s previsti (`API_TIMEOUT_TTS`) | `execute_with_retry(..., timeout=config.API_TIMEOUT_TTS)` |
| Medio | Barra downloader al 100% anche su errore di merge | `stop_merge_animation(mark_complete=(colore==verde))` |
| Medio | Cache TTS in memoria senza limite (RAM illimitata) | `MAX_TTS_MEMORY_ENTRIES=200` + trim FIFO |
| Alto | Frase audio oltre l'inizio della successiva spostava l'intera timeline (drift) | Anti-drift: taglio a `next_start - start_ms` |
| Medio | Pulsante "Update FFmpeg Engine" bloccava la UI (download sincrono 100MB+) | Esecuzione in background con timeout 120s (`urlopen`) |
| Medio | Riepilogo batch sempre "completata" anche con tutti i fallimenti | `process_all()` ritorna `(successi, totali)` e la GUI li mostra |
| Basso | `embed_srt` attivo ma ignorato in modalità solo-audio | Checkbox disabilitata automaticamente |
| Basso | `BatchProcessor.remove_from_queue()` mai chiamato (codice morto) | Rimosso |
| Basso | `urllib.request.urlretrieve` senza timeout (hang infinito su rete bloccata) | `urlopen(timeout=120)` + `shutil.copyfileobj` |
| 🔴 Critico (v1.8.2) | Race condition: batch e produzione singola potevano correre in parallelo (FFmpeg/TTS concorrenti sugli stessi output → file corrotti/crash) | `ProcessingGuard` condivisa + pulsanti incrociati disabilitati (`gui.py`, `logic.py`) |
| 🔴 Critico (v1.8.2) | SRT hardcoded UTF-8: `UnicodeDecodeError` su file UTF-16/ANSI (comuni su Windows) | `_read_text_file()` con rilevamento encoding (`logic.py`) |
| 🟡 Alto (v1.8.2) | Parser SRT `split('\n\n')` perdeva segmenti con CRLF, righe vuote multiple, spazi sulle righe vuote | `_iter_srt_blocks()` tollerante + parsing unificato |
| 🟡 Alto (v1.8.2) | Thread zombie: operazioni appese su socket senza timeout restavano vive in background | `socket.setdefaulttimeout(API_TIMEOUT)` + timeout espliciti su `edge_tts.Communicate` |
| 🔵 Medio (v1.8.2) | Cache JSON scritta direttamente: crash/concorrenza a metà write = cache corrotta | Scrittura atomica `.tmp` + `os.replace` |
| 🔵 Medio (v1.8.2) | `os.startfile` solo Windows; download FFmpeg win64 tentato su ogni piattaforma | `_open_with_system()` cross-platform + guard non-Windows in `config.py` |
| 🔵 Basso (v1.8.2) | Segmenti SRT invalidi scartati in silenzio (solo log); cache TTS in memoria non trimmata sui hit da disco; testo pulsante start alterato dopo un run | Pre-check `askyesno` + riepilogo nel messaggio; trim su hit da disco; testo ripristinato |

> Il drag-and-drop funziona installando `tkinterdnd2` (opzionale): senza di esso la GUI resta
> funzionante e segnala nel log come abilitarlo. I path con spazi sono gestiti via `tk.splitlist`.
