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
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydub import AudioSegment
from deep_translator import GoogleTranslator 
import config

# ==============================================================================
# LOGICA DI ELABORAZIONE (BACKEND)
# ==============================================================================

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
        
        if not hasattr(self, '_load_persistent_cache'):
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
            
            # Controllo dimensione cache
            self._enforce_cache_limit()
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
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

    def _get_cached_translation(self, text, src_lang, tgt_lang):
        """Recupera traduzione dal cache."""
        if not config.PERSISTENT_CACHE_ENABLED:
            return None
        
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
        
        cache_key = f"{text}_{src_lang}_{tgt_lang}"
        self._cache[cache_key] = {
            'translated_text': translated_text,
            '_timestamp': time.time()
        }
        
        # Salva su disco ogni 50 nuove voci per performance
        if len(self._cache) % 50 == 0:
            self._save_persistent_cache()

    def _get_cached_tts(self, text, lang_code, gender):
        """Recupera TTS dal cache (file audio)."""
        if not config.PERSISTENT_CACHE_ENABLED:
            return None
        
        cache_key = self._get_cache_key(text, lang_code, gender)
        audio_file = os.path.join(self._persistent_cache_dir, f'tts_{cache_key}.pkl')
        
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
        
        try:
            with open(audio_file, 'wb') as f:
                pickle.dump(audio_segment, f)
        except Exception as e:
            self.log(f"⚠️ Errore salva TTS cache: {e}")

    def execute_with_retry(self, func, *args, timeout=None, max_retries=3, initial_delay=2, **kwargs):
        """
        Implementa un meccanismo di resilienza tramite Exponential Backoff con timeout.

        Aggiunge un timeout configurabile per evitare blocchi infiniti sulle API.
        Utilizza ThreadPoolExecutor per eseguire la funzione con un timeout.
        """
        if timeout is None:
            timeout = config.API_TIMEOUT

        last_exception = None
        for attempt in range(max_retries):
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(lambda: func(*args, **kwargs))
                    return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                self.log(f"⏱️ Timeout API tentativo {attempt + 1}/{max_retries} ({timeout}s)")
                last_exception = Exception(f"Timeout dopo {timeout}s")
            except Exception as e:
                last_exception = e
                delay = initial_delay * (2 ** attempt)
                self.log(f"⚠️ Tentativo {attempt + 1}/{max_retries} fallito. Riprovo tra {delay}s... ({e})")
                time.sleep(delay)
        raise last_exception

    def ffmpeg_execute_with_retry(self, cmd, max_retries=None, initial_delay=None):
        """Retry logic per comandi FFmpeg (stretching/mixing)."""
        if max_retries is None:
            max_retries = config.FFMPEG_MAX_RETRIES
        if initial_delay is None:
            initial_delay = config.FFMPEG_RETRY_DELAY

        last_exception = None
        for attempt in range(max_retries):
            try:
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                return result
            except subprocess.CalledProcessError as e:
                last_exception = e
                delay = initial_delay * (2 ** attempt)
                self.log(f"⚠️ Tentativo FFmpeg {attempt + 1}/{max_retries} fallito. Riprovo tra {delay}s...")
                time.sleep(delay)
        raise last_exception

    def check_disk_space(self, path, required_mb):
        """Verifica spazio disco disponibile prima dell'elaborazione."""
        try:
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
        Gestisce formati SRT con virgola o punto come separatore dei decimali.
        """
        time_str = time_str.strip()
        
        if not time_str:
            raise ValueError("Timestamp vuoto")
        
        try:
            t = datetime.strptime(time_str, "%H:%M:%S,%f")
            return (t.hour * 3600000) + (t.minute * 60000) + (t.second * 1000) + (t.microsecond // 1000)
        except ValueError:
            pass
        
        try:
            time_str = time_str.replace('.', ',')
            t = datetime.strptime(time_str, "%H:%M:%S,%f")
            return (t.hour * 3600000) + (t.minute * 60000) + (t.second * 1000) + (t.microsecond // 1000)
        except ValueError:
            pass
        
        raise ValueError(f"Formato timestamp non valido: {time_str}")

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

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf_in:
            temp_in = tf_in.name
            audio_segment.export(temp_in, format="mp3")

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf_out:
            temp_out = tf_out.name

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
        if cache_key in self._tts_memory_cache:
            return self._tts_memory_cache[cache_key]
        
        # Controllo cache persistente (file audio)
        cached_audio = self._get_cached_tts(text, lang_code, gender)
        if cached_audio is not None:
            self._tts_memory_cache[cache_key] = cached_audio
            return cached_audio
        
        voice_map = config.VOICE_MAP.get(lang_code)
        if not voice_map:
            voice_map = {"male": "en-US-GuyNeural", "female": "en-US-AriaNeural"}
        voice = voice_map.get(gender, voice_map["male"])
        communicate = edge_tts.Communicate(text, voice)
        
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
            temp_path = tf.name
            await communicate.save(temp_path)
        
        audio = AudioSegment.from_file(temp_path)
        os.remove(temp_path)
        
        # Salva in cache memoria TTS (separata dalla cache testuale) e su disco
        self._tts_memory_cache[cache_key] = audio
        self._set_cached_tts(text, lang_code, gender, audio)
        
        return audio

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

    def translate_and_fetch_tts(self, data):
        """
        Metodo wrapper che coordina la traduzione del testo e la successiva generazione TTS.
        Viene eseguito all'interno di un ThreadPoolExecutor per parallelizzare le richieste.
        """
        idx, text, start_ms, src_lang, tgt_lang, gender = data
        
        # Cache persistente: controlla prima se c'è la traduzione
        cached_translation = self._get_cached_translation(text, src_lang, tgt_lang)
        if cached_translation:
            translated_text = cached_translation
        else:
            try:
                # 1. Traduzione tramite Google Translator
                def do_translate():
                    if src_lang != tgt_lang:
                        return GoogleTranslator(source=src_lang, target=tgt_lang).translate(text)
                    return text

                translated_text = self.execute_with_retry(do_translate)
                # Salva nella cache per uso futuro
                self._set_cached_translation(text, src_lang, tgt_lang, translated_text)
            except Exception as e:
                self.log(f"❌ Errore traduzione segmento {idx}: {e}")
                return idx, None, start_ms
        
        # Cache TTS: controlla se l'audio è già stato generato
        cache_key_tts = f"{text}_{tgt_lang}_{gender}"
        cached_tts = self._get_cached_tts(text, tgt_lang, gender)
        if cached_tts is not None:
            return idx, cached_tts, start_ms
        
        try:
            # 2. Sintesi Vocale Neurale (Edge-TTS richiede asyncio per funzionare)
            def do_tts():
                return asyncio.run(self._async_tts_generate(translated_text, tgt_lang, gender))

            phrase_audio = self.execute_with_retry(do_tts)
            
            # Salva TTS nella cache
            self._set_cached_tts(text, tgt_lang, gender, phrase_audio)
            
            return idx, phrase_audio, start_ms
        except Exception as e:
            self.log(f"❌ Errore critico segmento {idx}: {e}")
            return idx, None, start_ms

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
            
            with open(srt_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if not content or len(content) < 10:
                self.log(f"❌ File SRT vuoto o troppo piccolo")
                return False
            
            segments_data = [] 
            invalid_count = 0
            with open(srt_file, 'r', encoding='utf-8') as f:
                content = f.read().strip().split('\n\n')
                for i, block in enumerate(content):
                    lines = [line.strip() for line in block.split('\n') if line.strip()]
                    
                    if len(lines) < 3: 
                        invalid_count += 1
                        continue
                    
                    time_line = lines[1] if len(lines) > 1 else ""
                    if ' --> ' not in time_line:
                        invalid_count += 1
                        self.log(f"⚠️ Segmento {i}: formato timestamp mancante")
                        continue
                    
                    try:
                        parts = time_line.split(' --> ')
                        start_str, end_str = parts[0].strip(), parts[1].strip()
                        
                        start_ms = self.srt_time_to_ms(start_str)
                        end_ms = self.srt_time_to_ms(end_str)
                        limit_ms = end_ms - start_ms
                        
                        if limit_ms <= 0:
                            invalid_count += 1
                            self.log(f"⚠️ Segmento {i}: durata non positiva ({limit_ms}ms)")
                            continue
                        
                        if not start_str or not end_str:
                            invalid_count += 1
                            self.log(f"⚠️ Segmento {i}: timestamp vuoto")
                            continue
                        
                        text_lines = lines[2:] if len(lines) > 2 else []
                        text = " ".join(text_lines)
                        
                        if not text.strip():
                            invalid_count += 1
                            self.log(f"⚠️ Segmento {i}: testo vuoto")
                            continue
                        
                        segments_data.append({
                            'id': i, 'text': text, 
                            'start': start_ms, 
                            'limit': limit_ms
                        })
                    except ValueError as ve:
                        invalid_count += 1
                        self.log(f"⚠️ Segmento {i} timestamp invalido: {ve}")

            if invalid_count > 0:
                self.log(f"⚠️ {invalid_count} segmenti SRT ignorati (formato non valido)")
            
            # Controllo spazio disco necessario
            total_segments = len(segments_data)
            output_dir = os.path.dirname(output_file) or '.'
            srt_size_mb = os.path.getsize(srt_file) / (1024 * 1024) if os.path.exists(srt_file) else 5
            required_mb = int(srt_size_mb * 10 + total_segments * 0.5 + 200)
            if not self.check_disk_space(output_dir, required_mb):
                self.log("❌ Elaborazione annullata per spazio disco insufficiente")
                return False
            if total_segments == 0:
                self.log(f"❌ Nessun segmento SRT valido trovato")
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
            audio_pipeline = []
            last_end_time = 0

            for idx in range(total_segments):
                if idx not in results_map: continue
                _, phrase_audio, start_ms = results_map[idx]
                if phrase_audio is None: continue
                
                limit_ms = segments_data[idx]['limit']
                phrase_audio = self.stretch_audio(phrase_audio, limit_ms, force_sync=force_sync, max_speed=max_speed)
                
                # Calcolo del silenzio necessario prima di questa frase per mantenerla in sincro con il video
                silence_duration = start_ms - last_end_time
                if silence_duration > 0:
                    audio_pipeline.append(AudioSegment.silent(duration=silence_duration))
                
                audio_pipeline.append(phrase_audio)
                last_end_time = start_ms + len(phrase_audio)

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
        try:
            cmd = [config.FFMPEG_BIN.replace('ffmpeg', 'ffprobe'), '-v', 'error', '-show_entries',
                   'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            return float(result.stdout.decode().strip())
        except:
            return None

    def merge_audio_video_mixed(self, video_path, translated_audio_path, output_video_path, vol_orig=0.4, vol_trans=1.0, embed_srt=False, segments_data=None):
        """
        Mixer audio-video finale tramite FFmpeg Filter Complex con progress bar.

        ANALISI TECNICA DEL FILTRO:
        Viene costruita una catena di filtri (`filter_complex`) che opera come segue:
        - [0:a]volume={vol_orig}[bg]: Prende l'audio del video originale e ne scala il volume (Background).
        - [1:a]volume={vol_trans}[fg]: Prende la traccia tradotta e ne scala il volume (Foreground).
        - amix=inputs=2:duration=first[out]: Mixa i due flussi in uno solo. `duration=first` assicura 
          che l'output termini quando finisce il video originale, evitando silenzi finali se l'audio è più lungo.
        - -c:v copy: Evita la ricodifica del video (Stream Copy), mantenendo la qualità originale e velocizzando il processo.
        """
        try:
            self.log(f"🎬 Mixaggio finale (Orig: {vol_orig}, Trad: {vol_trans})...")

            total_duration = self.get_video_duration(video_path)

            filter_complex = f"[0:a]volume={vol_orig}[bg]; [1:a]volume={vol_trans}[fg]; [bg][fg]amix=inputs=2:duration=first[out]"
            
            cmd = [
                config.FFMPEG_BIN, '-y', '-i', video_path, '-i', translated_audio_path, 
                '-filter_complex', filter_complex, '-map', '0:v:0', '-map', '[out]', 
                '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', output_video_path
            ]
            
            if embed_srt and segments_data is not None:
                srt_path = os.path.join(tempfile.gettempdir(), f'embed_{os.path.basename(output_video_path)}.srt')
                with open(srt_path, 'w', encoding='utf-8') as srt_f:
                    for seg in segments_data:
                        start_time = datetime.fromtimestamp(seg['start'] / 1000)
                        end_time = datetime.fromtimestamp((seg['start'] + seg['limit']) / 1000)
                        srt_f.write(f"{seg['id']}\n")
                        srt_f.write(f"{start_time.strftime('%H:%M:%S,%f')[:-3]} --> {end_time.strftime('%H:%M:%S,%f')[:-3]}\n")
                        srt_f.write(f"{seg['text']}\n\n")
                cmd.extend(['-i', srt_path, '-c:s', 'mov_text', '-map', '2:s:0'])

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW
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

            if embed_srt and segments_data is not None:
                if os.path.exists(srt_path):
                    os.remove(srt_path)

            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd)

            self.log(f"🚀 VIDEO FINALE PRONTO!")
        except Exception as e:
            self.log(f"❌ Errore mixaggio finale: {e}")
            return False


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

    def remove_from_queue(self, index):
        if 0 <= index < len(self.queue):
            self.queue.pop(index)

    def clear_queue(self):
        self.queue.clear()

    def process_all(self, logic_engine):
        """Elabora tutti i file in coda sequenzialmente."""
        self.is_running = True
        total = len(self.queue)
        success_count = 0

        for i, item in enumerate(self.queue):
            self.log(f"\n{'='*50}")
            self.log(f"📦 Batch {i+1}/{total}: {os.path.basename(item['srt'])}")
            self.log(f"{'='*50}")

            try:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                    audio_tmp = tf.name

                if logic_engine.generate_synced_audio(
                    item['srt'], audio_tmp,
                    src_lang=item['src'], tgt_lang=item['tgt'],
                    gender=item['gender'], force_sync=item['force_sync'],
                    max_speed=item['max_speed']
                ):
                    if item['mode'] == 'video' and item['video']:
                        logic_engine.merge_audio_video_mixed(
                            item['video'], audio_tmp, item['output'],
                            vol_orig=item['vol_orig'], vol_trans=item['vol_trans'],
                            embed_srt=item['embed_srt'],
                            segments_data=None
                        )
                    else:
                        shutil.copy(audio_tmp, item['output'])

                    success_count += 1
                    self.log(f"✅ Batch {i+1}/{total} completato con successo")
                else:
                    self.log(f"❌ Batch {i+1}/{total} fallito")

                if os.path.exists(audio_tmp):
                    os.remove(audio_tmp)

            except Exception as e:
                self.log(f"❌ Batch {i+1}/{total} errore: {e}")

            if self.update_progress:
                self.update_progress((i + 1) / total, f"Batch {i+1}/{total}")

        self.log(f"\n{'='*50}")
        self.log(f"📊 Batch completato: {success_count}/{total} successi")
        self.is_running = False
