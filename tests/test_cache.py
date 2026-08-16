import json
import os

import config
from conftest import make_logic
from pydub import AudioSegment


def test_translation_cache_roundtrip():
    logic = make_logic()
    assert logic._get_cached_translation("ciao", "en", "it") is None
    logic._set_cached_translation("ciao", "en", "it", "hello")
    assert logic._get_cached_translation("ciao", "en", "it") == "hello"


def test_translation_cache_disabilitato():
    config.PERSISTENT_CACHE_ENABLED = False
    logic = make_logic()
    logic._set_cached_translation("ciao", "en", "it", "hello")
    assert logic._get_cached_translation("ciao", "en", "it") is None


def test_tts_cache_disco_roundtrip(tmp_path):
    logic = make_logic()
    audio = AudioSegment.silent(duration=100, frame_rate=44100)
    logic._set_cached_tts("testo", "it", "male", audio)
    cached = logic._get_cached_tts("testo", "it", "male")
    assert cached is not None
    assert len(cached) == 100


def test_tts_memory_cache_trim():
    logic = make_logic()
    config.MAX_TTS_MEMORY_ENTRIES = 5
    for i in range(10):
        logic._tts_memory_cache[f"k{i}"] = AudioSegment.silent(duration=10)
        logic._trim_tts_memory_cache()
    assert len(logic._tts_memory_cache) == 5
    # FIFO: le più vecchie rimosse per prime
    assert "k0" not in logic._tts_memory_cache
    assert "k9" in logic._tts_memory_cache


def test_get_cache_key_stabile():
    logic = make_logic()
    k1 = logic._get_cache_key("testo", "it", "male")
    k2 = logic._get_cache_key("testo", "it", "male")
    assert k1 == k2
    assert len(k1) == 16


# ----------------------------------------------------------------------
# Fix 5.1: scrittura cache JSON atomica (tmp + os.replace)
# ----------------------------------------------------------------------

def test_save_cache_non_lascia_tmp_e_file_valido(tmp_path):
    logic = make_logic()
    logic._set_cached_translation("ciao", "en", "it", "hello")
    logic._save_persistent_cache()

    cache_file = os.path.join(config.CACHE_DIR, 'translation_cache.json')
    assert os.path.exists(cache_file)
    assert not os.path.exists(cache_file + '.tmp'), "il file .tmp deve essere stato sostituito"
    with open(cache_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert data['ciao_en_it']['translated_text'] == 'hello'


def test_load_ignora_tmp_corrotto(tmp_path):
    """Un .tmp residuo/corrotto (es. da crash) non deve influenzare il load."""
    logic = make_logic()
    logic._set_cached_translation("ciao", "en", "it", "hello")
    logic._save_persistent_cache()

    cache_file = os.path.join(config.CACHE_DIR, 'translation_cache.json')
    with open(cache_file + '.tmp', 'w', encoding='utf-8') as f:
        f.write('{"corrotto": {{{')

    logic2 = make_logic()  # ricarica da disco in __init__
    assert logic2._get_cached_translation("ciao", "en", "it") == "hello"


def test_save_cache_soprascribe_tmp_corrotto(tmp_path):
    """Il save successivo deve sovrascrivere senza lasciare tmp corrotto."""
    logic = make_logic()
    logic._set_cached_translation("ciao", "en", "it", "hello")
    logic._save_persistent_cache()

    cache_file = os.path.join(config.CACHE_DIR, 'translation_cache.json')
    with open(cache_file + '.tmp', 'w', encoding='utf-8') as f:
        f.write('garbage')

    logic._set_cached_translation("mondo", "en", "it", "world")
    logic._save_persistent_cache()
    assert not os.path.exists(cache_file + '.tmp')
    with open(cache_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert data['mondo_en_it']['translated_text'] == 'world'


# ----------------------------------------------------------------------
# Fix 5.4: trim cache TTS in memoria anche su hit da disco
# ----------------------------------------------------------------------

def test_tts_memory_trim_su_hit_da_disco():
    """Con N hit da disco (N > limite), la cache in memoria non supera
    MAX_TTS_MEMORY_ENTRIES: prima del fix il ramo 'hit da disco' non chiamava
    _trim_tts_memory_cache()."""
    logic = make_logic()
    config.MAX_TTS_MEMORY_ENTRIES = 5
    try:
        # Popola solo la cache DISCO (non la memoria) con 10 file TTS
        for i in range(10):
            audio = AudioSegment.silent(duration=10, frame_rate=44100)
            logic._set_cached_tts(f"testo {i}", "it", "male", audio)
        assert len(logic._tts_memory_cache) == 0

        # Traduzione identica al testo: la chiave TTS coincide con quella su disco
        logic.translate_text = lambda text, src, tgt: text
        for i in range(10):
            idx, audio, start_ms, translated = logic.translate_and_fetch_tts(
                (i, f"testo {i}", 0, "en", "it", "male"))
            assert translated == f"testo {i}"
            assert audio is not None
            assert len(logic._tts_memory_cache) <= 5, \
                f"dopo hit {i + 1} la cache ha {len(logic._tts_memory_cache)} voci"
    finally:
        config.MAX_TTS_MEMORY_ENTRIES = 200
    assert len(logic._tts_memory_cache) == 5