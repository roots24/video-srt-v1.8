import pytest

from conftest import make_logic, FakeTTSLogic, write_srt


def test_extract_srt_text_sample(tmp_path):
    srt = tmp_path / 'sample.srt'
    write_srt(srt, [
        ("00:00:00,000", "00:00:02,000", "Prima frase sufficientemente lunga da superare la soglia minima"),
        ("00:00:02,000", "00:00:04,000", "Seconda frase"),
    ])
    logic = make_logic()
    sample = logic.extract_srt_text_sample(str(srt))
    assert sample.startswith("Prima frase")


def test_extract_srt_text_sample_ritorna_ultimo_se_tutti_corti(tmp_path):
    srt = tmp_path / 'short.srt'
    write_srt(srt, [
        ("00:00:00,000", "00:00:02,000", "Breve"),
        ("00:00:02,000", "00:00:04,000", "Breve anche questa"),
    ])
    logic = make_logic()
    sample = logic.extract_srt_text_sample(str(srt), min_chars=50)
    assert sample == "Breve anche questa"


def test_extract_srt_text_sample_srt_invalido(tmp_path):
    srt = tmp_path / 'bad.srt'
    srt.write_text("contenuto senza timestamp", encoding='utf-8')
    logic = make_logic()
    assert logic.extract_srt_text_sample(str(srt)) == ""


def test_generate_rifiuta_srt_vuoto(tmp_path):
    srt = tmp_path / 'empty.srt'
    srt.write_text("   ", encoding='utf-8')
    logs = []
    logic = make_logic(logs.append)
    assert logic.generate_synced_audio(str(srt), str(tmp_path / 'out.mp3')) is False
    assert any('vuoto' in m for m in logs)


def test_generate_ignora_segmenti_invalidi_conteggiandoli(tmp_path):
    srt = tmp_path / 'mixed.srt'
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nFrase valida\n\n"
        "2\nriga senza timestamp\nTesto orfano\n\n"
        "3\n00:00:99,000 --> 00:00:05,000\nTesto con timestamp invertito\n",
        encoding='utf-8'
    )
    logs = []
    logic = FakeTTSLogic(log_callback=logs.append)
    assert logic.generate_synced_audio(str(srt), str(tmp_path / 'out.mp3')) is True
    assert any('2 segmenti SRT ignorati' in m for m in logs)


def test_generate_nessun_segmento_valido(tmp_path):
    srt = tmp_path / 'allbad.srt'
    srt.write_text("1\n00:00:99,000 --> 00:00:05,000\nTesto\n", encoding='utf-8')
    logs = []
    logic = FakeTTSLogic(log_callback=logs.append)
    assert logic.generate_synced_audio(str(srt), str(tmp_path / 'out.mp3')) is False
    assert any('Nessun segmento SRT valido' in m for m in logs)


# ----------------------------------------------------------------------
# Fix 4.1: parser SRT tollerante a file "sporchi"
# ----------------------------------------------------------------------

CLEAN = (
    "1\n00:00:00,000 --> 00:00:01,000\nFrase una\n\n"
    "2\n00:00:01,000 --> 00:00:02,000\nFrase due\n\n"
    "3\n00:00:02,000 --> 00:00:03,000\nFrase tre\n"
)


def _parse_clean(logic):
    segments, invalid = logic._parse_srt_segments(CLEAN)
    return segments, invalid


def test_parser_file_pulito_baseline():
    logic = make_logic()
    segments, invalid = _parse_clean(logic)
    assert [s['text'] for s in segments] == ["Frase una", "Frase due", "Frase tre"]
    assert invalid == 0


def test_parser_cRLF(tmp_path):
    """Fine riga Windows \\r\\n: stesso numero di segmenti del file pulito."""
    logic = make_logic()
    segments, invalid = logic._parse_srt_segments(CLEAN.replace('\n', '\r\n'))
    clean_segments, clean_invalid = _parse_clean(logic)
    assert [s['text'] for s in segments] == [s['text'] for s in clean_segments]
    assert (invalid, clean_invalid) == (0, 0)


def test_parser_righe_vuote_multiple(tmp_path):
    """Righe vuote doppie/triple tra i blocchi: nessun segmento perso né
    blocchi vuoti conteggiati come segmenti invalidi."""
    dirty = CLEAN.replace('\n\n', '\n\n\n\n')  # spaziature extra tra blocchi
    logic = make_logic()
    segments, invalid = logic._parse_srt_segments(dirty)
    clean_segments, clean_invalid = _parse_clean(logic)
    assert [s['text'] for s in segments] == [s['text'] for s in clean_segments]
    assert invalid == clean_invalid == 0


def test_parser_spazi_sulle_righe_vuote(tmp_path):
    """Righe 'vuote' con spazi/tab tra i blocchi: trattate come separatori."""
    dirty = CLEAN.replace('\n\n', '\n   \n\t\n')
    logic = make_logic()
    segments, invalid = logic._parse_srt_segments(dirty)
    clean_segments, _ = _parse_clean(logic)
    assert [s['text'] for s in segments] == [s['text'] for s in clean_segments]
    assert invalid == 0


def test_parser_file_sporco_da_disco(tmp_path):
    """File completo con CRLF + righe vuote extra: parsing via parse_srt_file.
    Scritto in binary per evitare la conversione \\n -> \\r\\n del text mode
    Windows (che produrrebbe \\r\\r\\n, contenuto corrotto, non CRLF)."""
    srt = tmp_path / 'dirty.srt'
    dirty = CLEAN.replace('\n', '\r\n').replace('\r\n\r\n', '\r\n\r\n\r\n\r\n')
    with open(srt, 'wb') as f:
        f.write(dirty.encode('utf-8'))
    segments, invalid = make_logic().parse_srt_file(str(srt))
    assert [s['text'] for s in segments] == ["Frase una", "Frase due", "Frase tre"]
    assert invalid == 0


def test_parser_segmento_invalido_mancante_timestamp_conteggiato():
    """I blocchi malformati REALI (non i vuoti) restano conteggiati come invalidi."""
    logic = make_logic()
    segments, invalid = logic._parse_srt_segments(
        "1\n00:00:00,000 --> 00:00:01,000\nOk\n\n"
        "2\nrighe senza arrow\n\n"
        "3\n00:00:01,000 --> 00:00:02,000\nOk anche\n")
    assert [s['text'] for s in segments] == ["Ok", "Ok anche"]
    assert invalid == 1