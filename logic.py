import os
import asyncio
import time
import json
import pickle
import hashlib
import re
import subprocess
import tempfile
import shutil
import threading
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed

import config

# Il PATH per i binari FFmpeg viene preparato da config.py all'import
# (config e' importato qui sopra, PRIMA di pydub): vedi config.py.
# Senza questa preparazione pydub risolverebbe i binari in modo errato
# (RuntimeWarning "Couldn't find ffmpeg or avconv").

from pydub import AudioSegment
from deep_translator import GoogleTranslator

# Forza i binari di pydub sul percorso risolto da config.py (ffmpeg_persistent
# o percorso utente): pydub usa questi path per from_file/export.
if os.path.basename(str(config.FFMPEG_BIN)) == 'ffmpeg.exe' and os.path.exists(config.FFMPEG_BIN):
    AudioSegment.converter = config.FFMPEG_BIN
    _ffprobe_bin = os.path.join(os.path.dirname(config.FFMPEG_BIN), 'ffprobe.exe')
    if os.path.exists(_ffprobe_bin):
        AudioSegment.ffprobe = _ffprobe_bin

# Flag Windows per non mostrare finestre console nei subprocess (0 su altri OS)
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

# ==============================================================================
# LOGICA DI ELABORAZIONE (BACKEND)
# ==============================================================================

class ProcessingGuard:
    """Guardia condivisa per l'elaborazione: produzione singola e batch non
    devono mai correre in parallelo (due pipeline = FFmpeg/TTS concorrenti
    sugli stessi output → file corrotti o crash).

    Uso: `if not guard.try_begin(): rifiuta` ... `finally: guard.end()`."""

    def __init__(self):
        self._active = False

    @property
    def active(self):
        return self._active

    def try_begin(self):
        """Ritorna True (e blocca) se nessun'elaborazione è in corso."""
        if self._active:
            return False
        self._active = True
        return True

    def end(self):
        self._active = False


class VideoTranslatorLogic:
    """
    CORE ENGINE di elaborazione neurale per la traduzione audio-video.

    RUOLO TECNICO:
    - Orchestrazione della pipeline: SRT -> Traduzione -> TTS Neurale -> Sincronizzazione Temporale -> Mixaggio.
    - Gestione della resilienza tramite Exponential Backoff per le chiamate API esterne.
    - Manipolazione digitale dell'audio via pydub e FFmpeg (time-stretching senza pitch shift).
    """
    def __init__(self, log_callback, progress_callback=None):
        """
        Inizializza la logica di business.
        :param log_callback: Funzione chiamata per inviare messaggi alla console della GUI.
        :param progress_callback: Funzione chiamata per aggiornare la barra di progresso.
        """
        self.log = log_callback
        self.update_progress = progress_callback
        self._cache = {}
        self._tts_memory_cache = {}
        self._persistent_cache_dir = config.CACHE_DIR
        self._last_segments = []
        # Riepilogo ultimo parsing SRT: (segmenti_validi, segmenti_ignorati)
        self._last_summary = (0, 0)
        # RLock: la cache viene letta/scritta da più worker thread in parallelo
        self._cache_lock = threading.RLock()
        self._tts_cache_lock = threading.RLock()
        self._tts_cache_saves = 0
        self._load_persistent_cache()

    def _get_cache_key(self, text, lang_code=None, gender="male"):
        """Genera un hash SHA256 univoco per il cache."""
        key_str = f"{text}_{lang_code}_{gender}"
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]

    def _load_persistent_cache(self):
        """Carica la cache persistente da disco all'avvio."""
        if not config.PERSISTENT_CACHE_ENABLED:
            self.log("ℹ️ Cache persistente disabilitata")
            return
        
        try:
            cache_file = os.path.join(self._persistent_cache_dir, 'translation_cache.json')
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    loaded_cache = json.load(f)
                    self._cache.update(loaded_cache)
                    self.log(f"✅ Cache caricata: {len(loaded_cache)} elementi")
        except Exception as e:
            self.log(f"⚠️ Errore carica cache: {e}")

    def _save_persistent_cache(self):
        """Salva la cache su disco per persistenza."""
        if not config.PERSISTENT_CACHE_ENABLED:
            return
        
        try:
            cache_file = os.path.join(self._persistent_cache_dir, 'translation_cache.json')
            
            with self._cache_lock:
                # Controllo dimensione cache
                self._enforce_cache_limit()
                
                # Scrittura atomica: tmp + os.replace. Un crash a metà write
                # lascia il file precedente intatto (mai una cache corrotta).
                tmp_file = cache_file + '.tmp'
                with open(tmp_file, 'w', encoding='utf-8') as f:
                    json.dump(self._cache, f, ensure_ascii=False, indent=2)
                os.replace(tmp_file, cache_file)
        except Exception as e:
            self.log(f"⚠️ Errore salva cache: {e}")

    def _enforce_cache_limit(self):
        """Mantieni la cache entro i limiti di dimensione."""
        try:
            cache_file = os.path.join(self._persistent_cache_dir, 'translation_cache.json')
            if not os.path.exists(cache_file):
                return
            
            file_size_mb = os.path.getsize(cache_file) / (1024 * 1024)
            if file_size_mb > config.MAX_CACHE_SIZE_MB:
                self.log(f"📊 Cache troppo grande ({file_size_mb:.1f}MB), riduzione...")
                # Riduco la cache mantenendo solo il 50% degli elementi più recenti
                sorted_items = sorted(self._cache.items(), key=lambda x: x[1].get('_timestamp', 0), reverse=True)
                half_size = len(sorted_items) // 2
                self._cache = {k: v for k, v in sorted_items[:half_size]}
        except Exception as e:
            self.log(f"⚠️ Errore controllo dimensione cache: {e}")

    def _enforce_tts_cache_limit(self):
        """Rimuove i file audio TTS (tts_*.pkl) più vecchi finché la cache non rientra nel limite."""
        try:
            cache_dir = self._persistent_cache_dir
            if not os.path.isdir(cache_dir):
                return
            
            files = [f for f in os.listdir(cache_dir) if f.startswith('tts_') and f.endswith('.pkl')]
            if not files:
                return
            
            total_mb = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in files) / (1024 * 1024)
            if total_mb <= config.MAX_CACHE_SIZE_MB:
                return
            
            self.log(f"📊 Cache TTS troppo grande ({total_mb:.1f}MB), rimozione file più vecchi...")
            files.sort(key=lambda f: os.path.getmtime(os.path.join(cache_dir, f)))
            while total_mb > config.MAX_CACHE_SIZE_MB and files:
                oldest = files.pop(0)
                path = os.path.join(cache_dir, oldest)
                total_mb -= os.path.getsize(path) / (1024 * 1024)
                try:
                    os.remove(path)
                except OSError:
                    pass
        except Exception as e:
            self.log(f"⚠️ Errore pulizia cache TTS: {e}")

    def _get_cached_translation(self, text, src_lang, tgt_lang):
        """Recupera traduzione dal cache."""
        if not config.PERSISTENT_CACHE_ENABLED:
            return None
        
        with self._cache_lock:
            cache_key = f"{text}_{src_lang}_{tgt_lang}"
            if cache_key in self._cache:
                entry = self._cache[cache_key]
                # Aggiorna timestamp accesso
                entry['_timestamp'] = time.time()
                return entry.get('translated_text')
        
        return None

    def _set_cached_translation(self, text, src_lang, tgt_lang, translated_text):
        """Salva traduzione nel cache."""
        if not config.PERSISTENT_CACHE_ENABLED:
            return
        
        with self._cache_lock:
            cache_key = f"{text}_{src_lang}_{tgt_lang}"
            self._cache[cache_key] = {
                'translated_text': translated_text,
                '_timestamp': time.time()
            }
            
            # Salva su disco ogni 50 nuove voci per performance
            if len(self._cache) % 50 == 0:
                self._save_persistent_cache()

    def _trim_tts_memory_cache(self):
        """Mantiene la cache TTS in memoria entro un limite di voci
        (il dict preserva l'ordine di inserimento: vengono rimosse le più vecchie).
        Da chiamare SOLO con _tts_cache_lock già acquisito."""
        while len(self._tts_memory_cache) > config.MAX_TTS_MEMORY_ENTRIES:
            self._tts_memory_cache.pop(next(iter(self._tts_memory_cache)))

    def _get_cached_tts(self, text, lang_code, gender):
        """Recupera TTS dal cache (file audio)."""
        if not config.PERSISTENT_CACHE_ENABLED:
            return None

        cache_key = self._get_cache_key(text, lang_code, gender)
        audio_file = os.path.join(self._persistent_cache_dir, f'tts_{cache_key}.pkl')

        with self._tts_cache_lock:
            if os.path.exists(audio_file):
                try:
                    with open(audio_file, 'rb') as f:
                        return pickle.load(f)
                except Exception:
                    return None
        return None

    def _set_cached_tts(self, text, lang_code, gender, audio_segment):
        """Salva TTS nel cache (file audio)."""
        if not config.PERSISTENT_CACHE_ENABLED:
            return
        
        cache_key = self._get_cache_key(text, lang_code, gender)
        audio_file = os.path.join(self._persistent_cache_dir, f'tts_{cache_key}.pkl')
        
        with self._tts_cache_lock:
            try:
                with open(audio_file, 'wb') as f:
                    pickle.dump(audio_segment, f)
            except Exception as e:
                self.log(f"⚠️ Errore salva TTS cache: {e}")
                return
            # Pulizia periodica: verifica la dimensione ogni 10 salvataggi
            self._tts_cache_saves += 1
            if self._tts_cache_saves % 10 == 0:
                self._enforce_tts_cache_limit()

    def _retry_with_backoff(self, operation, label="API", timeout=None, max_retries=3, initial_delay=2):
        """Loop comune di retry con Exponential Backoff (usato da API e FFmpeg).

        - `operation`: callable senza argomenti, eseguita a ogni tentativo.
        - `timeout` non-None: esegue l'operazione in un ThreadPoolExecutor con
          timeout. Executor esplicito: con il context manager `shutdown(wait=True)`
          bloccherebbe l'esecuzione se il task resta appeso (timeout inefficace).
        - Ogni fallimento (eccezione o timeout) ripete il tentativo con backoff
          2s, 4s, 8s... senza attendere dopo l'ultimo tentativo.
        """
        last_exception = None
        for attempt in range(max_retries):
            try:
                if timeout is not None:
                    executor = ThreadPoolExecutor(max_workers=1)
                    try:
                        future = executor.submit(operation)
                        return future.result(timeout=timeout)
                    finally:
                        # Non attendiamo eventuali task appesi in background
                        executor.shutdown(wait=False)
                return operation()
            except concurrent.futures.TimeoutError:
                self.log(f"⏱️ Timeout {label} tentativo {attempt + 1}/{max_retries} ({timeout}s)")
                last_exception = Exception(f"Timeout dopo {timeout}s")
            except Exception as e:
                last_exception = e
                self.log(f"⚠️ {label} tentativo {attempt + 1}/{max_retries} fallito: {e}")

            delay = initial_delay * (2 ** attempt)
            if attempt < max_retries - 1:
                self.log(f"Riprovo {label} tra {delay}s...")
                time.sleep(delay)
        raise last_exception

    def execute_with_retry(self, func, *args, timeout=None, max_retries=3, initial_delay=2, **kwargs):
        """
        Esegue `func(*args, **kwargs)` con Exponential Backoff e timeout
        configurabile (evita blocchi infiniti sulle API).
        Default timeout da `config.API_TIMEOUT`.
        """
        if timeout is None:
            timeout = config.API_TIMEOUT
        return self._retry_with_backoff(lambda: func(*args, **kwargs), label="API",
                                        timeout=timeout, max_retries=max_retries,
                                        initial_delay=initial_delay)

    def ffmpeg_execute_with_retry(self, cmd, max_retries=None, initial_delay=None):
        """Retry logic per comandi FFmpeg (stretching/mixing)."""
        if max_retries is None:
            max_retries = config.FFMPEG_MAX_RETRIES
        if initial_delay is None:
            initial_delay = config.FFMPEG_RETRY_DELAY
        return self._retry_with_backoff(
            lambda: subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   check=True, creationflags=NO_WINDOW),
            label="FFmpeg", max_retries=max_retries, initial_delay=initial_delay)

    @staticmethod
    def _temp_file(suffix):
        """Crea un file temporaneo persistente su disco e ne restituisce il path
        (pattern `NamedTemporaryFile(delete=False)`: il file resta finché il
        chiamante non lo rimuove esplicitamente)."""
        tf = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        name = tf.name
        tf.close()
        return name

    def check_disk_space(self, path, required_mb):
        """Verifica spazio disco disponibile prima dell'elaborazione."""
        try:
            # Se il path non esiste ancora, crea le directory (nuovi percorsi utente)
            path = path or '.'
            os.makedirs(path, exist_ok=True)
            stat = shutil.disk_usage(path)
            available_mb = stat.free / (1024 * 1024)
            if available_mb < required_mb:
                raise Exception(
                    f"Spazio insufficiente: {available_mb:.1f}MB disponibili, "
                    f"richiesti {required_mb:.1f}MB"
                )
            self.log(f"💾 Spazio disco OK: {available_mb:.1f}MB disponibili (richiesti {required_mb:.1f}MB)")
            return True
        except Exception as e:
            self.log(f"❌ {e}")
            return False

    def srt_time_to_ms(self, time_str):
        """
        Converte una stringa di tempo in millisecondi totali.

        Gestisce formati SRT con virgola o punto come separatore dei decimali
        e supporta anche durate oltre le 24h (ore senza limite di 2 cifre).
        """
        if time_str is None or not time_str.strip():
            raise ValueError("Timestamp vuoto")

        m = re.fullmatch(r'\s*(\d+):(\d{1,2}):(\d{1,2})[.,](\d{1,4})\s*', time_str)
        if not m:
            raise ValueError(f"Formato timestamp non valido: {time_str}")

        hours, minutes, seconds, millis_str = m.groups()
        hours, minutes, seconds = int(hours), int(minutes), int(seconds)
        # Accetta anche millisecondi a 4+ cifre (formato non standard):
        # vengono considerate solo le prime 3 cifre significative
        millis = int(millis_str[:3].ljust(3, '0'))

        if minutes >= 60 or seconds >= 60:
            raise ValueError(f"Minuti o secondi fuori range: {time_str}")

        return (hours * 3600000) + (minutes * 60000) + (seconds * 1000) + millis

    def stretch_audio(self, audio_segment, target_duration_ms, force_sync=False, max_speed=1.5):
        """
        Sincronizzatore temporale del segmento audio tramite Time-Stretching.

        DETTAGLI TECNICI:
        Il problema principale è che la sintesi vocale (TTS) produce audio di durata variabile, 
        spesso diversa dalla finestra temporale definita nel file SRT.
        Per risolvere questo, utilizziamo il filtro `atempo` di FFmpeg:
        - A differenza della riproduzione veloce standard, `atempo` altera la velocità 
          di lettura senza cambiare la frequenza fondamentale (Pitch), mantenendo la voce naturale.
        - Se `force_sync=False`, l'accelerazione è limitata a `max_speed` per evitare l'effetto "chipmunk".
        """
        current_duration_ms = len(audio_segment)
        if current_duration_ms <= target_duration_ms:
            return audio_segment

        speed_factor = current_duration_ms / target_duration_ms
        
        if speed_factor > 1.3:
            self.log(f"⚠️ Attenzione: Segmento molto compresso ({speed_factor:.2f}x). Potrebbe risultare innaturale.")

        if not force_sync:
            if speed_factor > max_speed:
                self.log(f"⚠️ Segmento troppo lungo ({speed_factor:.2f}x). Limitando a {max_speed:.2f}x per qualità.")
                speed_factor = max_speed
        else:
            self.log(f"⚡ Sincronizzazione Forzata: applicando velocità esatta {speed_factor:.2f}x")

        # atempo di FFmpeg accetta fattori solo nell'intervallo [0.5, 100]
        speed_factor = max(0.5, min(speed_factor, 100.0))

        temp_in = self._temp_file(".mp3")
        audio_segment.export(temp_in, format="mp3")

        temp_out = self._temp_file(".mp3")

        try:
            cmd = [config.FFMPEG_BIN, '-y', '-i', temp_in, '-filter:a', f"atempo={speed_factor}", temp_out]
            self.ffmpeg_execute_with_retry(cmd)
            stretched_audio = AudioSegment.from_file(temp_out)
        except subprocess.CalledProcessError as e:
            self.log(f"❌ Errore FFmpeg durante stretch audio: {e}")
            return audio_segment
        finally:
            if os.path.exists(temp_in): os.remove(temp_in)
            if os.path.exists(temp_out): os.remove(temp_out)

        return stretched_audio

    async def _async_tts_generate(self, text, lang_code, gender="male"):
        """
        Interfaccia asincrona per la generazione di sintesi vocale neurale.

        IMPLEMENTAZIONE:
        - Utilizza il protocollo Microsoft Edge TTS via `edge-tts`.
        - Poiché l'operazione è I/O bound (richiesta di rete), è implementata come coroutine (`async`).
        - Il flusso audio viene salvato in un file temporaneo sul disco, caricato in memoria 
          come oggetto `AudioSegment` e successivamente il file fisico viene rimosso.
        """
        import edge_tts # Import locale per evitare conflitti di asyncio all'avvio
        
        cache_key = f"{text}_{lang_code}_{gender}"
        
        # Controllo cache in memoria prima (cache TTS separata)
        with self._tts_cache_lock:
            if cache_key in self._tts_memory_cache:
                return self._tts_memory_cache[cache_key]
        
        # Controllo cache persistente (file audio)
        cached_audio = self._get_cached_tts(text, lang_code, gender)
        if cached_audio is not None:
            with self._tts_cache_lock:
                self._tts_memory_cache[cache_key] = cached_audio
                self._trim_tts_memory_cache()
            return cached_audio
        
        voice_map = config.VOICE_MAP.get(lang_code, config.VOICE_MAP["en"])
        voice = voice_map.get(gender, voice_map["male"])
        # Timeout espliciti su edge-tts (versioni >= 6.0): evitano connessioni
        # appese che il solo wrapper executor non sa terminare
        try:
            communicate = edge_tts.Communicate(
                text, voice,
                connect_timeout=min(15, config.API_TIMEOUT_TTS),
                receive_timeout=config.API_TIMEOUT_TTS)
        except TypeError:
            # edge-tts vecchio senza parametri di timeout: si fa affidamento
            # sul wrapper executor di execute_with_retry (safety net)
            communicate = edge_tts.Communicate(text, voice)
        
        temp_path = self._temp_file(".mp3")
        await communicate.save(temp_path)
        
        audio = AudioSegment.from_file(temp_path)
        os.remove(temp_path)
        
        # Salva in cache memoria TTS (separata dalla cache testuale) e su disco
        with self._tts_cache_lock:
            self._tts_memory_cache[cache_key] = audio
            self._trim_tts_memory_cache()
        self._set_cached_tts(text, lang_code, gender, audio)
        
        return audio

    @staticmethod
    def _read_text_file(path):
        """Legge un file di testo rilevando l'encoding (UTF-8 con BOM, cp1252,
        UTF-16). I file SRT su Windows sono spesso ANSI o UTF-16: aprire sempre
        con utf-8 farebbe crashare con UnicodeDecodeError.

        L'ordine è significativo: cp1252 PRIMA di utf-16, perché un file cp1252
        con accenti fallisce UTF-8 ma verrebbe "decodificato" senza errore come
        UTF-16 garbage (il codec utf-16 non richiede BOM). Il test dei NUL
        discrimina: un UTF-16 letto come cp1252 produce NUL (gli SRT hanno
        timestamp ASCII, quindi in UTF-16 ogni carattere ASCII porta un byte 00)."""
        encodings = ['utf-8-sig', 'cp1252', 'utf-16']
        for enc in encodings:
            try:
                with open(path, 'r', encoding=enc) as f:
                    content = f.read()
                # Sanità: encoding errato (es. UTF-16 letto come cp1252) → NUL
                if '\x00' in content:
                    continue
                return content
            except (UnicodeDecodeError, UnicodeError):
                continue
        # Ultima spiaggia: lossy ma senza crash
        with open(path, 'r', encoding='cp1252', errors='replace') as f:
            return f.read()

    @staticmethod
    def _iter_srt_blocks(content):
        """Normalizza i fine riga e suddivide il contenuto SRT in blocchi
        non vuoti. Tollerante a \r\n, righe vuote multiple e spazi/tab sulle
        righe vuote (split('\n\n') perdeva segmenti in questi casi)."""
        content = content.replace('\r\n', '\n').replace('\r', '\n').strip()
        for block in re.split(r'\n[ \t]*\n+', content):
            block = block.strip()
            if block:
                yield block

    def extract_srt_text_sample(self, srt_file, min_chars=50):
        """Estrae un campione di testo dai primi segmenti SRT validi
        (riusa la stessa logica di validazione del parsing del backend,
        evitando la duplicazione del parser nella GUI)."""
        content = self._read_text_file(srt_file).strip()
        sample = ""
        for block in self._iter_srt_blocks(content):
            lines = [line.strip() for line in block.split('\n') if line.strip()]
            if len(lines) < 3:
                continue
            if '-->' not in lines[1]:
                continue
            text = ' '.join(lines[2:]).strip()
            if not text:
                continue
            sample = text
            if len(sample) >= min_chars:
                break
        return sample

    def detect_language(self, text_sample=None):
        """Rileva automaticamente la lingua di un testo campione."""
        try:
            from langdetect import detect, DetectorFactory, LangDetectException
            DetectorFactory.seed = 0
            if text_sample and len(text_sample.strip()) > 10:
                lang = detect(text_sample[:500])
                self.log(f"🌐 Lingua rilevata: {lang}")
                return lang
        except ImportError:
            self.log("ℹ️ langdetect non installato. Installa con: pip install langdetect")
        except LangDetectException:
            self.log("⚠️ Impossibile rilevare la lingua automaticamente")
        except Exception as e:
            self.log(f"⚠️ Errore rilevamento lingua: {e}")
        return None

    def translate_text(self, text, src_lang, tgt_lang):
        """Traduce un singolo testo tramite GoogleTranslator (cache persistente + retry).
        Ritorna il testo originale se src==tgt; None se la traduzione fallisce."""
        if src_lang == tgt_lang:
            return text
        cached = self._get_cached_translation(text, src_lang, tgt_lang)
        if cached:
            return cached
        try:
            translated = self.execute_with_retry(
                lambda: GoogleTranslator(source=src_lang, target=tgt_lang).translate(text))
            if translated:
                self._set_cached_translation(text, src_lang, tgt_lang, translated)
            return translated
        except Exception as e:
            self.log(f"⚠️ Traduzione fallita ({src_lang}->{tgt_lang}): {e}")
            return None

    def translate_and_fetch_tts(self, data):
        """
        Metodo wrapper che coordina la traduzione del testo e la successiva generazione TTS.
        Viene eseguito all'interno di un ThreadPoolExecutor per parallelizzare le richieste.

        Ritorna una tupla: (idx, audio_segment | None, start_ms, translated_text | None)
        """
        idx, text, start_ms, src_lang, tgt_lang, gender = data

        # 1. Traduzione tramite Google Translator (cache persistente + retry)
        translated_text = self.translate_text(text, src_lang, tgt_lang)
        if not translated_text:
            return idx, None, start_ms, None

        # Cache TTS uniforme: chiave basata sul TESTO TRADOTTO (sia memoria che disco)
        tts_key = f"{translated_text}_{tgt_lang}_{gender}"
        with self._tts_cache_lock:
            cached_tts = self._tts_memory_cache.get(tts_key)
            if cached_tts is None:
                cached_tts = self._get_cached_tts(translated_text, tgt_lang, gender)
                if cached_tts is not None:
                    self._tts_memory_cache[tts_key] = cached_tts
                    # Stesso trim del ramo di generazione: senza, i hit da disco
                    # farebbero crescere la cache in memoria oltre il limite
                    self._trim_tts_memory_cache()

        if cached_tts is not None:
            return idx, cached_tts, start_ms, translated_text

        try:
            # 2. Sintesi Vocale Neurale (Edge-TTS richiede asyncio per funzionare)
            def do_tts():
                return asyncio.run(self._async_tts_generate(translated_text, tgt_lang, gender))

            # Timeout TTS più lungo (config.API_TIMEOUT_TTS) rispetto alla traduzione
            phrase_audio = self.execute_with_retry(do_tts, timeout=config.API_TIMEOUT_TTS)
            with self._tts_cache_lock:
                self._tts_memory_cache[tts_key] = phrase_audio
                self._trim_tts_memory_cache()
            return idx, phrase_audio, start_ms, translated_text
        except Exception as e:
            self.log(f"❌ Errore critico segmento {idx}: {e}")
            return idx, None, start_ms, None

    def _parse_srt_segments(self, content):
        """Analizza il contenuto SRT in segmenti validati.
        Ritorna (segments_data, invalid_count); i segmenti non validi
        vengono conteggiati e saltati (stesso formato usato da _build_audio_timeline)."""
        segments_data = []
        invalid_count = 0
        for i, block in enumerate(self._iter_srt_blocks(content)):
            lines = [line.strip() for line in block.split('\n') if line.strip()]

            if len(lines) < 3:
                invalid_count += 1
                continue

            time_line = lines[1] if len(lines) > 1 else ""
            if '-->' not in time_line:
                invalid_count += 1
                self.log(f"⚠️ Segmento {i}: formato timestamp mancante")
                continue

            try:
                parts = re.split(r'\s*-->\s*', time_line)
                start_str, end_str = parts[0].strip(), parts[1].strip()

                start_ms = self.srt_time_to_ms(start_str)
                end_ms = self.srt_time_to_ms(end_str)
                limit_ms = end_ms - start_ms

                if limit_ms <= 0:
                    invalid_count += 1
                    self.log(f"⚠️ Segmento {i}: durata non positiva ({limit_ms}ms)")
                    continue

                text_lines = lines[2:] if len(lines) > 2 else []
                text = " ".join(text_lines)

                if not text.strip():
                    invalid_count += 1
                    self.log(f"⚠️ Segmento {i}: testo vuoto")
                    continue

                segments_data.append({
                    'id': len(segments_data), 'text': text,
                    'start': start_ms,
                    'limit': limit_ms,
                    'translated': None
                })
            except ValueError as ve:
                invalid_count += 1
                self.log(f"⚠️ Segmento {i} timestamp invalido: {ve}")
        return segments_data, invalid_count

    def parse_srt_file(self, srt_file):
        """Legge e analizza un file SRT. Ritorna (segments, invalid_count).
        Metodo pubblico: usato dalla GUI (preview) e dall'export multi-lingua."""
        content = self._read_text_file(srt_file).strip()
        return self._parse_srt_segments(content)

    def _check_pipeline_disk_space(self, output_file, srt_file, total_segments):
        """Verifica lo spazio disco richiesto per l'output e la temp dir.
        Ritorna False (con log di errore) se lo spazio è insufficiente."""
        output_dir = os.path.dirname(output_file) or '.'
        os.makedirs(output_dir, exist_ok=True)
        srt_size_mb = os.path.getsize(srt_file) / (1024 * 1024) if os.path.exists(srt_file) else 5
        required_mb = int(srt_size_mb * 10 + total_segments * 0.5 + 200)
        if not self.check_disk_space(output_dir, required_mb):
            self.log("❌ Elaborazione annullata per spazio disco insufficiente")
            return False
        # I file audio temporanei vengono scritti nella temp dir di sistema
        if not self.check_disk_space(tempfile.gettempdir(), required_mb):
            self.log("❌ Elaborazione annullata: spazio insufficiente nella directory temporanea")
            return False
        return True

    def _build_audio_timeline(self, segments_data, results_map, force_sync=False, max_speed=1.5):
        """Costruisce la timeline audio: stretching per segmento, taglio anti-drift
        e silenzi di allineamento. Aggiorna `translated` sui segmenti.
        Ritorna (audio_pipeline, success_count)."""
        audio_pipeline = []
        last_end_time = 0
        success_count = 0
        total_segments = len(segments_data)

        for idx in range(total_segments):
            res = results_map.get(idx)
            if res is None:
                continue
            _, phrase_audio, start_ms, translated_text = res
            if phrase_audio is None:
                continue
            success_count += 1

            if translated_text:
                segments_data[idx]['translated'] = translated_text

            limit_ms = segments_data[idx]['limit']
            phrase_audio = self.stretch_audio(phrase_audio, limit_ms, force_sync=force_sync, max_speed=max_speed)

            # Anti-drift: se la frase supera l'inizio della successiva (audio
            # oltre il limite o speed cap), viene tagliata per non spostare
            # le frasi successive in ritardo crescente.
            if idx + 1 < total_segments:
                next_start = segments_data[idx + 1]['start']
                max_len = next_start - start_ms
                if max_len > 0 and len(phrase_audio) > max_len:
                    phrase_audio = phrase_audio[:max_len]

            # Calcolo del silenzio necessario prima di questa frase per mantenerla in sincro con il video
            silence_duration = start_ms - last_end_time
            if silence_duration > 0:
                audio_pipeline.append(AudioSegment.silent(duration=silence_duration))

            audio_pipeline.append(phrase_audio)
            last_end_time = start_ms + len(phrase_audio)

        return audio_pipeline, success_count

    def export_translated_srt(self, srt_file, output_template, src_lang, target_langs, progress_callback=None):
        """Esporta l'SRT tradotto in più lingue (#7): per ogni lingua di destinazione
        genera un file `<output_template>.<lang>.srt`. Riusa il parser SRT validato
        e la cache di traduzione della pipeline principale.
        Ritorna la lista dei file generati (vuota se nessun segmento valido)."""
        if not target_langs:
            return []
        content = self._read_text_file(srt_file).strip()
        if not content:
            return []

        segments, invalid_count = self._parse_srt_segments(content)
        if not segments:
            self.log("❌ Nessun segmento SRT valido per l'export multi-lingua")
            return []
        if invalid_count > 0:
            self.log(f"⚠️ {invalid_count} segmenti SRT ignorati nell'export multi-lingua")

        output_dir = os.path.dirname(output_template) or '.'
        os.makedirs(output_dir, exist_ok=True)

        generated = []
        for i, tgt in enumerate(target_langs, 1):
            out_path = f"{output_template}.{tgt}.srt"
            self.log(f"📝 Export SRT in {tgt.upper()}...")
            with open(out_path, 'w', encoding='utf-8') as out:
                for num, seg in enumerate(segments, 1):
                    # Fallback al testo originale se la traduzione fallisce
                    translated = self.translate_text(seg['text'], src_lang, tgt) or seg['text']
                    out.write(f"{num}\n")
                    out.write(f"{self.ms_to_srt_time(seg['start'])} --> {self.ms_to_srt_time(seg['start'] + seg['limit'])}\n")
                    out.write(f"{translated}\n\n")
            generated.append(out_path)
            self.log(f"✅ SRT {tgt.upper()} esportato: {out_path}")
            if progress_callback:
                progress_callback(i / len(target_langs), f"Export SRT {tgt.upper()}")
        return generated

    # ----------------------------------------------------------------------
    # PREVIEW BEFORE/AFTER (#8)
    # ----------------------------------------------------------------------
    def extract_video_audio_segment(self, video_path, out_audio_path, start_ms, end_ms):
        """Estrae la porzione audio del video originale tra start_ms e end_ms
        (Preview BEFORE). Ritorna True se il file audio è stato generato."""
        duration_ms = max(end_ms - start_ms, 100)
        try:
            cmd = [
                config.FFMPEG_BIN, '-y',
                '-ss', f'{start_ms / 1000.0:.3f}',
                '-i', video_path,
                '-t', f'{duration_ms / 1000.0:.3f}',
                '-vn', '-c:a', 'libmp3lame', '-q:a', '4',
                out_audio_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    creationflags=NO_WINDOW)
            return (result.returncode == 0
                    and os.path.exists(out_audio_path)
                    and os.path.getsize(out_audio_path) > 0)
        except Exception as e:
            self.log(f"❌ Errore estrazione audio originale (preview): {e}")
            return False

    def preview_translated_audio(self, text, tgt_lang, gender, out_path):
        """Genera la sintesi TTS di un singolo segmento tradotto e la salva in
        out_path (Preview AFTER). Ritorna True se il file audio è stato creato."""
        try:
            def do_tts():
                return asyncio.run(self._async_tts_generate(text, tgt_lang, gender))
            audio = self.execute_with_retry(do_tts, timeout=config.API_TIMEOUT_TTS)
            audio.export(out_path, format="mp3", bitrate="192k")
            return os.path.exists(out_path) and os.path.getsize(out_path) > 0
        except Exception as e:
            self.log(f"❌ Errore generazione TTS preview: {e}")
            return False

    def generate_synced_audio(self, srt_file, output_file, src_lang='en', tgt_lang='it', gender='male', force_sync=False, max_speed=1.5):
        """
        Pipeline di produzione della traccia audio tradotta e sincronizzata.

        FLUSSO TECNICO DETTAGLIATO:
        1. PARSING SRT: Estrazione dei timestamp (inizio/fine) e del testo con validazione. Calcolo della durata massima (`limit`).
        2. PARALLELIZZAZIONE: Utilizzo di `ThreadPoolExecutor` per eseguire traduzioni e TTS in parallelo. 
            Il numero di worker è adattato dinamicamente al CPU count.
        3. SINCRONIZZAZIONE (Stretching): Per ogni segmento, se la durata TTS > limite SRT, viene applicato lo stretch audio.
        4. RICOSTRUZIONE TIMELINE: Inserimento di segmenti di silenzio (`AudioSegment.silent`) calcolati come 
            differenza tra l'inizio del segmento corrente e la fine del precedente.
        5. EXPORT: Rendering finale in MP3 a 320kbps.
        """
        try:
            self.log(f"⏳ Analisi SRT e Traduzione AI ({src_lang} -> {tgt_lang})...")

            content = self._read_text_file(srt_file).strip()

            if not content or len(content) < 10:
                self.log(f"❌ File SRT vuoto o troppo piccolo")
                return False

            segments_data, invalid_count = self._parse_srt_segments(content)

            # Riepilogo (totali/invalidi) esposto a process() per il messaggio finale
            self._last_summary = (len(segments_data), invalid_count)

            if invalid_count > 0:
                self.log(f"⚠️ {invalid_count} segmenti SRT ignorati (formato non valido)")

            total_segments = len(segments_data)
            if total_segments == 0:
                self.log(f"❌ Nessun segmento SRT valido trovato")
                return False

            if not self._check_pipeline_disk_space(output_file, srt_file, total_segments):
                return False

            self.log(f"⚡ Generazione Audio Neurale in parallelo ({total_segments} segmenti)...")
            
            # Worker dinamico: CPU count * 2, aumentato a 16 per performance
            cpu_count = os.cpu_count() or 4
            max_workers = min(cpu_count * 2, config.MAX_WORKERS)
            
            results_map = {}
            tts_tasks = [(s['id'], s['text'], s['start'], src_lang, tgt_lang, gender) for s in segments_data]
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_idx = {executor.submit(self.translate_and_fetch_tts, task): task[0] for task in tts_tasks}
                completed_count = 0
                for future in as_completed(future_to_idx):
                    res = future.result()
                    results_map[res[0]] = res
                    completed_count += 1
                    if self.update_progress:
                        progress_val = completed_count / total_segments
                        self.update_progress(progress_val, f"Elaborazione neurale segmento {completed_count} di {total_segments}")

            # Costruzione della timeline audio finale
            if self.update_progress:
                self.update_progress(0.9, "Stretching e sincronizzazione audio...")

            audio_pipeline, success_count = self._build_audio_timeline(segments_data, results_map, force_sync=force_sync, max_speed=max_speed)

            if success_count == 0:
                self.log("❌ Nessun segmento elaborato correttamente, nessun audio generato")
                return False

            # Espone i segmenti (con testo tradotto) per l'eventuale embed SRT nel video
            self._last_segments = segments_data

            final_audio = AudioSegment.empty()
            for segment in audio_pipeline:
                final_audio += segment

            final_audio.export(output_file, format="mp3", bitrate="320k")

            # Salva cache su disco alla fine del processo
            if config.PERSISTENT_CACHE_ENABLED:
                self._save_persistent_cache()

            self.log(f"✅ Traccia audio neurale creata con successo!")
            return True
        except Exception as e:
            self.log(f"❌ Errore generazione audio: {e}")
            return False

    def get_video_duration(self, video_path):
        """Recupera la durata del video in secondi usando ffprobe."""
        ffmpeg_bin = config.FFMPEG_BIN
        # Nota: NON usare .replace('ffmpeg','ffprobe') sul path completo:
        # riscriverebbe anche il nome della cartella (es. ffmpeg_persistent).
        if os.path.basename(str(ffmpeg_bin)) == 'ffmpeg.exe':
            ffprobe_bin = os.path.join(os.path.dirname(ffmpeg_bin), 'ffprobe.exe')
        else:
            ffprobe_bin = 'ffprobe'

        if ffprobe_bin != 'ffprobe' and not os.path.exists(ffprobe_bin):
            return None

        try:
            cmd = [ffprobe_bin, '-v', 'error', '-show_entries',
                   'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    creationflags=NO_WINDOW)
            return float(result.stdout.decode().strip())
        except Exception:
            return None

    @staticmethod
    def ms_to_srt_time(ms):
        """Converte millisecondi in timestamp SRT (HH:MM:SS,mmm) senza limiti sulle ore."""
        ms = max(int(ms), 0)
        hours, rem = divmod(ms, 3600000)
        minutes, rem = divmod(rem, 60000)
        seconds, millis = divmod(rem, 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    def merge_audio_video_mixed(self, video_path, translated_audio_path, output_video_path, vol_orig=0.4, vol_trans=1.0, embed_srt=False, segments_data=None):
        """
        Mixer audio-video finale tramite FFmpeg Filter Complex con progress bar.

        ANALISI TECNICA DEL FILTRO:
        Viene costruita una catena di filtri (`filter_complex`) che opera come segue:
        - [0:a]volume={vol_orig}[bg]: Prende l'audio del video originale e ne scala il volume (Background).
        - [1:a]volume={vol_trans}[fg]: Prende la traccia tradotta e ne scala il volume (Foreground).
        - amix=inputs=2:duration=first:normalize=0[out]: Mixa i due flussi in uno solo. `duration=first` assicura 
          che l'output termini quando finisce il video originale, evitando silenzi finali se l'audio è più lungo.
          `normalize=0` evita che FFmpeg abbassi il volume del mix.
        - -c:v copy: Evita la ricodifica del video (Stream Copy), mantenendo la qualità originale e velocizzando il processo.
        """
        srt_path = None
        try:
            self.log(f"🎬 Mixaggio finale (Orig: {vol_orig}, Trad: {vol_trans})...")

            total_duration = self.get_video_duration(video_path)

            filter_complex = f"[0:a]volume={vol_orig}[bg]; [1:a]volume={vol_trans}[fg]; [bg][fg]amix=inputs=2:duration=first:normalize=0[out]"

            # Tutti gli input (-i) vanno PRIMA delle opzioni di output:
            # -map/-c:s sono opzioni output e, se poste dopo un -i,
            # verrebbero applicate erroneamente all'input stesso.
            cmd = [
                config.FFMPEG_BIN, '-y',
                '-i', video_path,
                '-i', translated_audio_path,
            ]

            if embed_srt and segments_data is not None:
                # Usa il testo TRADOTTO quando disponibile e timestamp calcolati
                # senza datetime (evita lo shift del fuso orario e gestisce ore > 24h)
                valid_segments = [seg for seg in segments_data if (seg.get('translated') or seg.get('text') or '').strip()]
                if not valid_segments:
                    self.log("⚠️ Embed SRT richiesto ma nessun segmento con testo disponibile, salto i sottotitoli")
                    embed_srt = False
                else:
                    srt_path = self._temp_file(".srt")
                    with open(srt_path, 'w', encoding='utf-8') as srt_f:
                        for num, seg in enumerate(valid_segments, start=1):
                            seg_text = seg.get('translated') or seg.get('text') or ''
                            if not seg_text.strip():
                                continue
                            srt_f.write(f"{num}\n")
                            srt_f.write(f"{self.ms_to_srt_time(seg['start'])} --> {self.ms_to_srt_time(seg['start'] + seg['limit'])}\n")
                            srt_f.write(f"{seg_text}\n\n")
                    cmd.extend(['-i', srt_path])

            cmd += [
                '-filter_complex', filter_complex,
                '-map', '0:v:0', '-map', '[out]',
                '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
            ]

            if embed_srt and segments_data is not None:
                # L'input SRT è il terzo (-i) -> stream index 2
                cmd += ['-c:s', 'mov_text', '-map', '2:s:0']

            cmd.append(output_video_path)

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                encoding='utf-8',
                errors='replace',
                creationflags=NO_WINDOW
            )

            for line in process.stdout:
                if total_duration and 'time=' in line:
                    time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
                    if time_match:
                        hours, mins, secs = map(float, time_match.groups())
                        elapsed = (hours * 3600) + (mins * 60) + secs
                        progress = min(elapsed / total_duration, 1.0)
                        if self.update_progress:
                            self.update_progress(0.9 + progress * 0.1, f"Mixaggio video... {int(progress*100)}%")

            process.wait()

            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd)

            self.log(f"🚀 VIDEO FINALE PRONTO!")
            return True
        except Exception as e:
            self.log(f"❌ Errore mixaggio finale: {e}")
            return False
        finally:
            if srt_path and os.path.exists(srt_path):
                try:
                    os.remove(srt_path)
                except OSError:
                    pass

    def process(self, srt_file, output_file, video_file=None, src_lang='en', tgt_lang='it', gender='male',
                force_sync=False, max_speed=1.5, vol_orig=0.4, vol_trans=1.0, mode='video', embed_srt=False):
        """
        Pipeline completa unificata: genera l'audio tradotto sincronizzato e,
        se `mode='video'`, esegue il mixaggio con il video originale.

        Gestisce internamente il file audio temporaneo (creazione e pulizia),
        quindi GUI singola e Batch condividono lo stesso flusso.

        Ritorna: (success: bool, messaggio: str)
        """
        audio_tmp = None
        try:
            audio_tmp = self._temp_file(".mp3")
            if not self.generate_synced_audio(
                srt_file, audio_tmp,
                src_lang=src_lang, tgt_lang=tgt_lang, gender=gender,
                force_sync=force_sync, max_speed=max_speed
            ):
                return False, "Errore durante la generazione dell'audio neurale"

            if mode == 'video':
                if not video_file:
                    return False, "Modalità video ma nessun video originale selezionato"
                # Passa i segmenti tradotti generati per l'embed SRT nel video
                segments_data = self._last_segments if embed_srt else None
                if not self.merge_audio_video_mixed(
                    video_file, audio_tmp, output_file,
                    vol_orig=vol_orig, vol_trans=vol_trans,
                    embed_srt=embed_srt, segments_data=segments_data
                ):
                    return False, "Mixaggio video fallito"
            else:
                shutil.copy(audio_tmp, output_file)

            total, invalid = self._last_summary
            summary = f"{total} segmenti" + (f", {invalid} ignorati" if invalid else "")
            return True, f"Operazione completata con successo ({summary})"
        finally:
            if audio_tmp and os.path.exists(audio_tmp):
                try:
                    os.remove(audio_tmp)
                except OSError:
                    pass


class BatchProcessor:
    """Elabora piu file SRT in sequenza senza riavviare l'applicazione."""
    def __init__(self, log_callback, progress_callback=None):
        self.log = log_callback
        self.update_progress = progress_callback
        self.queue = []
        self.is_running = False

    def add_to_queue(self, srt_file, video_file, output_file, src_lang, tgt_lang, gender,
                     force_sync, max_speed, vol_orig, vol_trans, output_mode, embed_srt):
        self.queue.append({
            'srt': srt_file, 'video': video_file, 'output': output_file,
            'src': src_lang, 'tgt': tgt_lang, 'gender': gender,
            'force_sync': force_sync, 'max_speed': max_speed,
            'vol_orig': vol_orig, 'vol_trans': vol_trans,
            'mode': output_mode, 'embed_srt': embed_srt
        })

    def clear_queue(self):
        self.queue.clear()

    def process_all(self, logic_engine):
        """Elabora tutti i file in coda sequenzialmente.

        Ritorna: (success_count, total) per il riepilogo finale nella GUI."""
        self.is_running = True
        total = len(self.queue)
        success_count = 0

        for i, item in enumerate(self.queue):
            self.log(f"\n{'='*50}")
            self.log(f"📦 Batch {i+1}/{total}: {os.path.basename(item['srt'])}")
            self.log(f"{'='*50}")

            try:
                ok, msg = logic_engine.process(
                    item['srt'], item['output'], video_file=item['video'],
                    src_lang=item['src'], tgt_lang=item['tgt'], gender=item['gender'],
                    force_sync=item['force_sync'], max_speed=item['max_speed'],
                    vol_orig=item['vol_orig'], vol_trans=item['vol_trans'],
                    mode=item['mode'], embed_srt=item['embed_srt']
                )
                if ok:
                    success_count += 1
                    self.log(f"✅ Batch {i+1}/{total} completato con successo")
                else:
                    self.log(f"❌ Batch {i+1}/{total} fallito: {msg}")

            except Exception as e:
                self.log(f"❌ Batch {i+1}/{total} errore: {e}")

            if self.update_progress:
                self.update_progress((i + 1) / total, f"Batch {i+1}/{total}")

        self.log(f"\n{'='*50}")
        self.log(f"📊 Batch completato: {success_count}/{total} successi")
        self.is_running = False
        return success_count, total
