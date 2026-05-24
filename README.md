# Video SRT v1.8

Questo repository contiene un'applicazione Python per il download di video e la generazione di sottotitoli (SRT) utilizzando ffmpeg.

## Struttura del progetto

- `main.py`: Avvio dell'applicazione principale
- `gui.py`: Interfaccia grafica utente
- `logic.py`: Logica principale dell'applicazione
- `config.py`: Configurazioni generali
- `downloader_config.py`: Configurazioni specifiche per il downloader
- `downloader_logic.py`: Logica per il download dei video
- `video_downloader_pro.py`: Modulo avanzato per il download video
- `ffempeg/`: Contiene i binari e le risorse di ffmpeg

## Requisiti

- Python 3.8+
- ffmpeg (incluso nella cartella `ffempeg/`)

## Setup e Installazione

### Per Sviluppatori

1. Clona il repository.
2. Installa le dipendenze:

   ```bash
   pip install customtkinter edge-tts pydub deep-translator yt-dlp
   ```

3. Avvia l'applicazione: `python main.py`.

### Compilazione in Eseguibile (.exe)

Se desideri compilare l'applicazione in un singolo file eseguibile per Windows, segui questi passaggi:

1. **Installa PyInstaller**:

   ```bash
   pip install pyinstaller
   ```

2. **Lancia la compilazione** utilizzando il file di configurazione `.spec` fornito (che include automaticamente i binari FFmpeg e le dipendenze):

   ```bash
   pyinstaller build_app.spec
   ```

3. Troverai l'eseguibile finale nella cartella `dist/UltimateVideoTranslatorAI.exe`.

## Note

- Personalizza i file di configurazione secondo le tue esigenze.
- Consulta la documentazione ffmpeg nella cartella `ffempeg/temp_ffmpeg/ffmpeg-master-latest-win64-gpl-shared/doc/` per dettagli avanzati.
