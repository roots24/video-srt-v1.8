# Fix e Miglioramenti — Stato attuale

> ⚠️ NOTA: Tutti gli item elencati di seguito sono stati **implementati nella v1.8**
> e ulteriormente consolidati nella **v1.8.1** e nella **v1.8.2** (vedi
> `improvements.md`, `fix-plan.md` e `README.md`).
> Questo file è storico.
>
> **Bug aperti residui (v1.8.2):**
> - `mov_text` non supportato su contenitori `.avi`/`.webm` (usare `.mp4` per l'embed SRT)
> - Silenzi giganti su gap SRT estesi (timeline fedele al file SRT, ma audio lungo)
> - `ffmpeg_settings.txt` relativo alla working directory (con .exe PyInstaller finisce accanto all'eseguibile)
> - Drag-and-drop richiede `tkinterdnd2` (opzionale): senza, log informativo e nessun crash
>
> **Corretti nella v1.8.2** (piano in `fix-plan.md`, suite test 68 test):
> - Concorrenza tra batch e produzione singola: guardia condivisa `ProcessingGuard`
>   (`logic.py`) + disabilitazione incrociata dei pulsanti (`gui.py`)
> - Encoding SRT rigido: `_read_text_file()` rileva UTF-8 (±BOM), cp1252/ANSI, UTF-16
>   — prima `UnicodeDecodeError` su file non UTF-8
> - Parser SRT fragile: `_iter_srt_blocks()` tollerante a CRLF, righe vuote multiple
>   e spazi sulle righe vuote (niente più segmenti persi)
> - Thread zombie su timeout API: `socket.setdefaulttimeout(API_TIMEOUT)` in `config.py`
>   (copre `requests` senza timeout esplicito, es. deep_translator) + timeout espliciti
>   su `edge_tts.Communicate` (versioni che li supportano)
> - Cache JSON non atomica: scrittura via `.tmp` + `os.replace`
> - Codice Windows-centrico: `_open_with_system()` cross-platform (`gui.py`) e download
>   FFmpeg win64 bloccato con messaggio chiaro su piattaforme non-Windows (`config.py`)
> - Segmenti SRT invalidi nascosti: pre-check con `askyesno` prima di partire +
>   riepilogo nel messaggio di successo di `process()`
> - Cache TTS in memoria: trim anche sul ramo "hit da disco" di `translate_and_fetch_tts`
> - Pulsante start: testo non più alterato dopo un run (restava "AVVIA PRODUZIONE NEURALE"
>   invece dell'originale "AVVIA TRADUZIONE NEURALE")
>
> Tutti gli altri bug noti (segmenti SRT persi, esito mixaggio ignorato, FFMPEG_BIN stantio,
> cache TTS non ripulita, scritture cache concorrenti, rilevamento playlist, warning pydub,
> timeout TTS, drift timeline, batch senza riepilogo) sono stati corretti — vedi tabella
> "Bug Fixati" nel `README.md`.

## ✅ Implementati nella v1.8 / v1.8.1

⚡ Performance
4. Thread pool limitato a 8 (logic.py:304)
- max_workers = min(cpu_count * 2, 8) → aumentare o rendere configurabile
5. Cache TTS non persistente
- Riempie memoria RAM ma non viene salvata su disco
- Perdita cache a ogni riavvio
6. Nessun caching traduzioni
- Traduzioni Google Translator vengono ricalcolate ad ogni esecuzione
🎯 Feature Mancanti
7. Embedding SRT nel video (già citato in improvements.md)
- Aggiungere opzione -c:s mov_text
8. Auto-detect lingua sorgente
- Usare ffmpeg + speech recognition (whisper.cpp?)
9. Batch mode
- Processare più file SRT in coda
10. Export multi-language
- Generare versioni in più lingue simultaneamente
🛡️ Robustezza
11. Nessun timeout per API calls
- Traduzioni possono bloccarsi infinite volte
12. Retry FFmpeg hardcoded a 3 (logic.py:58-66)
- Non configurabile dall'utente
13. Nessun controllo spazio disco
- File temporanei possono saturare il disco
📱 UX/UI
14. No progress indicator per mixing
- L'ultima fase (mixaggio video) non mostra progresso
15. Log troppo semplice
- Nessun filtro per livello di log (INFO/WARN/ERROR)
16. Nessuna preview del risultato
- Non c'è anteprima before/after
