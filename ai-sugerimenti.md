# AI Suggestions - Funzioni da Implementare

> **Stato (v1.8.1):** implementati #1 Embed SRT, #2 Auto-detect (via langdetect), #3 Timeout API,
> #4 Retry FFmpeg, #5 Spazio disco, #6 Batch, #9 Progress mixaggio, #10 Log filter, #12 Timeout (alt),
> #13 Unit Test (`tests/`). Aperti: #7 Multi-language export, #8 Previews before/after.

## 🎯 Priority 1 - Alta Priorità (Impatto Directo)

### 1. Embedding SRT nel Video

**Descrizione:** Includere i sottotitoli tradotti direttamente nel video finale come traccia di sottotitoli.

**Implementazione:**

```python
# Aggiungere opzione in GUI:
embed_srt_checkbox = ctk.CTkCheckBox(..., text="Embed SRT nel video")

# In logic.py merge_audio_video_mixed():
if embed_srt and segments_data is not None:
    # Crea file SRT temporaneo con testi tradotti
    # Usa: -c:s mov_text per embeddare sottotitoli
    cmd.extend(['-i', srt_path, '-c:s', 'mov_text', '-map', '2:s:0'])
```

**Benefici:**

- Sottotitoli sempre visibili su qualsiasi player
- Nessun file .srt separato da gestire

---

### 2. Auto-Detect Lingua Sorgente

**Descrizione:** Rilevare automaticamente la lingua del file audio/video senza bisogno di specificarla manualmente.

**Implementazione:**

```python
# Usare whisper.cpp o similar per speech-to-text
import subprocess

def detect_language(video_path):
    # Estrai audio temporaneo
    # Usa whisper.cpp (lightweight) per rilevare lingua
    result = subprocess.run([
        'whisper', video_path, 
        '--language', 'detect',
        '--model', 'tiny'
    ], capture_output=True)
    
    return parse_detected_language(result.stdout)
```

**Benefici:**

- UX semplificata (uno step in meno)
- Riduce errori utente

---

## 🛡️ Priority 1.5 - Robustezza (Critico)

### 3. Timeout per API Calls

**Descrizione:** Aggiungere timeout configurabili per evitare blocco infinito delle API.

**Implementazione:**

```python
# In config.py:
API_TIMEOUT_TRANSLATION = 30  # seconds
API_TIMEOUT_TTS = 60          # seconds (più lungo per audio)

# In logic.py execute_with_retry():
import concurrent.futures

def execute_with_retry(self, func, timeout=None, max_retries=3, **kwargs):
    if timeout is None:
        timeout = config.API_TIMEOUT_TRANSLATION
    
    last_exception = None
    for attempt in range(max_retries):
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func)
                return future.result(timeout=timeout)
        except (concurrent.futures.TimeoutError, TimeoutError):
            self.log(f"⚠️ Timeout API tentativo {attempt + 1}/{max_retries}")
            last_exception = Exception("Timeout")
        except Exception as e:
            last_exception = e
        
        delay = 2 * (2 ** attempt)
        time.sleep(delay)
    
    raise last_exception
```

**Benefici:**

- Evita blocchi infiniti su API lente
- Configurabile per diversi tipi di chiamate

---

### 4. Retry FFmpeg Configurabile

**Descrizione:** Rendere configurabile il numero di retry per comandi FFmpeg.

**Implementazione:**

```python
# In config.py:
FFMPEG_MAX_RETRIES = 3
FFMPEG_RETRY_DELAY = 2  # seconds

# In logic.py ffmpeg_execute_with_retry():
def ffmpeg_execute_with_retry(self, cmd, max_retries=None, initial_delay=None):
    if max_retries is None:
        max_retries = config.FFMPEG_MAX_RETRIES
    if initial_delay is None:
        initial_delay = config.FFMPEG_RETRY_DELAY
    
    # ... existing code ...
```

---

### 5. Controllo Spazio Disco

**Descrizione:** Verificare spazio disponibile prima di elaborare file grandi.

**Implementazione:**

```python
import shutil

def check_disk_space(path, required_mb):
    """Verifica che ci sia abbastanza spazio su disco."""
    stat = shutil.disk_usage(path)
    available_mb = stat.free / (1024 * 1024)
    
    if available_mb < required_mb:
        raise Exception(
            f"Spazio insufficiente: {available_mb:.1f}MB disponibili, "
            f"richiesti {required_mb:.1f}MB"
        )
    return True

# Uso in logic.py:
def generate_synced_audio(self, srt_file, output_file, ...):
    # Calcola spazio necessario (video size * 2 per temp files)
    video_size = os.path.getsize(video_path) / (1024*1024) if video_path else 100
    required_space = int(video_size * 3 + 500)  # Buffer
    
    output_dir = os.path.dirname(output_file)
    check_disk_space(output_dir, required_space)
```

---

## 📋 Priority 2 - Media Priorità (Value Add)

### 6. Batch Mode

**Descrizione:** Elaborare più file SRT in sequenza senza riavviare l'applicazione.

**Implementazione:**

```python
class BatchProcessor:
    def __init__(self):
        self.queue = []
    
    def add_to_queue(self, srt_file, config):
        self.queue.append((srt_file, config))
    
    def process_all(self):
        for srt_file, config in self.queue:
            self.process_single(srt_file, config)
```

**GUI:**

- Lista file in coda
- Pulsante "Avvia Batch"
- Progresso globale

---

### 7. Export Multi-Language

**Descrizione:** Generare versioni tradotte in più lingue simultaneamente.

**Implementazione:**

```python
# In GUI:
tgt_langs = ["it", "en", "es"]  # Selezione multipla

for lang in tgt_langs:
    threading.Thread(
        target=logic.generate_synced_audio,
        args=(..., lang, ...)
    ).start()
```

**Benefici:**

- Risparmio tempo per content creators
- Una sola esecuzione per multiple lingue

---

### 8. Previews Before/After

**Descrizione:** Visualizzare anteprime audio/video prima del download.

**Implementazione:**

```python
# Slider or split-view comparison
class PreviewWidget:
    def __init__(self):
        self.original_audio = None
        self.translated_audio = None
    
    def play_original(self):
        # Play segment from original video
    
    def play_translated(self):
        # Play translated audio segment
```

---

### 9. No Progress Indicator per Mixing

**Descrizione:** Aggiornare progress bar durante la fase di mixaggio video.

**Implementazione:**

```python
# In logic.py merge_audio_video_mixed():
def merge_audio_video_mixed(self, video_path, translated_audio_path, output_video_path, ...):
    # Esegui FFmpeg in modo monitorabile
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True
    )
    
    for line in process.stdout:
        if 'time=' in line:
            # Estrai percentuale dal log di ffmpeg
            time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
            if time_match:
                hours, mins, secs = map(float, time_match.groups())
                total_duration = get_video_duration(video_path)
                elapsed = (hours * 3600) + (mins * 60) + secs
                progress = min(elapsed / total_duration, 1.0)
                
                if self.update_progress:
                    self.update_progress(progress, f"Mixaggio video... {int(progress*100)}%")
    
    process.wait()
```

---

### 10. Log Filter per Livello

**Descrizione:** Filtro visivo per livelli di log (INFO/WARN/ERROR).

**Implementazione:**

```python
# Slider or split-view comparison
class PreviewWidget:
    def __init__(self):
        self.original_audio = None
        self.translated_audio = None
    
    def play_original(self):
        # Play segment from original video
    
    def play_translated(self):
        # Play translated audio segment
```

---

## 🔧 Priority 3 - Low Priority (Polishing)

### 11. Log Filter per Livello

**Descrizione:** Filtro visivo per livelli di log (INFO/WARN/ERROR).

**Implementazione:**

```python
# In GUI:
self.log_filter = ctk.CTkSegmentedButton(
    master,
    values=["All", "Info", "Warn", "Error"],
    command=self.filter_logs
)

def filter_logs(self, level):
    # Nascondi/mostra log per livello
```

---

### 12. Timeout Configurabile API (Alternative)

**Descrizione:** Implementazione alternativa con contest manager.

**Config:**

```python
config.py:
API_TIMEOUT_TRANSLATION = 30  # seconds
API_TIMEOUT_TTS = 60          # seconds (più lungo per audio)
```

**In logic.py:**

```python
def execute_with_retry(self, func, timeout=None):
    if timeout is None:
        timeout = config.API_TIMEOUT
    
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func)
        try:
            result = future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutException()
```

---

### 13. Unit Tests

**Stato: ✅ IMPLEMENTATO** — `tests/` (41 test pytest)

```text
tests/
├── conftest.py         # fixture: cache isolata per test, FakeTTSLogic
├── test_time.py        # srt_time_to_ms / ms_to_srt_time (roundtrip, 4 cifre millis)
├── test_parsing.py     # extract_srt_text_sample, segmenti invalidi
├── test_cache.py       # cache traduzione/TTS memoria+disco, trim
├── test_retry.py       # backoff, esaurimento retry, timeout
├── test_audio.py       # stretch atempo, max_speed, anti-drift
├── test_process.py     # pipeline unificata (audio/video/embed)
└── test_batch.py       # conteggi, progress, eccezioni
```

**Esempio:**

```python
def test_srt_time_to_ms():
    assert logic.srt_time_to_ms("00:01:23,456") == 83456
    assert logic.srt_time_to_ms("00:01:23.456") == 83456
```

**Setup:**

```bash
pip install pytest
pytest tests/
```

---

## 🛠️ Build & Setup

### 14. Rimuovere package.json Non Utilizzato

**Azioni:**

- Verificare se npm serve per qualcosa
- Se no, rimuovere `package.json` e `.gitignore` relativo

### 15. PyInstaller Integration

**Aggiungere al .spec file:**

```python
# In build_app.spec:
datas=[
    ('ffmpeg_persistent/*', 'ffmpeg_persistent'),
    ('ffmpeg_settings.txt', '.'),
],
```

---

## 📊 Priority Matrix

| # | Funzione | Difficoltà | Impatto | Priorità |
| --- | ---------- | ----------- | --------- | ---------- |
| 1 | Embed SRT nel video | Media | Alto | **P1** |
| 2 | Auto-detect lingua | Alta | Alto | **P1** |
| 3 | Timeout per API calls | Media | Alto | **P1** (critico) |
| 4 | Retry FFmpeg configurabile | Basso | Medio | **P1.5** |
| 5 | Controllo spazio disco | Bassa | Alto | **P1.5** |
| 6 | Batch mode | Media | Alto | P2 |
| 7 | Multi-language export | Alta | Medio | P2 |
| 8 | Previews Before/After | Media | Medio | P2 |
| 9 | Progress mixaggio video | Bassa | Medio | P2 |
| 10 | Log filter livelli | Basso | Basso | P3 |
| 11 | Timeout API (alt) | Media | Medio | P3 |
| 12 | Unit tests | Media | Alto | **P1** (quality) |

> ✅ Implementati: 1-6, 9-13 (v1.8/v1.8.1). Aperti: **7** (multi-language export), **8** (previews).

---

## 🚀 Roadmap Raccomandata

### Sprint 1 (Settimana 1)

- [ ] Embed SRT nel video
- [ ] Timeout per API calls (critico)
- [ ] Controllo spazio disco

### Sprint 2 (Settimana 2)

- [ ] Auto-detect lingua sorgente
- [ ] Retry FFmpeg configurabile
- [ ] Batch mode semplice

### Sprint 3 (Settimana 3)

- [ ] Multi-language export
- [ ] Progress indicator mixing video
- [ ] Previews basic

### Sprint 4 (Settimana 4)

- [ ] Log filter livelli
- [ ] Unit tests completi
- [ ] Ottimizzazioni finali

---
