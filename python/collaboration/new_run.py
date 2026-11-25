"""Create an independent TCAD submission folder. Never runs a simulator."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
ASCII_COMPONENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z')
MEMBER_COMPONENT = re.compile(r'[\w-]{1,40}\Z', re.UNICODE)
RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}


def create_run(member, topic, run_id, root=ROOT):
    root = Path(root).resolve()
    for label, value, pattern in [('member', member, MEMBER_COMPONENT), ('topic', topic, ASCII_COMPONENT), ('run-id', run_id, ASCII_COMPONENT)]:
        if not pattern.fullmatch(value) or value.upper() in RESERVED:
            raise ValueError(f'Invalid {label}: use one safe folder name, no paths')
    workspace = root / '연구' / '팀원실험'
    owner = workspace / member
    if not (owner / 'README.md').is_file() or owner.is_symlink():
        raise ValueError('Register the member folder and README first; GitHub account is a separate setting')
    destination = owner / topic / run_id
    if not destination.resolve().is_relative_to(workspace.resolve()):
        raise ValueError('Destination escapes the team workspace')
    template = root / 'md' / '양식' / '실험'
    if not (template / 'README.md').is_file():
        raise FileNotFoundError('Experiment template is missing')
    # Exclusive creation rejects existing IDs, including an existing empty directory.
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copytree(template, destination, dirs_exist_ok=True)
    readme = destination / 'README.md'
    with readme.open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(f'# {member} / {topic} / {run_id}\n\n')
        stream.write(f'생성 시각: {datetime.now(timezone.utc).isoformat()} (UTC).\n\n')
        stream.write('계산: **NOT_RUN**. 수치 검사·메시·물리 검증: **NOT_VALIDATED**.\n\n')
        stream.write('목표를 먼저 기록하고 실제 실행 뒤 근거에 따라 상태를 갱신한다. 생성만으로 계산을 수행하지 않는다.\n\n')
        for title, path in [('사전계획', 'md/사전계획.md'), ('실행정보', 'md/실행정보.md'), ('결과요약', 'md/결과요약.md'), ('검증기록', '검증/검증기록.md'), ('원본목록', '검증/원본목록.md')]:
            stream.write(f'- [{title}]({path})\n')
        stream.write('\n입력 덱은 tcad/, 분석 코드는 python/, 원시 로그는 검증/raw/, 그림은 그림/에 보존한다.\n')
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--member', required=True)
    parser.add_argument('--topic', required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    try:
        destination = create_run(args.member, args.topic, args.run_id)
    except (ValueError, FileExistsError, FileNotFoundError) as exc:
        parser.exit(2, f'{type(exc).__name__}: {exc}\n')
    print(destination.relative_to(ROOT).as_posix())
    print('CREATED_ONLY: no TCAD execution or physical validation')


if __name__ == '__main__':
    main()
