import asyncio
import os
import socket

import pytest

from rag_agent.factory import build_agent


@pytest.mark.parametrize("scenario_id", [f"RAG-{i:02}" for i in range(1, 8)])
def test_repeated_fresh_reused_and_concurrent_runs(kb, scenarios, results, scenario_id):
    async def check():
        scenario = scenarios[scenario_id]
        expected = results[scenario_id].model_dump()
        agent = build_agent(scenario, kb)
        for _ in range(3):
            assert (await agent.run(scenario.question)).model_dump() == expected
            assert (
                await build_agent(scenario, kb).run(scenario.question)
            ).model_dump() == expected
        concurrent = await asyncio.gather(
            agent.run(scenario.question), agent.run(scenario.question)
        )
        assert all(result.model_dump() == expected for result in concurrent)

    asyncio.run(check())


def test_all_scenarios_with_network_blocked_and_no_credentials(
    monkeypatch, scenarios, results
):
    def deny_network(*args, **kwargs):
        raise AssertionError("Network access is forbidden in controlled mode")

    for key in list(os.environ):
        if (
            "API_KEY" in key
            or key.endswith("_TOKEN")
            or key in {"DATABASE_URL", "OPENAI_BASE_URL"}
        ):
            monkeypatch.delenv(key)

    async def check():
        # Install after the event loop's local wakeup socket exists (important on Windows).
        with monkeypatch.context() as blocked:
            blocked.setattr(socket, "getaddrinfo", deny_network)
            blocked.setattr(socket, "create_connection", deny_network)
            blocked.setattr(socket.socket, "connect", deny_network)
            blocked.setattr(socket.socket, "connect_ex", deny_network)
            blocked.setattr(socket.socket, "sendto", deny_network)
            with pytest.raises(AssertionError, match="Network access"):
                socket.create_connection(("example.invalid", 443))
            for name, scenario in scenarios.items():
                # Factory reloads the real packaged KB inside the network guard.
                result = await build_agent(scenario).run(scenario.question)
                assert result.model_dump() == results[name].model_dump()

    asyncio.run(check())
