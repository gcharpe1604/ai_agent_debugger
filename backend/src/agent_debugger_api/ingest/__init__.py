"""Durable ingest (protocol "1"): POST /api/v1/traces -> Kafka.

Separate from the local profile (`/api/v1/local/*`, protocol "local-1",
`traces/`): no loopback gating, no payload rejection, no shared models.
"""
