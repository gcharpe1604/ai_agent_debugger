"""One real Bedrock Converse call on a tiny prompt. Prints the stop reason and token usage only.

Needs BEDROCK_MODEL_ID, AWS_REGION and AWS_BEARER_TOKEN_BEDROCK (read by boto3) in the
environment. Run from the repo root:

    uv run --project backend --locked python scripts/bedrock_smoke.py

It never prints the key, the model's text or the provider's error message; on failure it
prints the error kind and the AWS error code and exits 1.
"""

from __future__ import annotations

import os
import sys

from agent_debugger_api.investigator.bedrock_provider import error_kind, make_client


def main() -> int:
    model_id = os.environ.get("BEDROCK_MODEL_ID", "")
    region = os.environ.get("AWS_REGION", "")
    missing = [name for name, value in (("BEDROCK_MODEL_ID", model_id), ("AWS_REGION", region)) if not value]
    if not os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
        missing.append("AWS_BEARER_TOKEN_BEDROCK")
    if missing:
        print("missing env: " + ", ".join(missing))
        return 2

    client = make_client(region, read_timeout_s=60)
    try:
        response = client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": "Reply with the single word: ok"}]}],
            inferenceConfig={"maxTokens": 16, "temperature": 0},
        )
    except Exception as error:  # noqa: BLE001
        kind, code = error_kind(error)
        print(f"error kind={kind} code={code}")
        return 1

    usage = response.get("usage") or {}
    print(f"stopReason={response.get('stopReason')}")
    print(f"inputTokens={usage.get('inputTokens')} outputTokens={usage.get('outputTokens')} totalTokens={usage.get('totalTokens')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
