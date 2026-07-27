import os
import sys
import re
import customtkinter as ctk
import urllib.request 
import zipfile 
import shutil 
import subprocess

# ==============================================================================
# MODULO DI CONFIGURAZIONE SISTEMA E RISORSE ESTERNE
# ==============================================================================
"""
Questo modulo centralizza le costanti globali e la gestione delle dipendenze esterne (FFmpeg).
Assicura che l'applicazione possa operare sia in ambiente di sviluppo che come eseguibile compilato.
"""

# Mappatura Lingue -> Voci Neurali Microsoft Edge
# Queste voci sono fornite tramite il protocollo edge-tts e richiedono una connessione internet.
VOICE_MAP = {
    "en": {"male": "en-US-GuyNeural", "female": "en-US-AriaNeural"},
    "it": {"male": "it-IT-DiegoNeural", "female": "it-IT-ElsaNeural"},
    "es": {"male": "es-ES-AlvaroNeural", "female": "es-ES-LiaNeural"},
    "fr": {"male": "fr-FR-HenriNeural", "female": "fr-FR-VivienneNeural"},
    "de": {"male": "de-DE-ConradNeural", "female": "de-DE-KatjaNeural"},
    "zh": {"male": "zh-CN-YunxiNeural", "female": "zh-CN-XiaoxiaoNeural"},
    "uk": {"male": "uk-UA-OstapNeural", "female": "uk-UA-PolinaNeural"},
    "sv": {"male": "sv-SE-SvenNeural", "female": "sv-SE-SofieNeural"},
    "nl": {"male": "nl-NL-MaartenNeural", "female": "nl-NL-FennaNeural"},
}

def get_ffmpeg_path():
    """
    Risolve il percorso dell'eseguibile FFmpeg seguendo un ordine di priorità gerarchico:
    1. Directory personalizzata salvata dall'utente in `ffmpeg_settings.txt`.
    2. Cartella persistente nella root del progetto (`ffmpeg_persistent/`).
    3. Cartella `/bin/` locale nella root del progetto.
    4. Cartella temporanea di PyInstaller (`_MEIPASS`), fondamentale per i file bundle .exe.
    5. Fallback al comando 'ffmpeg', assumendo che sia presente nel PATH di sistema.
    """
    # Prova a recuperare il percorso dall'install dir salvata nelle impostazioni
    install_dir = get_ffmpeg_install_dir()
    ffmpeg_exe = os.path.join(install_dir, 'ffmpeg.exe')
    if os.path.exists(ffmpeg_exe):
        return ffmpeg_exe

    local_bin = os.path.join(os.getcwd(), 'bin', 'ffmpeg.exe')
    if os.path.exists(local_bin): return local_bin

    if hasattr(sys, '_MEIPASS'):
        # Verifica sia nella root del bundle che nella sottocartella ffmpeg/
        bundled_root = sys._MEIPASS
        paths_to_check = [
            os.path.join(bundled_root, 'ffmpeg.exe'),
            os.path.join(bundled_root, 'ffmpeg', 'ffmpeg.exe')
        ]
        for p in paths_to_check:
            if os.path.exists(p): return p
    
    # Fallback to standard name if not found in custom paths
    return 'ffmpeg'

def save_ffmpeg_path(path):
    """Salva il percorso dell'eseguibile aggiornando la directory di installazione."""
    install_dir = os.path.dirname(path)
    save_ffmpeg_install_dir(install_dir)

def get_ffmpeg_install_dir():
    """Recupera la directory di installazione preferita per FFmpeg."""
    settings_file = "ffmpeg_settings.txt"
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as f:
            path = f.read().strip()
            if path and os.path.isdir(path):
                return path
    # Default: cartella persistente nella root del progetto
    default_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ffmpeg_persistent')
    os.makedirs(default_dir, exist_ok=True)
    return default_dir

def save_ffmpeg_install_dir(path):
    """Salva la directory di installazione preferita per FFmpeg."""
    with open("ffmpeg_settings.txt", "w") as f:
        f.write(path)

def check_and_update_ffmpeg(custom_install_dir=None):
    """
    Implementa l'auto-aggiornamento del motore FFmpeg.
    
    LOGICA TECNICA:
    1. Verifica se `ffmpeg.exe` esiste nel percorso configurato.
    2. Se esiste, esegue `ffmpeg -version` e controlla se l'output contiene "2024" 
       (metodo semplificato per identificare versioni obsolete).
    3. In caso di assenza o obsolescenza:
       - Scarica l'ultima release build win64-gpl-shared da GitHub.
       - Estrae il file ZIP in una cartella temporanea `temp_ffmpeg`.
       - Copia ricorsivamente tutti i binari e le DLL necessarie nella directory di installazione finale.
    """
    install_dir = custom_install_dir if custom_install_dir else get_ffmpeg_install_dir()
    local_ffmpeg_exe = os.path.join(install_dir, 'ffmpeg.exe')
    
    try:
        # Check if exists or if it's an old version (simplified check)
        exists = os.path.exists(local_ffmpeg_exe)
        is_old = False
        if exists:
            res = subprocess.run([local_ffmpeg_exe, '-version'], capture_output=True, text=True)
            version_match = re.search(r'20\d{2}', res.stdout)
            if not version_match or int(version_match.group()) < 2024:
                is_old = True

        if not exists or is_old:
            url = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip'
            # Scarichiamo in una sottocartella all'interno della dir di installazione
            temp_folder = os.path.join(install_dir, '_temp_download')
            os.makedirs(temp_folder, exist_ok=True)
            filename = os.path.join(temp_folder, 'ffmpeg.zip')
            urllib.request.urlretrieve(url, filename)
            with zipfile.ZipFile(filename, 'r') as zip_ref: 
                zip_ref.extractall(temp_folder)
            for root, dirs, files in os.walk(temp_folder):
                if 'ffmpeg.exe' in files:
                    for f in os.listdir(root): 
                        shutil.copy2(os.path.join(root, f), install_dir)
                    break
            
            # Aggiorniamo il percorso dell'eseguibile per l'applicazione
            save_ffmpeg_path(local_ffmpeg_exe)
            return True, "FFmpeg aggiornato correttamente!"
        return False, "FFmpeg è già aggiornato."
    except Exception as e:
        return False, f"Errore FFmpeg: {e}"

# Percorso globale per l'eseguibile FFmpeg
FFMPEG_BIN = get_ffmpeg_path()

# Impostazioni Tema Interfaccia Grafica (GUI)
ctk.set_appearance_mode("Dark") 
ctk.set_default_color_theme("blue")

# ==============================================================================
# CONFIGURAZIONE PERFORMANCE E CACHING
# ==============================================================================

# Directory per caching persistente (traduzioni e TTS)
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache')
os.makedirs(CACHE_DIR, exist_ok=True)

# Dimensione massima cache in MB (default 500MB)
MAX_CACHE_SIZE_MB = 500

# Numero max worker per processing parallelo (default: CPU * 2, max 16)
MAX_WORKERS = min(os.cpu_count() or 4 * 2, 16)

# Timeout per chiamate API (secondi)
API_TIMEOUT = 30
API_TIMEOUT_TTS = 60

# Retry FFmpeg configurabile
FFMPEG_MAX_RETRIES = 3
FFMPEG_RETRY_DELAY = 2

# Abilita caching persistente su disco
PERSISTENT_CACHE_ENABLED = True