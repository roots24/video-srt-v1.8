import os
import tempfile
import glob

import pytest

from logic import VideoTranslatorLogic, BatchProcessor
from pydub import AudioSegment


class StubLogic(VideoTranslatorLogic):
    """Logic con generate/merge stub: verifica solo il flusso di process()."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.merge_calls = []

    def generate_synced_audio(self, srt_file, output_file, **kwargs):
        AudioSegment.silent(duration=300, frame_rate=44100).export(output_file, format="mp3")
        return True

    def merge_audio_video_mixed(self, video_path, audio_path, out_path, **kwargs):
        self.merge_calls.append((video_path, audio_path, out_path))
        return True


def test_process_modalita_audio_copia_e_pulisce_temp(tmp_path):
    logic = StubLogic(log_callback=lambda m: None)
    srt = tmp_path / 'a.srt'
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nTesto\n", encoding='utf-8')
    out = tmp_path / 'out.mp3'

    # Baseline: residui di run precedenti possono esistere in %TEMP%;
    # il test deve verificare che process() NON ne aggiunga di nuovi
    tmp_dir = tempfile.gettempdir()
    before = {f for f in glob.glob(os.path.join(tmp_dir, 'tmp*.mp3')) if os.path.exists(f)}
    ok, msg = logic.process(str(srt), str(out), mode='audio')
    assert ok is True
    assert out.exists()
    assert logic.merge_calls == []
    # Nessun NUOVO file temporaneo .mp3 lasciato nella temp dir da process()
    leftovers = {f for f in glob.glob(os.path.join(tmp_dir, 'tmp*.mp3')) if os.path.exists(f)} - before
    assert not leftovers


def test_process_modalita_video_senza_video_errore_esplicito(tmp_path):
    logic = StubLogic(log_callback=lambda m: None)
    srt = tmp_path / 'a.srt'
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nTesto\n", encoding='utf-8')

    ok, msg = logic.process(str(srt), str(tmp_path / 'out.mp4'), mode='video')
    assert ok is False
    assert 'nessun video' in msg


def test_process_modalita_video_chiama_merge(tmp_path):
    logic = StubLogic(log_callback=lambda m: None)
    srt = tmp_path / 'a.srt'
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nTesto\n", encoding='utf-8')
    vid = tmp_path / 'v.mp4'
    vid.write_bytes(b'fake')
    out = tmp_path / 'out.mp4'

    ok, msg = logic.process(str(srt), str(out), video_file=str(vid), mode='video', vol_orig=0.4, vol_trans=1.0)
    assert ok is True
    assert len(logic.merge_calls) == 1
    assert logic.merge_calls[0][0] == str(vid)


def test_process_embed_srt_passa_segments(tmp_path):
    logic = StubLogic(log_callback=lambda m: None)
    logic._last_segments = [{'start': 0, 'limit': 1000, 'translated': 'ciao'}]
    srt = tmp_path / 'a.srt'
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nTesto\n", encoding='utf-8')
    vid = tmp_path / 'v.mp4'
    vid.write_bytes(b'fake')

    ok, _ = logic.process(str(srt), str(tmp_path / 'out.mp4'), video_file=str(vid),
                          mode='video', embed_srt=True)
    assert ok is True
    assert logic.merge_calls[0][2] == str(tmp_path / 'out.mp4')