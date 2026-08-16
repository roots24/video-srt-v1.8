"""
Punto di ingresso principale dell'applicazione Ultimate Video Translator AI PRO
(versione corrente: config.APP_VERSION, aggiornabile con `python bump_version.py`).

ARCHITETTURA TECNICA:
L'applicazione segue un pattern a separazione tra Interfaccia Utente (GUI) e Logica di Business (Backend).
- GUI: Gestita in `gui.py` utilizzando CustomTkinter per l'interfaccia moderna.
- Backend: Gestito in `logic.py`, `downloader_logic.py` e `config.py`.
- Entry Point: Questo file inizializza l'oggetto App e avvia il loop di eventi di Tkinter.
"""

from gui import App

if __name__ == "__main__":
    # Istanziazione della classe App (definita in gui.py).
    # L'oggetto 'app' eredita da ctk.CTk, inizializzando tutti i widget 
    # e collegando le callback della GUI ai metodi della classe VideoTranslatorLogic.
    app = App()

    # Avvio del Main Loop di Tkinter.
    # Questo metodo blocca l'esecuzione in questo punto e avvia il listener degli eventi.
    # Qualsiasi operazione pesante (TTS, Traduzione, Mixaggio) deve essere eseguita 
    # in Thread separati per evitare il freeze della UI (Application Not Responding).
    app.mainloop()
