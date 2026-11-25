"""One-time, non-overwriting documentation organization for the team transition."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def create(path, text):
    destination = ROOT / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text)


def main():
    original = subprocess.check_output(['git', 'show', '9393c4c68067fd9c058aaf90c8635fa64d670d6b:README.md'], cwd=ROOT).decode('utf-8')
    def relink(match):
        target = match.group(2)
        if re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
            return match.group(0)
        return '['+match.group(1)+'](../'+target+')'
    archive = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', relink, original)
    create('md/기존README_20261125.md',
           '# 2026-11-25 전환 전 README 보관\n\n'
           '원본: 커밋 `9393c4c68067fd9c058aaf90c8635fa64d670d6b`의 README.md. '
           '본문은 보관하고 이동에 따른 상대 링크만 조정했다. 아래 명령은 저장소 루트 기준이며 상태·권한·기한 예시는 과거 기록이다. '
           '현재 [협업 안내](협업/README.md)와 [AGENTS.md](../AGENTS.md)를 우선한다.\n\n'+archive)
    for member in ['곽민재', '권도현', '윤석영', '박선우', '진']:
        create(f'연구/팀원실험/{member}/README.md',
               f'# {member}의 실험 공간\n\n'
               '새 실험은 이 폴더 아래 `주제/실행ID/`로 추가한다. 아직 이 협업 공간에는 실제 실행 결과를 등록하지 않았다. '
               '기존 연구 결과의 유무와는 별개다.\n\n'
               '[시작 안내](../../../md/협업/README.md) · '
               '[실험 공유 규칙](../../../md/협업/실험공유규칙.md) · '
               '[빈 양식](../../../md/양식/실험/README.md)\n\n'
               'GitHub 아이디와 쓰기 권한은 [팀원명단](../../../md/협업/팀원명단.md)에서 별도로 관리한다.\n')
    print('Created archived README and five member entry folders; existing TCAD/results unchanged.')


if __name__ == '__main__':
    main()
