# Ultimate Video Translator AI PRO v1.8 (EdgeTTS Edition) - Documentazione Tecnica

Benvenuti nella versione 1.8 di **Ultimate Video Translator AI**, un applicativo professionale per la traduzione e il doppiaggio automatico di video basato su file SRT. Questa release rappresenta l'evoluzione massima del progetto, integrando sintesi vocale neurale, gestione resiliente delle API e un motore di download avanzato.

## 🏗️ Architettura Software

L'applicazione adotta un pattern a **separazione tra Interfaccia Utente (GUI) e Logica di Business (Backend)**:

- **Frontend (`gui.py`, `video_downloader_pro.py`)**: Sviluppato in `CustomTkinter`. Gestisce l'input utente, il binding dei dati tramite variabili di stato (`StringVar`, `DoubleVar`) e l'aggiornamento asincrono della UI via callback thread-safe (`self.after`).
- **Core Logic (`logic.py`)**: Il cuore del sistema che orchestra la pipeline: *Parsing SRT $\rightarrow$ Traduzione AI $\rightarrow$ Sintesi Neurale TTS $\rightarrow$ Sincronizzazione Temporale $\rightarrow$ Mixaggio Audio/Video*.
- **Configurazione e Risorse (`config.py`, `downloader_config.py`)**: Centralizza le costanti, la mappatura delle voci neurali e la gestione dinamica dei binari esterni (FFmpeg).

---

## ⚙️ Specifiche Tecniche del Backend

### 🎙️ Sintesi Vocale Neurale & Traduzione

- **Edge-TTS**: Utilizza il protocollo neurale di Microsoft Edge per generare audio naturale. L'implementazione è asincrona (`asyncio`) per ottimizzare i tempi di risposta della rete.
- **Google Translator**: Integrazione via `deep-translator` per la traduzione multilingua dei segmenti SRT.
- **Resilienza API (Exponential Backoff)**: Per prevenire il ban dell'indirizzo IP (errore HTTP 429), l'applicazione implementa un algoritmo di *Exponential Backoff*. In caso di errore, il sistema attende intervalli crescenti (2s, 4s, 8s...) prima di riprovare.

### ⏱️ Sincronizzazione Audio Avanzata

Il problema della durata variabile dell'audio TTS rispetto al sottotitolo è risolto tramite:

- **Time-Stretching via FFmpeg**: Utilizzo del filtro `atempo`, che permette di accelerare o rallentare l'audio senza alterarne il pitch (tono della voce), evitando l'effetto "chipmunk".
- **Timeline Reconstruction**: Calcolo matematico dei silenzi tra i segmenti per garantire che ogni frase inizi esattamente al millisecondo previsto dal file SRT.

### 🎬 Mixaggio Audio-Video Professionale

Il mixaggio finale avviene tramite un `filter_complex` di FFmpeg:

- **Dual Stream Scaling**: L'audio originale (Background) e quello tradotto (Foreground) vengono scalati indipendentemente in volume prima dell'unione.
- **Sincronizzazione Durata**: Il parametro `duration=first` assicura che l'output termini esattamente con la fine del video originale.
- **Stream Copy**: Il flusso video non viene ricodificato (`-c:v copy`), preservando la qualità originale e riducendo drasticamente i tempi di esportazione.

---

## 🚀 Motore di Download (Multi-Video Downloader)

Il modulo integrato per il download dei contenuti si basa su `yt-dlp` e offre:

- **Profili di Qualità**: Configurazione granulare tra compatibilità H.264, alta efficienza HEVC (H.265 con CRF 23), risoluzioni fisse (da 480p a 4K) o sola estrazione audio MP3 (320kbps).
- **Bypass Restrizioni**: Supporto per l'estrazione automatica dei cookie dai browser installati (`chrome`, `firefox`, `edge`, ecc.) per scaricare contenuti protetti.
- **Coda Asincrona**: Ogni download viene gestito in un thread separato, permettendo l'esecuzione di task multipli paralleli senza bloccare la GUI.

---

## 🛠️ Gestione FFmpeg & Packaging

### Risoluzione Binari (Priority Path)

L'applicazione risolve il percorso di FFmpeg seguendo una gerarchia di priorità, fondamentale sia in modalità script che in modalità bundle:

1. **Configurazione Utente**: Percorso salvato in `ffmpeg_settings.txt`.
2. **Ambiente Sviluppo**: Cartella `/bin/` locale nel progetto.
3. **Bundle PyInstaller**: Directory temporanea `_MEIPASS`. Il sistema verifica sia la root del bundle che la sottocartella `ffmpeg/` per garantire il funzionamento dell'eseguibile standalone.
4. **Sistema**: Comando globale nel PATH di sistema.

### Auto-Update Engine

Il sistema verifica autonomamente la versione di FFmpeg. Se assente o obsoleta, scarica automaticamente l'ultima build *win64-gpl-shared* da GitHub, estrae i binari e le DLL necessarie e configura il sistema per l'utilizzo immediato.

### Packaging & Distribuzione (EXE)

L'applicazione è configurata per essere compilata in un singolo file `.exe` tramite **PyInstaller**.

- **Configurazione Spec**: Viene utilizzato un file `build_app.spec` che istruisce PyInstaller a includere la cartella `ffmpeg_persistent/*` e il file `ffmpeg_settings.txt` all'interno del bundle.
- **Dependency Mapping**: I moduli critici come `edge-tts`, `yt-dlp` e `customtkinter` sono mappati come `hiddenimports` per evitare errori di runtime nel bundle compilato.
- **UX Standalone**: Il file `build_app.spec` usa `console=True` (finestra terminale visibile per i log). Per nasconderla, impostare `console=False`.

---

## 📖 Requisiti & Avvio

### Librerie Python

```bash
pip install -r requirements.txt
# equivalenza: customtkinter edge-tts pydub deep-translator yt-dlp langdetect audioop-lts
```

### Esecuzione

```bash
python main.py
```

---
*Sviluppato per automatizzare il doppiaggio video con l'integrazione di tecnologie neurali e processing audio professionale.*
