"""Fix 3.2: parsing SRT con encoding non UTF-8 (UTF-8 BOM, UTF-16, cp1252/ANSI).

Prima del fix ogni lettura era hardcoded su utf-8 e crashava con
UnicodeDecodeError su file salvati come UTF-16 o ANSI/Windows-1252."""
from conftest import make_logic, write_srt

# Gli accenti sono essenziali: in cp1252 sono byte (es. è=0xE8) non validi
# come UTF-8, quindi solo con essi si verifica davvero il fallback di encoding
BLOCKS = [
    ("00:00:00,000", "00:00:02,000", "Ciao, oggi è una bella giornata"),
    ("00:00:02,000", "00:00:04,500", "Andiamo a fare una passeggiata, non è vero?"),
]


def _expected_texts():
    return [b[2] for b in BLOCKS]


def test_parsing_utf8_con_bom(tmp_path):
    srt = write_srt(tmp_path / 'utf8_bom.srt', BLOCKS, encoding='utf-8-sig')
    segments, invalid = make_logic().parse_srt_file(str(srt))
    assert [s['text'] for s in segments] == _expected_texts()
    assert invalid == 0


def test_parsing_utf16_le_con_bom(tmp_path):
    srt = write_srt(tmp_path / 'utf16.srt', BLOCKS, encoding='utf-16')
    segments, invalid = make_logic().parse_srt_file(str(srt))
    assert [s['text'] for s in segments] == _expected_texts()
    assert invalid == 0


def test_parsing_cp1252_con_accents(tmp_path):
    # Caratteri accentati: in cp1252 sono byte non validi come UTF-8,
    # quindi prima del fix qui si sollevava UnicodeDecodeError
    srt = write_srt(tmp_path / 'win1252.srt', BLOCKS, encoding='cp1252')
    segments, invalid = make_logic().parse_srt_file(str(srt))
    assert [s['text'] for s in segments] == _expected_texts()
    assert invalid == 0


def test_read_text_file_cp1252_puro_ascii(tmp_path):
    """File cp1252 ma con solo byte ASCII: leggibile anche come UTF-8, stesso testo."""
    blocks = [("00:00:00,000", "00:00:01,000", "Only ascii here")]
    srt = write_srt(tmp_path / 'ascii.srt', blocks, encoding='cp1252')
    content = make_logic()._read_text_file(str(srt))
    assert "Only ascii here" in content


def test_extract_srt_text_sample_encodings(tmp_path):
    logic = make_logic()
    for enc in ('utf-8-sig', 'utf-16', 'cp1252'):
        srt = write_srt(tmp_path / f'sample_{enc}.srt', BLOCKS, encoding=enc)
        sample = logic.extract_srt_text_sample(str(srt), min_chars=10)
        assert sample == BLOCKS[0][2], f"fail con encoding {enc}"


def test_read_text_file_ultima_spiaggia_senza_crash(tmp_path):
    """Byte che non sono né UTF-8 né UTF-16: il reader non deve mai crashare."""
    p = tmp_path / 'garbage.bin'
    p.write_bytes(b'\x80\x81\x82\x90\x91\x00\xff')
    content = make_logic()._read_text_file(str(p))
    assert isinstance(content, str)
