"""Read-only Linux collector for the two explicitly scoped GAA workflows."""
from pathlib import Path
import argparse
import json
import os
import shutil
import time

JOBS = ['gaa_overnight_20261116T080149Z', 'gaa_autonomous_20261117T064609Z']
targets=Path(__file__).with_name('targets.json')
if targets.exists():
    import re
    extra=json.loads(targets.read_text())['jobs']
    if not all(re.fullmatch(r'gaa_continuation_[A-Za-z0-9_-]+',job) for job in extra):raise ValueError('Unsafe target')
    JOBS+=extra


def copy_small(src, dst, limit=1024*1024):
    if src.is_file() and not src.is_symlink() and src.stat().st_size <= limit:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-seconds')
    args = parser.parse_args()
    report = {'snapshot_epoch': time.time(), 'jobs': {}, 'read_only': True, 'simulators_started': 0}
    base = (Path.home() / 'gaa_tcad_runs').resolve()
    for job in JOBS:
        root = base / job / 'durable'
        if not root.is_dir():
            report['jobs'][job] = {'exists': False}
            continue
        dest = args.output / job
        data = {'exists': True, 'files': {}, 'snapshot_epoch': time.time()}
        for name in ['launch.json', 'complete.json', 'results/progress.json', 'results/workflow_status.json', 'results/status.json', 'workflow.json']:
            p = root / name
            if p.is_file():
                data['files'][name] = json.loads(p.read_text())
                copy_small(p, dest / name)
        launch = data['files'].get('launch.json', {})
        pid = launch.get('scheduler_pid', launch.get('pid'))
        if pid:
            try:
                os.kill(pid, 0)
                data['recorded_pid_exists'] = True
            except ProcessLookupError:
                data['recorded_pid_exists'] = False
            proc = Path('/proc') / str(pid)
            if (proc / 'cmdline').is_file():
                data['pid_cmdline'] = (proc / 'cmdline').read_bytes().decode(errors='replace').replace('\0', ' ')
        data['scoped_live_processes'] = []
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit(): continue
            try:
                if proc.stat().st_uid != os.getuid(): continue
                cwd = (proc / 'cwd').resolve(strict=True)
                cwd.relative_to(root.parent.resolve())
                command = (proc / 'cmdline').read_bytes().decode(errors='replace').replace('\0', ' ')
                data['scoped_live_processes'].append({'pid':int(proc.name),'cwd':str(cwd),'cmdline':command})
            except (OSError, ValueError): continue
        for case in (root / 'results').iterdir():
            if not case.is_dir() or case.is_symlink():
                continue
            selected = case
            selection = case / 'selected_attempt.json'
            if selection.is_file():
                selected = (case / json.loads(selection.read_text())['directory']).resolve()
                selected.relative_to(case.resolve())
                copy_small(selection, dest / 'cases' / case.name / 'selected_attempt.json')
            cdest = dest / 'cases' / case.name
            for name in ['status.json', 'progress.json', 'run_config.json', 'validated_metrics.json', 'validation_failure.json', 'retained_structures.json']:
                copy_small(selected / name, cdest / name)
            copy_small(selected / 'gaa/process.json', cdest / 'process.json')
            copy_small(case / 'scheduler_console.txt', cdest / 'scheduler_console.txt', 256*1024)
            execution = selected / 'gaa/execution'
            if execution.is_dir():
                for p in execution.iterdir():
                    if p.suffix in ['.dat', '.log', '.in']:
                        copy_small(p, cdest / p.name)
                solver = execution / 'solver.out'
                copy_small(solver, cdest / 'solver.out', 1024*1024)
                if solver.is_file():
                    cdest.mkdir(parents=True, exist_ok=True)
                    with solver.open('rb') as stream:
                        stream.seek(max(0, solver.stat().st_size-16384))
                        (cdest / 'solver_tail.txt').write_bytes(stream.read())
        data['snapshot_end_epoch'] = time.time()
        report['jobs'][job] = data
    (args.output / 'presentation_snapshot.json').write_text(json.dumps(report, indent=2))
    (args.output / 'status.json').write_text(json.dumps({'status': 'READ_ONLY_SNAPSHOT', 'stages': [], 'physical_validation': 'NOT_VALIDATED'}))


if __name__ == '__main__':
    main()
