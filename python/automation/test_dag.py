import json
from pathlib import Path
import tempfile
import unittest
from dag_scheduler import run_plan,validate


def task(name,seconds=0,after=None,exitcode=0):
    return dict(id=name,after=after or [],timeout_seconds=5,
                command=['{python}','-c','import time,sys;time.sleep(%s);sys.exit(%s)'%(seconds,exitcode)])


class Scheduler(unittest.TestCase):
    def test_successor_starts_before_other_roots_finish_with_three_slots(self):
        plan=dict(max_parallel=3,tasks=[task('A',.02),task('B',1.5),task('C',1.5),task('A2',.02,['A'])])
        with tempfile.TemporaryDirectory() as tmp:
            s=run_plan(plan,tmp,Path(tmp)/'out',10)
        self.assertTrue(all(v['status']=='SUCCEEDED' for v in s.values()))
        self.assertLess(s['A2']['started'],min(s['B']['finished'],s['C']['finished']))
        events=sorted([(v['started'],1) for v in s.values()]+[(v['finished'],-1) for v in s.values()])
        count=0
        for _,change in events:
            count+=change;self.assertLessEqual(count,3)

    def test_validation_failure_blocks_only_dependents(self):
        a=task('A');a['checks']=[['{python}','-c','raise SystemExit(2)']]
        with tempfile.TemporaryDirectory() as tmp:
            s=run_plan(dict(max_parallel=3,tasks=[a,task('A2',after=['A']),task('B')]),tmp,Path(tmp)/'out',10)
        self.assertEqual(s['A']['status'],'FAILED');self.assertEqual(s['A2']['status'],'BLOCKED');self.assertEqual(s['B']['status'],'SUCCEEDED')

    def test_cycle_rejected_before_execution(self):
        with self.assertRaises(ValueError):validate(dict(tasks=[task('A',after=['B']),task('B',after=['A'])]))

    def test_unlimited_tasks_and_budget(self):
        a=task('A',.02);a['timeout_seconds']=None
        b=task('B',.02,['A']);b.pop('timeout_seconds')
        with tempfile.TemporaryDirectory() as tmp:
            s=run_plan(dict(max_parallel=3,tasks=[a,b]),tmp,Path(tmp)/'out')
        self.assertTrue(all(v['status']=='SUCCEEDED' and not v['timeout'] for v in s.values()))

    def test_explicit_timeout_is_still_enforced(self):
        a=task('A',1);a['timeout_seconds']=.05
        with tempfile.TemporaryDirectory() as tmp:
            s=run_plan(dict(tasks=[a,task('B',after=['A'])]),tmp,Path(tmp)/'out')
        self.assertEqual(s['A']['status'],'TIMED_OUT');self.assertEqual(s['B']['status'],'BLOCKED')


if __name__=='__main__':unittest.main()
