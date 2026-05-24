import os
import sys
import customtkinter as ctk
import urllib.request 
import zipfile 
import shutil 
import subprocess

# ==============================================================================
# CONFIGURAZIONI E COSTANTI
# ==============================================================================

# Mappatura Lingue -> Voci Neurali Microsoft Edge
VOICE_MAP = {
    "en": "en-US-GuyNeural",   # Inglese USA - Voce maschile
    "it": "it-IT-DiegoNeural", # Italiano - Voce maschile
    "es": "es-ES-AlvaroNeural", # Spagnolo - Voce maschile
    "fr": "fr-FR-HenriNeural",  # Francese - Voce maschile
    "de": "de-DE-ConradNeural", # Tedesco - Voce maschile
    "zh": "zh-CN-YunxiNeural",  # Cinese - Voce maschile
    "uk": "uk-UA-OstapNeural",  # Ucraino - Voce maschile
    "sv": "sv-SE-SvenNeural",   # Svedese - Voce maschile
    "nl": "nl-NL-MaartenNeural", # Olandese - Voce maschile
}

def get_ffmpeg_path():
    """Determina il percorso di FFmpeg: Config file -> ./bin/ -> PyInstaller -> System PATH."""
    # Prova a recuperare il percorso dall'install dir salvata nelle impostazioni
    install_dir = get_ffmpeg_install_dir()
    ffmpeg_exe = os.path.join(install_dir, 'ffmpeg.exe')
    if os.path.exists(ffmpeg_exe):
        return ffmpeg_exe

    local_bin = os.path.join(os.getcwd(), 'bin', 'ffmpeg.exe')
    if os.path.exists(local_bin): return local_bin

    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'ffmpeg.exe')
    
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
    # Default: cartella dell'applicazione
    return os.path.dirname(os.path.abspath(__file__))

def save_ffmpeg_install_dir(path):
    """Salva la directory di installazione preferita per FFmpeg."""
    with open("ffmpeg_settings.txt", "w") as f:
        f.write(path)

def check_and_update_ffmpeg(custom_install_dir=None):
    """Verifica la presenza di FFmpeg e lo aggiorna se necessario o obsoleto."""
    install_dir = custom_install_dir if custom_install_dir else get_ffmpeg_install_dir()
    local_ffmpeg_exe = os.path.join(install_dir, 'ffmpeg.exe')
    
    try:
        # Check if exists or if it's an old version (simplified check)
        exists = os.path.exists(local_ffmpeg_exe)
        is_old = False
        if exists:
            res = subprocess.run([local_ffmpeg_exe, '-version'], capture_output=True, text=True)
            if "2024" not in res.stdout:
                is_old = True

        if not exists or is_old:
            url = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip'
            # Scarichiamo in una sottocartella temporanea all'interno della dir di installazione o app_root
            temp_folder = os.path.join(install_dir, 'temp_ffmpeg')
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