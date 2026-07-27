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
