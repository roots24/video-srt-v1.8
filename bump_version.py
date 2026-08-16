"""
Versionamento incrementale dell'applicazione.

Uso:
    python bump_version.py            → mostra la versione corrente
    python bump_version.py patch      → 1.8.2 -> 1.8.3 (fix, robustezza)
    python bump_version.py minor      → 1.8.2 -> 1.9.0 (nuova feature)
    python bump_version.py major      → 1.8.2 -> 2.0.0 (cambio sostanziale)

La fonte unica di verità è la costante APP_VERSION in config.py (usata dalla
GUI per titolo e header). Lo script aggiorna inoltre il titolo di README.md
così che documentazione e binario non divergano.

Il bump modifica subito i file; il commit resta un passo separato e esplicito.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / 'config.py'
README_FILE = ROOT / 'README.md'

VERSION_RE = re.compile(r'^APP_VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)"\s*$', re.M)
README_TITLE_RE = re.compile(r'^(#.*Ultimate Video Translator AI PRO )v(\d+\.\d+(\.\d+)?)')

KINDS = ('patch', 'minor', 'major')


def read_version(config_file=CONFIG_FILE):
    """Ritorna la versione corrente come tupla (major, minor, patch)."""
    m = VERSION_RE.search(Path(config_file).read_text(encoding='utf-8'))
    if not m:
        raise ValueError(f"APP_VERSION non trovata in {config_file}")
    return tuple(int(x) for x in m.groups())


def next_version(parts, kind):
    """Calcola la versione successiva secondo la regola di bumping."""
    major, minor, patch = parts
    if kind == 'patch':
        return (major, minor, patch + 1)
    if kind == 'minor':
        return (major, minor + 1, 0)
    if kind == 'major':
        return (major + 1, 0, 0)
    raise ValueError(f"Tipo di bump non valido: {kind} (usa uno di {KINDS})")


def bump(kind, config_file=CONFIG_FILE, readme_file=README_FILE):
    """Applica il bump su config.py (sempre) e README.md (se presente).
    Ritorna (vecchia_versione, nuova_versione) come stringhe."""
    old = read_version(config_file)
    new = next_version(old, kind)
    old_s = '.'.join(map(str, old))
    new_s = '.'.join(map(str, new))

    cfg_path = Path(config_file)
    updated, n = VERSION_RE.subn(f'APP_VERSION = "{new_s}"', cfg_path.read_text(encoding='utf-8'), count=1)
    if n != 1:
        raise RuntimeError("Sostituzione APP_VERSION fallita (formato inatteso in config.py)")
    cfg_path.write_text(updated, encoding='utf-8')

    rd_path = Path(readme_file)
    if rd_path.exists():
        readme = rd_path.read_text(encoding='utf-8')
        updated_rd, n2 = README_TITLE_RE.subn(rf'\g<1>v{new_s}', readme, count=1)
        if n2:
            rd_path.write_text(updated_rd, encoding='utf-8')
    return old_s, new_s


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        current = '.'.join(map(str, read_version()))
    except ValueError as e:
        print(f"Errore: {e}")
        return 1

    if not argv or argv[0] in ('-h', '--help'):
        cur = read_version()

        def fmt(parts):
            return '.'.join(map(str, parts))

        print(f"Versione corrente: {current}")
        print(f"\nUso: python bump_version.py [patch|minor|major]")
        print(f"  patch  {current} -> {fmt(next_version(cur, 'patch'))}")
        print(f"  minor  {current} -> {fmt(next_version(cur, 'minor'))}")
        print(f"  major  {current} -> {fmt(next_version(cur, 'major'))}")
        return 0

    kind = argv[0]
    try:
        old_s, new_s = bump(kind)
    except ValueError as e:
        print(f"Errore: {e}")
        return 1
    print(f"[OK] Versione incrementata: {old_s} -> {new_s}")
    print(f"   config.py: APP_VERSION aggiornato")
    if README_FILE.exists():
        print(f"   README.md: titolo aggiornato")
    print(f"\nRicorda di commitare i cambiamenti.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
