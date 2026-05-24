# Ultimate Video Translator AI PRO v1.8 (EdgeTTS Edition)

Benvenuti nella versione 1.8 di **Ultimate Video Translator AI**, un applicativo professionale per la traduzione e il doppiaggio automatico di video basato su file SRT. Questa versione introduce un salto qualitativo significativo grazie all'integrazione di voci neurali e una struttura software modulare.

## 🌟 Novità della Versione 1.8

### 🎙️ Voci Neurali con Edge-TTS

La principale novità è la sostituzione di `gTTS` con **Edge-TTS**. Questo permette di ottenere:

- **Qualità Vocale Superiore**: Voci naturali, meno robotiche e più espressive.
- **Voci Neurali**: Utilizzo di modelli neurali di Microsoft Edge per una sintesi vocale di alta qualità gratuitamente.
- **Mappatura Lingue**: Supporto ottimizzato per diverse lingue (English, Italian, Spanish, French, German, Chinese, Ukrainian) con voci specifiche assegnate.

### 🚀 Ottimizzazioni Tecniche & Architettura

- **Struttura Modulare**: Il codice è stato rifattorizzato in più moduli (`config`, `logic`, `gui`, `main`) per garantire una migliore manutenibilità e scalabilità.
- **Gestione Asincrona**: Implementazione di `asyncio` all'interno dei thread worker per gestire le chiamate API a Edge-TTS in modo efficiente.
- **Concurrency Refactoring**: Ottimizzazione del `ThreadPoolExecutor` per bilanciare velocità di elaborazione e stabilità della connessione, evitando blocchi o ban dalle API.
- **Sincronizzazione Temporale Avanzata**:
  - **Time-Stretching Dinamico**: Adattamento automatico della velocità dell'audio tramite FFmpeg `atempo`.
  - **Controllo Limite Velocità**: Possibilità di impostare un limite massimo di accelerazione (da 1.0x a 3.0x) per preservare la naturalezza della voce.
  - **Sincronizzazione Forzata**: Modalità opzionale che ignora i limiti di velocità per garantire che l'audio entri esattamente nei tempi del video, indipendentemente dalla distorsione.

### 🎨 UI/UX Enhancements

- **Feedback in Tempo Reale**: Barra di progressione (`CTkProgressBar`) sincronizzata con l'avanzamento reale dei segmenti elaborati.
- **Controllo Mixaggio Audio**: Aggiunti cursori per la regolazione dinamica del volume sia dell'audio originale che della nuova traccia tradotta.
- **Interfaccia Moderna**: Utilizzo di `customtkinter` per un look professionale e dark mode nativa.

## 🛠️ Requisiti di Sistema

Per far funzionare l'applicativo, è necessario installare le seguenti dipendenze:

### Python Libraries

```bash
pip install customtkinter edge-tts pydub deep-translator
```

### Software Esterni

- **FFmpeg**: Fondamentale per il mixaggio audio/video e il time-stretching. L'applicazione gestisce automaticamente il percorso tramite il file `ffmpeg_settings.txt` (che memorizza la directory di installazione), oppure può utilizzare l'eseguibile presente nel PATH di sistema.

## 📖 Guida Rapida all'Uso

1. **Avvio**: Avvia l'applicazione eseguendo il file principale:

   ```bash
   python main.py
   ```

2. **Carica i File**: Seleziona il file `.srt` dei sottotitoli e il video originale `.mp4`.
3. **Scegli le Lingue**: Imposta la lingua sorgente (default: Ucraino `uk`) e quella di destinazione.
4. **Configura Sincronizzazione**:
    - Scegli se attivare la **"Sincronizzazione Forzata"** per una precisione temporale assoluta.
    - Regola il **"Limite Velocità Max"** per definire quanto l'audio può essere accelerato senza distorsioni eccessive.
5. **Regola il Mixaggio**: Utilizza i cursori per bilanciare il volume tra l'audio originale e quello tradotto.
6. **Scegli l'Output**:
   - **Video Completo**: Crea un nuovo video mixando le due tracce secondo i volumi impostati.
   - **Solo Audio**: Esporta esclusivamente la traccia audio tradotta in `.mp3`.
7. **Avvia**: Clicca su "AVVIA PRODUZIONE NEURALE" e monitora il progresso nella console e nella barra di avanzamento.

## ⚙️ Dettagli Tecnici del Workflow

1. **Analisi SRT**: Il software scompone l'SRT in segmenti con timestamp precisi.
2. **Traduzione AI**: Ogni segmento viene tradotto via Google Translator (deep-translator).
3. **Sintesi Neural**: Il testo tradotto viene inviato a Edge-TTS per generare un file audio MP3 di alta qualità.
4. **Sincronizzazione**: L'audio viene accelerato/rallentato tramite il filtro `atempo` di FFmpeg se la durata supera il limite del sottotitolo.
5. **Mixaggio Finale**: FFmpeg unisce le tracce utilizzando un complesso sistema di filtri (`amix`) per garantire un risultato professionale.

---
*Sviluppato per automatizzare il doppiaggio video con la massima qualità possibile senza l'uso di API a pagamento.*
