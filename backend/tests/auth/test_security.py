"""auth/security.py helpers and auth/settings.py. No database."""

import hashlib
import os
import subprocess
import sys
import textwrap
import unittest
from unittest import mock

from pydantic import ValidationError

from agent_debugger_api.auth.security import (
    KEY_PREFIX,
    hash_key,
    hash_password,
    new_key,
    verify_password,
)
from agent_debugger_api.auth.settings import AuthSettings


class PasswordTests(unittest.TestCase):
    def test_hash_is_argon2id_salted_and_not_the_password(self):
        first, second = hash_password("correct horse"), hash_password("correct horse")
        self.assertTrue(first.startswith("$argon2id$"))
        self.assertNotIn("correct horse", first)
        self.assertNotEqual(first, second)  # a new salt each time

    def test_verify_accepts_the_password_and_rejects_others(self):
        stored = hash_password("correct horse")
        self.assertIs(verify_password("correct horse", stored), True)
        for wrong in ("correct hors", "Correct horse", "", "correct horse "):
            self.assertIs(verify_password(wrong, stored), False, wrong)

    def test_verify_returns_false_for_a_malformed_hash_and_never_raises(self):
        for stored in ("", "not-a-hash", "$argon2id$v=19$m=65536,t=3,p=4$broken"):
            self.assertIs(verify_password("anything", stored), False, stored)


class ApiKeyTests(unittest.TestCase):
    def test_new_key_has_the_prefix_and_32_random_bytes(self):
        key, _, _ = new_key()
        self.assertEqual(KEY_PREFIX, "adbg_sk_")
        self.assertTrue(key.startswith(KEY_PREFIX))
        self.assertEqual(len(key), len(KEY_PREFIX) + 43)  # token_urlsafe(32): 43 base64url characters
        self.assertRegex(key[len(KEY_PREFIX):], r"\A[A-Za-z0-9_-]{43}\Z")

    def test_prefix_is_the_first_12_characters_and_hash_is_sha256_hex(self):
        key, prefix, key_hash = new_key()
        self.assertEqual(prefix, key[:12])
        self.assertEqual(key_hash, hashlib.sha256(key.encode()).hexdigest())
        self.assertEqual(key_hash, hash_key(key))
        self.assertRegex(key_hash, r"\A[0-9a-f]{64}\Z")

    def test_keys_are_unique(self):
        keys = {new_key()[0] for _ in range(1000)}
        self.assertEqual(len(keys), 1000)

    def test_hash_key_is_deterministic_and_case_sensitive(self):
        self.assertEqual(hash_key("adbg_sk_abc"), hash_key("adbg_sk_abc"))
        self.assertNotEqual(hash_key("adbg_sk_abc"), hash_key("adbg_sk_ABC"))


class AuthSettingsTests(unittest.TestCase):
    def settings(self, **env):
        with mock.patch.dict(os.environ, env):
            for name in ("SESSION_SECRET", "SESSION_COOKIE_SECURE", "ALLOW_SIGNUP"):
                if name not in env:
                    os.environ.pop(name, None)
            return AuthSettings(_env_file=None)

    def test_session_secret_is_required_and_not_empty(self):
        with self.assertRaises(ValidationError):
            self.settings()
        with self.assertRaises(ValidationError):
            self.settings(SESSION_SECRET="")

    def test_defaults_insecure_cookie_and_signup_allowed(self):
        settings = self.settings(SESSION_SECRET="s3cret")
        self.assertEqual(settings.session_secret.get_secret_value(), "s3cret")
        self.assertNotIn("s3cret", repr(settings))
        self.assertIs(settings.session_cookie_secure, False)
        self.assertIs(settings.allow_signup, True)

    def test_flags_are_read_from_the_environment(self):
        settings = self.settings(SESSION_SECRET="x", SESSION_COOKIE_SECURE="true", ALLOW_SIGNUP="false")
        self.assertIs(settings.session_cookie_secure, True)
        self.assertIs(settings.allow_signup, False)

    def test_app_does_not_start_without_session_secret(self):
        # Fresh interpreter, SESSION_SECRET unset and the repo .env ignored.
        script = textwrap.dedent(
            """
            from agent_debugger_api.auth.settings import AuthSettings
            AuthSettings.model_config["env_file"] = None
            import agent_debugger_api.main
            """
        )
        env = {k: v for k, v in os.environ.items() if k != "SESSION_SECRET"}
        result = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True, text=True, env=env,
                                timeout=60, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("session_secret", result.stderr)
