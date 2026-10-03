#!/usr/bin/env python3
from __future__ import annotations

import argparse
from getpass import getpass
from pathlib import Path

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
    args = parser.parse_args()

    first = getpass("Enter owner authorization code: ")
    second = getpass("Re-enter owner authorization code: ")
    if first != second:
        raise SystemExit("Codes did not match.")

    auth = OwnerAuthorization(args.path)
    auth.configure(first)
    print(f"Owner authorization verifier created at {args.path}")
    print("The authorization code itself is not stored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
