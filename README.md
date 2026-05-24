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

## Setup

1. Clona il repository
2. Installa le dipendenze richieste (se presenti)
3. Avvia `main.py`

## Note

- Personalizza i file di configurazione secondo le tue esigenze.
- Consulta la documentazione ffmpeg nella cartella `ffempeg/temp_ffmpeg/ffmpeg-master-latest-win64-gpl-shared/doc/` per dettagli avanzati.
