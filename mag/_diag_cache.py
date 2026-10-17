import sys, json
sys.path.insert(0, r"c:\Users\ESTATE_USER\Documents\projects\local_sovereign_agent")
from models.providers import chat_provider
from mag.rib_cache import FROZEN_RIB

for i in (1, 2):
    r = chat_provider("z_ai", system=FROZEN_RIB,
                      user=f"Cache diagnostic call {i}. Reply with exactly: ok",
                      model="glm-4.7-flash", thinking=False, max_tokens=32, tier="T2")
    print(f"call{i} ok={r.get('ok')} err={str(r.get('error'))[:60]}")
    print("  usage=" + json.dumps(r.get("usage") or {}))
