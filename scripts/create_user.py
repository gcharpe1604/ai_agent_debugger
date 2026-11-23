"""Create a user from the command line and print its API key once.

    uv run --project backend --locked python -B scripts/create_user.py --email ada@example.com --name "Ada"

The password comes from the CREATE_USER_PASSWORD environment variable, else a
prompt (not echoed). Same rules and same project assignment as
POST /api/v1/auth/register (the first user gets DEFAULT_PROJECT_ID), but
ALLOW_SIGNUP does not apply: this is how users are made when sign-up is off.

stdout: the API key, alone on one line (only its hash is stored; it cannot be
shown again). stderr: what was created.

Exit codes: 0 created; 1 email already registered; 2 invalid name, email or
password; 3 database unreachable or not migrated
(`uv run --project backend --locked alembic -c backend/alembic.ini upgrade head`).
Database: DATABASE_URL from the environment or the repo-root .env.
"""

import argparse
import asyncio
import getpass
import os
import sys

from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError

from agent_debugger_api.auth.schemas import RegisterIn
from agent_debugger_api.auth.users import EmailTaken, create_user
from agent_debugger_api.db.session import get_engine, get_session_factory


def read_password() -> str:
    password = os.environ.get("CREATE_USER_PASSWORD")
    if password is not None:
        return password
    password = getpass.getpass("Password (at least 8 characters): ")
    if getpass.getpass("Repeat password: ") != password:
        print("Passwords do not match.", file=sys.stderr)
        raise SystemExit(2)
    return password


async def create(body: RegisterIn):
    engine = get_engine()
    try:
        async with get_session_factory()() as db:
            return await create_user(db, name=body.name, email=body.email, password=body.password)
    finally:
        await engine.dispose()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args(argv)
    try:
        body = RegisterIn(name=args.name, email=args.email, password=read_password())
    except ValidationError as exc:
        # Field names and messages only: never the submitted values.
        for error in exc.errors():
            print(f"invalid {'.'.join(map(str, error['loc']))}: {error['msg']}", file=sys.stderr)
        return 2
    try:
        user, api_key = asyncio.run(create(body))
    except ValidationError:  # settings, not the body: DATABASE_URL missing
        print("DATABASE_URL is not set (environment or repo-root .env).", file=sys.stderr)
        return 3
    except EmailTaken:
        print(f"{body.email} is already registered.", file=sys.stderr)
        return 1
    except (DBAPIError, OSError) as exc:
        print(f"database error ({type(exc).__name__}): is PostgreSQL up and migrated?", file=sys.stderr)
        return 3
    print(f"created {user.email} (user {user.id}, project {user.project_id}); key prefix {user.key_prefix}.",
          file=sys.stderr)
    print("The API key below is shown once. Set it as AGENT_DEBUGGER_API_KEY for the SDK.", file=sys.stderr)
    print(api_key)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
