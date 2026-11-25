"""Static submission layout/link checks only; never validates TCAD or physics."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 20 * 1024 * 1024
REQUIRED = ['README.md', 'md/사전계획.md', 'md/실행정보.md', 'md/결과요약.md',
            '검증/검증기록.md', '검증/원본목록.md', 'tcad', 'python', '검증/raw', '그림']
LINK = re.compile(r'\[[^\]]*\]\(([^)]+)\)')
FORBIDDEN_NAMES = {'token.txt', 'bootstrap.txt', 'private_discovery.json', 'route_settings.json',
                   'discovery_settings.json', 'id_rsa', 'id_ed25519', '.env'}


def check(root=ROOT):
    root = Path(root).resolve()
    errors = []
    members = [p for p in root.iterdir() if p.is_dir() and (p / '문헌/README.md').is_file() and (p / '연구/README.md').is_file()]
    runs = [readme for member in members for readme in (member / '연구').glob('*/*/README.md')]
    for readme in runs:
        run = readme.parent
        for item in REQUIRED:
            path = run / item
            is_dir = item in {'tcad', 'python', '검증/raw', '그림'}
            if not (path.is_dir() if is_dir else path.is_file()):
                errors.append(f'Missing path: {path.relative_to(root).as_posix()}')
    docs = [root / name for name in ['README.md', 'md/접근권한.md', 'md/기존README_20261125.md']]
    for folder in ['md/협업', 'md/양식', 'md/운영']:
        docs.extend((root / folder).rglob('*.md'))
    for member in members:
        docs.extend(member.rglob('*.md'))
    docs.extend([root / '연구/README.md', root / '연구/01_GAA_IdVg/README.md', root / '연구/02_치수변화/README.md'])
    for path in docs:
        if not path.is_file():
            errors.append(f'Missing document: {path.relative_to(root).as_posix()}'); continue
        for target in LINK.findall(path.read_text(encoding='utf-8')):
            target = unquote(target.strip('<>').split('#', 1)[0])
            if not target or re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:', target):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.is_relative_to(root) or not resolved.exists():
                errors.append(f'Broken local link: {path.relative_to(root).as_posix()} -> {target}')
    # Inspect tracked + unignored additions only. Git-ignored raw archives remain external.
    result = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=root, capture_output=True, check=True)
    files = set(p for p in result.stdout.decode('utf-8').split('\0') if p)
    for relative in sorted(files):
        path = root / relative
        if not path.is_file():
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            errors.append(f'Symlink/outside path: {relative}'); continue
        if path.stat().st_size > LIMIT:
            errors.append(f'Over 20 MiB: {relative}')
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in {'.lic', '.pem', '.key', '.str', '.zip', '.pfx', '.p12'} or path.name.startswith('.env.'):
            errors.append(f'Private/large artifact filename: {relative}')
    return dict(scope='STATIC_ONLY; no simulator execution, numerical or physical validation',
                checked_members=len(members), checked_runs=len(runs), checked_documents=len(docs), checked_files=len(files), errors=errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    report = check()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(bool(report['errors']))


if __name__ == '__main__':
    main()
