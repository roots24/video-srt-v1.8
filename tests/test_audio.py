from conftest import make_logic, FakeTTSLogic, write_srt
from pydub import AudioSegment


def test_stretch_restituisce_invariato_se_gia_corto():
    logic = make_logic()
    audio = AudioSegment.silent(duration=500, frame_rate=44100)
    out = logic.stretch_audio(audio, target_duration_ms=1000)
    assert len(out) == 500


def test_stretch_via_ffmpeg_atempo():
    logic = make_logic()
    audio = AudioSegment.silent(duration=2000, frame_rate=44100)
    out = logic.stretch_audio(audio, target_duration_ms=1000, force_sync=True)
    assert abs(len(out) - 1000) <= 80


def test_stretch_rispetta_max_speed():
    logic = make_logic()
    audio = AudioSegment.silent(duration=3000, frame_rate=44100)
    # max_speed 1.5: 3000 -> minimo 2000ms, mai sotto
    out = logic.stretch_audio(audio, target_duration_ms=500, max_speed=1.5)
    assert len(out) >= 1900


def test_anti_drift_taglia_audio_in_ritardo(tmp_path):
    srt = write_srt(str(tmp_path / 'drift.srt'), [
        ("00:00:00,000", "00:00:00,800", "Frase A"),
        ("00:00:00,600", "00:00:01,600", "Frase B"),
    ])
    # TTS di 1200ms: la frase A (800ms) supera l'inizio della frase B (600ms)
    # -> anti-drift la taglia a 600ms; la frase B resta 1000ms (1.2x)
    # -> timeline totale 600 + 1000 = 1600ms
    logic = FakeTTSLogic(tts_duration_ms=1200, log_callback=lambda m: None)
    out = str(tmp_path / 'out.mp3')
    assert logic.generate_synced_audio(srt, out) is True
    final = AudioSegment.from_file(out)
    assert abs(len(final) - 1600) <= 100


def test_anti_drift_pipeline_durata_totale(tmp_path):
    """Con TTS entro i limiti, la durata finale e' l'ultimo end della frase."""
    srt = write_srt(str(tmp_path / 'ok.srt'), [
        ("00:00:00,000", "00:00:01,000", "Prima frase"),
        ("00:00:01,000", "00:00:02,500", "Seconda frase"),
    ])
    logic = FakeTTSLogic(tts_duration_ms=600, log_callback=lambda m: None)
    out = str(tmp_path / 'out.mp3')
    assert logic.generate_synced_audio(srt, out) is True
    final = AudioSegment.from_file(out)
    assert abs(len(final) - 1600) <= 100