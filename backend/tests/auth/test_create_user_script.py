"""scripts/create_user.py, run as a process against a scratch database."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select

from agent_debugger_api.auth.security import KEY_PREFIX, hash_key, verify_password
from agent_debugger_api.db.models import User
from agent_debugger_api.ingest.settings import DEFAULT_PROJECT_ID
from tests.postgres.harness import PostgresTestCase

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "create_user.py"
PASSWORD = "correct horse battery"


class CreateUserScriptTests(PostgresTestCase):
    def run_script(self, *args, password=PASSWORD, database_url=None):
        env = {**os.environ, "DATABASE_URL": database_url or self.database_url, "PYTHONIOENCODING": "utf-8"}
        env.pop("CREATE_USER_PASSWORD", None)
        if password is not None:
            env["CREATE_USER_PASSWORD"] = password
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *args], capture_output=True, text=True, check=False,
                              env=env, stdin=subprocess.DEVNULL, timeout=120)

    def users(self):
        return self.run_db(lambda s: s.scalars(select(User))).all()

    def test_creates_a_user_and_prints_only_the_key_on_stdout(self):
        result = self.run_script("--email", " Ada@Example.com", "--name", "Ada")
        self.assertEqual(result.returncode, 0, result.stderr)
        api_key = result.stdout.strip()
        self.assertEqual(result.stdout, api_key + "\n")
        self.assertTrue(api_key.startswith(KEY_PREFIX))
        self.assertNotIn(api_key, result.stderr)
        self.assertNotIn(PASSWORD, result.stdout + result.stderr)
        [user] = self.users()
        self.assertEqual((user.email, user.name, user.project_id), ("ada@example.com", "Ada", DEFAULT_PROJECT_ID))
        self.assertEqual(user.key_hash, hash_key(api_key))
        self.assertTrue(verify_password(PASSWORD, user.password_hash))

    def test_existing_email_is_exit_1_and_prints_no_key(self):
        self.assertEqual(self.run_script("--email", "ada@example.com", "--name", "Ada").returncode, 0)
        result = self.run_script("--email", "ADA@example.com", "--name", "Other")
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertEqual(len(self.users()), 1)

    def test_invalid_input_is_exit_2_without_echoing_it(self):
        for label, args, password in (("short password", ("--email", "ada@example.com", "--name", "Ada"), "short12"),
                                      ("bad email", ("--email", "not-an-email", "--name", "Ada"), PASSWORD),
                                      ("empty name", ("--email", "ada@example.com", "--name", " "), PASSWORD)):
            with self.subTest(label):
                result = self.run_script(*args, password=password)
                self.assertEqual((result.returncode, result.stdout), (2, ""))
                self.assertNotIn(password, result.stderr)
        self.assertEqual(self.users(), [])

    def test_unmigrated_database_is_exit_3(self):
        url = self.database_url.rsplit("/", 1)[0] + "/postgres"  # the server's maintenance database: no users table
        result = self.run_script("--email", "ada@example.com", "--name", "Ada", database_url=url)
        self.assertEqual((result.returncode, result.stdout), (3, ""), result.stderr)
