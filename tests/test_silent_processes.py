import subprocess
import unittest
from unittest import mock

from backend.process_utils import silent_process_kwargs


class SilentProcessTests(unittest.TestCase):
    def test_windows_processes_use_no_window_flags(self):
        with mock.patch("backend.process_utils.os.name", "nt"):
            options = silent_process_kwargs()

        self.assertTrue(options["creationflags"] & subprocess.CREATE_NO_WINDOW)
        self.assertEqual(options["startupinfo"].wShowWindow, subprocess.SW_HIDE)

    def test_non_windows_processes_keep_default_options(self):
        with mock.patch("backend.process_utils.os.name", "posix"):
            self.assertEqual(silent_process_kwargs(), {})


if __name__ == "__main__":
    unittest.main()
