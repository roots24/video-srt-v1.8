# ==============================================================================
# MODULO DI CONFIGURAZIONE DEI PROFILI DI DOWNLOAD (YT-DLP)
# ==============================================================================
"""
Questo modulo definisce i profili di qualità e formato per il download dei video.
Ogni profilo mappa a una stringa di selezione formato (`fmt`) compatibile con yt-dlp,
definendo l'estensione finale e gli argomenti di post-processing per FFmpeg.
"""

def _profile(fmt, ext=None, args=None, preset=False, post=None):
    """Crea un profilo di download. `args` viene copiato: ogni profilo ha la
    propria lista, evitando mutazioni condivise tra profili (es. Android/iOS)."""
    return {
        "fmt": fmt,
        "ext": ext,
        "args": list(args) if args else None,
        "preset_support": preset,
        "post": post,
    }

# Template condivisi tra profili (evita duplicazione letterale Android/iOS)
_H264_FMT = "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best"
_BEST_FMT = "bestvideo+bestaudio/best"
_HEVC_ARGS = ['-c:v', 'libx265', '-crf', '23']

FORMAT_CONFIG = {
    "Compatibilità (H.264)": {
        # Utilizza codec H.264 (avc1) e audio m4a per massima compatibilità cross-platform senza necessità di transcoding pesante.
        "Android (MP4 H.264 - Compatibile)": _profile(_H264_FMT, ext="mp4", preset=True),
        "Apple/iOS (MP4 H.264 - Compatibile)": _profile(_H264_FMT, ext="mp4", preset=True),
    },
    "Alta Efficienza (HEVC)": {
        # Forzatura del codec H.265/HEVC tramite FFmpeg per ridurre le dimensioni del file mantenendo l'alta qualità.
        # Il CRF 23 è un bilanciamento standard tra dimensione e fedeltà visiva.
        "Android High-Eff (H.265 / HEVC)": _profile(_BEST_FMT, ext="mp4", args=_HEVC_ARGS, preset=True),
        "iOS High-Eff (H.265 / HEVC)": _profile(_BEST_FMT, ext="mp4", args=_HEVC_ARGS, preset=True),
    },
    "Risoluzione": {
        # Download della versione a più alta risoluzione disponibile senza limiti di altezza.
        "Qualità Massima (Originale 4K/8K)": _profile(_BEST_FMT, ext=None),
        # Formato MKV per preservare i flussi originali senza ricodifica se possibile.
        "Professionale (MKV - Best Quality)": _profile(_BEST_FMT, ext="mkv"),
        # Limite di altezza fissato tramite selettori yt-dlp [height<=X].
        "2K Alta Qualità (1440p MP4)": _profile("bestvideo[height<=1440]+bestaudio/best[height<=1440]", ext="mp4"),
        "Full HD (1080p MP4)": _profile("bestvideo[height<=1080]+bestaudio/best[height<=1080]", ext="mp4"),
        "HD (720p MP4)": _profile("bestvideo[height<=720]+bestaudio/best[height<=720]", ext="mp4"),
        "SD (480p MP4)": _profile("bestvideo[height<=480]+bestaudio/best[height<=480]", ext="mp4"),
    },
    "Audio": {
        # Estrazione audio pura con post-processing FFmpeg per convertire in MP3 a bitrate specificato.
        "Solo Audio (MP3 320kbps High Quality)": _profile("bestaudio/best", post={"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}),
        "Solo Audio Qualità Media (MP3 192kbps)": _profile("bestaudio/best", post={"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}),
    },
    "Legacy / Altri": {
        "Formato AVI (Compatibilità Vecchia)": _profile(_BEST_FMT, ext="avi"),
        "Formato AV Universal (MP4 Stable)": _profile("bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best", ext="mp4"),
    }
}