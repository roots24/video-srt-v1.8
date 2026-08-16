"""Versionamento incrementale: verifica la logica di bump di bump_version.py
(senza toccare i file reali: si opera su copie temporanee)."""
import pytest

import bump_version


CONFIG_SAMPLE = 'x = 1\nAPP_VERSION = "1.8.2"\ny = 2\n'
README_SAMPLE = "# Ultimate Video Translator AI PRO v1.8.2\n\nContenuti...\n"


def _write_pair(tmp_path, config_text=CONFIG_SAMPLE, readme_text=README_SAMPLE):
    cfg = tmp_path / 'config.py'
    cfg.write_text(config_text, encoding='utf-8')
    rd = tmp_path / 'README.md'
    rd.write_text(readme_text, encoding='utf-8')
    return cfg, rd


def test_next_version_patch():
    assert bump_version.next_version((1, 8, 2), 'patch') == (1, 8, 3)


def test_next_version_minor_azzera_patch():
    assert bump_version.next_version((1, 8, 2), 'minor') == (1, 9, 0)


def test_next_version_major_azzera_tutto():
    assert bump_version.next_version((1, 8, 2), 'major') == (2, 0, 0)


def test_next_version_tipo_invalido():
    with pytest.raises(ValueError):
        bump_version.next_version((1, 8, 2), 'lfg')


def test_read_version(tmp_path):
    cfg, _ = _write_pair(tmp_path)
    assert bump_version.read_version(cfg) == (1, 8, 2)


def test_read_version_mancante(tmp_path):
    cfg = tmp_path / 'config.py'
    cfg.write_text('niente versione qui\n', encoding='utf-8')
    with pytest.raises(ValueError):
        bump_version.read_version(cfg)


def test_bump_patch_aggiorna_config_e_readme(tmp_path):
    cfg, rd = _write_pair(tmp_path)
    old_s, new_s = bump_version.bump('patch', config_file=cfg, readme_file=rd)
    assert (old_s, new_s) == ('1.8.2', '1.8.3')
    assert bump_version.read_version(cfg) == (1, 8, 3)
    assert rd.read_text(encoding='utf-8').startswith('# Ultimate Video Translator AI PRO v1.8.3')


def test_bump_minor_aggiorna_config_e_readme(tmp_path):
    cfg, rd = _write_pair(tmp_path)
    old_s, new_s = bump_version.bump('minor', config_file=cfg, readme_file=rd)
    assert (old_s, new_s) == ('1.8.2', '1.9.0')
    assert bump_version.read_version(cfg) == (1, 9, 0)
    assert 'v1.9.0' in rd.read_text(encoding='utf-8')


def test_bump_maggiore_di_minore(tmp_path):
    """Due bump di fila: patch poi minor — la sequenza resta coerente."""
    cfg, rd = _write_pair(tmp_path)
    bump_version.bump('patch', config_file=cfg, readme_file=rd)
    old_s, new_s = bump_version.bump('minor', config_file=cfg, readme_file=rd)
    assert (old_s, new_s) == ('1.8.3', '1.9.0')
    assert bump_version.read_version(cfg) == (1, 9, 0)


def test_bump_readme_mancante_non_crasha(tmp_path):
    cfg = tmp_path / 'config.py'
    cfg.write_text(CONFIG_SAMPLE, encoding='utf-8')
    rd = tmp_path / 'README_assente.md'
    old_s, new_s = bump_version.bump('patch', config_file=cfg, readme_file=rd)
    assert (old_s, new_s) == ('1.8.2', '1.8.3')
    assert bump_version.read_version(cfg) == (1, 8, 3)


def test_app_version_esistente_in_config_reale():
    """La fonte di verità esiste davvero in config.py del progetto."""
    major, minor, patch = bump_version.read_version(bump_version.CONFIG_FILE)
    assert (major, minor) >= (1, 8)
    assert patch >= 0
    assert bump_version.__file__  # modulo importabile dalla root
