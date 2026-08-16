import yt_dlp
import os
import re
import config

def is_valid_url(url):
    """Verifica se l'URL fornito è valido."""
    return re.match(r'(https?://).+', url) is not None

def run_download_process(url, job_row, category, fmt_choice, save_path, browser_choice, preset_var):
    """
    Motore di download asincrono basato su yt-dlp.

    PARAMETRI TECNICI:
    - url: L'indirizzo del video/playlist.
    - job_row: Istanza di DownloadJobRow per aggiornamenti UI in tempo reale tramite callback.
    - category/fmt_choice: Selettori per recuperare la configurazione dal modulo `downloader_config`.
    - browser_choice: Specifica il browser da cui estrarre i cookie (fondamentale per bypassare blocchi di contenuti protetti).
    - preset_var: Variabile CustomTkinter che contiene il preset FFmpeg (es. 'ultrafast').

    FLUSSO DI ESECUZIONE:
    1. Recupero configurazione formato e percorso FFmpeg unificato.
    2. Definizione del template di output (`outtmpl`) per gestire sia singoli video che playlist.
    3. Configurazione di `progress_hook` per mappare i byte scaricati alla barra di progresso della GUI.
    4. Esecuzione di yt-dlp con le opzioni specificate (cookies, formati, post-processori).
    5. Notifica dello stato finale (Successo/Errore) tramite la riga della GUI.
    """
    try:
        from downloader_config import FORMAT_CONFIG
        conf = FORMAT_CONFIG[category][fmt_choice]
        
        # Utilizziamo il percorso FFmpeg unificato da config.py
        ffmpeg_path = config.get_ffmpeg_path()

        # exist_ok: la cartella (spesso il CWD predefinito) esiste già —
        # senza questa flag os.makedirs solleva FileExistsError e il download fallisce
        os.makedirs(save_path, exist_ok=True)

        def progress_hook(d):
            """
            Callback chiamata da yt-dlp durante il download.
            Calcola la percentuale di completamento e attiva l'animazione di merge 
            quando il download dei flussi audio/video è terminato e inizia l'unione tramite FFmpeg.
            """
            if d['status'] == 'downloading':
                downloaded, total = d.get('downloaded_bytes'), (d.get('total_bytes') or d.get('final_filesize'))
                float_p = downloaded / total if (downloaded and total) else 0
                job_row.update_progress(float_p, f"{d.get('_percent_str', '0%')} | {d.get('_speed_str', 'N/A')}")
            elif d['status'] == 'finished':
                job_row.start_merge_animation()

        ydl_opts = {
            'nocheckcertificate': True, 
            'quiet': True, 
            'no_warnings': True,
            'cookies_from_browser': browser_choice, 
            'retries': 10,
            'ffmpeg_location': ffmpeg_path, 
            'progress_hooks': [progress_hook],
            'format': conf['fmt']
        }

        if conf.get('ext'): 
            ydl_opts['merge_output_format'] = conf['ext']
            
        current_preset = preset_var.get() if hasattr(preset_var, 'get') else "medium"
        
        if conf.get("preset_support", False):
            # Copia la lista: senza list() l'extend muterebbe gli args condivisi
            # tra profili identici (Android/iOS HEVC), accumulando preset duplicati
            args = list(conf.get('args') or [])
            args.extend(['-preset', current_preset])
            ydl_opts['postprocessor_args'] = args
        elif conf.get('args'):
            ydl_opts['postprocessor_args'] = conf['args']

        if conf.get('post'): 
            ydl_opts['postprocessors'] = [conf['post']]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Estrazione unica dei metadati: il tipo (video/playlist) determina il template di output
            info = ydl.extract_info(url, download=False)
            is_playlist = info.get('_type') == 'playlist'
            outtmpl = (os.path.join(save_path, '%(playlist_title)s/%(playlist_index)s - %(title)s.%(ext)s')
                       if is_playlist else os.path.join(save_path, '%(title)s.%(ext)s'))
            # In yt-dlp moderno outtmpl deve essere un dict {'default': ...}, non una stringa
            ydl.params['outtmpl'] = {'default': outtmpl}
            # Aggiornamento nome file tramite callback della riga
            title = (info.get('title') or 'Video')[:40] + "..."
            job_row.after(0, lambda t=title: setattr(job_row.lbl_name, 'text', t))
            # Download senza seconda estrazione dei metadati
            ydl.process_ie_result(info, download=True)

        job_row.set_final_status("✅ Completato", "green")
    except Exception as e:
        job_row.set_final_status(f"❌ Errore: {e}", "red")