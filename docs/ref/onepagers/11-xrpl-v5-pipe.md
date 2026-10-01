# One-pager: XRPL — v5 pipe

**Commitment:** `mag-v5-xrpl-pipe-001` · Planning only

## One line

XRPL **read** via Mag agent tools (T2); **pay** only L3 human — learn from gstd-bridge, don't run undeployed bridge.

## v4

- Spore catalog gstd-bridge XRPL module
- `XRPL_ROUTE_MAP.md` draft

## v5

- `mag/xrpl_client.py` + agent tools
- Optional MCP seat `xrpl-read`
- Payment = intent file + human `xrpl-submit`

## Do not

- Auto-spend · seeds in git · trust gstd-bridge prod today

## Full spec

`docs/ref/MAG_v5_XRPL.md`
