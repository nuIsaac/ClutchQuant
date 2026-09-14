"""Offline configuration contract; requires PyYAML (CI installs it explicitly)."""
from pathlib import Path
import yaml

root = Path(__file__).resolve().parents[1]
workflow = yaml.safe_load((root / '.github/workflows/prospective-demo.yml').read_text())
events = workflow.get('on', workflow.get(True))  # PyYAML's YAML 1.1 boolean spelling
assert events['schedule'] == [{'cron': '17 */3 * * *'}]
assert 'pull_request' not in events
assert workflow['concurrency']['cancel-in-progress'] is False
job = workflow['jobs']['collect']
assert job['timeout-minutes'] == 6
assert job['if'] == "vars.FREE_DEMO_ENABLED == 'true'"
step = job['steps'][-1]
assert step['run'] == 'python -u -m app.pipeline --once --demo-cycle --pages 1'
assert 'secrets.DEMO_DATABASE_URL' in step['env']['DATABASE_URL']
service, = yaml.safe_load((root / 'render.yaml').read_text())['services']
assert service['plan'] == 'free' and service['runtime'] == 'docker'
assert service['healthCheckPath'] == '/api/v1/ready'
assert (root / service['dockerfilePath']).is_file()
env = {item['key']: item for item in service['envVars']}
assert env['ARTIFACT_READ_ONLY']['value'] == 'true'
assert env['DATABASE_URL']['sync'] is False
assert env['SUPABASE_SERVICE_ROLE_KEY']['sync'] is False
assert 'HUMAN_FORECAST_TOKEN' not in env
print('Demo configuration checks passed')
