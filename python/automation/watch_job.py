"""Collect and summarize a job without desktop control or repeated model calls."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import sys
import time

import control
import relay


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def summarize(folder):
    status=json.loads((folder/'status.json').read_text())
    report=dict(status=status['status'],stages=[],physical_validation='NOT_VALIDATED')
    for stage in status.get('stages',[]):
        relevant=[s for s in stage.get('fatal_lines',[]) if 'transport error: no error' not in s.lower()]
        report['stages'].append(dict(stage=stage['stage'],returncode=stage['returncode'],
                timeout=stage['timeout'],seconds=stage['seconds'],missing=stage['missing'],
                errors=relevant[-5:]))
    execution=folder/'gaa'/'execution'
    if execution.is_dir():
        text=(execution/'solver.out').read_text(errors='replace') if (execution/'solver.out').is_file() else ''
        report['versions']=re.findall(r'(?:Version:|this is deckbuild version|devedit)\s+[^\n]{0,85}',text)[:5]
        report['mesh']=re.findall(r'Read [^\n]*(?:nodes|prisms)[^\n]*',text)[:4]
        report['equilibrium_file']=(execution/'equilibrium.str').is_file()
        report['normal_atlas_finish']=bool(re.search(r'ATLAS version[^\n]*finished',text,re.I))
        report['license_diagnostic']=any(s in text.lower() for s in ['can not get license','license server'])
        if (execution/'high_drain.dat').is_file():
            analysis=module('gaa_analyze',control.STUDY/'python'/'analyze.py')
            try:
                metrics,_=analysis.analyze(execution,.04)
                relay.write_json(folder/'metrics.json',metrics)
                report['engineering_targets']=metrics['engineering_targets']
                report['metrics_file']=str(folder/'metrics.json')
            except ValueError as error:report['analysis_error']=str(error)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime',type=Path,required=True);p.add_argument('--job',required=True)
    a=p.parse_args()
    if not relay.JOB.fullmatch(a.job):raise ValueError('Invalid job')
    runtime=a.runtime.resolve();output=runtime/('watch_'+a.job+'.json')
    relay.write_json(output,dict(status='WAITING_RESULT',job=a.job,ui_input_used=False))
    receipt=runtime/'results'/(a.job+'.receipt.json')
    while not receipt.exists():
        state=control.state(runtime)
        if state['session_status'] in ['STOPPED','EXPIRED']:
            relay.write_json(output,dict(status='SESSION_CLOSED_RESULT_UNVERIFIED',job=a.job));return 2
        time.sleep(10)
    folder=control.LOCAL/'collected'/a.job
    if not folder.exists():
        control.collect_archive(runtime/'results'/(a.job+'.zip'),json.loads(receipt.read_text()),folder)
    report=summarize(folder)
    report.update(job=a.job,collected=str(folder),ui_input_used=False,
                  checked_utc=datetime.now(timezone.utc).isoformat())
    relay.write_json(output,report)
    relay.write_json(runtime/'latest_summary.json',report)
    return 0


if __name__=='__main__':raise SystemExit(main())
