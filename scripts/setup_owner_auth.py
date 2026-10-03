#!/usr/bin/env python3
from __future__ import annotations

import argparse
from getpass import getpass
from pathlib import Path
import sys

from core.security.owner_override import OwnerAuthorization


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure the local Super-Ai owner authentication verifier."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path(".super-ai/security/owner_auth.json"),
    )
    parser.add_argument(
        "--rotate",
        action="store_true",
        help="Replace an existing verifier after explicit confirmation.",
    )
    args = parser.parse_args()

    if not sys.stdin.isatty():
        raise SystemExit(
            "For security, run this command from an interactive terminal. "
            "Do not pipe, echo, or pass the owner code as a shell argument."
        )

    auth = OwnerAuthorization(args.path)
    if auth.configured and not args.rotate:
        raise SystemExit(
            "An owner verifier already exists. Re-run with --rotate to replace it."
        )
    if auth.configured and args.rotate:
        confirm = input(
            "Existing owner verifier will be replaced. Type ROTATE to continue: "
        ).strip()
        if confirm != "ROTATE":
            raise SystemExit("Verifier rotation cancelled.")

    first = getpass("Enter new owner authorization code (hidden): ")
    second = getpass("Re-enter new owner authorization code (hidden): ")
    try:
        if first != second:
            raise SystemExit("Codes did not match.")
        auth.configure(first)
    finally:
        # Drop the only local references as soon as possible. Python cannot
        # guarantee memory scrubbing for immutable str objects.
        first = ""
        second = ""

    print(f"Owner authorization verifier created at {args.path}")
    print("Only the salted scrypt verifier is stored; the owner code is not.")
    print("The code must never be placed in shell commands, environment variables,")
    print("Git files, logs, model context, or task output.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
