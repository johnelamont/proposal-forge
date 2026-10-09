"""One-time move of local Supabase data to the hosted project.

Copies the operator's rows from the local stack's `public` tables into the
hosted database, rewriting `user_id` from the local account to the hosted one
(create the hosted account by signing in to the deployed app first, then run
this). Auth internals are not copied; only your data is.

Usage (PowerShell or Git Bash, from the repo root, local stack running):

    uv run --directory backend python ../scripts/migrate_local_to_cloud.py \
        --cloud-url "<session pooler connection string>" \
        --cloud-user-id <uuid of your account in the hosted project>

The cloud URL is the *Session pooler* connection string from the Supabase
dashboard (Project Settings → Database). Your hosted user id is under
Authentication → Users. Run with --dry-run first to see what would move.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

LOCAL_CONTAINER = "supabase_db_proposal-forge"
TABLES = ["public.work_history", "public.job_posts"]  # parents before children
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def sh(args: list[str], **kw) -> str:
    out = subprocess.run(args, capture_output=True, text=True, **kw)
    if out.returncode != 0:
        sys.exit(f"command failed: {' '.join(args)}\n{out.stderr}")
    return out.stdout


def local_user_ids() -> list[str]:
    rows = sh(
        [
            "docker",
            "exec",
            LOCAL_CONTAINER,
            "psql",
            "-U",
            "postgres",
            "-tAc",
            "select id || ' ' || email from auth.users order by created_at",
        ]
    )
    return [line for line in rows.strip().splitlines() if line]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cloud-url", required=True)
    ap.add_argument("--cloud-user-id", required=True)
    ap.add_argument("--local-user-id", help="defaults to the only local user")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not UUID.fullmatch(args.cloud_user_id):
        sys.exit("--cloud-user-id must be a UUID")

    users = local_user_ids()
    if args.local_user_id:
        local_uid = args.local_user_id
    elif len(users) == 1:
        local_uid = users[0].split()[0]
    else:
        sys.exit("Several local users; pass --local-user-id:\n  " + "\n  ".join(users))
    print(f"local user: {local_uid}\ncloud user: {args.cloud_user_id}")

    dump = sh(
        [
            "docker",
            "exec",
            LOCAL_CONTAINER,
            "pg_dump",
            "-U",
            "postgres",
            "--data-only",
            "--column-inserts",
            "--no-owner",
            *sum((["-t", t] for t in TABLES), []),
        ]
    )
    rewritten = dump.replace(local_uid, args.cloud_user_id)
    rows = sum(rewritten.count(f"INSERT INTO {t}") for t in TABLES)
    print(f"rows to move: {rows} across {', '.join(TABLES)}")
    if args.dry_run:
        print(rewritten[:2000] + ("\n…" if len(rewritten) > 2000 else ""))
        return

    with tempfile.NamedTemporaryFile(
        "w", suffix=".sql", delete=False, encoding="utf-8"
    ) as f:
        f.write("begin;\n" + rewritten + "\ncommit;\n")
        path = Path(f.name)
    try:
        # psql via the official image so nothing needs installing locally.
        sh(
            [
                "docker",
                "run",
                "--rm",
                "-i",
                "-v",
                f"{path}:/move.sql:ro",
                "postgres:17-alpine",
                "psql",
                args.cloud_url,
                "-v",
                "ON_ERROR_STOP=1",
                "-f",
                "/move.sql",
            ]
        )
    finally:
        path.unlink(missing_ok=True)
    print("done — check the hosted app, then this local data can be left or reset")


if __name__ == "__main__":
    main()
