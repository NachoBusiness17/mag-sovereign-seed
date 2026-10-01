"""One-shot: fire deepseek-flash on the fish->horse reinterpretation (Viz Lab attempt 2)."""
import sys, json
sys.path.insert(0, ".")
from models.providers import chat_provider
from mag.ractor_vessels import PROVIDER

FISH = open("dashboard/static/viz_spore_fish.html", encoding="utf-8").read()

SYSTEM = ("You are a creative parametric coder in the lineage of tiny honest art tools: "
          "one canvas, closed-form math, no assets, no libraries. Output ONE complete "
          "self-contained HTML file and NOTHING else - no markdown fences, no commentary, "
          "no explanation. Start with <!DOCTYPE html>.")

USER = f"""Here is viz_spore_fish.html - "the Tsubuyaki spore", a parametric math-creature
(10,000 points per frame from a closed-form equation, 36 lines, dark warm background):

{FISH}

Reinterpret it: THE SAME PARAMETRIC SPIRIT, but a HORSE RUNNING.
Requirements:
- A horse in full gallop, built from the same kind of closed-form parametric point/line math
  (no images, no sprite sheets, no external anything).
- The gallop must visibly CYCLE: leg phases (extension/compression), body bounce and pitch,
  mane and tail streaming. A viewer should say "that's a horse running" within 2 seconds.
- Keep the ~40-line-class spirit and the lab aesthetic: dark background #0a0806, warm
  foreground #efe3d0, one canvas, one caption div.
- Caption div text: 'The spore, re-run - <b>attempt 2</b>. The fish was beautiful and wrong;
  attempt 2 is the organism in motion - galloping toward the Republic it was supposed to draw.'
- Title: 'Spore Form - the horse (attempt 2)'
- Same canvas size 520x520.
Output the complete HTML file only."""

resp = chat_provider(PROVIDER, SYSTEM, USER, temperature=0.85, tier="T2",
                     session_id="viz-horse-attempt2")
err = resp.get("error")
if err:
    print("ERROR:", err); sys.exit(1)
text = resp.get("content") or resp.get("text") or ""
if not text:
    print("KEYS:", list(resp.keys())); print(str(resp)[:400]); sys.exit(1)
# strip fences if the model added them
text = text.strip()
if text.startswith("```"):
    text = text.split("```")[1]
    if text.startswith("html"): text = text[4:]
text = text.strip()
if not text.lower().startswith("<!doctype"):
    print("MODEL DID NOT RETURN CLEAN HTML; head:"); print(text[:300]); sys.exit(1)
open("dashboard/static/viz_horse_run.html", "w", encoding="utf-8").write(text)
print("SAVED dashboard/static/viz_horse_run.html  bytes:", len(text))
print("model:", resp.get("model", "?"))
