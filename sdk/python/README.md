# Python Debugger SDK

This package currently provides OpenTelemetry span helpers and bounded capture.
Standalone Debugger use exports ended spans to the console. `HttpSpanExporter`
and `TraceSession` now support bounded batched HTTP export to the explicit local
capture profile. `DurableSpanExporter` sends protocol "1" batches, with
payloads, to `POST /api/v1/traces` (see Durable export). API-key authentication
is not implemented yet.
See [normal development setup](../../docs/local-development.md).

## Public API

```python
from ai_agent_debugger_sdk import CaptureConfig, Debugger

debugger = Debugger(
    service_name="my-agent",
    capture=CaptureConfig(
        capture_inputs=True,
        capture_outputs=True,
        max_payload_bytes=16_384,
        max_depth=8,
        max_nodes=512,
        secret_fields=("session_id",),
    ),
)

with debugger.run("support-run"):
    with debugger.agent("support-agent"):
        with debugger.tool("lookup") as span:
            span.set_input({"query": "sample"})
            span.set_output({"found": True})
            span.set_attribute("attempt", 1)
```

`Debugger(service_name, *, capture=None, tracer_provider=None)` retains the
original positional/keyword `service_name` argument. The two new options are
keyword-only. `endpoint` and `api_key` are not currently accepted.

The context managers `run(name)`, `agent(name)`, `model(name)`, `tool(name)` and
`retrieval(name)` yield a `SpanHandle`. It provides:

- `set_input(value)` and `set_output(value)` for safe JSON capture;
- `set_attribute(key, value)` for explicit string, integer, finite float or
  boolean attributes.

Helpers retain the `debugger.operation.type` attribute and leave span IDs,
trace IDs, parentage, context, events and status to OpenTelemetry.

## Provider ownership and resources

If `tracer_provider` is supplied, the SDK obtains its tracer from that provider
without changing its resource, adding processors, registering it globally or
shutting it down. The application owns exporter configuration and lifecycle:

```python
# application_provider is the provider already configured by your application.
debugger = Debugger("my-agent", tracer_provider=application_provider)
```

Without an explicit provider, an already configured global OpenTelemetry
provider is reused with the same ownership rules. Its existing `service.name`
and all other resource attributes remain intact; `service_name` does not
override a host resource. Existing sampling and span limits also apply.
Host attribute-length/count limits may further truncate or omit captured JSON
and its metadata; the SDK does not override those limits.

When no global provider has been configured, the SDK creates its own private
provider with `Resource.create({"service.name": service_name})` and a
`SimpleSpanProcessor(ConsoleSpanExporter())`. It never replaces the global
provider. Configure the application's provider **before** constructing the
debugger, or pass it explicitly; an existing debugger does not switch providers
when the application later configures a new global provider.

## Run and exception semantics

`run()` follows ordinary OpenTelemetry parentage. Without an active span it
starts a root in a new trace. Within an active host span or another `run()`, it
creates a child in the existing trace. It does not detach context or enforce a
new trace boundary. Independent top-level calls create independent traces.
The protocol's one-Run/one-trace profile therefore requires a top-level Run
boundary; nested calls are operations within the existing trace.

Context follows normal OpenTelemetry propagation through `asyncio` tasks.
Tasks created within a Run inherit its context and maintain their own nested
spans. Thread/process propagation requires the application's usual OTel context
handling.

Exceptions escaping agent/tool code propagate unchanged. OpenTelemetry records
the exception event and error status once per affected span. A caught child
failure leaves its parent `UNSET` unless application code sets another status
or a later exception escapes that parent. Capture helpers do not catch exceptions
around the user's context-manager body.

## Capture safety and limits

`CaptureConfig` is immutable. Invalid configuration raises `ValueError` at
construction; it is a developer configuration error.

| Option | Default | Accepted values |
|---|---|---|
| `capture_inputs` / `capture_outputs` | `True` | Exact booleans |
| `capture_errors` | `True` | Exact boolean; used by the durable exporter only |
| `max_payload_bytes` | 16,384 | Integer, 64–131,072 |
| `max_depth` | 8 | Integer, 0–32; root is depth 0 |
| `max_nodes` | 512 | Integer, 1–10,000; total visited values, including root |
| `secret_fields` | `()` | Tuple of additional nonempty field names, each at most 256 characters |

Capture accepts only exact built-in `None`, booleans, strings, integers, finite
floats, dictionaries, lists and tuples. Tuples become JSON arrays. It does not
call application `str()`, `repr()`, iteration methods, property accessors or
custom JSON encoders. Subclasses and other objects (including bytes, sets,
datetimes and model objects) become `"[unsupported]"`. Non-string dictionary
keys are omitted. NaN and infinity are unsupported. Convert domain objects to
plain data explicitly in application code if their contents should be captured.

Secret fields are redacted recursively, including inside arrays, before their
values are inspected. Matching ignores case and punctuation; dotted attribute
names also match their last segment. Defaults include passwords, API keys,
authorization, cookies, tokens, client secrets, private keys and credentials.
Additional `secret_fields` extend these defaults. The input object is never
modified.

Traversal is bounded by depth, node count and a shared byte budget. The budget
counts bytes of the final ASCII-escaped JSON, including escapes, quotes, commas
and brackets, so a value is cut inside its structure: a long string keeps a
real prefix, and list items or dictionary keys that no longer fit are dropped.
Cycles become `"[circular]"`; excessive depth or integer magnitude becomes
`"[truncated]"`. Integer conversion is limited to at most 1,024 bits (and the
remaining budget). The result is always valid JSON within `max_payload_bytes`,
including Unicode and lone-surrogate input.

`debugger.input` and `debugger.output` hold the JSON strings. Each has boolean
metadata attributes `.redacted`, `.truncated`, `.unsupported`, `.disabled` and
`.capture_error`. These are refreshed on each capture call. Disabled capture
does not inspect the value and omits its payload. An ordinary capture/attribute
write exception is swallowed without logging payloads or exception text. If a
replacement capture fails, a prior value is replaced with
`"[capture unavailable]"` where attribute writes remain available.

Explicit attributes are also restricted to exact primitive types. Secret-named
attributes are redacted, oversized strings are replaced with `[truncated]`, and
invalid values are ignored. Setting the reserved `debugger.input` or
`debugger.output` attributes routes through capture controls.

Process-control exceptions such as `KeyboardInterrupt` and `SystemExit` are not
swallowed. No guarantee is made for a faulty custom host provider/processor.

### Scope of redaction

Field-name redaction is not content scanning. Secrets embedded in prose or
stored under an unrecognized field name can remain. Disable capture or supply
appropriate secret field names for sensitive data. The SDK does not sanitize
OpenTelemetry's automatic exception messages/stack traces, application-created
events or writes made directly to the underlying OTel span. Host exporters can
still emit those fields. This preserves existing OTel event/status behavior.

## Durable export (protocol "1")

```python
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from ai_agent_debugger_sdk import CaptureConfig, Debugger, DurableSpanExporter

capture = CaptureConfig(secret_fields=("session_id",))
provider = TracerProvider(resource=Resource.create({"service.name": "my-agent"}))
provider.add_span_processor(
    BatchSpanProcessor(DurableSpanExporter("http://127.0.0.1:8008/api/v1/traces", capture))
)
debugger = Debugger("my-agent", capture=capture, tracer_provider=provider)
```

The endpoint must be `/api/v1/traces`; `https` is required unless the host is
loopback. `TraceSession` picks this exporter when its endpoint has that path
and accepts the same `capture=` option; its wrapped calls still record no
arguments or results.

Each exported span carries three payloads, each with its own state:

| State | Meaning | Payload |
|---|---|---|
| `captured` | stored as recorded | JSON |
| `redacted` | at least one secret field was replaced by `"[redacted]"` | JSON |
| `truncated` | something was cut at a limit | the cut JSON (still valid JSON) |
| `disabled` | the capture switch is off | empty |
| `unavailable` | never set, capture failed, or the whole value is not JSON | empty |

When several apply, the first of `disabled`, `unavailable`, `truncated`,
`redacted`, `captured` is used, and the flags it cannot express remain as
attributes (`debugger.input.redacted`, `.truncated`, `.unsupported`).

The error payload is `{"type", "message"}` from the first exception event. A
stack trace is never exported. With `capture_errors=False` the exception
message and the status description are not exported either.

Attribute keys that match a secret field name are exported as `"[redacted]"`.
Per span, attributes and events are each limited to 32 KiB; attributes past
that are dropped and counted in `debugger.export.dropped_attributes`.

Delivery: `export` makes one attempt on the calling thread. An HTTP 503 is
retried up to 3 times with exponential backoff (1 s, 2 s, 4 s) on the
exporter's own daemon thread, then dropped. A 413, a 422, any other status and
a connection error are dropped at once and never retried. `export` never waits
for a backoff. `force_flush(timeout_millis)` waits for pending retries up to
its timeout (`TraceSession` calls it once, with 10 s, when the run ends);
`shutdown()` gives them up. Counters: `exported_spans`, `retries`, `failures`
and `dropped_spans`. Use `BatchSpanProcessor`, as above: with
`SimpleSpanProcessor` the first attempt runs on the thread that ends the span.

This policy is a user decision of 2026-11-16:
`docs/proposals/clickhouse-span-record.md` §9.

## Tests and demo

The optional `test` extra declares pytest; runtime dependencies remain only
OpenTelemetry API/SDK. With pytest already available, from `sdk/python` run:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
```

The tests use real providers and an in-memory exporter, make no provider
calls, and assert that SDK imports resolve to this package's source directory.
The durable exporter tests post to a stub HTTP server on loopback.
They cover hierarchy, async concurrency, failures/recovery, capture safety and
limits, and host-provider ownership.

The root `test_sdk.py` remains a console demonstration. Importing it has no
tracing side effects; running it directly executes `main()`.

## CLI-owned live runs

`TraceSession` reads `AGENT_DEBUGGER_ENDPOINT`; unset means no export or method wrapping. On the durable path (`/api/v1/traces`) the exporter sends `Authorization: Bearer <key>` from `AGENT_DEBUGGER_API_KEY` (or `DurableSpanExporter(..., api_key=...)`); the key is never logged. A 401 drops the batch and logs one warning per exporter; it is never retried. It owns a private OTel provider and bounded BatchSpanProcessor, ends and flushes the run explicitly, reports acknowledged delivery, and shuts down only its own provider. It wraps explicitly named methods on caller-owned instances, supports synchronous/asynchronous calls, and records exceptions without arguments, prompts or stacks. It does not install global monkey patches.

A wrapped call records no arguments or results by default. To record them, pass explicit extractors: `wrap_callable(..., payloads=(input_fn, output_fn))` or `instrument(instance, operations, payloads={"method": (input_fn, output_fn)})`. `input_fn(*args, **kwargs)` and `output_fn(result)` return the plain data to record (the capture rules above apply: built-in JSON-like types only, secret field names redacted, size bounded); either may be `None`. Extractors run on the durable path (`/api/v1/traces`) only, never on the local route, which stays metadata-only. An extractor that raises is ignored. A call that raises has its input and its error type, and no output. The example agents keep their extractors in `<agent>/telemetry.py` (`tool_task_agent`, `rag_agent`).

The repository's four agent CLIs use `TraceSession.local(...)` for both `ask` and `run SCENARIO`. This explicit helper defaults to the existing loopback capture endpoint; `AGENT_DEBUGGER_ENDPOINT` overrides it and an empty value disables it. Live-model and controlled execution modes are recorded separately; controlled methods are custom operations, not model/API calls. They label their existing local dependencies explicitly. General `TraceSession(...)`, `Debugger` and caller-supplied provider semantics are unchanged. Direct Python users must open a session and instrument their calls explicitly; importing an agent does not install global tracing.
