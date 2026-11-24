import os

# Importing agent_debugger_api.main requires SESSION_SECRET (auth/settings.py).
# Tests that do not set one get this test-only value; it signs nothing real.
os.environ.setdefault("SESSION_SECRET", "test-only-session-secret-0123456789abcdef")
