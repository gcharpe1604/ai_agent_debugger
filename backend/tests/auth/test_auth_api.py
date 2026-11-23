"""/api/v1/auth against a real PostgreSQL (scratch database, real migrations).

Tests marked [needs current_user] call GET /auth/me or POST /auth/key/rotate,
so they fail with NotImplementedError until auth/deps.py is written. The rest
check sessions by decoding the signed cookie, so they do not depend on it.
"""

import uuid
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from agent_debugger_api.api.routes import auth as auth_routes
from agent_debugger_api.auth.security import KEY_PREFIX, hash_key, verify_password
from agent_debugger_api.auth.settings import AuthSettings, get_auth_settings
from agent_debugger_api.db.deps import get_db
from agent_debugger_api.db.models import User
from agent_debugger_api.ingest.settings import DEFAULT_PROJECT_ID
from agent_debugger_api.main import app
from tests.auth.factories import session_cookie, session_data
from tests.postgres.harness import PostgresTestCase

REGISTER, LOGIN, LOGOUT, ME, ROTATE = (
    "/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/auth/me", "/api/v1/auth/key/rotate"
)
PASSWORD = "correct horse battery"


class AuthApiCase(PostgresTestCase):
    def setUp(self):
        super().setUp()
        sessions = self.sessions

        async def test_db():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_db] = test_db
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    def register(self, client=None, **body):
        body = {"name": "Ada Lovelace", "email": "ada@example.com", "password": PASSWORD, **body}
        return (client or self.client).post(REGISTER, json=body)

    def users(self) -> list[User]:
        async def work(session):
            return list(await session.scalars(select(User).order_by(User.created_at)))

        return self.run_db(work)

    def user_count(self) -> int:
        return self.run_db(lambda session: session.scalar(select(func.count()).select_from(User)))


class RegisterTests(AuthApiCase):
    def test_register_is_201_with_the_user_and_a_key_shown_once(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(set(body), {"user", "api_key"})
        self.assertEqual(set(body["user"]), {"id", "name", "email", "key_prefix"})
        [user] = self.users()
        self.assertEqual(body["user"], {"id": str(user.id), "name": "Ada Lovelace", "email": "ada@example.com",
                                        "key_prefix": body["api_key"][:12]})
        self.assertTrue(body["api_key"].startswith(KEY_PREFIX))

    def test_register_starts_a_session_for_the_new_user(self):
        response = self.register()
        [user] = self.users()
        self.assertEqual(session_data(response), {"user_id": str(user.id)})

    def test_session_cookie_attributes(self):
        cookie = session_cookie(self.register())
        self.assertEqual(cookie["max-age"], str(7 * 24 * 60 * 60))
        self.assertEqual(cookie["path"], "/")
        self.assertEqual(cookie["samesite"].lower(), "lax")
        self.assertTrue(cookie["httponly"])
        self.assertFalse(cookie["secure"])  # SESSION_COOKIE_SECURE defaults to false

    def test_only_hashes_are_stored(self):
        api_key = self.register().json()["api_key"]
        [user] = self.users()
        self.assertTrue(user.password_hash.startswith("$argon2id$"))
        self.assertTrue(verify_password(PASSWORD, user.password_hash))
        self.assertEqual(user.key_hash, hash_key(api_key))
        self.assertEqual(user.key_prefix, api_key[:12])
        for column in (user.email, user.name, user.password_hash, user.key_prefix, user.key_hash):
            self.assertNotIn(PASSWORD, column)
            self.assertNotIn(api_key, column)

    def test_first_user_gets_default_project_id_later_users_a_new_uuid4(self):
        self.register()
        self.register(TestClient(app), email="grace@example.com")
        self.register(TestClient(app), email="alan@example.com")
        first, second, third = (user.project_id for user in self.users())
        self.assertEqual(first, DEFAULT_PROJECT_ID)
        self.assertEqual(len({first, second, third}), 3)
        self.assertEqual((second.version, third.version), (4, 4))

    def test_project_id_collision_is_retried_once_with_a_new_uuid4(self):
        self.register()
        taken = self.users()[0].project_id
        fresh = uuid.uuid4()
        with mock.patch("agent_debugger_api.auth.users.uuid4", side_effect=[taken, fresh]):
            response = self.register(email="grace@example.com")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.users()[1].project_id, fresh)

    def test_email_is_stripped_and_lowercased_before_save(self):
        response = self.register(email="  Ada@Example.COM ")
        self.assertEqual(response.json()["user"]["email"], "ada@example.com")
        self.assertEqual(self.users()[0].email, "ada@example.com")

    def test_existing_email_is_409_in_any_case_and_creates_nothing(self):
        self.register()
        for email in ("ada@example.com", "ADA@example.com", " ada@example.com"):
            response = self.register(TestClient(app), email=email, name="Someone else")
            self.assertEqual((response.status_code, response.json()), (409, {"detail": "Email already registered"}), email)
            self.assertIsNone(session_cookie(response))
        self.assertEqual(self.user_count(), 1)

    def test_signup_disabled_is_403_and_creates_nothing(self):
        app.dependency_overrides[get_auth_settings] = lambda: AuthSettings(
            _env_file=None, session_secret="x", allow_signup=False
        )
        for body in ({}, {"password": "short"}):  # 403 even before the body is validated
            response = self.register(**body)
            self.assertEqual((response.status_code, response.json()), (403, {"detail": "Sign-up is disabled"}))
        self.assertEqual(self.user_count(), 0)

    def test_invalid_bodies_are_422_create_nothing_and_echo_no_values(self):
        long_name = "n" * 81
        cases = {
            "empty name": {"name": ""},
            "blank name": {"name": "   "},
            "81-character name": {"name": long_name},
            "no @": {"email": "ada.example.com"},
            "no dot in domain": {"email": "ada@example"},
            "space in email": {"email": "ada lovelace@example.com"},
            "7-character password": {"password": "s3cr3t!"},
        }
        for label, override in cases.items():
            with self.subTest(label):
                response = self.register(**override)
                self.assertEqual(response.status_code, 422)
                self.assertNotIn("input", response.text)
                for value in override.values():
                    if value.strip():
                        self.assertNotIn(value, response.text)
        for field in ("name", "email", "password"):
            with self.subTest(f"missing {field}"):
                body = {"name": "Ada", "email": "ada@example.com", "password": PASSWORD}
                del body[field]
                self.assertEqual(self.client.post(REGISTER, json=body).status_code, 422)
        self.assertEqual(self.user_count(), 0)

    def test_boundaries_80_character_name_and_8_character_password_are_accepted(self):
        response = self.register(name="n" * 80, password="8chars!!")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.users()[0].name, "n" * 80)

    def test_name_is_stripped(self):
        self.register(name="  Ada  ")
        self.assertEqual(self.users()[0].name, "Ada")


class LoginLogoutTests(AuthApiCase):
    def setUp(self):
        super().setUp()
        self.register()
        [self.user] = self.users()

    def login(self, email="ada@example.com", password=PASSWORD):
        return TestClient(app).post(LOGIN, json={"email": email, "password": password})

    def test_right_password_is_204_and_starts_a_session(self):
        response = self.login()
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(session_data(response), {"user_id": str(self.user.id)})

    def test_email_is_matched_after_strip_and_lowercase(self):
        self.assertEqual(self.login(email=" ADA@Example.com ").status_code, 204)

    def test_wrong_password_and_unknown_email_are_the_same_401(self):
        for label, response in (("wrong password", self.login(password=PASSWORD + "x")),
                                ("unknown email", self.login(email="nobody@example.com")),
                                ("empty", self.login(email="", password=""))):
            with self.subTest(label):
                self.assertEqual((response.status_code, response.json()), (401, {"detail": "Invalid email or password"}))
                self.assertIsNone(session_cookie(response))

    def test_unknown_email_is_still_checked_against_a_password_hash(self):
        with mock.patch.object(auth_routes, "verify_password", wraps=verify_password) as verify:
            self.login(email="nobody@example.com")
        verify.assert_called_once()
        password, password_hash = verify.call_args.args
        self.assertEqual(password, PASSWORD)
        self.assertTrue(password_hash.startswith("$argon2id$"))
        self.assertNotEqual(password_hash, self.user.password_hash)

    def test_logout_is_204_and_expires_the_session_cookie(self):
        client = TestClient(app)
        client.post(LOGIN, json={"email": "ada@example.com", "password": PASSWORD})
        response = client.post(LOGOUT)
        self.assertEqual(response.status_code, 204)
        cookie = session_cookie(response)
        self.assertIn("1970", cookie["expires"])

    def test_logout_without_a_session_is_204(self):
        self.assertEqual(TestClient(app).post(LOGOUT).status_code, 204)


class MeAndRotateTests(AuthApiCase):
    """[needs current_user]"""

    def setUp(self):
        super().setUp()
        self.api_key = self.register().json()["api_key"]
        [self.user] = self.users()

    def test_me_returns_the_session_user(self):
        response = self.client.get(ME)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": str(self.user.id), "name": "Ada Lovelace",
                                           "email": "ada@example.com", "key_prefix": self.api_key[:12]})

    def test_me_after_login_in_a_new_client(self):
        client = TestClient(app)
        client.post(LOGIN, json={"email": "ada@example.com", "password": PASSWORD})
        self.assertEqual(client.get(ME).json()["id"], str(self.user.id))

    def test_me_after_logout_is_401(self):
        self.client.post(LOGOUT)
        self.assertEqual(self.client.get(ME).status_code, 401)

    def test_rotate_returns_a_new_key_and_stores_only_its_hash(self):
        response = self.client.post(ROTATE)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {"api_key", "key_prefix"})
        self.assertTrue(body["api_key"].startswith(KEY_PREFIX))
        self.assertNotEqual(body["api_key"], self.api_key)
        self.assertEqual(body["key_prefix"], body["api_key"][:12])
        [user] = self.users()
        self.assertEqual((user.key_hash, user.key_prefix), (hash_key(body["api_key"]), body["key_prefix"]))
        self.assertEqual(user.project_id, self.user.project_id)  # same project, new key
        self.assertEqual(self.client.get(ME).json()["key_prefix"], body["key_prefix"])
