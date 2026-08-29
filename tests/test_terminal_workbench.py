import unittest

from fastapi.testclient import TestClient

import backend.main as backend


class TerminalWorkbenchTests(unittest.TestCase):
    def test_terminal_workbench_has_blocks_history_and_safe_formatted_output(self):
        html = TestClient(backend.app).get("/").text
        for control_id in (
            "terminal-workbench",
            "terminal-block-list",
            "result-render-mode",
            "copy-latest-output",
            "bookmark-latest-output",
            "terminal-history-refresh",
            "shell-panel",
            "shell-output",
            "shell-input",
            "terminal-start",
            "terminal-open",
            "terminal-refresh",
            "terminal-session-tabs",
            "terminal-send",
            "terminal-interrupt",
            "terminal-stop",
            "runtime-running-count",
            "runtime-queued-count",
            "runtime-parallel-limit",
            "runtime-complete-count",
            "codex-bridge-panel",
            "codex-bridge-start",
            "codex-bridge-parallel",
            "codex-bridge-run",
            "codex-bridge-interrupt",
            "codex-bridge-recents",
            "codex-bridge-approvals",
            "codex-bridge-output",
        ):
            self.assertIn(f'id="{control_id}"', html)
        for symbol in (
            "function renderRouteBlocks",
            "function renderSafeMarkdown",
            "function copyLatestOutput",
            "function toggleRunBookmark",
            "Ctrl+Shift+P",
            "function startLocalTerminal",
            "function connectTerminalSocket",
            "function sendTerminalLine",
            "function initializeLocalTerminal",
            "function queueTerminalResize",
            "function renderTerminalSessionTabs",
            "function refreshTerminalSessions",
            "function terminalWorkspaceReady",
            "function activateTerminalSession",
            "function closeTerminalSession",
            "function openLocalTerminal",
            "function restoreLocalTerminalSession",
            "function reconnectTerminalSocket",
            "function startCodexBridgeThread",
            "function runCodexBridgeTurn",
            "function resumeCodexBridgeThread",
            "function interruptCodexBridgeTurn",
            "function decideCodexBridgeApproval",
            "function codexBridgeEventThreadId",
            "function codexBridgeWorkerPreview",
            "function applyCodexBridgeWorkerEvents",
            "Waiting for this worker’s own redacted activity",
            "TERMINAL_SESSION_STORAGE_KEY",
            "terminalMatchesCurrentWorkspace",
        ):
            self.assertIn(symbol, html)
        self.assertIn('/static/vendor/xterm/xterm.js', html)
        self.assertIn('/static/vendor/xterm/addon-fit.js', html)
        self.assertIn("OBus local shell", html)
        self.assertIn("Choose a workspace, then start the local shell", html)
        self.assertIn("Reconnecting…", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
