import os
import sys
import re
import socket
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

# ==============================================================================
# VERSIONE APPLICAZIONE (UNICA FONTE DI VERITÀ)
# ==============================================================================
# Mai hardcodare la versione altrove (GUI, spec, script): usare config.APP_VERSION.
# Versionamento incrementale:
#   python bump_version.py patch   → 1.8.2 -> 1.8.3 (fix, robustezza)
#   python bump_version.py minor   → 1.8.2 -> 1.9.0 (nuova feature)
#   python bump_version.py major   → 1.8.2 -> 2.0.0 (cambio sostanziale)
APP_VERSION = "1.8.2"
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

# Lingue supportate dall'applicazione (unica fonte: evita liste duplicate in gui.py)
SUPPORTED_LANGS = list(VOICE_MAP.keys())

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
        # .exe onedir: la cartella ffmpeg/ accanto all'eseguibile
        # (generata dalla build in dist/UltimateVideoTranslatorAI/)
        for folder in ('ffmpeg', 'ffmpeg_persistent'):
            next_to_exe = os.path.join(os.path.dirname(sys.executable), folder, 'ffmpeg.exe')
            if os.path.exists(next_to_exe):
                return next_to_exe
        # Verifica root, sottocartella ffmpeg/ e ffmpeg_persistent/ del bundle
        bundled_root = sys._MEIPASS
        paths_to_check = [
            os.path.join(bundled_root, 'ffmpeg.exe'),
            os.path.join(bundled_root, 'ffmpeg', 'ffmpeg.exe'),
            os.path.join(bundled_root, 'ffmpeg_persistent', 'ffmpeg.exe'),
        ]
        for p in paths_to_check:
            if os.path.exists(p): return p
    
    # Fallback to standard name if not found in custom paths
    return 'ffmpeg'

def save_ffmpeg_path(path):
    """Salva il percorso dell'eseguibile aggiornando la directory di installazione."""
    install_dir = os.path.dirname(path)
    save_ffmpeg_install_dir(install_dir)

def _settings_path():
    """Percorso del file ffmpeg_settings.txt.
    Frozen (.exe): accanto all'eseguibile (scrivibile e persistente).
    Sviluppo: nella working directory corrente (comportamento storico)."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(os.path.dirname(sys.executable), 'ffmpeg_settings.txt')
    return os.path.join(os.getcwd(), 'ffmpeg_settings.txt')


def get_ffmpeg_install_dir():
    """Recupera la directory di installazione preferita per FFmpeg."""
    settings_file = _settings_path()
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as f:
            path = f.read().strip()
            if path and os.path.isdir(path):
                return path
    if hasattr(sys, '_MEIPASS'):
        # Fallback .exe: settings bundle nella build
        bundled_settings = os.path.join(sys._MEIPASS, 'ffmpeg_settings.txt')
        if os.path.exists(bundled_settings):
            with open(bundled_settings, 'r') as f:
                path = f.read().strip()
                if path and os.path.isdir(path):
                    return path
    # Default: cartella persistente nella root del progetto
    default_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ffmpeg_persistent')
    os.makedirs(default_dir, exist_ok=True)
    return default_dir

def save_ffmpeg_install_dir(path):
    """Salva la directory di installazione preferita per FFmpeg."""
    settings_file = _settings_path()
    os.makedirs(os.path.dirname(settings_file), exist_ok=True)
    with open(settings_file, "w") as f:
        f.write(path)

def set_ffmpeg_bin(path):
    """Aggiorna il percorso FFmpeg a runtime, lo aggiunge al PATH di processo
    e sincronizza i binari interni di pydub (`AudioSegment.converter`/`ffprobe`),
    altrimenti dopo un cambio runtime pydub continuerebbe a usare il binario
    vecchio (o il default 'ffmpeg') provocando errori di conversione."""
    global FFMPEG_BIN
    FFMPEG_BIN = path
    install_dir = os.path.dirname(path)
    if install_dir:
        current = os.environ.get('PATH', '')
        if install_dir not in current.split(os.pathsep):
            os.environ['PATH'] = install_dir + os.pathsep + current
    try:
        from pydub import AudioSegment
        AudioSegment.converter = path
        ffprobe_bin = os.path.join(install_dir, 'ffprobe.exe') if install_dir else ''
        if ffprobe_bin and os.path.exists(ffprobe_bin):
            AudioSegment.ffprobe = ffprobe_bin
    except ImportError:
        pass

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

    Il download automatico usa build FFmpeg win64: su piattaforme non-Windows
    non è applicabile, quindi si restituisce un messaggio chiaro invece di
    scaricare un binario inusabile.
    """
    if sys.platform != 'win32':
        return False, ("Download automatico FFmpeg non supportato su questa piattaforma "
                       "(build disponibili solo per Windows): installa ffmpeg manualmente "
                       "(es. 'brew install ffmpeg' o 'sudo apt install ffmpeg')")
    install_dir = custom_install_dir if custom_install_dir else get_ffmpeg_install_dir()
    local_ffmpeg_exe = os.path.join(install_dir, 'ffmpeg.exe')
    
    try:
        # Check if exists or if it's an old version (simplified check)
        exists = os.path.exists(local_ffmpeg_exe)
        is_old = False
        if exists:
            res = subprocess.run([local_ffmpeg_exe, '-version'], capture_output=True, text=True,
                                 encoding='utf-8', errors='replace',
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            version_match = re.search(r'20\d{2}', res.stdout)
            # Se l'output non contiene un anno, NON forziamo un re-download
            # (evita download da 100MB+ ad ogni avvio per build senza data)
            if version_match and int(version_match.group()) < 2024:
                is_old = True

        if not exists or is_old:
            url = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip'
            # Scarichiamo in una sottocartella all'interno della dir di installazione
            temp_folder = os.path.join(install_dir, '_temp_download')
            os.makedirs(temp_folder, exist_ok=True)
            filename = os.path.join(temp_folder, 'ffmpeg.zip')
            # urlopen con timeout: urlretrieve non lo supporta e resterebbe
            # appeso per sempre su connessioni bloccate
            with urllib.request.urlopen(url, timeout=120) as resp, open(filename, 'wb') as out:
                shutil.copyfileobj(resp, out)
            with zipfile.ZipFile(filename, 'r') as zip_ref: 
                zip_ref.extractall(temp_folder)
            for root, dirs, files in os.walk(temp_folder):
                if 'ffmpeg.exe' in files:
                    for f in os.listdir(root): 
                        shutil.copy2(os.path.join(root, f), install_dir)
                    break
            else:
                raise Exception("Binario ffmpeg.exe non trovato nell'archivio scaricato")
            
            # Pulizia file temporanei di download
            shutil.rmtree(temp_folder, ignore_errors=True)
            
            # Aggiorniamo il percorso dell'eseguibile per l'applicazione
            save_ffmpeg_path(local_ffmpeg_exe)
            set_ffmpeg_bin(local_ffmpeg_exe)
            return True, "FFmpeg aggiornato correttamente!"
        return False, "FFmpeg è già aggiornato."
    except Exception as e:
        temp_folder = os.path.join(install_dir, '_temp_download')
        shutil.rmtree(temp_folder, ignore_errors=True)
        return False, f"Errore FFmpeg: {e}"

# Percorso globale per l'eseguibile FFmpeg
FFMPEG_BIN = get_ffmpeg_path()

# ==============================================================================
# PREPARAZIONE PATH PER PYDUBS
# ==============================================================================
# pydub valuta `AudioSegment.converter = get_encoder_name()` a livello di CLASSE
# durante l'import del modulo: se il PATH non e' aggiornato compare il
# RuntimeWarning "Couldn't find ffmpeg or avconv" e i binari vengono risolti
# erroneamente. Centralizzato qui (config e' il primo modulo importato da gui,
# logic, downloader e test) cosi' ogni successivo `import pydub` trova ffmpeg.
if os.path.basename(str(FFMPEG_BIN)) == 'ffmpeg.exe' and os.path.exists(FFMPEG_BIN):
    _ffmpeg_dir = os.path.dirname(FFMPEG_BIN)
    if os.path.exists(os.path.join(_ffmpeg_dir, 'ffmpeg.exe')):
        os.environ['PATH'] = _ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')

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

# Numero massimo di voci audio nella cache TTS in memoria (evita RAM illimitata)
MAX_TTS_MEMORY_ENTRIES = 200

# Numero max worker per processing parallelo (default: CPU * 2, max 16)
MAX_WORKERS = min((os.cpu_count() or 4) * 2, 16)

# Timeout per chiamate API (secondi)
API_TIMEOUT = 30
API_TIMEOUT_TTS = 60

# Timeout di default a livello socket: le librerie di terze parti che usano
# requests/urllib SENZA timeout esplicito (es. deep_translator) ereditano questo
# limite, quindi una chiamata appesa non resta viva per sempre e i thread del
# retry wrapper possono terminare (fix "thread zombie"). I timeout espliciti
# (es. download FFmpeg a 120s) prevalgono sul default.
socket.setdefaulttimeout(API_TIMEOUT)

# Retry FFmpeg configurabile
FFMPEG_MAX_RETRIES = 3
FFMPEG_RETRY_DELAY = 2

# Abilita caching persistente su disco
PERSISTENT_CACHE_ENABLED = True