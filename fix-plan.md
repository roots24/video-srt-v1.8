# 📋 Piano di Fix — Ultimate Video Translator AI PRO v1.8

> **Obiettivo:** risolvere i bug e le criticità identificate nell'analisi del codice
> (`logic.py`, `gui.py`, `config.py`) con interventi prioritizzati, testati e documentati.
>
> **Stato:** ✅ IMPLEMENTATO (v1.8.2) — branch `fix/1.8-robustezza`, suite 68/68 verde.
> **Scope:** nessuna modifica alle feature già funzionanti; solo fix mirati + test di regressione.

---

## 1. Riepilogo dei Problemi e Priorità

| # | Priorità | Problema | File / Riferimento | Effort |
|---|:---:|:---|:---|:---:|
| 1 | 🔴 P0 | Race condition tra Batch e produzione singola | `gui.py` (`start_batch` vs `start_production`) | S |
| 2 | 🔴 P0 | Encoding SRT rigido (`utf-8` hardcoded) → `UnicodeDecodeError` | `logic.py:435, 582, 652, 738` | S |
| 3 | 🟡 P1 | Parser SRT fragile (`split('\n\n')`) → segmenti persi | `logic.py:438-439, 534-535` | M |
| 4 | 🟡 P1 | Thread zombie su timeout API (executor non terminati) | `logic.py:225-245` (`_retry_with_backoff`) | M |
| 5 | 🔵 P2 | Cache JSON non atomica → corruzione su crash/concorrenza | `logic.py:88-101` (`_save_persistent_cache`) | S |
| 6 | 🔵 P2 | Codice Windows-centrico (`os.startfile`, download FFmpeg win64) | `gui.py:515,535` · `config.py` | M |
| 7 | 🔵 P2 | Segmenti SRT invalidi nascosti all'utente (solo log) | `gui.py` / `logic.py` (UX) | S |
| 8 | 🔵 P2 | Cache TTS in memoria senza trim su hit da disco | `logic.py:487+` (`translate_and_fetch_tts`) | XS |

**Nota:** il progetto ha già una suite di test solida (43 test in `tests/`, fixture `FakeTTSLogic`,
`write_srt`, `isolated_cache` in `tests/conftest.py`). Ogni fix deve mantenere verde la suite esistente
e aggiungere test di copertura mirati.

---

## 2. Fase 0 — Preparazione (10 min)

- [x] Creare un branch dedicato: `git checkout -b fix/1.8-robustezza`
- [x] Eseguire la baseline dei test: `python -m pytest -q` → **tutti verdi (47/47** alla baseline, non 43: la suite era cresciuta)
- [x] Verificare che l'app parta in modalità dev: import + istanziamento `App()` OK (smoke test)
- [x] File SRT di esempio in 3 varianti: generati on-the-fly da `tests/test_encoding.py` (UTF-8 BOM, UTF-16, cp1252) invece di file manuali

---

## 3. Fase 1 — Fix 🔴 P0 (priorità critica)

### 3.1 Race condition Batch ↔ Produzione singola

**Problema:** `gui.py:777-780` usa `self._production_running` solo per il pulsante singolo.
`start_batch` (`gui.py:724`) controlla solo `self._batch_processor.is_running`. Un utente può
avviare un batch e, mentre è in corso, lanciare una produzione singola → due pipeline parallele
che usano FFmpeg e possono scrivere sullo stesso output → file corrotti o crash.

**Fix proposto:**
1. Introdurre un unico flag condiviso `self._processing_active` (o un `threading.Lock` non bloccante).
2. `start_production` → controlla `self._processing_active` al posto di `_production_running`.
3. `start_batch` → controlla `self._processing_active` (oltre a `is_running` del batch).
4. Disabilitare i pulsanti dell'altra modalità durante l'elaborazione (UX):
   - durante batch: `btn_start` disabilitato (già fatto) **e** `btn_batch_add`/`btn_batch_clear` disabilitati;
   - durante singola: `btn_batch_start` disabilitato (oggi non lo è).

**Modifica concreta (`gui.py`):**

```python
# in __init__: sostituire _production_running con un flag condiviso
self._processing_active = False

# in start_production():
if self._processing_active:
    messagebox.showinfo("Info", "Elaborazione già in corso, attendi il completamento")
    return
self._processing_active = True
# ... (task esistente) ...
# nel finally:
self._processing_active = False

# in start_batch(): aggiungere in cima
if self._processing_active:
    messagebox.showinfo("Batch", "Elaborazione già in corso, attendi il completamento")
    return
# e nel batch_task: disabilitare/riabilitare btn_batch_add, btn_batch_clear,
# oltre a quanto già fatto per btn_start / btn_batch_start
```

**Criteri di accettazione:**
- [x] Avviando un batch, `btn_start` è disabilitato e `start_production` mostra "già in corso".
- [x] Avviando una singola, `btn_batch_start` è disabilitato e `start_batch` mostra "già in corso".
- [x] Al termine (successo o errore), tutti i pulsanti tornano abilitati (riabilitazione in `finally`, anche su eccezione).
- [x] Test automatizzato: `tests/test_batch.py` → `ProcessingGuard` (la stessa classe usata dalla GUI) verifica il rifiuto dell'avvio concorrente.

> Implementazione: il flag booleano del piano è stato estratto in `ProcessingGuard`
> (`logic.py`) perché la GUI non è istanziabile nei test headless; `gui.py` lo usa
> con lo stesso comportamento previsto (`try_begin()` al via, `end()` in `finally`).

---

### 3.2 Encoding SRT rigido → `UnicodeDecodeError`

**Problema:** tutti i `open(srt_file, 'r', encoding='utf-8')` in `logic.py` (righe 435, 582, 652, 738)
crashano su file SRT in UTF-16 o ANSI/Windows-1252 (comuni su Windows).

**Fix proposto:**
1. Aggiungere un helper `_read_text_file(path)` in `logic.py` che:
   - prova `utf-8-sig` (gestisce anche il BOM);
   - fallback `utf-16` (rileva BOM automaticamente);
   - fallback `cp1252` con `errors='replace'` come ultima spiaggia;
   - (opzionale) se `chardet` è installato, usarlo prima dei fallback.
2. Sostituire TUTTI i `open(srt_file, 'r', encoding='utf-8')` di lettura SRT con `self._read_text_file(...)`.
3. **Non** toccare i `open(..., 'w', encoding='utf-8')` di scrittura (output sempre UTF-8, corretto).

**Modifica concreta (`logic.py`):**

```python
def _read_text_file(self, path):
    """Legge un file di testo rilevando l'encoding (UTF-8 con BOM, UTF-16, cp1252)."""
    encodings = ['utf-8-sig', 'utf-16', 'cp1252']
    for enc in encodings:
        try:
            with open(path, 'r', encoding=enc) as f:
                content = f.read()
            # sanity check: niente caratteri di controllo anomali → encoding plausibile
            if '\x00' in content:
                continue
            return content
        except (UnicodeDecodeError, UnicodeError):
            continue
    # Ultima spiaggia: lossy ma senza crash
    with open(path, 'r', encoding='cp1252', errors='replace') as f:
        return f.read()
```

**Criteri di accettazione:**
- [x] `parse_srt_file`, `generate_synced_audio`, `export_translated_srt`, `extract_srt_text_sample` funzionano con i 3 file di esempio (UTF-8, UTF-16, cp1252).
- [x] Nessuna eccezione `UnicodeDecodeError` propagata alla GUI.
- [x] Test automatizzato: nuovo `tests/test_encoding.py` con 3 file generati nelle 3 codifiche → il parsing produce segmenti identici.
- [x] Nota: il fixture `write_srt` in `conftest.py` scrive già UTF-8; aggiunto un parametro `encoding` al fixture per i nuovi test.

> **Deviazione dal piano (bug trovato):** l'ordine degli encoding proposto
> (`utf-8-sig, utf-16, cp1252`) era sbagliato: un file cp1252 con accenti fallisce
> UTF-8 ma verrebbe "decodificato" senza errore come UTF-16 garbage (il codec
> `utf-16` non richiede BOM). L'implementazione usa `utf-8-sig, cp1252, utf-16`:
> il test dei NUL discrimina (un UTF-16 letto come cp1252 produce NUL, e ogni
> SRT ha timestamp ASCII → in UTF-16 ogni carattere ASCII porta un byte `00`).

---

## 4. Fase 2 — Fix 🟡 P1

### 4.1 Parser SRT fragile (`split('\n\n')`)

**Problema:** `content.split('\n\n')` (righe 438 e 534) genera blocchi vuoti o perde segmenti con:
- doppie righe vuote (`\n\n\n`);
- fine riga `\r\n` senza normalizzazione (block con `\r` residui);
- spazi/tab su righe vuote.

**Fix proposto:**
1. Normalizzare i fine riga all'inizio: `content = content.replace('\r\n', '\n').replace('\r', '\n')`.
2. Suddividere con regex che tollera righe vuote multiple e spazi:
   `re.split(r'\n[ \t]*\n+', content.strip('\n'))` (attenzione: mantenere il comportamento attuale di ignorare i blocchi malformati).
3. Estrarre il parsing in un metodo unico riusabile `_iter_srt_blocks(content)` per evitare la duplicazione tra riga 438 e 534 (DRY).

**Modifica concreta (`logic.py`):**

```python
@staticmethod
def _iter_srt_blocks(content):
    """Normalizza i fine riga e suddivide il contenuto SRT in blocchi.
    Tollerante a \r\n, righe vuote multiple e spazi sulle righe vuote."""
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    for block in re.split(r'\n[ \t]*\n+', content.strip('\n')):
        block = block.strip()
        if block:
            yield block
```

Poi in `_parse_srt_segments` (riga 534) e `extract_srt_text_sample` (riga 438):
`splitting` → `for block in self._iter_srt_blocks(content):`.

**Criteri di accettazione:**
- [x] File con `\r\n`, righe vuote doppie/triple, spazi sulle righe vuote → stesso numero di segmenti di un file pulito.
- [x] Nessun cambiamento nel comportamento per i file SRT standard (i blocchi malformati REALI restano conteggiati come invalidi; i blocchi VUOTI non lo sono più — era parte del bug).
- [x] Test automatizzato: esteso `tests/test_parsing.py` con file "sporchi" (CRLF, blank multipli, spazi) confrontati con il caso pulito.

---

### 4.2 Thread zombie su timeout API

**Problema:** in `_retry_with_backoff` (riga 225), con timeout viene creato un
`ThreadPoolExecutor(max_workers=1)` per tentativo e si chiama `shutdown(wait=False)`
(riga 245): se l'operazione resta appesa (socket senza timeout), il thread resta
vivo in background finché l'OS non lo chiude. Su batch lunghi si accumulano thread orfani.

**Analisi delle cause:**
- `deep_translator` (GoogleTranslator) usa `requests` **senza timeout** esplicito → può restare appeso per sempre.
- `edge-tts` usa `aiohttp`; `Communicate` accetta parametri di timeout nelle versioni recenti.

**Fix proposto (a strati):**
1. **Default timeout a livello socket** in `config.py` (fix globale per `requests`/urllib3):
   ```python
   import socket
   socket.setdefaulttimeout(API_TIMEOUT)   # urllib3 rispetta il default se nessun timeout esplicito
   ```
   (attenzione: va fatto DOPO la definizione di `API_TIMEOUT`).
2. **Timeout esplicito per edge-tts:** passare `connect_timeout`/`receive_timeout` a
   `edge_tts.Communicate(text, voice, ...)` se supportati (controllare la versione installata);
   in alternativa mantenere il wrapper executor come safety net.
3. **Mantenere il wrapper executor** (linea 245) come rete di sicurezza, ma documentare che i thread
   residui ora terminano entro `API_TIMEOUT` (grazie ai fix 1-2).
4. Verificare che `GoogleTranslator.translate` accetti un parametro `timeout` o eseguirlo con
   `requests` patchato: se non disponibile, il fix 1 è sufficiente.

**Criteri di accettazione:**
- [x] Una chiamata a `translate_text` contro un endpoint irraggiungibile ritorna entro ~`API_TIMEOUT`+backoff, senza thread orfani permanenti (il socket di `requests` eredita `socket.setdefaulttimeout(API_TIMEOUT)`; `deep_translator` non accetta timeout espliciti → il fix globale è l'unico possibile).
- [x] Il task dell'executor completa l'operazione e non resta in zombie (verificato con `threading.Event` nel test; `active_count()` non è usato perché `ThreadPoolExecutor` mantiene i worker idle vivi fino a 60s anche a lavoro concluso — sarebbe un falso negativo).
- [x] Test automatizzato: esteso `tests/test_retry.py` → operazione lenta oltre il timeout: il chiamante è rilasciato entro ~timeout e il thread del task completa l'operazione.

---

## 5. Fase 3 — Fix 🔵 P2 (robustezza e UX)

### 5.1 Scrittura cache JSON atomica

**Problema:** `_save_persistent_cache` (riga 88) scrive direttamente su
`translation_cache.json`: un crash o un write concorrente a metà scrittura corrompe l'intera cache.

**Fix proposto:** scrittura atomica via file temporaneo + `os.replace`:

```python
tmp_file = cache_file + '.tmp'
with open(tmp_file, 'w', encoding='utf-8') as f:
    json.dump(self._cache, f, ensure_ascii=False, indent=2)
os.replace(tmp_file, cache_file)   # atomico su Windows e Unix
```

**Criteri di accettazione:**
- [x] Simulando un crash a metà scrittura (kill del processo), il file cache originale resta valido (o manca, mai corrotto) — garantito da `os.replace`.
- [x] Test: esteso `tests/test_cache.py` → `.tmp` corrotto ignorato dal load; il save successivo sovrascrive senza lasciare tmp.

### 5.2 Ridurre la dipendenza Windows-centrica

**Problema:** `gui.py:515,535` usa `os.startfile` (solo Windows); `config.py` scarica build FFmpeg win64.

**Fix proposto:**
1. Helper cross-platform in `gui.py`:
   ```python
   def _open_with_system(self, path):
       if sys.platform == 'win32':
           os.startfile(path)
       elif sys.platform == 'darwin':
           subprocess.Popen(['open', path])
       else:
           subprocess.Popen(['xdg-open', path])
   ```
   (usare al posto di `os.startfile` nelle 2 occorrenze della preview).
2. In `config.py`, rendere esplicita la limitazione del download FFmpeg:
   - mantenere l'URL win64 per Windows;
   - su altri OS, loggare un messaggio chiaro ("download automatico non supportato,
     installa ffmpeg manualmente") invece di tentare il download win64.

**Criteri di accettazione:**
- [x] La preview apre il player correttamente su Windows (nessuna regressione: `os.startfile` resta il ramo win32).
- [x] Su macOS/Linux l'app non crasha su `open_with_system` (rami `open`/`xdg-open`; verificabile solo su quelle piattaforme).
- [x] `check_and_update_ffmpeg` su piattaforma non-Windows non scarica build win64 (early return con messaggio esplicito).

### 5.3 Visibilità dei segmenti SRT invalidi (UX)

**Problema:** `invalid_count` viene solo loggato; l'utente non sa quanti segmenti sono stati scartati.

**Fix proposto:**
1. `process()` (riga 936) deve arricchire il messaggio di ritorno con il riepilogo
   (`f"{total} segmenti, {invalid} ignorati"`), propagato da `generate_synced_audio`.
2. Prima di avviare l'elaborazione, la GUI mostra un riepilogo con `messagebox.askyesno`
   se `invalid_count > 0`: "⚠️ N segmenti SRT ignorati (formato non valido). Continuare?".

**Criteri di accettazione:**
- [x] Con un SRT che ha segmenti malformati, la GUI avvisa l'utente prima di partire (`_warn_invalid_segments` → `askyesno`).
- [x] Con SRT pulito, nessun dialogo aggiuntivo (nessuna regressione UX).

### 5.4 Cache TTS in memoria: trim su hit da disco

**Problema:** in `translate_and_fetch_tts` (riga ~487), quando il TTS viene caricato dal disco
(`cached_tts is not None`), si inserisce nella `_tts_memory_cache` **senza** chiamare
`_trim_tts_memory_cache()` → la cache in memoria può superare `MAX_TTS_MEMORY_ENTRIES`.

**Fix proposto:** aggiungere `self._trim_tts_memory_cache()` subito dopo l'inserimento
nel ramo "hit da disco" (come già fatto nel ramo di generazione).

**Criteri di accettazione:**
- [x] Dopo N hit da disco con N > `MAX_TTS_MEMORY_ENTRIES`, `len(self._tts_memory_cache) <= MAX_TTS_MEMORY_ENTRIES`.
- [x] Test: esteso `tests/test_cache.py` → cache disco popolata con 10 file, hit ripetuti, limite 5 rispettato ad ogni passo.

---

## 6. Fase 4 — Regressione, Build e Documentazione

- [x] Eseguire l'intera suite: `python -m pytest -q` → **verde** (68/68: 47 baseline + 21 nuovi).
- [ ] Smoke test manuale end-to-end con un SRT piccolo (richiede video reale + rete per API TTS/translate):
  1. Modalità audio (più veloce) → OK;
  2. Modalità video con mix → OK;
  3. Embed SRT → OK;
  4. Batch con 2 file → OK;
  5. Preview before/after → OK.
- [x] Verificare che l'avvio non produca warning nuovi: import di `config`/`logic`/`gui` + istanziamento `App()` puliti.
- [x] Aggiornato `fix.md`: bug risolti nella v1.8.2 e sezione "Bug aperti residui" aggiornata.
- [x] Aggiornato `README.md`: sezione v1.8.2 + nuove righe nella tabella "Bug Fixati".
- [ ] (Opzionale) Rebuild del bundle: `pyinstaller build_app.spec` e smoke test del `.exe`.

---

## 7. Test Nuovi da Aggiungere

| File test | Copertura |
|:---|:---|
| `tests/test_encoding.py` (nuovo) | Parsing SRT in UTF-8-sig, UTF-16, cp1252 → segmenti identici |
| `tests/test_parsing.py` (estensione) | CRLF, righe vuote multiple, spazi su righe vuote → nessun segmento perso |
| `tests/test_retry.py` (estensione) | Timeout reale: `operation` lenta → termine entro il tempo atteso; nessun thread orfano |
| `tests/test_cache.py` (estensione) | Scrittura atomica (tmp ignorato se corrotto); trim cache TTS su hit da disco |
| `tests/test_batch.py` (estensione) | Rifiuto di avvio concorrente (batch+singola) |

---

## 8. Ordine di Esecuzione Consigliato

1. **Fase 0** (baseline + branch) — 10 min
2. **3.1** Concorrenza — 30 min
3. **3.2** Encoding — 30 min (+ test)
4. **4.1** Parser SRT — 45 min (+ test)
5. **4.2** Timeout/zombie — 1 h (+ test)
6. **5.1** Cache atomica — 20 min (+ test)
7. **5.4** Trim TTS — 10 min (+ test)
8. **5.2 / 5.3** Cross-platform + UX — 45 min
9. **Fase 4** Regressione e docs — 30 min

**Totale stimato: ~4-5 ore.**

---

## 9. Rischi e Note

- **`socket.setdefaulttimeout`** è globale di processo: verificare che non degradi altre parti
  dell'app (es. download FFmpeg usa `urllib` con timeout esplicito a 120s → nessun impatto).
- **`edge-tts` timeout**: dipende dalla versione installata; verificare la firma di
  `edge_tts.Communicate` prima di aggiungere parametri (altrimenti mantenere il wrapper).
- **`_read_text_file`**: il fallback `cp1252` con `errors='replace'` può alterare caratteri
  rari su file realmente UTF-8 corrotti — accettabile come ultima spiaggia, loggare l'encoding usato.
- **Nessuna modifica** a `stretch_audio`, `merge_audio_video_mixed`, `_build_audio_timeline`,
  `BatchProcessor.process_all`: logica già solida e coperta da test.
