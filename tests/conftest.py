import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from logic import VideoTranslatorLogic
from pydub import AudioSegment


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Ogni test usa una cache dedicata e temporanea (mai quella reale dell'utente)."""
    monkeypatch.setattr(config, 'PERSISTENT_CACHE_ENABLED', True)
    cache_dir = str(tmp_path / 'cache')
    monkeypatch.setattr(config, 'CACHE_DIR', cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    yield
    monkeypatch.setattr(config, 'PERSISTENT_CACHE_ENABLED', False)


def make_logic(log_callback=None, **kwargs):
    return VideoTranslatorLogic(log_callback or (lambda m: None), **kwargs)


class FakeTTSLogic(VideoTranslatorLogic):
    """Logic senza rete: TTS = silenzio di durata fissa, traduzione = testo dato."""
    def __init__(self, tts_duration_ms=1200, **kwargs):
        super().__init__(**kwargs)
        self.tts_duration_ms = tts_duration_ms

    def translate_and_fetch_tts(self, data):
        idx, text, start_ms, src_lang, tgt_lang, gender = data
        audio = AudioSegment.silent(duration=self.tts_duration_ms, frame_rate=44100)
        return idx, audio, start_ms, 'tradotto'


def write_srt(path, blocks, encoding='utf-8'):
    """Scrive un file SRT da una lista di (start, end, text).
    `encoding` permette di generare file in codifiche non UTF-8 (es. 'utf-16-le',
    'cp1252') per i test di robustezza del reader."""
    lines = []
    for num, (start, end, text) in enumerate(blocks, start=1):
        lines.append(f"{num}\n{start} --> {end}\n{text}\n")
    with open(path, 'w', encoding=encoding) as f:
        f.write('\n'.join(lines))
    return path