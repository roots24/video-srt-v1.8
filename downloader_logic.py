import yt_dlp
import os
import re
import threading
from tkinter import messagebox
import config

def is_valid_url(url):
    """Verifica se l'URL fornito è valido."""
    return re.match(r'(https?://).+', url) is not None

def run_download_process(url, job_row, category, fmt_choice, save_path, browser_choice, preset_var):
    """
    Gestisce il processo di download in modo indipendente dalla GUI.
    job_row è l'oggetto della riga della GUI che deve essere aggiornato.
    """
    try:
        from downloader_config import FORMAT_CONFIG
        conf = FORMAT_CONFIG[category][fmt_choice]
        
        # Utilizziamo il percorso FFmpeg unificato da config.py
        ffmpeg_path = config.get_ffmpeg_path()

        if not os.path.exists(save_path): 
            os.makedirs(save_path)
            
        outtmpl = os.path.join(save_path, '%(playlist_title)s/%(playlist_index)s - %(title)s.%(ext)s') if 'playlist' in url else os.path.join(save_path, '%(title)s.%(ext)s')

        def progress_hook(d):
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
            'outtmpl': outtmpl,
            'progress_hooks': [progress_hook],
            'format': conf['fmt']
        }

        if conf.get('ext'): 
            ydl_opts['merge_output_format'] = conf['ext']
            
        current_preset = preset_var.get() if hasattr(preset_var, 'get') else "medium"
        
        if conf.get("preset_support", False):
            args = conf.get('args', []) if conf.get('args') else []
            args.extend(['-preset', current_preset]) 
            ydl_opts['postprocessor_args'] = args
        elif conf.get('args'):
            ydl_opts['postprocessor_args'] = conf['args']

        if conf.get('post'): 
            ydl_opts['postprocessors'] = [conf['post']]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # Aggiornamento nome file tramite callback della riga
            job_row.after(0, lambda: setattr(job_row.lbl_name, 'text', info.get('title', 'Video')[:40] + "..."))
            ydl.download([url])

        job_row.set_final_status("✅ Completato", "green")
    except Exception as e:
        job_row.set_final_status(f"❌ Errore: {e}", "red")