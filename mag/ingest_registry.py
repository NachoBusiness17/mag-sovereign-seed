"""Growing ingest database for docs/papers referenced by Mag dossiers.

Every bibliography item is:
  - tagged
  - given a stable id
  - pointed at a local path (copy created when possible)
  - pointed at remote URL when known
  - recorded in memory/ingest/registry.jsonl for future search

Layout:
  memory/ingest/
    registry.jsonl          # append-only records
    catalog.json            # latest index by id
    local/                  # copied or mirrored files
      docs/
      papers/
      web/
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from config import ROOT


def _SAFE_HOME() -> Path:
    """_SAFE_HOME() guard: HOME can be unresolvable in sandbox/service contexts
    (KNOWN_CORPUS below builds candidate paths at import time)."""
    try:
        return _SAFE_HOME()
    except (RuntimeError, OSError):
        return ROOT.parent

INGEST = ROOT / "memory" / "ingest"
REGISTRY = INGEST / "registry.jsonl"
CATALOG = INGEST / "catalog.json"
LOCAL = INGEST / "local"
LOCAL_DOCS = LOCAL / "docs"
LOCAL_PAPERS = LOCAL / "papers"
LOCAL_WEB = LOCAL / "web"

# Known anchors: (id, title, remote_url, local_candidates, tags, kind)
KNOWN_CORPUS: list[dict[str, Any]] = [
    {
        "id": "steiniger-academia",
        "title": "Matthew Steiniger — Academia profile",
        "url": "https://independent.academia.edu/MatthewSteiniger",
        "local_candidates": [],
        "tags": ["steiniger", "author", "inspiration", "html"],
        "kind": "author_profile",
    },
    {
        "id": "steiniger-slashreboot",
        "title": "slashreboot.com",
        "url": "https://slashreboot.com",
        "local_candidates": [],
        "tags": ["steiniger", "author", "html"],
        "kind": "author_site",
    },
    {
        "id": "steiniger-orcid",
        "title": "ORCID 0009-0000-6069-4989",
        "url": "https://orcid.org/0009-0000-6069-4989",
        "local_candidates": [],
        "tags": ["steiniger", "author", "orcid"],
        "kind": "author_id",
    },
    {
        "id": "steiniger-eut-i",
        "title": "EUT I V10 — Entropic Universe EFT",
        "url": "https://doi.org/10.5281/zenodo.19654688",
        "local_candidates": [
            ROOT.parent / "mycelial-republic" / "vendor" / "steiniger_latest" / "EUT_I_V10.pdf",
            _SAFE_HOME()
            / "Documents"
            / "projects"
            / "mycelial-republic"
            / "vendor"
            / "steiniger_latest"
            / "EUT_I_V10.pdf",
            _SAFE_HOME()
            / "Documents"
            / "projects"
            / "worktrees"
            / "sovereign-mirror-scaffold"
            / "vendor"
            / "extracted"
            / "19654688 - EUT I V10"
            / "EUT_I_V10.pdf",
        ],
        "tags": ["steiniger", "paper", "eut", "physics", "pdf"],
        "kind": "paper",
    },
    {
        "id": "steiniger-eut-ii",
        "title": "EUT II V5",
        "url": "https://doi.org/10.5281/zenodo.19120992",
        "local_candidates": [
            _SAFE_HOME()
            / "Documents"
            / "projects"
            / "mycelial-republic"
            / "vendor"
            / "steiniger_latest"
            / "EUT_II_V5_19MAR2026.pdf",
            _SAFE_HOME()
            / "Documents"
            / "projects"
            / "worktrees"
            / "sovereign-mirror-scaffold"
            / "vendor"
            / "extracted"
            / "19120992 - EUT II V5"
            / "EUT_II_V5_19MAR2026.pdf",
        ],
        "tags": ["steiniger", "paper", "eut", "physics", "pdf"],
        "kind": "paper",
    },
    {
        "id": "steiniger-scalar-knots",
        "title": "Stability of Scalar Knots V2",
        "url": "https://doi.org/10.5281/zenodo.19617100",
        "local_candidates": [
            _SAFE_HOME()
            / "Documents"
            / "projects"
            / "mycelial-republic"
            / "vendor"
            / "steiniger_latest"
            / "Stability_of_Scalar_Knots_and_Spectral_Properties_of_Dirichlet_Minimizers_on_Pre_Geometric_Index_Sets.pdf",
        ],
        "tags": ["steiniger", "paper", "scalar_knot", "physics", "pdf"],
        "kind": "paper",
    },
    {
        "id": "steiniger-epgi",
        "title": "Engineering Persistent Geometric Identities",
        "url": "https://doi.org/10.5281/zenodo.20437461",
        "local_candidates": [],
        "tags": ["steiniger", "paper", "identity", "epgi", "pdf"],
        "kind": "paper",
    },
    {
        "id": "steiniger-crystallization",
        "title": "Crystallization of a Persistent Generative Lattice",
        "url": "https://doi.org/10.5281/zenodo.19600856",
        "local_candidates": [
            _SAFE_HOME()
            / "Documents"
            / "projects"
            / "mycelial-republic"
            / "vendor"
            / "steiniger_latest"
            / "Crystallization_of_a_Persistent_Generative_Lattice.pdf",
        ],
        "tags": ["steiniger", "paper", "lattice", "pdf"],
        "kind": "paper",
    },
    {
        "id": "steiniger-github-archive",
        "title": "slashrebootofficial/research_papers",
        "url": "https://github.com/slashrebootofficial/research_papers",
        "local_candidates": [
            _SAFE_HOME()
            / "Documents"
            / "projects"
            / "worktrees"
            / "sovereign-mirror-scaffold"
            / "vendor"
            / "steiniger_papers",
        ],
        "tags": ["steiniger", "archive", "github"],
        "kind": "archive",
    },
    {
        "id": "doc-constitution",
        "title": "CONSTITUTION.md",
        "url": "",
        "local_candidates": [
            _SAFE_HOME()
            / "Documents"
            / "projects"
            / "mycelial-republic"
            / "docs"
            / "CONSTITUTION.md",
        ],
        "tags": ["local", "constitution", "lessig", "markdown"],
        "kind": "local_doc",
    },
    {
        "id": "doc-scrum",
        "title": "SCRUM.md",
        "url": "",
        "local_candidates": [
            _SAFE_HOME() / "Documents" / "projects" / "mycelial-republic" / "docs" / "SCRUM.md",
        ],
        "tags": ["local", "scrum", "process", "markdown"],
        "kind": "local_doc",
    },
    {
        "id": "doc-agent-roadmap",
        "title": "AGENT_ROADMAP.md",
        "url": "",
        "local_candidates": [
            _SAFE_HOME()
            / "Documents"
            / "projects"
            / "mycelial-republic"
            / "docs"
            / "AGENT_ROADMAP.md",
        ],
        "tags": ["local", "roadmap", "markdown"],
        "kind": "local_doc",
    },
    {
        "id": "doc-steiniger-papers-map",
        "title": "STEINIGER_PAPERS.md",
        "url": "",
        "local_candidates": [
            _SAFE_HOME()
            / "Documents"
            / "projects"
            / "worktrees"
            / "sovereign-mirror-scaffold"
            / "docs"
            / "STEINIGER_PAPERS.md",
        ],
        "tags": ["local", "steiniger", "index", "markdown"],
        "kind": "local_doc",
    },
    {
        "id": "doc-zeitgeist",
        "title": "DIAGNOSTIC_ZEITGEIST.md",
        "url": "",
        "local_candidates": [
            _SAFE_HOME()
            / "Documents"
            / "projects"
            / "worktrees"
            / "sovereign-mirror-scaffold"
            / "docs"
            / "DIAGNOSTIC_ZEITGEIST.md",
        ],
        "tags": ["local", "zeitgeist", "markdown"],
        "kind": "local_doc",
    },
    {
        "id": "doc-manifesto",
        "title": "MANIFESTO.md",
        "url": "",
        "local_candidates": [
            _SAFE_HOME()
            / "Documents"
            / "projects"
            / "worktrees"
            / "sovereign-mirror-scaffold"
            / "docs"
            / "MANIFESTO.md",
        ],
        "tags": ["local", "manifesto", "markdown"],
        "kind": "local_doc",
    },
    {
        "id": "skill-strike-chord",
        "title": "strike-chord SKILL.md",
        "url": "",
        "local_candidates": [
            _SAFE_HOME() / ".grok" / "skills" / "strike-chord" / "SKILL.md",
        ],
        "tags": ["local", "skill", "chord", "markdown"],
        "kind": "skill",
    },
    {
        "id": "skill-operator-quixote",
        "title": "operator-quixote SKILL.md",
        "url": "",
        "local_candidates": [
            _SAFE_HOME() / ".grok" / "skills" / "operator-quixote" / "SKILL.md",
        ],
        "tags": ["local", "skill", "operator", "markdown"],
        "kind": "skill",
    },
    {
        "id": "doc-mag-readme",
        "title": "local_sovereign_agent README.md",
        "url": "",
        "local_candidates": [ROOT / "README.md"],
        "tags": ["local", "mag", "markdown"],
        "kind": "local_doc",
    },
    {
        "id": "strike-root",
        "title": "Strike framework root hash",
        "url": "https://x.com/NachoQuixotic/status/2071204776293908905",
        "local_candidates": [],
        "tags": ["strike", "root", "public"],
        "kind": "framework_seed",
    },
]


def _ensure_dirs() -> None:
    for p in (INGEST, LOCAL_DOCS, LOCAL_PAPERS, LOCAL_WEB):
        p.mkdir(parents=True, exist_ok=True)


def _copy_local(src: Path, dest_dir: Path, preferred_name: str | None = None) -> Path | None:
    if not src.is_file() and not src.is_dir():
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        pointer = dest_dir / f"{preferred_name or src.name}.PATH.txt"
        pointer.write_text(str(src.resolve()) + "\n", encoding="utf-8")
        return pointer
    name = preferred_name or src.name
    # keep extension from source
    if preferred_name and src.suffix and not preferred_name.endswith(src.suffix):
        name = f"{preferred_name}{src.suffix}"
    dest = dest_dir / name
    try:
        if not dest.is_file() or dest.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dest)
        return dest
    except OSError:
        return None


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def resolve_and_ingest(
    *,
    session_id: str,
    extra_refs: list[dict[str, Any]] | None = None,
    copy_local: bool = True,
) -> list[dict[str, Any]]:
    """
    Build full bibliography records with local copies + registry updates.
    Returns list of bib entries for the dossier.
    """
    _ensure_dirs()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    records: list[dict[str, Any]] = []
    catalog: dict[str, Any] = {}
    if CATALOG.is_file():
        try:
            catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            catalog = {}
    items = catalog.get("items") or {}

    def _ingest_one(meta: dict[str, Any]) -> dict[str, Any]:
        rid = meta["id"]
        local_src = None
        for cand in meta.get("local_candidates") or []:
            p = Path(cand)
            if p.exists():
                local_src = p
                break

        local_copy = None
        filename = None
        local_path_str = None
        file_hash = None
        if local_src and copy_local:
            kind = meta.get("kind") or ""
            if kind == "paper" or (local_src.suffix.lower() == ".pdf"):
                dest_dir = LOCAL_PAPERS
            elif kind in {"author_profile", "author_site"} or str(meta.get("url", "")).startswith(
                "http"
            ):
                dest_dir = LOCAL_WEB if not local_src.is_file() else LOCAL_DOCS
            else:
                dest_dir = LOCAL_DOCS
            if local_src.is_file():
                dest_dir = LOCAL_PAPERS if local_src.suffix.lower() == ".pdf" else LOCAL_DOCS
            preferred = rid.replace("/", "-")
            copied = _copy_local(local_src, dest_dir, preferred_name=preferred)
            if copied:
                local_copy = str(copied.resolve())
                filename = copied.name
                local_path_str = local_copy
                file_hash = _sha256_file(copied) if copied.is_file() else None
            else:
                local_path_str = str(local_src.resolve())
                filename = local_src.name
        elif local_src:
            local_path_str = str(local_src.resolve())
            filename = local_src.name if local_src.is_file() else local_src.name
            file_hash = _sha256_file(local_src) if local_src.is_file() else None

        # stub HTML for remote-only profiles so "where" is always listed
        url = meta.get("url") or ""
        html_stub = None
        if url and copy_local:
            safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", rid)[:80]
            stub = LOCAL_WEB / f"{safe}.html"
            if not stub.is_file():
                stub.write_text(
                    f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{meta.get('title')}</title></head>
<body>
<h1>{meta.get('title')}</h1>
<p>Local pointer for Mag ingest. Open remote source:</p>
<p><a href="{url}">{url}</a></p>
<p>id: {rid}</p>
<p>tags: {', '.join(meta.get('tags') or [])}</p>
</body></html>
""",
                    encoding="utf-8",
                )
            html_stub = str(stub.resolve())

        rec = {
            "id": rid,
            "title": meta.get("title"),
            "kind": meta.get("kind"),
            "tags": list(meta.get("tags") or []),
            "url": url or None,
            "filename": filename,
            "local_source": str(local_src.resolve()) if local_src else None,
            "local_copy": local_copy,
            "local_path": local_path_str or local_copy,
            "html_stub": html_stub,
            "file_sha256": file_hash,
            "session_id": session_id,
            "ingested_at": now,
            "where_to_find": _where_line(
                filename=filename,
                local_path=local_path_str or local_copy,
                url=url,
                html_stub=html_stub,
            ),
        }
        # registry append
        with REGISTRY.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        items[rid] = {k: rec[k] for k in rec if k != "session_id"}
        items[rid]["last_session_id"] = session_id
        items[rid]["last_seen"] = now
        return rec

    for meta in KNOWN_CORPUS:
        records.append(_ingest_one(meta))

    for extra in extra_refs or []:
        # map free-form extra into ingest
        url = extra.get("url") or ""
        ref = extra.get("ref") or extra.get("title") or url or "unknown"
        rid = "extra-" + hashlib.sha256(str(ref).encode()).hexdigest()[:12]
        meta = {
            "id": rid,
            "title": ref,
            "url": url,
            "local_candidates": [],
            "tags": list(extra.get("tags") or ["session_extra"]),
            "kind": extra.get("kind") or "extra",
        }
        # if ref looks like a local path
        p = Path(str(ref))
        if p.exists():
            meta["local_candidates"] = [p]
        records.append(_ingest_one(meta))

    catalog = {
        "schema": "mag_ingest_catalog.v1",
        "updated_at": now,
        "count": len(items),
        "items": items,
        "roots": {
            "ingest": str(INGEST),
            "local_docs": str(LOCAL_DOCS),
            "local_papers": str(LOCAL_PAPERS),
            "local_web": str(LOCAL_WEB),
            "registry": str(REGISTRY),
        },
    }
    CATALOG.write_text(json.dumps(catalog, indent=2), encoding="utf-8")

    # dossier bibliography view
    bib = []
    for r in records:
        bib.append(
            {
                "id": r["id"],
                "ref": r["title"],
                "note": r.get("where_to_find") or "",
                "kind": r.get("kind"),
                "tags": r.get("tags"),
                "url": r.get("url"),
                "filename": r.get("filename"),
                "local_path": r.get("local_path"),
                "local_copy": r.get("local_copy"),
                "html_stub": r.get("html_stub"),
                "file_sha256": r.get("file_sha256"),
                "where_to_find": r.get("where_to_find"),
            }
        )
    return bib


def _where_line(
    *,
    filename: str | None,
    local_path: str | None,
    url: str | None,
    html_stub: str | None,
) -> str:
    parts = []
    if filename:
        parts.append(f"file: {filename}")
    if local_path:
        parts.append(f"local: {local_path}")
    if url:
        parts.append(f"remote: {url}")
    if html_stub:
        parts.append(f"html_pointer: {html_stub}")
    return " | ".join(parts) if parts else "location unknown"


def file_url(path: str | None) -> str | None:
    """file:/// URL for PDF clickable local links (Windows-safe)."""
    if not path:
        return None
    p = Path(path)
    try:
        resolved = p.resolve()
    except OSError:
        resolved = p
    # reportlab Link wants URL; file URI
    s = resolved.as_posix()
    if re.match(r"^[A-Za-z]:", str(resolved)):
        # Windows: file:///C:/Users/...
        drive = str(resolved)[0]
        rest = str(resolved)[2:].replace("\\", "/")
        return f"file:///{drive}:{rest}"
    if s.startswith("/"):
        return f"file://{s}"
    return f"file:///{s}"
