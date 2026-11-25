"""Apply/re-read explicitly authorized collaboration settings using existing Git auth.

Never prints or stores credentials. No invitations without exact user-supplied IDs.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'python/automation'))
from rendezvous_publish import REPO, api, publish
import control


def snapshot():
    base = '/repos/'+REPO
    repo = api(base)
    report = dict(checked_utc=datetime.now(timezone.utc).isoformat(), repository=REPO,
                  repository_settings={k: repo.get(k) for k in ['visibility', 'private', 'default_branch', 'has_issues', 'allow_update_branch', 'delete_branch_on_merge', 'allow_squash_merge']},
                  collaborators=[dict(login=p['login'], permissions=p['permissions']) for p in api(base+'/collaborators')],
                  invitations=[dict(login=p['invitee']['login'], permissions=p['permissions']) for p in api(base+'/invitations')],
                  member_invitations='DEFERRED: exact GitHub IDs not yet supplied')
    try:
        value = api(base+'/branches/main/protection')
        report['main_protection'] = {k: value.get(k) for k in ['required_pull_request_reviews', 'enforce_admins', 'allow_force_pushes', 'allow_deletions', 'required_conversation_resolution']}
    except urllib.error.HTTPError as exc:
        report['main_protection'] = dict(http_error=exc.code)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply-public', action='store_true')
    parser.add_argument('--apply-protection', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError('Use a fresh report path')
    base = '/repos/'+REPO
    if args.apply_public:
        runtime = control.current(None)
        settings = json.loads((runtime/'route_settings.json').read_text())
        if settings.get('allow_public_discovery') is not True:
            raise RuntimeError('Prepare and validate public-compatible transport first')
        api(base, dict(visibility='public', has_issues=True, allow_update_branch=True, delete_branch_on_merge=False), 'PATCH')
        session = json.loads((runtime/'session.json').read_text())
        published = publish(session['base_url'], settings['mac_key'], allow_public=True)
    if args.apply_protection:
        api(base+'/branches/main/protection', dict(required_status_checks=None, enforce_admins=False,
            required_pull_request_reviews=dict(dismiss_stale_reviews=True, require_code_owner_reviews=True, required_approving_review_count=1),
            restrictions=None, required_linear_history=False, allow_force_pushes=False,
            allow_deletions=False, required_conversation_resolution=True), 'PUT')
    report = snapshot()
    if args.apply_public:
        report['signed_manifest_published_after_public_transition'] = published
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
