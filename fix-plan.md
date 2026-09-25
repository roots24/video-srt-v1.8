# 📋 Piano di Miglioramento e Robustezza — Ultimate Video Translator AI v1.8.x

> **Obiettivo:** consolidare le correzioni critiche già implementate (v1.8.2) e aggiungere miglioramenti UX/Manutenibilità identificati durante la revisione del codice.
>
> **Stato Corrente:**
>
> - ✅ Core Robustness: Implementata e verificata (Race conditions, Encoding fallbacks, Zombie threads).
> - 🏗️ In corso: Integrazione feedback di revisione UX/Manutenibilità.

---

## 1. Riepilogo Problemi Risolti (✅ IMPLEMENTATO)

| # | Priorità | Problema | Stato | Nota |
| --- | :---: | :--- | :---: | :--- |
| 1 | 🔴 P0 | Race condition tra Batch e produzione singola | ✅ | Integrata `ProcessingGuard` in `logic.py` e `gui.py`. |
| 2 | 🔴 P0 | Encoding SRT rigido → `UnicodeDecodeError` | ✅ | Implementato `_read_text_file` con fallback (`utf-8-sig`, `cp1252`, `utf-16`). |
| 3 | 🟡 P1 | Parser SRT fragile (`split('\n\n')`) | ✅ | Sostituito con iteratore regex `_iter_srt_blocks`. |
| 4 | 🟡 P1 | Thread zombie su timeout API | ✅ | Aggiunto `socket.setdefaulttimeout` e gestione `executor.shutdown(wait=False)`. |
| 5 | 🔵 P2 | Cache JSON non atomica | ✅ | Implementata scrittura tramite file `.tmp` e `os.replace`. |
| 6 | 🔵 P2 | Cache TTS in memoria senza trim | ✅ | Aggiunta funzione di trimming dinamico su ogni hit/generazione. |

---

## 2. Nuovi Obiettivi (In Corso - Revisione Round 1)

### 2.1 Configurazione Codifica Esportazione (P1)

**Problema:** L'esportazione SRT usa `utf-8` hardcoded in `logic.py`. Alcuni lettori legacy su Windows richiedono CP1252.
**Fix proposto:**

1. Aggiungere `EXPORT_ENCODING = 'utf-8'` in `config.py`.
2. Aggiornare `export_multi_lang` in `logic.py:760` per usare il valore di configurazione.
**Criteri di accettazione:** L'utente può scegliere la codifica dall'interfaccia o dal file di config; i file esportati sono corretti.

### 2.2 Feedback UX per Dipendenze Mancanti (P1)

**Problema:** Se librerie come `langdetect` mancano, l'app scrive solo nei log interni, lasciando l'utente confuso se un tasto non risponde.
**Fix proposto:**

1. In `gui.py`, verificare la presenza delle dipendenze prima di avviare le azioni correlate (es. tasto 🔍).
2. Mostrare un `messagebox.showwarning` esplicito se una funzionalità è disabilitata per mancanza di librerie.
**Criteri di accettazione:** L'utente riceve un popup chiaro invece di un messaggio silenzioso nei log.

### 2.3 Dettaglio Errori Segmenti SRT (P1)

**Problema:** Durante l'esportazione, se vengono scartati segmenti, il log contiene i dettagli ma la GUI mostra solo il conteggio totale.
**Fix proposto:**

1. Modificare `_parse_srt_segments` in `logic.py` per restituire una lista di errori (ID segmento + motivo).
2. Aggiornare la GUI per mostrare un riepilogo più dettagliato (es. "3 segmenti scartati: [04, 12, 45] - Formato non valido").
**Criteri di accettazione:** L'utente può identificare rapidamente quali parti del file originale sono state ignorate.

### 2.4 Alert durante Esportazione Attiva (P2)

**Problema:** Gli alert per segmenti invalidi appaiono solo nel pre-check; durante l'esportazione attiva, i problemi sono silenti.
**Fix proposto:**

1. Integrare un sistema di notifica o un log evidenziato nella GUI che aggiorni il progresso se vengono incontrati blocchi durante il processing attivo.
**Criteri di accettazione:** Coerenza tra il comportamento del pre-check e quello dell'esecuzione vera e propria.

### 2.5 Robustezza Controllo Versione FFmpeg (P2)

**Problema:** Il controllo `int(version_match.group()) < 2024` in `config.py` è fragile.
**Fix proposto:**

1. Usare una funzione di parsing versione più standard o permettere all'utente di definire la versione minima richiesta nel config.
**Criteri di accettazione:** Il check non fallisce per versioni con nomi non standard e permette configurazioni personalizzate.

### 2.6 Ottimizzazione ThreadPoolExecutor (P2)

**Problema:** In `_retry_with_backoff`, un nuovo executor viene creato in ogni iterazione del loop di retry.
**Fix proposto:**

1. Spostare l'istanziatura dell'executor fuori dal ciclo `for attempt`.
**Criteri di accettazione:** Riduzione della creazione/distruzione di oggetti durante i tentativi di connessione rapidi.

---

## 3. Piano di Esecuzione Consigliato

1. **Sprint UX (P1):** Configurazione encoding + Feedback dipendenze + Dettaglio errori segmenti.
2. **Sprint Polish (P2):** Alert esportazione + Versione FFmpeg + Ottimizzazione Executor.

---
*Ultimo aggiornamento: 2026-08-24 - Sintesi Review Loop.*
