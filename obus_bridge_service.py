"""Windows Service wrapper for the autonomous OBus Hermes bridge."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import win32event
import win32service
import win32serviceutil

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class OBusHermesBridgeService(win32serviceutil.ServiceFramework):
    _svc_name_ = "OBusHermesBridge"
    _svc_display_name_ = "OBus Hermes Bridge"
    _svc_description_ = "Runs OBus autonomously and exposes its local route to Hermes as OBus."

    def __init__(self, args):
        super().__init__(args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcShutdown(self):
        self.SvcStop()

    def SvcDoRun(self):
        os.chdir(PROJECT_ROOT)
        os.environ.setdefault("OBUS_EXE", r"C:\Users\Hermes\OneDrive\OBus-MOA-Digital\OBus.exe")
        os.environ.setdefault("OBUS_URL", "http://127.0.0.1:38173")
        os.environ.setdefault("OBUS_BRIDGE_PORT", "38174")
        from obus_hermes_bridge import serve

        serve(stop_event=self.hWaitStop)


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(OBusHermesBridgeService)
