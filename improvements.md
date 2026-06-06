# Suggerimenti di Miglioramento — Ultimate Video Translator AI PRO v1.8

## Bug / Typo

- `ffempeg/` → rinominare in `ffmpeg/` (typo presente ovunque nel codice)
- `config.py:104` — check versione "2024" fragile; usare regex su output reale di `ffmpeg -version`

## Performance

- Cache TTS/translation: memorizzare risultati per segmenti identici, evitare re-chiamate API
- Limitare `max_workers=12` hardcoded; adattarlo dinamicamente al rate-limit Edge-TTS

## UX / UI (già applicato)

- ✅ Selezione voce female/male per ogni lingua (VOICE_MAP ha solo male voices)
- ✅ Stadio-progress bar: mostrare fase corrente (Parsing → Translation → TTS → Stretching → Mixing)
- ✅ Drag-and-drop file support nella GUI

## Features

- Embedding SRT tradotto nel video finale (`-c:s mov_text`)
- Auto-detect lingua sorgente dall'audio/video (ffmpeg + speech recognition)
- Batch mode: processare multiple SRT in parallelo
- Export multi-language: generare versioni in più lingue simultaneamente

## Robustness

- `logic.py:182` — parsing SRT fragile; aggiungere validazione format, handling segmenti malformed
- Retry logic per FFmpeg commands (stretching/mixing)
- Unit tests per SRT parsing, time conversion, audio stretching

## Build

- `package.json` unused → rimuovere o integrare se serve Node deps
- Spec: includere `ffmpeg_settings.txt` nel bundle PyInstaller
