import os
import tempfile

from downloader_config import FORMAT_CONFIG


def test_profili_struttura_completa():
    for category, profiles in FORMAT_CONFIG.items():
        for name, profile in profiles.items():
            assert 'fmt' in profile, f"{category}/{name}: manca fmt"
            assert 'ext' in profile and 'args' in profile and 'post' in profile
            assert 'preset_support' in profile


def test_profili_h264_android_ios_identici_ma_indipendenti():
    android = FORMAT_CONFIG['Compatibilità (H.264)']['Android (MP4 H.264 - Compatibile)']
    ios = FORMAT_CONFIG['Compatibilità (H.264)']['Apple/iOS (MP4 H.264 - Compatibile)']
    assert android['fmt'] == ios['fmt'] == 'bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    assert android['ext'] == ios['ext'] == 'mp4'
    assert android['preset_support'] is True


def test_profili_hevc_args_non_condivisi():
    android = FORMAT_CONFIG['Alta Efficienza (HEVC)']['Android High-Eff (H.265 / HEVC)']
    ios = FORMAT_CONFIG['Alta Efficienza (HEVC)']['iOS High-Eff (H.265 / HEVC)']
    assert android['args'] == ['-c:v', 'libx265', '-crf', '23']
    # Liste separate: l'extend del preset su uno NON deve toccare l'altro
    assert android['args'] is not ios['args']
    android['args'].append('mutazione-test')
    assert ios['args'] == ['-c:v', 'libx265', '-crf', '23']
    android['args'].pop()  # ripristina per non contaminare gli altri test


def test_preset_extend_non_muta_config():
    """Riproduce la logica di downloader_logic: list() prima dell'extend."""
    conf = FORMAT_CONFIG['Alta Efficienza (HEVC)']['Android High-Eff (H.265 / HEVC)']
    args = list(conf.get('args') or [])
    args.extend(['-preset', 'medium'])
    assert args == ['-c:v', 'libx265', '-crf', '23', '-preset', 'medium']
    assert conf['args'] == ['-c:v', 'libx265', '-crf', '23']


def test_makedirs_cartella_esistente():
    d = tempfile.mkdtemp()
    os.makedirs(d, exist_ok=True)
    assert os.path.isdir(d)


def test_profili_risoluzione():
    res = FORMAT_CONFIG['Risoluzione']
    assert res['Qualità Massima (Originale 4K/8K)']['ext'] is None
    assert res['Full HD (1080p MP4)']['fmt'] == 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
    assert res['SD (480p MP4)']['fmt'] == 'bestvideo[height<=480]+bestaudio/best[height<=480]'