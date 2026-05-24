# ==============================================================================
# MODULO DI CONFIGURAZIONE DEI PROFILI DI DOWNLOAD (YT-DLP)
# ==============================================================================
"""
Questo modulo definisce i profili di qualità e formato per il download dei video.
Ogni profilo mappa a una stringa di selezione formato (`fmt`) compatibile con yt-dlp,
definendo l'estensione finale e gli argomenti di post-processing per FFmpeg.
"""

FORMAT_CONFIG = {
    "Compatibilità (H.264)": {
        # Utilizza codec H.264 (avc1) e audio m4a per massima compatibilità cross-platform senza necessità di transcoding pesante.
        "Android (MP4 H.264 - Compatibile)": {"fmt": "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best", "ext": "mp4", "preset_support": True},
        "Apple/iOS (MP4 H.264 - Compatibile)": {"fmt": "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best", "ext": "mp4", "preset_support": True},
    },
    "Alta Efficienza (HEVC)": {
        # Forzatura del codec H.265/HEVC tramite FFmpeg per ridurre le dimensioni del file mantenendo l'alta qualità.
        # Il CRF 23 è un bilanciamento standard tra dimensione e fedeltà visiva.
        "Android High-Eff (H.265 / HEVC)": {"fmt": "bestvideo+bestaudio/best", "ext": "mp4", "args": ['-c:v', 'libx265', '-crf', '23'], "preset_support": True},
        "iOS High-Eff (H.265 / HEVC)": {"fmt": "bestvideo+bestaudio/best", "ext": "mp4", "args": ['-c:v', 'libx265', '-crf', '23'], "preset_support": True},
    },
    "Risoluzione": {
        # Download della versione a più alta risoluzione disponibile senza limiti di altezza.
        "Qualità Massima (Originale 4K/8K)": {"fmt": "bestvideo+bestaudio/best", "ext": None, "preset_support": False},
        # Formato MKV per preservare i flussi originali senza ricodifica se possibile.
        "Professionale (MKV - Best Quality)": {"fmt": "bestvideo+bestaudio/best", "ext": "mkv", "preset_support": False},
        # Limite di altezza fissato tramite selettori yt-dlp [height<=X].
        "2K Alta Qualità (1440p MP4)": {"fmt": "bestvideo[height<=1440]+bestaudio/best[height<=1440]", "ext": "mp4", "preset_support": False},
        "Full HD (1080p MP4)": {"fmt": "bestvideo[height<=1080]+bestaudio/best[height<=1080]", "ext": "mp4", "preset_support": False},
        "HD (720p MP4)": {"fmt": "bestvideo[height<=720]+bestaudio/best[height<=720]", "ext": "mp4", "preset_support": False},
        "SD (480p MP4)": {"fmt": "bestvideo[height<=480]+bestaudio/best[height<=480]", "ext": "mp4", "preset_support": False},
    },
    "Audio": {
        # Estrazione audio pura con post-processing FFmpeg per convertire in MP3 a bitrate specificato.
        "Solo Audio (MP3 320kbps High Quality)": {"fmt": "bestaudio/best", "post": {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}, "preset_support": False},
        "Solo Audio Qualità Media (MP3 192kbps)": {"fmt": "bestaudio/best", "post": {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}, "preset_support": False},
    },
    "Legacy / Altri": {
        "Formato AVI (Compatibilità Vecchia)": {"fmt": "bestvideo+bestaudio/best", "ext": "avi", "preset_support": False},
        "Formato AV Universal (MP4 Stable)": {"fmt": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best", "ext": "mp4", "preset_support": False},
    }
}