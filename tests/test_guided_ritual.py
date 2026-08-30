import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "backend" / "static" / "index.html"
GUIDED_CSS = ROOT / "backend" / "static" / "aui" / "guided-ritual.css"
GUIDED_JS = ROOT / "backend" / "static" / "aui" / "guided-ritual.js"


class GuidedRitualContractTests(unittest.TestCase):
    def test_selected_home_direction_is_packaged_and_loaded(self):
        html = INDEX.read_text(encoding="utf-8")
        self.assertIn('/static/aui/guided-ritual.css', html)
        self.assertIn('/static/aui/guided-ritual.js', html)
        self.assertTrue(GUIDED_CSS.exists())
        self.assertTrue(GUIDED_JS.exists())

    def test_home_has_a_plain_language_primary_path_without_redundant_guided_copy(self):
        html = INDEX.read_text(encoding="utf-8")
        for marker in (
            'id="route-input"',
            'id="route-btn">Begin',
            'class="guided-route-context"',
            'Local by default',
            'Asks before external access',
        ):
            self.assertIn(marker, html)
        self.assertNotIn('id="guided-context-title"', html)
        self.assertNotIn('While this runs', html)
        self.assertNotIn('id="guided-plan-title"', html)
        self.assertNotIn('id="guided-welcome-title"', html)
        self.assertNotIn('What would you like OBus to do?', html)

    def test_advanced_capabilities_remain_discoverable(self):
        html = INDEX.read_text(encoding="utf-8")
        for marker in (
            'class="guided-advanced-nav"',
            'class="guided-advanced-options"',
            'class="guided-rail-advanced"',
            'class="guided-dashboard-advanced"',
            'id="shell-panel"',
            'id="harness-panel"',
            'id="harness-autopicker"',
            'id="provider-connection"',
            'id="workspace-context"',
        ):
            self.assertIn(marker, html)

    def test_primary_pages_use_beginner_friendly_language(self):
        html = INDEX.read_text(encoding="utf-8")
        for marker in (
            '<h2>Tasks</h2>',
            'Create a task plan',
            'Create plan</button>',
            '<h2>Workspace</h2>',
            'id="guided-workspace-mount"',
            '<h2>Memory</h2>',
            'Connections and sync <span>Advanced</span>',
            '<h2>Settings</h2>',
            'aria-label="Interface level"',
            '<option value="terminal">Simple</option>',
            'Maximum parallel helpers',
        ):
            self.assertIn(marker, html)

    def test_guided_layout_keeps_accessibility_and_responsive_contracts(self):
        css = GUIDED_CSS.read_text(encoding="utf-8")
        script = GUIDED_JS.read_text(encoding="utf-8")
        for marker in (
            ':focus-visible',
            'min-height: 42px',
            '@media (max-width: 960px)',
            '@media (prefers-reduced-motion: reduce)',
        ):
            self.assertIn(marker, css)
        self.assertIn("header = one('#home-status-header')", script)
        self.assertIn("header.setAttribute('aria-hidden', String(!isHome))", script)
        self.assertIn("header.hidden = !isHome", script)
        self.assertNotIn('header.hidden = true', script)
        self.assertIn('#home-status-header[hidden]', css)
        self.assertIn('display: none !important', css)
        self.assertIn("dashboard: 'Home'", script)
        self.assertIn("data-guided-workspace", INDEX.read_text(encoding="utf-8"))

    def test_home_places_voice_inside_agent_context_and_providers_offer_safe_auto_aid(self):
        html = INDEX.read_text(encoding="utf-8")
        visuals = (ROOT / "backend" / "static" / "aui" / "agent-visuals.js").read_text(encoding="utf-8")
        self.assertIn('id="voice-toggle" data-route-voice', html)
        self.assertIn('id="harness-task-voice" data-route-voice data-route-voice-target="harness-task-objective"', html)
        self.assertIn("Transcript added — review it, then choose Begin.", html)
        self.assertIn("Transcript added — review it, then choose Quick Start or Run guarded task.", html)
        self.assertIn('id="provider-auto-aid"', html)
        self.assertIn("Auto-aid checks only the local Ollama route", html)
        self.assertIn('meta.kind === "route" && index === 0', visuals)

    def test_dynamic_harness_cards_keep_persona_art_and_autopicker(self):
        html = INDEX.read_text(encoding="utf-8")

        self.assertIn('id="harness-autopicker"', html)
        self.assertIn('class="harness-card-art"', html)
        self.assertIn('src="${escapeHtml(card.image)}"', html)
        self.assertIn("function enableHarnessAutopicker()", html)
        self.assertIn("no model pairing is permanent", html)

    def test_idle_activity_is_concise_until_a_task_starts(self):
        html = INDEX.read_text(encoding="utf-8")
        css = GUIDED_CSS.read_text(encoding="utf-8")
        script = GUIDED_JS.read_text(encoding="utf-8")
        self.assertIn('id="guided-idle-activity"', html)
        self.assertIn('No task running', html)
        self.assertIn('data-guided-route-state="idle"', css)
        self.assertIn('syncRouteState', script)

    def test_home_places_the_next_route_composer_after_agent_activity(self):
        html = INDEX.read_text(encoding="utf-8")
        css = GUIDED_CSS.read_text(encoding="utf-8")
        self.assertIn('id="route-command-panel"', html)
        self.assertIn('.terminal-stack > #route-output-panel { order: 1; }', css)
        self.assertIn('.terminal-stack > #route-command-panel { order: 2; }', css)

    def test_home_uses_the_autonomous_monitor_for_live_task_status(self):
        script = GUIDED_JS.read_text(encoding="utf-8")
        html = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="home-autonomous-monitor"', html)
        self.assertIn('id="home-autonomous-state"', html)
        self.assertIn('id="home-autonomous-review"', html)
        self.assertIn('id="home-autonomous-events"', html)
        self.assertIn('function openHomeAutonomousChangeReview()', html)
        self.assertIn('checkpoint-bound, read-only workspace change review', html)
        self.assertNotIn('syncContext', script)


if __name__ == "__main__":
    unittest.main(verbosity=2)
