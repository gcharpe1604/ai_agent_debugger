"""Example agents export input/output payloads on the durable path.

Each controlled scenario runs through its CLI, the SDK's durable exporter and
the real POST /api/v1/traces route (in-memory publisher). The assertions check
that the recorded payloads hold the facts the expected finding needs: the test
states the fact, it does not run an investigator.

Expected facts come from the scenario definitions (`data/scenarios/*`), not
from `ground_truth/` (evaluation-only).
"""

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from show_payload_states import DurableApp

from agent_debugger_api.contracts import PayloadState, StatusCode

READABLE = {PayloadState.CAPTURED, PayloadState.REDACTED, PayloadState.TRUNCATED}


def setUpModule():
    global durable
    durable = DurableApp().__enter__()


def tearDownModule():
    durable.__exit__(None, None, None)


def named(records, name):
    return [record for record in records if record.span_name == name]


def step(records, step_id):
    """Tool spans of one plan step, by attempt."""
    spans = [record for record in records if record.attributes.get("debugger.step") == step_id]
    return sorted(spans, key=lambda record: record.attempt)


def root_of(records):
    return next(record for record in records if record.parent_span_id is None)


def load(record, kind):
    state = getattr(record, f"{kind}_state")
    if state not in READABLE:
        raise AssertionError(f"{record.span_name}: {kind} payload is {state.value}")
    return json.loads(getattr(record, f"{kind}_payload"))


class ToolAgentPayloadTests(unittest.TestCase):
    def test_tool_01_clean_run_records_every_step(self):
        records = durable.run_scenario("TOOL-01")
        self.assertTrue(all(record.status_code is StatusCode.OK for record in records))
        tools = [record for record in records if record.operation_type == "tool"]
        # By step, not by position: spans that start within one clock tick have no reliable order.
        self.assertEqual(
            {record.attributes["debugger.step"]: load(record, "input")["tool"] for record in tools},
            {
                "order": "get_order",
                "reserve": "reserve_inventory",
                "pay": "charge_payment",
                "ship": "create_shipment",
                "inspect": "inspect_fulfillment",
            },
        )
        for record in tools:
            self.assertIn("result", load(record, "output"))
            self.assertIs(record.error_state, PayloadState.UNAVAILABLE)
        (plan,) = named(records, "controlled.plan")
        self.assertEqual(load(plan, "input"), {"request": "Fulfill order ORD-100."})
        self.assertEqual(len(load(plan, "output")["plan"]), 5)
        (respond,) = named(records, "controlled.respond")
        final = load(respond, "output")
        self.assertEqual(
            (final["status"], final["shipment_id"], final["quantity"]), ("completed", "SHIP-100", 2)
        )
        # Spans that wrap no model, tool or retrieval call carry no payload.
        for record in records:
            if record.operation_type in ("run", "agent"):
                self.assertIs(record.input_state, PayloadState.UNAVAILABLE)
                self.assertIs(record.output_state, PayloadState.UNAVAILABLE)

    def test_tool_03_bad_quantity_is_visible_in_the_plan_and_in_the_failed_call(self):
        records = durable.run_scenario("TOOL-03")
        (plan,) = named(records, "controlled.plan")
        planned = {call["step_id"]: call for call in load(plan, "output")["plan"]}
        (reserve,) = step(records, "reserve")
        (order,) = step(records, "order")

        # The planner asked for quantity 0 ...
        self.assertIs(plan.status_code, StatusCode.OK)
        self.assertEqual(planned["reserve"]["arguments"]["quantity"], 0)
        # ... the order it was planning for has quantity 2 ...
        self.assertEqual(load(order, "output")["result"]["quantity"], 2)
        # ... and the call that failed received exactly that 0.
        self.assertIs(reserve.status_code, StatusCode.ERROR)
        self.assertEqual(reserve.error_type, "ToolError")
        self.assertEqual(load(reserve, "input")["arguments"]["quantity"], 0)
        self.assertIs(reserve.output_state, PayloadState.UNAVAILABLE)
        self.assertEqual(load(reserve, "error")["type"], "ToolError")

        (respond,) = named(records, "controlled.respond")
        self.assertEqual(load(respond, "input")["error_code"], "invalid_arguments")
        self.assertEqual(step(records, "pay"), [])  # nothing ran after the failure
        self.assertEqual(root_of(records).attributes["debugger.result.status"], "failed")

    def test_tool_07_recovered_retry_shows_the_same_call_failing_then_succeeding(self):
        records = durable.run_scenario("TOOL-07")
        first, second = step(records, "pay")
        self.assertEqual((first.attempt, second.attempt), (1, 2))
        self.assertIs(first.status_code, StatusCode.ERROR)
        self.assertEqual(first.error_type, "TransientToolError")
        self.assertIs(first.output_state, PayloadState.UNAVAILABLE)
        self.assertIs(second.status_code, StatusCode.OK)
        self.assertEqual(second.retry_of_span_id, first.span_id)
        # Same arguments on both attempts, and the second one produced the payment.
        self.assertEqual(load(first, "input")["arguments"], load(second, "input")["arguments"])
        self.assertEqual(load(second, "output")["result"]["payment_id"], "PAY-100")

        (respond,) = named(records, "controlled.respond")
        self.assertEqual(load(respond, "output")["status"], "completed")
        root = root_of(records)
        self.assertIs(root.status_code, StatusCode.OK)
        self.assertEqual(root.attributes["debugger.result.status"], "completed")

    def test_tool_08_exhausted_retry_shows_three_failed_attempts_and_no_payment(self):
        records = durable.run_scenario("TOOL-08")
        attempts = step(records, "pay")
        self.assertEqual([record.attempt for record in attempts], [1, 2, 3])
        self.assertEqual(attempts[1].retry_of_span_id, attempts[0].span_id)
        self.assertEqual(attempts[2].retry_of_span_id, attempts[1].span_id)
        for record in attempts:
            self.assertIs(record.status_code, StatusCode.ERROR)
            self.assertEqual(record.error_type, "TransientToolError")
            self.assertIs(record.output_state, PayloadState.UNAVAILABLE)
            self.assertEqual(
                load(record, "input")["arguments"], load(attempts[0], "input")["arguments"]
            )

        (respond,) = named(records, "controlled.respond")
        self.assertIsNone(load(respond, "input")["state"]["payment"])
        self.assertEqual(load(respond, "output")["status"], "failed")
        self.assertEqual(step(records, "ship"), [])
        self.assertIs(root_of(records).status_code, StatusCode.ERROR)


class RagAgentPayloadTests(unittest.TestCase):
    def test_rag_04_answer_and_retrieved_document_disagree_in_recorded_text(self):
        records = durable.run_scenario("RAG-04")
        self.assertTrue(all(record.status_code is StatusCode.OK for record in records))
        (search,) = named(records, "ScenarioAwareRetriever.search")
        documents = {item["document_id"]: item for item in load(search, "output")["documents"]}
        (answer,) = named(records, "controlled.generate_answer")
        generated = load(answer, "output")

        # The retrieved document says 14 days; the answer cites it and says 30 days.
        self.assertIn("restored for 14 days", documents["KB-01"]["excerpt"])
        self.assertEqual(generated["supporting_document_ids"], ["KB-01"])
        self.assertIn("30 days", generated["answer"])
        self.assertNotIn("14 days", generated["answer"])
        # The model step was given that same document text.
        given = {item["document_id"]: item for item in load(answer, "input")["documents"]}
        self.assertIn("restored for 14 days", given["KB-01"]["excerpt"])

    def test_rag_05_abstention_is_backed_by_two_searches_and_a_missing_fact(self):
        records = durable.run_scenario("RAG-05")
        self.assertTrue(all(record.status_code is StatusCode.OK for record in records))
        searches = named(records, "ScenarioAwareRetriever.search")
        self.assertEqual(len(searches), 2)
        queries = [load(record, "input")["query"] for record in searches]
        self.assertEqual(len(set(queries)), 2)
        for record in searches:
            self.assertIn("documents", load(record, "output"))
            self.assertIsNone(record.attempt)  # a refined search is not a retry
            self.assertIsNone(record.retry_of_span_id)

        assessments = [
            load(record, "output") for record in named(records, "controlled.assess_evidence")
        ]
        self.assertEqual(len(assessments), 2)
        for assessment in assessments:
            self.assertFalse(assessment["sufficient"])
            self.assertEqual(assessment["missing_facts"], ["data_residency"])

        (answer,) = named(records, "controlled.generate_answer")
        generated = load(answer, "output")
        self.assertEqual(generated["status"], "insufficient_evidence")
        self.assertEqual(generated["supporting_document_ids"], [])
        root = root_of(records)
        self.assertEqual(root.attributes["debugger.result.status"], "insufficient_evidence")
        self.assertIs(root.status_code, StatusCode.OK)


if __name__ == "__main__":
    unittest.main()
