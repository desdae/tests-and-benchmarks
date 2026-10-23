import copy
import datetime as dt
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import benchmark as b


def fixture():
    """Synthetic schemas/prices solely for testing; not claims about API Mart."""
    config, prompts = b.load()
    config = copy.deepcopy(config)
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    api = config['api']
    for field in ['probe_success_pointer', 'token_balance_pointer', 'token_unlimited_pointer', 'usage_path']:
        api[field] = None
    api.update(verified_at=stamp, auth_probe_path='/v1/test-account',
               balance_path='/v1/test-account', balance_pointer='/available',
               balance_currency='USD', balance_semantics='available_usd', balance_divisor='1',
               submission_task_id_pointer='/data/0/task', task_status_pointer='/data/state',
               video_url_pointer='/data/output/0/url', actual_cost_pointer='/data/usd',
               actual_cost_currency='USD', statuses={'pending': ['working'], 'completed': ['ready'], 'failed': ['error']},
               evidence={'sources': ['https://docs.apimart.ai/test-fixture'],
                         **dict.fromkeys(['authentication', 'response_formats', 'read_only_probe', 'billing'], True)})
    for model in config['models']:
        model.update(verified_at=stamp, request_template={'model': model['model_id'], 'prompt': '{prompt}'},
                     estimate_usd='0.40', maximum_charge_usd='0.50', maximum_reservation_usd='0.50',
                     output_duration_upper_bound_seconds=10, evidence={
                         'sources': [model['documentation_url']],
                         **dict.fromkeys(['availability', 'parameters', 'native_audio', 'pricing', 'reservation_bound', 'duration_bound'], True)})
    return config, prompts


def prepare(root):
    (root / 'results').mkdir()
    (root / '.runtime').mkdir()
    (root / 'templates').mkdir()
    shutil.copy(b.ROOT / 'templates/comparison.html', root / 'templates/comparison.html')


class FakeClient:
    posts = 0
    calls = []

    def __init__(self, key):
        pass

    def request(self, method, path, payload=None):
        self.calls.append((method, path))
        if method == 'POST':
            type(self).posts += 1
            return {'data': [{'task': 'fixture-' + str(self.posts)}]}
        if path == '/v1/test-account':
            return {'available': '10.00'}
        return {'data': {'state': 'ready', 'usd': '0.4', 'output': [{'url': 'https://cdn.example.com/fixture.mp4'}]}}
