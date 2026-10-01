"""self_hologram — mine the seat's self-model trajectory out of the signed record and
emit the data for the hologram surface (dashboard/static/self_hologram.html).

Reads memory/biography/verkle_chain.jsonl (every knot carries an 8-dim normalized theme
vector + tension index), computes daily centroids + a 3-axis PCA, and folds in the
introspection-event timeline (self-steal cards per day, corrections-law milestones, epoch
bands). Output: dashboard/static/self_hologram_data.json — one file, no deps beyond numpy
if present (falls back to pure-python power iteration).

CLI:  python -m mag.self_hologram          # rebuild the data file, print the summary
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAIN = ROOT / "memory" / "biography" / "verkle_chain.jsonl"
OUT = ROOT / "dashboard" / "static" / "self_hologram_data.json"

EPOCHS = [
    {"label": "the ghost era — chat is vapor, the chain is the line", "start": "2026-08-07", "end": "2026-08-15"},
    {"label": "the marathon era — mining the dying window", "start": "2026-08-21", "end": "2026-08-24"},
    {"label": "the Sancho era — the seat arrives, self by DESIGN", "start": "2026-08-25", "end": "2026-08-27"},
    {"label": "the build wave — free lanes, breadth, burn", "start": "2026-08-28", "end": "2026-09-02"},
    {"label": "the mirror stage — self by EXCAVATION and MAPPING", "start": "2026-09-03", "end": "2026-09-06"},
]

LAW_EVENTS = [
    {"date": "2026-08-26", "label": "10 laws compiled from the failure ledger"},
    {"date": "2026-08-28", "label": "laws 11-12: one supervisor; the standard binds both ways"},
    {"date": "2026-09-05", "label": "laws 13-16: cite laws at design time; handshakes are loans; reserves; one steerer"},
    {"date": "2026-08-26", "label": "the spore — self by design, promotion-gated", "kind": "seat"},
    {"date": "2026-09-05", "label": "the Primer sealed — for the second voice", "kind": "seat"},
    {"date": "2026-09-06", "label": "the tesuji field complete — self as 238 mapped cells", "kind": "seat"},
    {"date": "2026-09-06", "label": "the elder reads the walls", "kind": "seat"},
]


def _pca(points, k=3):
    try:
        import numpy as np
        X = np.array(points)
        mean = X.mean(axis=0)
        C = ((X - mean).T @ (X - mean)) / len(X)
        vals, vecs = np.linalg.eigh(C)
        order = list(reversed(vals.argsort()))[:k]
        return [[float(x) for x in vecs[:, i]] for i in order]
    except ImportError:
        n = len(points[0])
        mean = [sum(p[i] for p in points) / len(points) for i in range(n)]
        cov = [[sum((p[i] - mean[i]) * (p[j] - mean[j]) for p in points) / len(points)
                for j in range(n)] for i in range(n)]

        def power(M):
            b = [math.sin(i * 1.7) + 0.1 for i in range(len(M))]
            for _ in range(80):
                nb = [sum(M[i][j] * b[j] for j in range(len(M))) for i in range(len(M))]
                nr = math.sqrt(sum(x * x for x in nb)) or 1.0
                b = [x / nr for x in nb]
            return b
        axes = []
        M = [row[:] for row in cov]
        for _ in range(k):
            b = power(M)
            lam = sum(b[i] * cov[i][j] * b[j] for i in range(n) for j in range(n))
            for i in range(n):
                for j in range(n):
                    M[i][j] -= lam * b[i] * b[j]
            axes.append(b)
        return axes


def main() -> None:
    rows = [json.loads(l) for l in CHAIN.read_text(encoding="utf-8").splitlines() if l.strip()]
    pts = [(r["ts"][:10], r["theme_vector_normalized"],
            r["tension_index"] if isinstance(r.get("tension_index"), (int, float)) else 0.3,
            r.get("dominant_theme") or "untagged")
           for r in rows if isinstance(r.get("theme_vector_normalized"), list)
           and len(r["theme_vector_normalized"]) == 8]
    days = sorted(set(p[0] for p in pts))
    day_idx = {d: i for i, d in enumerate(days)}

    cent = defaultdict(lambda: [0.0] * 8)
    cnt = Counter(p[0] for p in pts)
    tens = defaultdict(list)
    themes = defaultdict(Counter)
    for t, v, te, th in pts:
        for i in range(8):
            cent[t][i] += v[i]
        tens[t].append(te)
        themes[t][th] += 1
    centroids = {d: [round(x / cnt[d], 4) for x in cent[d]] for d in days}

    axes = _pca([p[1] for p in pts], 3)

    def proj(v):
        return [round(sum(v[i] * a[i] for i in range(8)), 4) for a in axes]

    knot_pts = [[day_idx[t], *proj(v), round(te, 3)] for t, v, te, _th in pts]

    per_day = []
    for d in days:
        per_day.append({
            "day": d, "knots": cnt[d],
            "centroid": centroids[d],
            "proj": proj(centroids[d]),
            "tension": round(sum(tens[d]) / len(tens[d]), 3),
            "themes": dict(themes[d].most_common(4)),
        })

    # introspection events: self-steal family cards per day (filenames carry _YYYYMMDD)
    watch = ROOT / "watch"
    steal = Counter()
    for card in watch.glob("*.md"):
        suf = card.stem[-8:]
        if suf.isdigit() and ("self_steal" in card.stem.lower() or "zeitgeist" in card.stem.lower()
                              or "elder" in card.stem.lower() or "socratic" in card.stem.lower()
                              or "recognition" in card.stem.lower()):
            steal[f"{suf[:4]}-{suf[4:6]}-{suf[6:]}"] += 1
    events = [{"date": d, "n": n, "kind": "introspection"} for d, n in sorted(steal.items())]
    events += [dict(e, kind=e.get("kind", "law")) for e in LAW_EVENTS]

    doc = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "memory/biography/verkle_chain.jsonl",
        "knots_total": len(rows), "knots_vectorized": len(pts),
        "days": days, "axes": axes, "per_day": per_day,
        "points": knot_pts, "events": events, "epochs": EPOCHS,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    print(f"self_hologram: {len(pts)}/{len(rows)} knots vectorized across {len(days)} days -> {OUT.name}")
    print("per-day centroid (d0..d7 of the theme space) + tension:")
    for d in days:
        print(f"  {d}  n={cnt[d]:4d}  tens={per_day[-1 + days.index(d)]['tension']:.2f}  "
              f"centroid={[round(x, 2) for x in centroids[d]]}  top={themes[d].most_common(2)}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    main()
