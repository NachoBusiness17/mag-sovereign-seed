# Ontology Compiler - Extraction Engine (Phase 1)
# Purpose: Parse session logs, extract failure points and surprising successes, cluster them.

INPUT_FILES = ["memory/percolator/explore.jsonl", "memory/thinking/app_reasoning.jsonl"]
OUTPUT_DIR = "memory/ontology/candidates"

CATEGORIES = [
    "missing_data",
    "ambiguous_language",
    "conflicting_rules",
    "stale_knowledge",
    "wrong_model",
]

def classify(event):
    status = event.get("status", "")
    if status in ("FAILED", "TIMEOUT", "ERROR"):
        return "failure"
    if event.get("kind") == "milestone":
        return "success"
    return "neutral"

def cluster(events):
    clusters = {c: [] for c in CATEGORIES}
    for ev in events:
        cat = ev.get("cluster", "neutral")
        if cat in clusters:
            clusters[cat].append(ev)
    return clusters

def propose(cluster_events):
    candidates = []
    for ev in cluster_events:
        candidates.append({
            "seq": ev.get("seq"),
            "cluster": ev.get("cluster"),
            "candidate": ev.get("detail", "")[:200],
            "confidence": 0.5,
            "expected_improvement": "tbd",
        })
    return candidates

def main():
    print("Ontology Compiler extract engine - Phase 1 skeleton")
    print("Reads explore.jsonl + app_reasoning.jsonl")
    print("Outputs candidate diffs to memory/ontology/candidates/")

if __name__ == "__main__":
    main()