"""Importing the app must not read database settings.

Postgres is only used by GET /health today. Building the engine at import time
made every import of agent_debugger_api.main require DATABASE_URL (or the root
.env), which broke CI for tests that never touch Postgres.
"""

import subprocess
import sys
import textwrap
import unittest

# Runs in a fresh interpreter so no module is already imported. get_settings is
# replaced before anything imports it; any call at import time fails the import.
IMPORT_WITHOUT_SETTINGS = textwrap.dedent(
    """
    import agent_debugger_api.config as config

    def fail():
        raise AssertionError("database settings were read at import time")

    config.get_settings = fail
    import agent_debugger_api.main
    """
)


class AppImportTests(unittest.TestCase):
    def test_importing_main_does_not_read_database_settings(self):
        result = subprocess.run(
            [sys.executable, "-B", "-c", IMPORT_WITHOUT_SETTINGS],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
