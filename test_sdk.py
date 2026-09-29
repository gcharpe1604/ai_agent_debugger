from ai_agent_debugger_sdk import Debugger


debugger = Debugger(service_name="demo-agent")


with debugger.run("refund-run"):
    with debugger.agent("refund-agent"):

        with debugger.retrieval("refund-policy-search") as span:
            query = "refund policy"

            span.set_input({
                "query": query,
            })

            policy = {
                "refund_windows_days": 14,
            }

            span.set_output(policy)

        with debugger.tool("get-order") as span:
            span.set_input({
                "order_id": "ORD-123",
            })

            order = {
                "order_id": "ORD-123",
                "age_days": 25,
            }

            span.set_output(order)

        with debugger.model("final-response") as span:
            span.set_input({
                "refund_windows_days": 14,
                "order_age_days": 25,
            })

            decision = {
                "refund_eligible": True,
            }

            span.set_output(decision)