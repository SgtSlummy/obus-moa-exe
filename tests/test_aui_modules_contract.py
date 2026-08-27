import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import backend.main as backend


class AUIModuleContractTests(unittest.TestCase):
    def test_html_loads_external_aui_modules(self):
        html = TestClient(backend.app).get("/").text
        self.assertIn('/static/aui/tokens.css', html)
        self.assertIn('/static/aui/route-events.js', html)
        self.assertIn('/static/aui/layout.js', html)
        self.assertIn('/static/aui/workspace.js', html)
        self.assertIn('/static/aui/runtime.js', html)
        self.assertIn('/static/aui/providers.js', html)
        self.assertIn('/static/aui/rooms.js', html)
        self.assertIn('/static/aui/plan.js', html)
        self.assertIn('/static/aui/memory.js', html)
        self.assertIn('/static/aui/codex-bridge-synthesis.js', html)
        self.assertIn('/static/aui/codex-bridge-events.js', html)
        self.assertIn('legacyRuntime', html)

    def test_external_aui_modules_are_served(self):
        client = TestClient(backend.app)
        css = client.get('/static/aui/tokens.css')
        js = client.get('/static/aui/route-events.js')
        layout = client.get('/static/aui/layout.js')
        workspace = client.get('/static/aui/workspace.js')
        runtime = client.get('/static/aui/runtime.js')
        visuals = client.get('/static/aui/agent-visuals.js')
        visual_css = client.get('/static/aui/agent-visuals.css')
        providers = client.get('/static/aui/providers.js')
        rooms = client.get('/static/aui/rooms.js')
        plan = client.get('/static/aui/plan.js')
        memory = client.get('/static/aui/memory.js')
        synthesis = client.get('/static/aui/codex-bridge-synthesis.js')
        bridge_events = client.get('/static/aui/codex-bridge-events.js')
        self.assertEqual(css.status_code, 200)
        self.assertEqual(js.status_code, 200)
        self.assertEqual(layout.status_code, 200)
        self.assertEqual(workspace.status_code, 200)
        self.assertEqual(runtime.status_code, 200)
        self.assertEqual(visuals.status_code, 200)
        self.assertEqual(visual_css.status_code, 200)
        self.assertEqual(providers.status_code, 200)
        self.assertEqual(rooms.status_code, 200)
        self.assertEqual(plan.status_code, 200)
        self.assertEqual(memory.status_code, 200)
        self.assertEqual(synthesis.status_code, 200)
        self.assertEqual(bridge_events.status_code, 200)
        self.assertIn('--aui-density-scale', css.text)
        self.assertIn('OBusRouteEvents', js.text)
        self.assertIn('OBusAuiLayout', layout.text)
        self.assertIn('OBusWorkspace', workspace.text)
        self.assertIn('OBusRuntime', runtime.text)
        self.assertIn('contextMeterMarkup', visuals.text)
        self.assertIn('sanitized prompt', visuals.text)
        self.assertIn('.agent-context-meter', visual_css.text)
        self.assertIn('OBusProviders', providers.text)
        self.assertIn('OBusRooms', rooms.text)
        self.assertIn('OBusPlan', plan.text)
        self.assertIn('OBusMemory', memory.text)
        self.assertIn('/api/codex-bridge/parallel/synthesize', synthesis.text)
        self.assertIn('Read-only synthesis', synthesis.text)
        self.assertIn('Start reviewed task', synthesis.text)
        self.assertIn('/promote', synthesis.text)
        self.assertIn('item/agentMessage/delta', bridge_events.text)
        self.assertIn('Approval required', bridge_events.text)

    def test_agent_jobs_expose_safe_autonomous_schedule_controls(self):
        client = TestClient(backend.app)
        html = client.get('/').text
        runtime = client.get('/static/aui/runtime.js').text
        for control_id in (
            'autonomy-job-name', 'autonomy-job-objective', 'autonomy-job-interval',
            'autonomy-job-provider', 'autonomy-job-workspace', 'autonomy-job-create',
            'autonomy-job-refresh', 'autonomy-job-list',
        ):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn('destructive and hardware-risk work must be started as a one-time local task', html)
        for marker in ('/api/harness/objectives', 'scheduleWorkspace', 'createSchedule', 'scheduleAction'):
            self.assertIn(marker, runtime)

    def test_agent_jobs_expose_guarded_task_queue_controls(self):
        client = TestClient(backend.app)
        html = client.get('/').text
        runtime = client.get('/static/aui/runtime.js').text
        for control_id in (
            'harness-task-objective', 'harness-task-provider', 'harness-task-attempts',
            'harness-task-priority', 'harness-task-workspace', 'harness-task-approval-status',
            'harness-task-submit', 'harness-task-refresh', 'harness-task-list', 'harness-task-detail',
            'harness-task-timeline', 'harness-task-timeline-status',
            'harness-task-voice',
            'harness-approval-count', 'harness-approval-list',
        ):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn('data-route-voice-target="harness-task-objective"', html)
        self.assertIn("routeVoiceTarget", html)
        for marker in ('/api/harness/tasks', '/api/harness/approvals', '/events/stream', 'EventSource', 'startTaskEventStream', 'launchTask', 'loadApprovals',
                       'decideApproval', 'approval_id', 'retainedDraftMatchesApproval', 'Approve & start',
                       'inspectTask', 'cancelTask', 'Task cancellation requested'):
            self.assertIn(marker, runtime)

    def test_agent_jobs_expose_read_only_task_change_review(self):
        client = TestClient(backend.app)
        html = client.get('/').text
        runtime = client.get('/static/aui/runtime.js').text
        for control_id in ('harness-task-change-summary', 'harness-task-changes-refresh', 'harness-task-change-list', 'harness-task-change-diff'):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn('Change review is read-only', html)
        for marker in ('/changes', 'loadTaskChanges', 'inspectTaskChange', 'bounded, redacted diff'):
            self.assertIn(marker, runtime)

    def test_plan_workbench_can_launch_its_reviewed_parallel_team(self):
        client = TestClient(backend.app)
        html = client.get('/').text
        plan = client.get('/static/aui/plan.js').text
        for control_id in ('plan-team-size', 'plan-execute'):
            self.assertIn(f'id="{control_id}"', html)
        for marker in ('/api/plan/execute', 'reviewedPlan', 'Launch parallel team', 'loadRuntime', 'selectTeamLedger'):
            self.assertIn(marker, plan)

    def test_runtime_exposes_redacted_parallel_team_results(self):
        client = TestClient(backend.app)
        html = client.get('/').text
        runtime = client.get('/static/aui/runtime.js').text
        for control_id in ('runtime-ledger-refresh', 'runtime-ledger-list', 'runtime-ledger-detail'):
            self.assertIn(f'id="{control_id}"', html)
        for marker in ('/api/runtime/task-ledgers', 'renderLedgers', 'inspectLedger', 'Redacted findings', 'private contexts + redacted evidence', 'Per-agent context'):
            self.assertIn(marker, runtime)

    def test_runtime_surfaces_explicit_safe_resume_without_auto_replay(self):
        runtime = TestClient(backend.app).get('/static/aui/runtime.js').text

        for marker in ('Resume safely', 'data-action="${resumable ? "resume" : "run"}"', 'button.dataset.action',
                       'interrupted', 'OBus never restarts interrupted work automatically'):
            self.assertIn(marker, runtime)

    def test_heritage_workbench_loads_last_with_offline_safe_phi_tokens(self):
        client = TestClient(backend.app)
        html = client.get('/').text
        heritage = client.get('/static/aui/heritage-workbench.css')

        self.assertIn('/static/aui/heritage-workbench.css', html)
        self.assertLess(html.index('</style>'), html.index('/static/aui/heritage-workbench.css'))
        self.assertEqual(heritage.status_code, 200)
        for marker in (
            '--phi: 1.61803398875',
            '--space-phi',
            '--ink:',
            '--parchment:',
            '--brass:',
            '--verdigris:',
            '--focus:',
            '--control-min: 40px',
            'grid-template-columns: minmax(0, 1.618fr) minmax(17rem, 1fr)',
            'resize: vertical',
        ):
            self.assertIn(marker, heritage.text)
        self.assertNotIn('@import url(', heritage.text)
        self.assertNotIn('https://fonts.', heritage.text)
        phone = heritage.text.replace('\r\n', '\n').split('@media (max-width: 720px)', 1)[1].split('@media', 1)[0]
        self.assertIn('display: block', phone)
        self.assertIn('grid-template-columns: minmax(0, 1fr)', phone)
        self.assertIn('overflow-x: visible', phone)
        self.assertNotIn('overflow-x: auto', phone)
        self.assertIn('.top {\n    display: grid', phone)
        self.assertIn('.top > .actions > *', phone)
        self.assertIn('animation: none', heritage.text.split('.key-shuffle-deck .shuffle-card {', 1)[1].split('}', 1)[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
