"""Disposable offline simulation: no real Codex tasks or external operations."""
import importlib.util
import json
from pathlib import Path
import tempfile

path = Path(__file__).resolve().parents[1] / 'dev-continuity/scripts/continuity.py'
spec = importlib.util.spec_from_file_location('continuity_demo', path)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

with tempfile.TemporaryDirectory(prefix='continuity-demo-') as folder:
    root = Path(folder).resolve()
    source = root / 'request.txt'
    source.write_text('Synthetic request: preserve original data; complete the one-file review.\n', encoding='utf8')
    anchor = c.make_anchor(source, 0, source.stat().st_size)
    note = {
        'goal': 'Demonstrate recoverable development state with synthetic data.',
        'acceptance': ['Original source remains readable after a file change.'],
        'batch': {'id': 'demo', 'scope': 'One offline source-retention and handoff example.', 'done_when': 'Successor accepts and original source is verified.'},
        'progress': {'done': [], 'active': 'Retain original request', 'remaining': ['Simulate handoff']},
        'decisions': [], 'preserve': ['Never overwrite the original evidence.'],
        'operations': [], 'evidence': [], 'next': ['Verify retained source and simulate ownership transfer.'],
        'blockers': [], 'files': [], 'sources': [],
        'records': [{'id': 'request', 'kind': 'requirement', 'scope': 'demo',
                     'text': 'Preserve original data; complete the one-file review.',
                     'basis': 'user', 'state': 'confirmed', 'critical': True, 'sources': [anchor]}]
    }
    rev = c.save(root, 'demo', 'simulated-old', note, 'new', retain_sources=True)['revision']
    source.write_text('A later revision of the mutable file.\n', encoding='utf8')
    assert c.read_source(anchor, root).decode('utf8').startswith('Synthetic request:')
    check = c.verify(root, 'demo')
    rev = c.save(root, 'demo', 'simulated-old', {'memory_review': {
        'basis_sha256': check['memory_basis_sha256'], 'critical_ids': check['critical_ids']}}, rev, patch=True)['revision']
    for action in ('prepare', 'target', 'release', 'accept'):
        session = 'simulated-new' if action == 'accept' else 'simulated-old'
        result = c.transfer(root, 'demo', session, rev, action, successor='simulated-new' if action == 'target' else None)
        rev = result['revision']
    final = c.verify(root, 'demo', history=True)
    assert final['ok'] and final['history']['ok']
    state, _ = c.load(root, 'demo')
    assert state['owner'] == 'simulated-new' and state['handoff']['phase'] == 'ACCEPTED'
    print(json.dumps({'simulation': True, 'source_preserved': True, 'phase': state['handoff']['phase'], 'external_actions': 0}))
