"""tandem_key_test — fire the free-lane round from ONE OpenRouter account key (2026-08-23).

Operator: "can you launch free models from both separate keys in tandem to test?"
The honest way to test TWO separate account pools in TRUE tandem is TWO OS PROCESSES, each pinned
to its own key (chat_provider reads its key from os.environ at call time). This module does one
account's half of that: it loads the chosen key, pins it, and fires a small parallel round of
free-lane cold-vertex asks through real_swarm's openrouter path. Run one per account side by side.

Run (two terminals, simultaneously):
  python -m mag.tandem_key_test --account 1 --n 8
  python -m mag.tandem_key_test --account 2 --n 8

NOTE: ox-alpha is upstream-shared-pool throttled right now; this tests the ROTATION + multi-key
path, so it may surface 429s from hot lanes — that's the honest result, not a failure.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load_dotenv() -> dict[str, str]:
    """Parse .env (values only) so we can pin a specific account key without echoing it."""
    out = {}
    p = ROOT / ".env"
    if not p.is_file():
        return out
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tandem-key-test")
    ap.add_argument("--account", type=int, default=1, choices=[1, 2], help="which OpenRouter account key")
    ap.add_argument("--n", type=int, default=8, help="asks to fire this round")
    a = ap.parse_args(argv)

    env = _load_dotenv()
    if a.account == 1:
        key = env.get("OPENROUTER_API_KEY") or ""
        label = "account-1 (funded)"
    else:
        key = env.get("OPENROUTER_API_KEY_2") or ""
        label = "account-2 (sd, free)"
    if not key:
        print(json.dumps({"ok": False, "error": f"no key for account {a.account} in .env"}, indent=2))
        return 1

    # pin THIS account's key so chat_provider routes through this account's pool only
    os.environ["OPENROUTER_API_KEY"] = key
    os.environ.pop("OPENROUTER_API_KEY_2", None)

    import mag.real_swarm as rs
    # fire a small free-lane round through the openrouter path (rotates across free lanes)
    res = rs.run(provider="openrouter", rnd=2)
    out = {"ok": bool(res.get("ok")), "schema": "tandem_key_test.v1", "account": a.account,
           "label": label, "n_asks": a.n, "per_provider": res.get("per_provider"),
           "banked": res.get("done_total")}
    open(ROOT / "handoff" / f"TANDEM_KEY_{a.account}.json", "w", encoding="utf-8").write(
        json.dumps(out, indent=2, default=str))
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
