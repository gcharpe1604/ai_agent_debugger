"""Who can write and read what: the real current_user / ingest_user against PostgreSQL.

Every test here needs auth/deps.py: until current_user and ingest_user are
written they fail with NotImplementedError. Users are registered through the
API; traces go to an in-memory publisher and are read from an in-memory store,
so no Kafka or ClickHouse is needed.
"""

from fastapi.testclient import TestClient
from sqlalchemy import select

from agent_debugger_api.api.routes.durable_runs import get_trace_store
from agent_debugger_api.api.routes.traces import get_span_publisher
from agent_debugger_api.contracts.fakes import InMemorySpanPublisher, InMemoryTraceStore
from agent_debugger_api.db.deps import get_db
from agent_debugger_api.db.models import User
from agent_debugger_api.ingest.settings import DEFAULT_PROJECT_ID
from agent_debugger_api.main import app
from tests.contracts.factories import make_span
from tests.postgres.harness import PostgresTestCase

TRACE = "c" * 32
ROOT = "a" * 16
TRACES = "/api/v1/traces"
RUNS = "/api/v1/projects/default/runs"


def batch(trace_id=TRACE) -> dict:
    span = {"trace_id": trace_id, "span_id": ROOT, "parent_span_id": None, "name": "run",
            "operation_type": "run", "start_time": 1, "end_time": 2, "status": {"code": "OK"}}
    return {"protocol_version": "1", "spans": [span]}


class AuthorizationTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        sessions = self.sessions

        async def test_db():
            async with sessions() as session:
                yield session

        self.store = InMemoryTraceStore()
        self.publisher = InMemorySpanPublisher()
        app.dependency_overrides[get_db] = test_db
        app.dependency_overrides[get_trace_store] = lambda: self.store
        app.dependency_overrides[get_span_publisher] = lambda: self.publisher
        self.addCleanup(app.dependency_overrides.clear)
        self.a, self.a_key, self.a_project = self.account("ada@example.com")
        self.b, self.b_key, self.b_project = self.account("grace@example.com")
        self.anonymous = TestClient(app)

    def account(self, email):
        client = TestClient(app)
        response = client.post("/api/v1/auth/register", json={"name": email.split("@")[0], "email": email,
                                                              "password": "correct horse battery"})
        self.assertEqual(response.status_code, 201)
        project = self.run_db(lambda s: s.scalar(select(User.project_id).where(User.email == email)))
        return client, response.json()["api_key"], project

    def ingest(self, key=None, headers=None):
        headers = headers if headers is not None else {"Authorization": f"Bearer {key}"}
        return self.anonymous.post(TRACES, json=batch(), headers=headers)

    def published_projects(self):
        return [record.project_id for _, record in self.publisher.acked]

    # --- logged out -----------------------------------------------------------

    def test_logged_out_reads_are_401(self):
        for path in ("/api/v1/auth/me", "/api/v1/projects", RUNS, f"{RUNS}/{TRACE}", f"{RUNS}/{TRACE}/spans/{ROOT}",
                     "/api/v1/projects/other/runs"):
            self.assertEqual(self.anonymous.get(path).status_code, 401, path)
        self.assertEqual(self.anonymous.post("/api/v1/auth/key/rotate").status_code, 401)

    def test_ingest_without_a_valid_key_is_401_and_publishes_nothing(self):
        cases = {
            "no header": {},
            "unknown key": {"Authorization": "Bearer adbg_sk_" + "x" * 43},
            "empty bearer": {"Authorization": "Bearer "},
            "other scheme": {"Authorization": f"Basic {self.a_key}"},
            "key without scheme": {"Authorization": self.a_key},
        }
        for label, headers in cases.items():
            self.assertEqual(self.ingest(headers=headers).status_code, 401, label)
        self.assertEqual(self.published_projects(), [])

    # --- writes ---------------------------------------------------------------

    def test_key_writes_into_its_owners_project(self):
        self.assertEqual(self.ingest(self.a_key).status_code, 202)
        self.assertEqual(self.ingest(self.b_key).status_code, 202)
        self.assertEqual(self.published_projects(), [self.a_project, self.b_project])

    def test_first_users_key_writes_into_default_project_id(self):
        self.assertEqual(self.a_project, DEFAULT_PROJECT_ID)
        self.ingest(self.a_key)
        self.assertEqual(self.published_projects(), [DEFAULT_PROJECT_ID])

    def test_rotated_key_is_401_and_the_new_key_writes(self):
        rotated = self.a.post("/api/v1/auth/key/rotate").json()["api_key"]
        self.assertEqual(self.ingest(self.a_key).status_code, 401)
        self.assertEqual(self.ingest(rotated).status_code, 202)
        self.assertEqual(self.published_projects(), [self.a_project])

    # --- reads ----------------------------------------------------------------

    def test_projects_lists_one_default_project_named_after_the_user(self):
        self.assertEqual(self.a.get("/api/v1/projects").json(), [{"id": "default", "name": "ada"}])
        self.assertEqual(self.b.get("/api/v1/projects").json(), [{"id": "default", "name": "grace"}])

    def test_user_gets_404_on_another_users_run_and_span(self):
        self.store.insert_spans([make_span(project_id=self.b_project, trace_id=TRACE, span_id=ROOT)])
        # B, the owner, sees it.
        self.assertEqual(self.b.get(f"{RUNS}/{TRACE}").status_code, 200)
        self.assertEqual(self.b.get(f"{RUNS}/{TRACE}/spans/{ROOT}").status_code, 200)
        self.assertEqual([run["trace_id"] for run in self.b.get(RUNS).json()["runs"]], [TRACE])
        # A gets the same answer as for a trace that does not exist.
        for path in (f"{RUNS}/{TRACE}", f"{RUNS}/{TRACE}/spans/{ROOT}"):
            response = self.a.get(path)
            self.assertEqual((response.status_code, response.json()), (404, {"detail": "Trace not found"}), path)
        self.assertEqual(self.a.get(RUNS).json()["runs"], [])

    def test_only_the_default_project_exists_for_a_logged_in_user(self):
        for project in ("local", "other", str(self.a_project)):
            self.assertEqual(self.a.get(f"/api/v1/projects/{project}/runs").status_code, 404, project)
