## Finding — what your cell yields

The four operator-only gates (KEYS, spend, ONE STOP, operator GO) are documented as policy in `dashboard/claim_check.html` and `RTFM_20260904.md`, but lack corresponding code enforcement. Only `burn_gate.py` (promo hours) and `trust_gate.py` (content sanity) exist as implemented gates. The KEYS/spend/ONE STOP gates are policy declarations without code mechanisms.

## Evidence — what in the repo supports it (file/shape, no invention)

- `dashboard/static/claim_check.html:63`: "operator gate (KEYS / spend / ONE STOP / operator GO). The gate defers, not the lane."
- `docs/ref/RTFM_20260904.md:50`: "Only operator gates (KEYS/spend/ONE STOP) defer, and the card names the gate."
- `mag/burn_gate.py`: promo hours gate (one of four)
- `mag/trust_gate.py`: content sanity gate (one of four)
- Missing: no `keys_gate.py`, `spend_gate.py`, `one_stop_gate.py`, or `operator_go_gate.py`
- Law registry (`mag/law.py`) contains generic laws but no operator-specific gate laws

## Risk if wrong — what the audit breaks on if this is missed

Matthew Steiniger's EUT framework would identify this as a "ceremony vs enforcement" gap. The audit would question whether operator gates are security theater rather than functional constraints. The gap undermines claims about "code-as-law" governance and the verkle chain's integrity as a tamper-evident record.

## The act — the concrete prep step (file/spec/number)

Create `docs/ref/OPERATOR_GATES_SCHEMA.md` defining the missing gate interfaces with falsifiable test cases:

```markdown
# Operator Gates Schema

## Gate Interface Contract
Each gate MUST implement:
- `gate(task, context) -> {ok: bool, reason: str, evidence: dict}`
- `status() -> {schema: str, state: dict}`
- CLI: `python -m mag.{gate_name} check|status`

## Missing Gates
1. **keys_gate** - Validates task against operator's cryptographic key authority
2. **spend_gate** - Enforces budget/spending limits per lane/provider  
3. **one_stop_gate** - Implements the "one stop" build freeze mechanism
4. **operator_go_gate** - Operator override authorization

## Test Suite
- `test_keys_gate.py`: Verify key-based task authorization
- `test_spend_gate.py`: Validate budget enforcement
- `test_one_stop_gate.py`: Confirm freeze mechanism
- `test_operator_go_gate.py`: Test override protocols
```

## Falsifier — what would prove this wrong

A code search that reveals existing implementations of `keys_gate.py`, `spend_gate.py`, `one_stop_gate.py`, or `operator_go_gate.py` in the mag/ directory, or active enforcement of these gates in the swarm worker, fuel feed, or law enforcement systems.