"""Campaign Reader — browse generated adventures as readable narratives.

Usage:
  python -m mag.campaign_reader              # list all campaigns
  python -m mag.campaign_reader <id>          # read one campaign as markdown
  python -m mag.campaign_reader --all         # export all as markdown files
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

CAMPAIGNS_DIR = ROOT / "memory" / "campaigns"
EXPORT_DIR = ROOT / "memory" / "campaigns" / "readable"


def list_campaigns() -> list[dict]:
    """List all saved campaigns with summaries."""
    campaigns = []
    for cf in sorted(CAMPAIGNS_DIR.glob("*.json")):
        try:
            data = json.loads(cf.read_text(encoding="utf-8"))
            campaigns.append({
                "id": data.get("campaign_id", cf.stem),
                "quest": data.get("quest", "?"),
                "domain": data.get("domain", "?"),
                "party_size": len(data.get("party", [])),
                "encounters": len(data.get("encounters", [])),
                "villain": data.get("villain", "?")[:80],
                "ts": data.get("ts", ""),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return campaigns


def read_campaign(campaign_id: str) -> str:
    """Read a campaign as beautiful markdown narrative."""
    cf = CAMPAIGNS_DIR / f"{campaign_id}.json"
    if not cf.is_file():
        # Try partial match
        for f in CAMPAIGNS_DIR.glob("*.json"):
            if campaign_id in f.stem:
                cf = f
                break
        else:
            return f"Campaign '{campaign_id}' not found."

    data = json.loads(cf.read_text(encoding="utf-8"))

    lines = []
    lines.append(f"# {data.get('quest', 'Untitled Quest')}")
    lines.append(f"*Campaign {data.get('campaign_id', '?')}*")
    lines.append("")

    # Setting
    lines.append("## The Setting")
    lines.append(f"**{data.get('domain', 'Unknown Domain').replace('_', ' ').title()}**")
    lines.append("")
    lines.append(data.get("setting", "A realm of mystery and wonder."))
    lines.append("")

    # Villain & Quest
    lines.append("## The Threat")
    lines.append(f"**{data.get('villain', 'An unknown darkness.')}**")
    lines.append("")

    lines.append("## The Quest")
    lines.append(f"*Seek the {data.get('quest_item', 'artifact of power')}.*")
    lines.append("")

    # Party
    lines.append("## The Party")
    party = data.get("party", [])
    for i, p in enumerate(party):
        lines.append(f"### {p['class']} — {p['subclass']}")
        lines.append(f"*{p['alignment']}*")
        lines.append(f"> {p['catchphrase']}")
        lines.append(f"**Role:** {p['role']}")
        if i < len(party) - 1:
            lines.append("")

    lines.append("")
    lines.append("## The Journey")
    lines.append("")

    # Encounters
    encounters = data.get("encounters", [])
    for e in encounters:
        difficulty_marker = {"Easy": "[Easy]", "Medium": "[Medium]", "Hard": "[HARD]", "Deadly": "[DEADLY]"}.get(
            e.get("difficulty", "Medium"), "[?]"
        )

        lines.append(f"### {difficulty_marker} Encounter {e.get('number', '?')}: {e.get('title', 'Unknown')}")
        lines.append(f"*{e.get('difficulty', '?')}*")
        lines.append("")
        lines.append(e.get("description", "The path ahead is shrouded in mist."))
        lines.append("")

    # Bard passage
    bard = data.get("bard_passage", "")
    if bard and len(bard) > 20:
        lines.append("## The Bard's Telling")
        lines.append(f"*As recorded in the tapestry:*")
        lines.append("")
        lines.append(f"> {bard[:1000]}")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated {data.get('ts', '')}*")

    return "\n".join(lines)


def export_all():
    """Export all campaigns as readable markdown files."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    exported = 0
    for campaign in list_campaigns():
        cid = campaign["id"]
        md = read_campaign(cid)
        out_path = EXPORT_DIR / f"{cid}.md"
        out_path.write_text(md, encoding="utf-8")
        exported += 1
        print(f"  Exported: {out_path.name}")
    print(f"\n{exported} campaigns exported to {EXPORT_DIR}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--all":
            export_all()
        elif arg == "--list":
            campaigns = list_campaigns()
            print(f"\n{'ID':<20} {'Quest':<40} {'Party':<6} {'Encounters':<4}")
            print("-" * 75)
            for c in campaigns:
                print(f"{c['id']:<20} {c['quest'][:38]:<40} {c['party_size']:<6} {c['encounters']:<4}")
        else:
            print(read_campaign(arg))
    else:
        print("Usage: python -m mag.campaign_reader [--list|--all|<campaign_id>]")
        print(f"Campaigns directory: {CAMPAIGNS_DIR}")
