import os
import asyncio
import time
import subprocess
import tempfile
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

    def execute_with_retry(self, func, *args, max_retries=3, initial_delay=2, **kwargs):
        """
        Implementa un meccanismo di resilienza tramite Exponential Backoff.

        LOGICA TECNICA:
        In caso di eccezione (tipicamente errori HTTP 429 Too Many Requests), il sistema
        attende un intervallo che raddoppia ad ogni tentativo (2s, 4s, 8s...).
        Questo approccio è fondamentale per interagire con API gratuite (Google Translate, Edge-TTS)
        evitando il ban temporaneo dell'indirizzo IP.
        """
        last_exception = None
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                # Calcolo del ritardo: 2s, 4s, 8s...
                delay = initial_delay * (2 ** attempt) 
                self.log(f"⚠️ Tentativo {attempt + 1}/{max_retries} fallito. Riprovo tra {delay}s... ({e})")
                time.sleep(delay)
        raise last_exception

    def ffmpeg_execute_with_retry(self, cmd, max_retries=3, initial_delay=2):
        """Retry logic per comandi FFmpeg (stretching/mixing)."""
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

    def srt_time_to_ms(self, time_str):
        """
        Converte una stringa di tempo in formato SRT (00:00:00,000) in millisecondi totali.
        Utile per calcolare precise durate e posizionamenti audio tramite pydub.
        """
        t = datetime.strptime(time_str.strip(), "%H:%M:%S,%f")
        return (t.hour * 3600000) + (t.minute * 60000) + (t.second * 1000) + (t.microsecond // 1000)

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
        if cache_key in self._cache:
            return self._cache[cache_key]
        
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
        self._cache[cache_key] = audio
        return audio

    def translate_and_fetch_tts(self, data):
        """
        Metodo wrapper che coordina la traduzione del testo e la successiva generazione TTS.
        Viene eseguito all'interno di un ThreadPoolExecutor per parallelizzare le richieste.
        """
        idx, text, start_ms, src_lang, tgt_lang, gender = data
        
        cache_key = f"{text}_{src_lang}_{tgt_lang}"
        if cache_key in self._cache:
            translated_text = self._cache[cache_key]
        else:
            try:
                # 1. Traduzione tramite Google Translator
                def do_translate():
                    if src_lang != tgt_lang:
                        return GoogleTranslator(source=src_lang, target=tgt_lang).translate(text)
                    return text

                translated_text = self.execute_with_retry(do_translate)
                self._cache[cache_key] = translated_text
            except Exception as e:
                self.log(f"❌ Errore traduzione segmento {idx}: {e}")
                return idx, None, start_ms
        
        try:
            # 2. Sintesi Vocale Neurale (Edge-TTS richiede asyncio per funzionare)
            def do_tts():
                return asyncio.run(self._async_tts_generate(translated_text, tgt_lang, gender))

            phrase_audio = self.execute_with_retry(do_tts)
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
                    lines = block.split('\n')
                    if len(lines) < 3: 
                        invalid_count += 1
                        continue
                    
                    time_line = lines[1]
                    if ' --> ' not in time_line:
                        invalid_count += 1
                        continue
                    
                    start_str, end_str = time_line.split(' --> ')
                    
                    try:
                        start_ms = self.srt_time_to_ms(start_str)
                        end_ms = self.srt_time_to_ms(end_str)
                        limit_ms = end_ms - start_ms
                        
                        if limit_ms <= 0:
                            invalid_count += 1
                            continue
                        
                        segments_data.append({
                            'id': i, 'text': " ".join(lines[2:]), 
                            'start': start_ms, 
                            'limit': limit_ms
                        })
                    except ValueError as ve:
                        self.log(f"⚠️ Segmento {i} timestamp invalido: {ve}")
                        invalid_count += 1

            if invalid_count > 0:
                self.log(f"⚠️ {invalid_count} segmenti SRT ignorati (formato non valido)")
            
            total_segments = len(segments_data)
            if total_segments == 0:
                self.log(f"❌ Nessun segmento SRT valido trovato")
                return False
            
            self.log(f"⚡ Generazione Audio Neurale in parallelo ({total_segments} segmenti)...")
            
            # Worker dinamico: CPU count * 2, limitato a 8 per rate-limit Edge-TTS
            cpu_count = os.cpu_count() or 4
            max_workers = min(cpu_count * 2, 8)
            
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
            self.log(f"✅ Traccia audio neurale creata con successo!")
            return True
        except Exception as e:
            self.log(f"❌ Errore generazione audio: {e}")
            return False

    def merge_audio_video_mixed(self, video_path, translated_audio_path, output_video_path, vol_orig=0.4, vol_trans=1.0, embed_srt=False, segments_data=None):
        """
        Mixer audio-video finale tramite FFmpeg Filter Complex.

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
            
            filter_complex = f"[0:a]volume={vol_orig}[bg]; [1:a]volume={vol_trans}[fg]; [bg][fg]amix=inputs=2:duration=first[out]"
            
            cmd = [
                config.FFMPEG_BIN, '-y', '-i', video_path, '-i', translated_audio_path, 
                '-filter_complex', filter_complex, '-map', '0:v:0', '-map', '[out]', 
                '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', output_video_path
            ]
            
            if embed_srt and segments_data is not None:
                srt_input = tempfile.NamedTemporaryFile(suffix='.srt', delete=False)
                srt_path = srt_input.name
                srt_input.close()
                
                with open(srt_path, 'w', encoding='utf-8') as srt_f:
                    for seg in segments_data:
                        start_time = datetime.fromtimestamp(seg['start'] / 1000)
                        end_time = datetime.fromtimestamp((seg['start'] + seg['limit']) / 1000)
                        srt_f.write(f"{seg['id']}\n")
                        srt_f.write(f"{start_time.strftime('%H:%M:%S,%f')[:-3]} --> {end_time.strftime('%H:%M:%S,%f')[:-3]}\n")
                        srt_f.write(f"{seg['text']}\n\n")
                
                cmd.extend(['-i', srt_path, '-c:s', 'mov_text', '-map', '2:s:0'])
                os.remove(srt_path)
            
            self.ffmpeg_execute_with_retry(cmd)
            self.log(f"🚀 VIDEO FINALE PRONTO!")
        except Exception as e:
            self.log(f"❌ Errore mixaggio finale: {e}")
            return False
