# CACHE CRAFT LAWS — the 6 laws, extracted from SELF_STEAL_SHAPE_TRAIN_20260903 (2026-09-06)

Decision-acted (board ruling: window — extract to docs/ref). Full text in the
consult transcript, watch/salon_receipts/. Source verified line-by-line.

1. Pad shared prefixes ≥1100 tokens; smoke-test `cache_creation_input_tokens > 0` on every first call.
2. Breakpoints: stable-to-volatile left→right; system/tools | brief | ledger; tail dead last. Tail before a breakpoint = 7 cache entries instead of 1.
3. Break-even: N_min = (w−r)/(1−r) ≈ 2 uses in-TTL; 7-shape fan-out = 1 write + 6 reads ≈ 74% prefix savings. **No keep-warm pings** for bursty salons — let it expire, eat one write.
4. Silent killers ranked: trailing whitespace, timestamps above the breakpoint, JSON key-order drift, unpinned model aliases, tool-schema regeneration, NFC/NFD unicode, mid-deploy breakpoint moves. Store prefixes as checksummed committed files; diff bytes sent, not source.
5. Fold loop: breakpoint at last round's ledger end, append-only ledger, corrections are new entries never edits — O(n²)→O(n), ~86% off at 7 rounds. Append-only and cache-friendly: same requirement, two hats.
6. Per-lane tagging: cache economics proven on Anthropic are Unproven on GLM/DeepSeek/ollama until measured.

Cites: SELF_STEAL_SHAPE_TRAIN_20260903, ZERO_BACKREF_TRIAGE_20260905
Decision: none (extracted + filed in-turn, 2026-09-06)
