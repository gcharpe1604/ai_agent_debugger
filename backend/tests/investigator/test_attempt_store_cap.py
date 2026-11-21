"""InMemoryAttemptStore keeps at most `max_attempts`; the oldest attempt is evicted on create."""

import os
import unittest
from unittest import mock
from uuid import UUID

from agent_debugger_api.investigator.attempts import AnalysisAttempt, InMemoryAttemptStore
from tests.contracts.factories import PROJECT_A, TRACE_1


def attempt(number, created_at, status="pending"):
    return AnalysisAttempt(
        attempt_id=UUID(int=number), project_id=PROJECT_A, trace_id=TRACE_1, status=status,
        provider_name="stub-scripted", model_id="scripted-1", prompt_version="v", created_at=created_at,
    )


class AttemptCapTests(unittest.TestCase):
    def test_creating_past_the_cap_evicts_the_oldest_by_created_at(self):
        store = InMemoryAttemptStore(max_attempts=3)
        for number, created_at in ((1, 30), (2, 10), (3, 20)):  # created out of clock order
            store.create(attempt(number, created_at))
        store.create(attempt(4, 40))
        self.assertIsNone(store.get(UUID(int=2)))  # created_at 10: the oldest
        self.assertEqual([a.attempt_id.int for a in store.list_for_trace(PROJECT_A, TRACE_1)], [3, 1, 4])

    def test_the_cap_holds_over_many_creates(self):
        store = InMemoryAttemptStore(max_attempts=5)
        for number in range(1, 21):
            store.create(attempt(number, number))
        self.assertEqual([a.attempt_id.int for a in store.list_for_trace(PROJECT_A, TRACE_1)], [16, 17, 18, 19, 20])

    def test_default_cap_is_200_and_env_overrides_it(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(InMemoryAttemptStore().max_attempts, 200)
        with mock.patch.dict(os.environ, {"INVESTIGATOR_MAX_ATTEMPTS": "7"}):
            self.assertEqual(InMemoryAttemptStore().max_attempts, 7)


if __name__ == "__main__":
    unittest.main()
