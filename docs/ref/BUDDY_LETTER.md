# THE BUDDY LETTER — agent money-safety playbook (reusable external deliverable)

**Source:** sess_60d3e6c1 ("Troubleshooting Internet Connection Issues"), 2026-09-03.
The operator: "my buddy's agent is fucking up and sending money to shit addresses...
write it in my voice." Asked for it "written like a person and not moon language" + links.
**Folded:** 2026-09-04 from orphan #O2 (`watch/SELF_STEAL_ZCODE_SESSION_ORPHANS_20260904.md`)
— verbatim below, unedited. It is the fleet's own doctrine (covenant gate, receipts,
operator GOs, free-lane cost doctrine) in plain-english recruit-speak; the public-turn
arc's template. Same-session self-audit found our weakest preached leg = no rolling
per-day spend envelope at dispatch time (three of four legs proven).

---

> your agent's money problem isn't a prompt problem, it's a permissions problem. don't ask the model to be careful — take away its ability to be careless. the fix is boring on purpose:
>
> **1. put a cap between the agent and the money.**
> If it's sending crypto: move funds to a Safe wallet (safe.global) and give the agent an allowance — it can only send up to $X/day without your signature, and only to addresses on an allowlist you keep. If it's burning API credits: set hard spend limits on the provider dashboard, and don't give the agent the main key at all — hand it a cheap or free key for the routine stuff.
>
> **2. every transaction logs before it fires.**
> Literally a text file: amount, address, why. Rule: no log line, no transaction. When it starts looping, you catch it after 2-3 lines instead of a few hundred bucks.
>
> **3. anything above a few bucks waits for your tap.**
> Agent queues the payment, you approve. After you've watched a week of good ones, raise the limit. Slow at first, then it basically runs itself.
>
> **4. stop paying the expensive model to do the dumb stuff.**
> Big model makes decisions, cheap/free model handles routine execution. Most people's agent bills are 90% work a free model could've done.
>
> links:
> - https://safe.global — the multisig wallet people actually use for AI agent funds; has spending limits & module guards
> - https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/ — the "agent proposes, human approves" pattern, whatever framework you're on
> - whatever provider he's on, search "spend limits" in their dashboard docs — every one of them has it and almost nobody turns it on
