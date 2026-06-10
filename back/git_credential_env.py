#!/usr/bin/env python3
"""Git credential helper — supplies the GitHub token from back/.env (GIT_HUB_TOKEN) on demand.

The token stays ONLY in back/.env (the repo's single source of truth for secrets); it is never
written into .git/config or the remote URL. Headless/CI-friendly: no interactive prompt, no
OS keychain dependency.

Wire it up (repo-local, scoped to github.com) with:
    git config --local credential.https://github.com.helper ""
    git config --local --add credential.https://github.com.helper \
        '!python "<repo>/back/git_credential_env.py"'
The empty first entry resets any system/global helper so ONLY this one runs for github.com.

Git calls this with the operation as argv[1] ("get"/"store"/"erase") and feeds key=value lines
on stdin. For "get" we emit username/password; "store"/"erase" are no-ops (nothing to persist)."""
from __future__ import annotations

import os
import sys


def _read_token() -> str:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(env_path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("GIT_HUB_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        return ""
    return ""


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action != "get":          # store / erase: nothing to do (token lives in .env)
        return
    token = _read_token()
    if not token:                # let git fall back if the token is missing
        return
    sys.stdout.write("username=x-access-token\n")
    sys.stdout.write(f"password={token}\n")


if __name__ == "__main__":
    main()
