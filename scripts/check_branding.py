"""Reject undocumented legacy identifiers; preserve explicit compatibility surfaces."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"clutch[\s_-]?quant|\bcq[_-]", re.I)
# Each exemption is explained in docs/rebrand-compatibility.md. UI components
# deliberately have no exemption: legacy display branding must never return.
COMPATIBILITY = {
    'apps/api/app/legacy.py', 'apps/web/src/lib/legacy.ts',
    'apps/web/src/lib/watchlist.ts', 'apps/web/tests/watchlist.test.mjs',
    'apps/api/tests/test_postgres_contract.py',
    '.github/workflows/prospective-demo.yml',
    'compose.yaml', 'compose.production.yaml', 'render.yaml',
    'deploy/.env.example', 'deploy/.env.demo.example',
    'deploy/init-db.sh', 'deploy/supabase-demo.sql', 'deploy/smoke.py',
    'README.md', 'docs/deployment.md', 'docs/free-demo.md',
    'docs/rebrand-compatibility.md',
}
paths = subprocess.check_output(
    ['git', 'ls-files', '-co', '--exclude-standard'], cwd=ROOT, text=True
).splitlines()
failures = []
retained = 0
for name in sorted(set(paths)):
    path = ROOT / name
    if not path.is_file():
        continue
    try:
        lines = path.read_text().splitlines()
    except UnicodeError:
        continue
    for number, line in enumerate(lines, 1):
        if not PATTERN.search(line):
            continue
        if name in COMPATIBILITY or name.startswith(('docs/legacy/', 'apps/api/migrations/versions/')):
            retained += 1
        else:
            failures.append(f'{name}:{number}')
if failures:
    raise SystemExit('Undocumented legacy branding: ' + ', '.join(failures))
print(f'Branding check passed; {retained} documented compatibility/history lines retained.')
