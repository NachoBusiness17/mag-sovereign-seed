"""kv_seal — SALT-AND-SEAL KV PAGES (ask A7, 2026-09-22).

Per-tenant integrity for KV page files: an HMAC-SHA256 sidecar written next to
each page, keyed by that tenant's salt. A page whose bytes were corrupted or
tampered with no longer verifies; the CALLER then deletes the page and refills
it (refill_page is the stub hook — it does nothing but report, never invents).

  seal_page(path, tenant_salt)    -> HMAC-SHA256 over the page bytes, sidecar
                                     written to <path>.sealed (kv-seal.v1 JSON)
  verify_page(path, tenant_salt)  -> {"ok": bool, "refill": bool, ...}; ok=False
                                     means the caller deletes and refills
  refill_page(path)               -> STUB HOOK: the real refill (fetch from the
                                     source of truth) lands later

Tenant isolation: the salt IS the HMAC key material, so a page sealed under
tenant A's salt fails verification under tenant B's salt — cross-tenant swaps
are caught the same as tampering.

Schema: kv-seal.v1 · deterministic · stdlib only · $0 local.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
from typing import Any, Union

PathLike = Union[str, os.PathLike]
SCHEMA = "kv-seal.v1"
SIDECAR_SUFFIX = ".sealed"

try:  # keep Windows consoles honest on non-ascii digests/paths
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


def _salt_bytes(tenant_salt: Union[str, bytes]) -> bytes:
    """Normalize the tenant salt to bytes; refuse an empty salt (that would
    seal pages with a known key = no integrity at all)."""
    if isinstance(tenant_salt, str):
        salt = tenant_salt.encode("utf-8")
    elif isinstance(tenant_salt, bytes):
        salt = tenant_salt
    else:
        raise TypeError("tenant_salt must be str or bytes")
    if not salt:
        raise ValueError("tenant_salt must be non-empty")
    return salt


def _page_digest(page_bytes: bytes, salt: bytes) -> str:
    """HMAC-SHA256 over the page bytes, keyed by the tenant salt."""
    return hmac.new(salt, page_bytes, hashlib.sha256).hexdigest()


def sidecar_path(path: PathLike) -> Path:
    """The .sealed sidecar that lives next to the page."""
    return Path(str(path) + SIDECAR_SUFFIX)


def seal_page(path: PathLike, tenant_salt: Union[str, bytes]) -> dict[str, Any]:
    """SEAL: HMAC the page bytes under the tenant salt, write the .sealed sidecar.

    The page is read as raw bytes (KV pages are opaque payloads); the sidecar is
    deterministic JSON {schema, digest} so it can be diffed and re-verified forever.
    Raises FileNotFoundError if the page is missing — never seals nothing.
    """
    p = Path(path)
    salt = _salt_bytes(tenant_salt)  # validate key material BEFORE touching disk
    page_bytes = p.read_bytes()
    digest = _page_digest(page_bytes, salt)
    side = sidecar_path(p)
    side.write_text(
        json.dumps({"schema": SCHEMA, "digest": digest}, ensure_ascii=False),
        encoding="utf-8")
    return {"ok": True, "schema": SCHEMA, "path": str(p), "sidecar": str(side),
            "digest": digest, "size": len(page_bytes)}


def verify_page(path: PathLike, tenant_salt: Union[str, bytes]) -> dict[str, Any]:
    """VERIFY: recompute the HMAC over the page's current bytes and compare to the
    sidecar (constant-time). Returns {"ok", "refill", "reason", ...}:
      ok=True                       -> page bytes intact, safe to serve
      ok=False, refill=True         -> missing/unverifiable/tampered — the caller
                                       deletes the page and calls refill_page
    Missing page or missing/unreadable sidecar are NOT treated as ok: an
    unverifiable page is a refill, not a pass.
    """
    p = Path(path)
    salt = _salt_bytes(tenant_salt)  # validate key material BEFORE page-state verdicts
    side = sidecar_path(p)
    if not p.is_file():
        return {"ok": False, "refill": True, "reason": "page-missing",
                "path": str(p)}
    if not side.is_file():
        return {"ok": False, "refill": True, "reason": "sidecar-missing",
                "path": str(p)}
    try:
        rec = json.loads(side.read_text(encoding="utf-8"))
        stored = str(rec["digest"]).strip().lower()
    except Exception:  # noqa: BLE001 — unreadable sidecar is un-verifiable
        return {"ok": False, "refill": True, "reason": "sidecar-unreadable",
                "path": str(p)}
    if rec.get("schema") != SCHEMA:
        return {"ok": False, "refill": True, "reason": "schema-mismatch",
                "path": str(p), "sidecar_schema": rec.get("schema")}
    page_bytes = p.read_bytes()
    expected = _page_digest(page_bytes, salt)
    if hmac.compare_digest(expected, stored):
        return {"ok": True, "refill": False, "path": str(p), "digest": expected,
                "size": len(page_bytes)}
    return {"ok": False, "refill": True, "reason": "digest-mismatch",
            "path": str(p), "expected": expected, "found": stored}


def refill_page(path: PathLike) -> dict[str, Any]:
    """STUB HOOK — called by the caller AFTER it deleted a failed page.

    The real refill (re-fetch the page from the source of truth / upstream KV)
    lands later. Today this only reports the hook fired and which page it is
    for; it never fabricates page bytes and never touches the filesystem.
    """
    return {"ok": False, "stub": True, "action": "refill", "path": str(path),
            "note": "stub hook: refill not implemented; caller must fill the page"}


def status() -> dict[str, Any]:
    """The contract, legible — matches the estate's seal.py status() habit."""
    return {"ok": True, "schema": SCHEMA,
            "contract": "seal_page() = HMAC-SHA256 over page bytes keyed by the "
                        "tenant salt -> .sealed sidecar; verify_page() = {ok, refill}; "
                        "on refill=True the caller deletes and calls refill_page()",
            "sidecar_suffix": SIDECAR_SUFFIX,
            "built": "2026-09-22 — ask A7 salt-and-seal KV pages (8-wide capacity cohort)"}


if __name__ == "__main__":
    print(json.dumps(status(), indent=2, ensure_ascii=False))
