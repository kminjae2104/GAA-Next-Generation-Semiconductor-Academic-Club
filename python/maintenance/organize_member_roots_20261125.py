"""Move member spaces to repository roots, with checked destinations and no overwrite."""
from datetime import datetime, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEMBERS = ['곽민재', '권도현', '윤석영', '박선우', '진']


def write(path, text):
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(text)


def main():
    legacy = ROOT / '연구/팀원실험'
    index = ROOT / 'md/협업/팀원공간.md'
    moves = [(legacy / 'README.md', index)]
    for name in MEMBERS:
        source, destination = legacy / name, ROOT / name
        if not source.is_dir() or destination.exists():
            raise RuntimeError(f'Missing source or existing member destination: {name}')
        moves.append((source, destination))
    # Validate resolved targets before any move. No recursive deletion is used.
    for source, destination in moves:
        if not source.resolve().is_relative_to(ROOT) or not destination.resolve().is_relative_to(ROOT):
            raise ValueError('Move escapes workspace')
        if not source.exists() or destination.exists():
            raise FileExistsError('Refusing missing source / existing destination')
    for source, destination in moves:
        source.rename(destination)
    for name in MEMBERS:
        owner = ROOT / name
        descriptions = {
            '문헌': '문헌의 서지정보·링크·읽기 기록·주장과 근거를 정리한다. 저작권이 있는 논문 전체 파일이나 상용 자료를 임의로 공개하지 않는다. 공통 출처는 [공통 문헌](../../문헌/README.md)을 참고한다.',
            '연구': '주제/실행ID/ 아래에 사전계획·덱·로그·검증·분석을 보존한다. 공통 기준 연구는 [공통 연구](../../연구/README.md)에 있다. 새 실험은 저장소 루트에서 생성 도구를 실행한다.',
            'md': '실험 하나에 속하지 않는 개인 연구 노트·계획·설명을 둔다. 개별 실행 문서는 ../연구/주제/실행ID/md/에 둔다.',
            'python': '여러 개인 연구에서 함께 쓰는 Python 도구를 둔다. 개별 실행 분석 코드는 ../연구/주제/실행ID/python/에 둔다.',
            '검증': '여러 개인 연구에 걸친 검증 기록을 둔다. 개별 실행 원시 로그와 검증은 ../연구/주제/실행ID/검증/에 둔다. 실제 출력과 정적/합성 검증을 구별한다.',
            '그림': '여러 개인 연구에서 함께 쓰는 그림을 둔다. 개별 실행 그림은 ../연구/주제/실행ID/그림/에 두고 원시 근거와 연결한다.',
        }
        # If topics existed in the old member folder, preserve them below 연구/.
        old_topics = [p for p in owner.iterdir() if p.name != 'README.md']
        for folder, description in descriptions.items():
            (owner / folder).mkdir(exist_ok=False)
            write(owner / folder / 'README.md', f'# {name} · {folder}\n\n{description}\n\n[개인 공간](../README.md) · [팀원 안내](../../md/협업/README.md)\n')
        for topic in old_topics:
            target = owner / '연구' / topic.name
            if target.exists():
                raise FileExistsError('Refusing an existing research topic')
            topic.rename(target)
        write(owner / 'README.md', f'# {name}의 연구 공간\n\n'
              '저장소 최상위의 개인 공간이다. 이름과 GitHub 계정·접근 권한은 별개다.\n\n'
              '| 폴더 | 내용 |\n| --- | --- |\n'
              '| [문헌](문헌/README.md) | 출처·읽기 기록 |\n'
              '| [연구](연구/README.md) | 주제/실행ID별 실험과 결과 |\n'
              '| [md](md/README.md) | 개인 연구 노트·계획 |\n'
              '| [python](python/README.md) | 개인 공통 도구 |\n'
              '| [검증](검증/README.md) | 개인 공통 검증 기록 |\n'
              '| [그림](그림/README.md) | 개인 공통 그림 |\n\n'
              '각 실행의 덱은 `연구/주제/실행ID/tcad/`, 로그는 `연구/주제/실행ID/검증/raw/`에 둔다. '
              '수정·재실행은 새 ID로 보존한다. 이 폴더를 만든 것만으로 계산을 수행한 것은 아니다.\n\n'
              '[시작 안내](../md/협업/README.md) · [공유 규칙](../md/협업/실험공유규칙.md) · [팀원명단](../md/협업/팀원명단.md)\n')
    # The old parent contains no remaining files. rmdir refuses nonempty directories.
    legacy.rmdir()
    documents = [ROOT/'README.md', ROOT/'AGENTS.md', ROOT/'md/양식/실험/README.md']
    documents.extend((ROOT/'md/협업').glob('*.md'))
    for path in documents:
        if path == index:
            continue
        content = path.read_text(encoding='utf-8')
        for name in MEMBERS:
            content = content.replace(f'연구/팀원실험/{name}/README.md', f'{name}/README.md')
            content = content.replace(f'연구/팀원실험/{name}', f'{name}/연구')
        content = content.replace('연구/팀원실험/README.md', 'md/협업/팀원공간.md')
        content = content.replace('연구/팀원실험/<이름>/<주제>/<실행ID>/', '<이름>/연구/<주제>/<실행ID>/')
        content = content.replace('연구/팀원실험/이름/주제/실행ID/', '이름/연구/주제/실행ID/')
        if path.name == '실험공유규칙.md':
            content = content.replace('이름은 [팀원명단]', '최상위 이름 폴더 아래의 연구 공간을 사용한다. 문헌 읽기 기록은 `이름/문헌/`에 둔다. 이름은 [팀원명단]')
            content = content.replace('[팀원실험 색인]', '[팀원 공간 색인]')
        if path == ROOT/'AGENTS.md':
            content = content.replace('- 팀원의 새 실험은', '- 팀원 이름 폴더는 저장소 최상위에 두고 그 아래에 `문헌/`, `연구/`, `md/`, `python/`, `검증/`, `그림/`을 둔다. 팀원의 새 실험은')
        if path == ROOT/'README.md':
            start = content.index('```text\n')
            end = content.index('```', start+8)+3
            tree = '''```text
곽민재/                      최상위 개인 공간
  문헌/                      문헌 출처·읽기 기록
  연구/주제/실행ID/          각 실행의 md/·tcad/·python/·검증/·그림/
  md/                        개인 공통 문서
  python/                    개인 공통 분석 도구
  검증/                      개인 공통 검증 기록
  그림/                      개인 공통 그림
권도현/                      위와 동일한 개인 구조
윤석영/                      위와 동일한 개인 구조
박선우/                      위와 동일한 개인 구조
진/                          위와 동일한 개인 구조
md/                          공통 협업 안내·양식·운영·연구계획·발표자료
python/                      공통 생성·검사·원격 자동화 도구
연구/                        기존 공통 기준 소자·후속 연구
문헌/                        공통 출처
검증/                        기존 공통 연구·운영 검증 자료
그림/                        공통 그림
.github/                     PR·Issue 양식, 검토 담당자
.local/                      Git 제외: 로컬 회수·임시 상태
README.md / AGENTS.md         팀 입구 / 작업 규칙
```'''
            content = content[:start]+tree+content[end:]
            content = content.replace('새 팀 실험은 이름/주제/실행 ID로 분리했다.', '팀원 폴더를 저장소 최상위로 옮겼다. 개인 문헌은 `이름/문헌/`, 새 실험은 `이름/연구/주제/실행ID/`에 둔다.')
        write(path, content)
    write(index, '# 최상위 팀원 공간\n\n'
          '각 팀원 이름 폴더가 저장소 최상위에 있다. 그 아래 문헌/·연구/·md/·python/·검증/·그림/을 사용한다. '
          '공통 기준 연구와 원격 자동화는 기존 공용 경로에 유지했다.\n\n'
          '| 팀원 | 개인 공간 | 문헌 | 연구 |\n| --- | --- | --- | --- |\n'+
          ''.join(f'| {name} | [{name}](../../{name}/README.md) | [문헌](../../{name}/문헌/README.md) | [연구](../../{name}/연구/README.md) |\n' for name in MEMBERS)+
          '\n새 실험 경로: `이름/연구/주제/실행ID/`. 각 실행은 md/·tcad/·python/·검증/·그림/으로 나눈다. '
          '개인 문헌 읽기 기록은 이름/문헌/에 추가한다.\n\n'
          '[시작 안내](README.md) · [공유 규칙](실험공유규칙.md) · [빈 양식](../양식/실험/README.md)\n')
    for relative in ['연구/README.md', '연구/01_GAA_IdVg/README.md', '연구/02_치수변화/README.md']:
        path = ROOT/relative
        content = path.read_text(encoding='utf-8')
        content = content.replace('../팀원실험/README.md', '../../md/협업/팀원공간.md')
        content = content.replace('팀원실험/README.md', '../md/협업/팀원공간.md')
        content = content.replace('[팀원실험]', '[최상위 팀원 공간]')
        write(path, content)
    report = dict(checked_utc=datetime.now(timezone.utc).isoformat(),
                  moved=[dict(source=str(a.relative_to(ROOT)), destination=str(b.relative_to(ROOT))) for a, b in moves],
                  member_subfolders=['문헌', '연구', 'md', 'python', '검증', '그림'],
                  experiment_path='<이름>/연구/<주제>/<실행ID>',
                  common_research_and_automation='UNCHANGED', tcad_execution='NOT_RUN')
    output = ROOT / '검증/협업체계_20261125/member_roots.json'
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print('Moved five member spaces to repository roots; common execution paths unchanged.')


if __name__ == '__main__':
    main()
