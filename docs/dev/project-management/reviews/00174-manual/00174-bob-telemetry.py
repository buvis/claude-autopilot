import json
from pathlib import Path
import sys
sys.path.insert(0, '/Users/bob/git/src/github.com/buvis/claude-autopilot/skills/run-autopilot')
from cli import render_report, statectl

task = {'id': '1', 'name': 'stale wider task', 'model': 'sonnet', 'status': 'in_progress', 'qwen_eligible': True}
state = {'tasks': [task], 'tasks_completed': 0}
entry = {'attempt': 1, 'model': 'sonnet', 'implementor': 'claude', 'outcome': 'completed', 'preflight_outcome': None, 'qwen_excluded_reason': 'files'}
statectl.do_task_done(state, '1', entry)
line = render_report._exclusion_line(state['tasks'])
assert line is None
print(json.dumps({'case': 'stale-runtime-files-exclusion', 'recorded_attempt': task['attempts'][0], 'exclusion_line': line}))

task2 = {'id': '2', 'name': 'Qwen no edit', 'model': 'haiku', 'status': 'in_progress', 'qwen_eligible': True}
state2 = {'tasks': [task2], 'tasks_completed': 0}
statectl.do_append_attempt(state2, '2', {'attempt': 1, 'model': 'haiku', 'implementor': 'qwen', 'cause': 'qwen_no_edit', 'outcome': 'escalated', 'preflight_outcome': 'healthy', 'qwen_gate_failed': True})
assert state2['tasks_completed'] == 0 and task2['status'] == 'in_progress'
statectl.do_task_done(state2, '2', {'attempt': 2, 'model': 'sonnet', 'implementor': 'claude', 'cause': None, 'outcome': 'completed', 'preflight_outcome': None, 'escalation_reason': 'gate_failure', 'escalated_from': 'qwen'})
assert state2['tasks_completed'] == 1 and len(task2['attempts']) == 2
assert 'escalated_from' not in task2['attempts'][0] and task2['attempts'][1]['escalated_from'] == 'qwen'
print(json.dumps({'case': 'two-rung-state-ownership', 'attempts': task2['attempts'], 'tasks_completed': state2['tasks_completed']}))
