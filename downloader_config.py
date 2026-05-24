# ==============================================================================
# CONFIGURAZIONE TECNICA DEI FORMATI DI DOWNLOAD
# ==============================================================================

FORMAT_CONFIG = {
    "Compatibilità (H.264)": {
        "Android (MP4 H.264 - Compatibile)": {"fmt": "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best", "ext": "mp4", "preset_support": True},
        "Apple/iOS (MP4 H.264 - Compatibile)": {"fmt": "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best", "ext": "mp4", "preset_support": True},
    },
    "Alta Efficienza (HEVC)": {
        "Android High-Eff (H.265 / HEVC)": {"fmt": "bestvideo+bestaudio/best", "ext": "mp4", "args": ['-c:v', 'libx265', '-crf', '23'], "preset_support": True},
        "iOS High-Eff (H.265 / HEVC)": {"fmt": "bestvideo+bestaudio/best", "ext": "mp4", "args": ['-c:v', 'libx265', '-crf', '23'], "preset_support": True},
    },
    "Risoluzione": {
        "Qualità Massima (Originale 4K/8K)": {"fmt": "bestvideo+bestaudio/best", "ext": None, "preset_support": False},
        "Professionale (MKV - Best Quality)": {"fmt": "bestvideo+bestaudio/best", "ext": "mkv", "preset_support": False},
        "2K Alta Qualità (1440p MP4)": {"fmt": "bestvideo[height<=1440]+bestaudio/best[height<=1440]", "ext": "mp4", "preset_support": False},
        "Full HD (1080p MP4)": {"fmt": "bestvideo[height<=1080]+bestaudio/best[height<=1080]", "ext": "mp4", "preset_support": False},
        "HD (720p MP4)": {"fmt": "bestvideo[height<=720]+bestaudio/best[height<=720]", "ext": "mp4", "preset_support": False},
        "SD (480p MP4)": {"fmt": "bestvideo[height<=480]+bestaudio/best[height<=480]", "ext": "mp4", "preset_support": False},
    },
    "Audio": {
        "Solo Audio (MP3 320kbps High Quality)": {"fmt": "bestaudio/best", "post": {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}, "preset_support": False},
        "Solo Audio Qualità Media (MP3 192kbps)": {"fmt": "bestaudio/best", "post": {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}, "preset_support": False},
    },
    "Legacy / Altri": {
        "Formato AVI (Compatibilità Vecchia)": {"fmt": "bestvideo+bestaudio/best", "ext": "avi", "preset_support": False},
        "Formato AV Universal (MP4 Stable)": {"fmt": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best", "ext": "mp4", "preset_support": False},
    }
}