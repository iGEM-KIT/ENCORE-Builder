"""JSON stdin/stdout adapter for the Nitro backend."""

from __future__ import annotations

import json
import sys

from .design import build_fasta, design_construct


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        result = design_construct(payload)
        if payload.get("fasta"):
            result["fasta"] = build_fasta(result)
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        json.dump({"ok": False, "error": str(error)}, sys.stdout)
        return 1

    json.dump({"ok": True, "design": result}, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())