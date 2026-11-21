"""One real Bedrock Converse call on a tiny prompt. Prints the stop reason and token usage only.

Needs BEDROCK_MODEL_ID, AWS_REGION and AWS_BEARER_TOKEN_BEDROCK (read by boto3) in the
environment. Run from the repo root:

    uv run --project backend --locked python scripts/bedrock_smoke.py
    uv run --project backend --locked python scripts/bedrock_smoke.py --dry-run [--snapshot FILE]

--dry-run makes no call and needs no key: it prints the shape of the investigator's
Converse request (keys and sizes, not the prompt) for a snapshot file, or for an empty
snapshot.

Never printed: the key, the model's text, the provider's error message.

Exit codes:
  0 ok              3 credentials rejected or missing   6 throttled
  1 other failure   4 no access to this model            7 timeout or service unavailable
  2 env not set     5 model not found in this region / bad request
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from agent_debugger_api.investigator.bedrock_provider import BedrockProvider, error_kind, make_client
from agent_debugger_api.investigator.engine import INSTRUCTIONS, MAX_OUTPUT_TOKENS, PROVIDER_TIMEOUT_S
from agent_debugger_api.investigator.provider import InvestigationRequest
from agent_debugger_api.investigator.schema import output_json_schema

MESSAGES = {
    "auth": (3, "credentials rejected or missing: check AWS_BEARER_TOKEN_BEDROCK (a Bedrock API key) is set and not expired"),
    "AccessDeniedException": (
        4,
        "access denied: this key cannot invoke this model here; enable model access for BEDROCK_MODEL_ID in AWS_REGION, "
        "or use an inference profile ID the account can call",
    ),
    "ResourceNotFoundException": (5, "model not found: check BEDROCK_MODEL_ID and that it is offered in AWS_REGION"),
    "ValidationException": (
        5,
        "request rejected: usually a model ID that is wrong for this region or needs an inference profile (e.g. us./eu. prefix)",
    ),
    "EndpointConnectionError": (5, "cannot reach bedrock-runtime in AWS_REGION: check the region name and the network"),
    "rate_limited": (6, "throttled: wait a minute and retry; new accounts start with low quotas"),
    "timeout": (7, "timed out: retry; the first structured-output call can take up to ~90 s"),
    "unavailable": (7, "Bedrock unavailable or model not ready: retry later"),
}


def describe_failure(kind: str, code: str) -> tuple[int, str]:
    """(exit code, one line) for a ProviderError kind and AWS code. Never includes provider text."""
    exit_code, line = MESSAGES.get(code) or MESSAGES.get(kind) or (1, "failed")
    return exit_code, f"error: {line} [kind={kind} code={code}]"


def dry_run(model_id: str, region: str, snapshot_path: str | None) -> int:
    snapshot_json = '{"spans":[]}'
    if snapshot_path:
        with open(snapshot_path, encoding="utf-8") as handle:
            snapshot_json = json.dumps(json.load(handle), sort_keys=True, separators=(",", ":"))
    provider = BedrockProvider(model_id or "<unset>", region or "<unset>", client=object())
    request = InvestigationRequest(
        instructions=INSTRUCTIONS,
        snapshot_json=snapshot_json,
        output_schema=output_json_schema(),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        timeout_s=PROVIDER_TIMEOUT_S,
    )
    kwargs = provider.converse_kwargs(request)
    (message,) = kwargs["messages"]
    text_format = kwargs["outputConfig"]["textFormat"]
    schema = text_format["structure"]["jsonSchema"]
    print(f"modelId={kwargs['modelId']} region={provider.region}")
    print(f"request keys={sorted(kwargs)}")
    print(f"system: {len(kwargs['system'])} block, {len(INSTRUCTIONS.encode())} bytes")
    print(f"user message: {len(message['content'])} blocks; snapshot {len(snapshot_json.encode())} bytes")
    print(f"inferenceConfig={kwargs['inferenceConfig']}")
    print(f"outputConfig.textFormat: type={text_format['type']} name={schema['name']} schema {len(schema['schema'])} bytes")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One Bedrock Converse smoke call, or --dry-run.")
    parser.add_argument("--dry-run", action="store_true", help="print the request shape and snapshot size; no call")
    parser.add_argument("--snapshot", help="snapshot JSON file for --dry-run (e.g. a stored attempt's snapshot_json)")
    args = parser.parse_args(argv)

    model_id = os.environ.get("BEDROCK_MODEL_ID", "")
    region = os.environ.get("AWS_REGION", "")
    if args.dry_run:
        return dry_run(model_id, region, args.snapshot)

    missing = [name for name, value in (("BEDROCK_MODEL_ID", model_id), ("AWS_REGION", region)) if not value]
    if not os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
        missing.append("AWS_BEARER_TOKEN_BEDROCK")
    if missing:
        print("error: env not set: " + ", ".join(missing))
        return 2

    client = make_client(region, read_timeout_s=60)
    try:
        response = client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": "Reply with the single word: ok"}]}],
            inferenceConfig={"maxTokens": 16, "temperature": 0},
        )
    except Exception as error:  # noqa: BLE001
        exit_code, line = describe_failure(*error_kind(error))
        print(line)
        return exit_code

    usage = response.get("usage") or {}
    print(f"ok: stopReason={response.get('stopReason')}")
    print(f"inputTokens={usage.get('inputTokens')} outputTokens={usage.get('outputTokens')} totalTokens={usage.get('totalTokens')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
