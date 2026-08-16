import pytest
from logic import VideoTranslatorLogic


def test_srt_time_to_ms_standard():
    logic = VideoTranslatorLogic(lambda m: None)
    assert logic.srt_time_to_ms("00:00:01,500") == 1500
    assert logic.srt_time_to_ms("00:01:02,000") == 62000
    assert logic.srt_time_to_ms("01:00:00,000") == 3600000


def test_srt_time_to_ms_punto_invece_di_virgola():
    logic = VideoTranslatorLogic(lambda m: None)
    assert logic.srt_time_to_ms("00:00:01.250") == 1250


def test_srt_time_to_ms_4_cifre_millis():
    # Formato non standard: 00:01:23,4567 -> prime 3 cifre significative
    logic = VideoTranslatorLogic(lambda m: None)
    assert logic.srt_time_to_ms("00:01:23,4567") == 83456


def test_srt_time_to_ms_ore_oltre_24h():
    logic = VideoTranslatorLogic(lambda m: None)
    assert logic.srt_time_to_ms("25:00:00,000") == 90000000


def test_srt_time_to_ms_minuti_mancanti():
    logic = VideoTranslatorLogic(lambda m: None)
    assert logic.srt_time_to_ms("00:00:1,000") == 1000


@pytest.mark.parametrize("bad", ["", "abc", "00:00:00", "00:00:60,000", "00:60:00,000"])
def test_srt_time_to_ms_invalidi(bad):
    logic = VideoTranslatorLogic(lambda m: None)
    with pytest.raises(ValueError):
        logic.srt_time_to_ms(bad)


def test_ms_to_srt_time_roundtrip():
    logic = VideoTranslatorLogic(lambda m: None)
    for ms in [0, 1, 999, 1000, 1500, 62000, 90000000, 83456]:
        assert logic.srt_time_to_ms(logic.ms_to_srt_time(ms)) == ms


def test_ms_to_srt_time_zero():
    logic = VideoTranslatorLogic(lambda m: None)
    assert logic.ms_to_srt_time(0) == "00:00:00,000"