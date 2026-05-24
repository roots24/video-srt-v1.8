"""
Punto di ingresso principale dell'applicazione Ultimate Video Translator AI PRO v1.8.
Questo file si occupa di inizializzare l'interfaccia grafica e avviare il loop principale di Tkinter.
"""

from gui import App

if __name__ == "__main__":
    # Creazione dell'istanza della classe App definita in gui.py
    # L'oggetto 'app' eredita da ctk.CTk (CustomTkinter) e contiene 
    # l'intera struttura della GUI e il collegamento alla logica di business.
    app = App()

    # Avvio del loop principale dell'interfaccia grafica.
    # Questo metodo mantiene aperta la finestra e gestisce gli eventi (click, input, etc.)
    # finché l'utente non chiude l'applicazione.
    app.mainloop()