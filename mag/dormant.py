"""dormant: ONE reader of the providers.yaml dormant flag for mag/ lane lists.

Law (mag/doctor.py:607): `dormant: true` is a DECLARED state, never probed, never
alarmed. B2-204 extended the law to routing (models/quota.py: a dormant lane is
never pickable at the quota seam); B2-133 extends it to the mag/ hardcoded lane
lists and the cost view, which kept routing or pricing cerebras after B2-36 set it
dormant (card-gated 30-day trial, chat 402 no-credit). Operator GO flips the flag
in configs/providers.yaml and every gate wired here restores the lane with no code
edit (each provider block carries its own GO note).

Consumers gated (B2-133): mag/fuel_feed.py FREE_LANES, mag/rotation_harness.py
LANES, mag/lane_salon.py WITNESSES, mag/quorum_window.py FREE_LANES,
mag/research_fanout.py LANES (host match; its lane ids are lane-local like
cerebras-oss), mag/cost_truth.py _PROVIDER_FREE_OR_CREDIT, mag/free_tier.py
FREE_SURFACES.

Failure semantics: a config that cannot be read yields an EMPTY dormant set.
Missing evidence never invents dormancy, and a dead lane still down-reports
honestly at call time (the fuel_feed/salon/quorum contracts).

Receipt: watch/inbox/burn_wave_20260926/B2_133_cerebras_purge_20260926.md
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

try:
    from config import ROOT
except Exception:  # noqa: BLE001
    ROOT = Path(__file__).resolve().parent.parent

PROVIDERS_YAML = ROOT / "configs" / "providers.yaml"


def _host(url: object) -> str | None:
    try:
        return (urlsplit(str(url)).hostname or "").lower() or None
    except ValueError:
        return None


def dormant_providers(path: Path | None = None) -> dict[str, dict]:
    """provider id -> block, for every providers.yaml provider carrying dormant: true."""
    p = Path(path) if path else PROVIDERS_YAML
    try:
        import yaml

        cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001: unreadable config must not invent dormancy
        return {}
    out: dict[str, dict] = {}
    for pid, pcfg in (cfg.get("providers") or {}).items():
        if isinstance(pcfg, dict) and pcfg.get("dormant"):
            out[str(pid)] = pcfg
    return out


def dormant_ids(path: Path | None = None) -> set[str]:
    """Provider ids carrying dormant: true (match a lane entry's provider id)."""
    return set(dormant_providers(path))


def dormant_hosts(path: Path | None = None) -> set[str]:
    """Hostnames of the dormant providers' base_url (match raw-URL lane lists)."""
    hosts: set[str] = set()
    for pcfg in dormant_providers(path).values():
        h = _host(pcfg.get("base_url"))
        if h:
            hosts.add(h)
    return hosts


def is_dormant(provider_id: str | None = None, base_url: str | None = None,
               path: Path | None = None) -> bool:
    """True if this provider id, or the host of this raw base_url, is declared dormant."""
    d = dormant_providers(path)
    if provider_id and str(provider_id) in d:
        return True
    if base_url:
        h = _host(base_url)
        if h and any(_host(pc.get("base_url")) == h for pc in d.values()):
            return True
    return False
