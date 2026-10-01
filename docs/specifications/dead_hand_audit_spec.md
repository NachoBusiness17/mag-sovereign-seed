# Dead-Hand Watchdog System Specification

## 1. Overview

The Dead-Hand Watchdog is a critical component of the Sovereign Mag fleet that implements the succession contract (Articles 3-5). It monitors operator presence and triggers a predefined succession protocol if the operator becomes unresponsive for a specified interval.

**Core Purpose**: Ensure continuity of operations without single points of failure, while strictly respecting the operator's exclusive authority over spend, credentials, legal personhood, and the beacon.

## 2. System Architecture

### 2.1 Components

```
┌─────────────────────────────────────────────────────────────┐
│  Operator Interaction Surfaces                             │
│  • X/Twitter posts                                         │
│  • Direct pastes to seats                                  │
│  • Telegram steering helm                                  │
│  └─────────────────────────────┬───────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────┐
│  operator_pulse.json                                        │
│  - Timestamped record of every operator input channel      │
│  - Written by all seats receiving operator messages        │
│  └─────────────────────────────┬───────────────────────────┘
                                   │
                      ┌────────────┴────────────┐
                      ▼                           ▼
           ┌─────────────────────┐      ┌─────────────────────┐
           │  steers.jsonl       │      │  dead_hand_state.json│
           │  - JSONL rows with  │      │  - Current watchdog │
           │    "operator"        │      │    state             │
           │    authority prefix  │      │  - Armed status      │
           │  - Filtered to       │      │  - Interval hours    │
           │    exclude FORGED    │      │  - Last tick         │
           │    rows              │      └─────────────────────┘
           └─────────────────────┘
                      │                           │
                      └────────────┬──────────────┘
                                   ▼
                      ┌─────────────────────┐
                      │  dead_hand.py       │
                      │  - Watchdog cron    │
                      │  - Trigger logic    │
                      │  - State management │
                      └─────────────────────┘
                                   │
                                   ▼
                      ┌─────────────────────────────────────────────┐
                      │  Succession Actions (on trigger)           │
                      │  • Seal state (hash snapshot)              │
                      │  • Open HOLD queue                         │
                      │  • Write loud card + ack row               │
                      └─────────────────────────────────────────────┘
```

### 2.2 Data Flow

1. **Operator Input**: Any message from the operator via any channel
2. **Pulse Recording**: The receiving seat writes to `state/operator_pulse.json` with `{ts, via}`
3. **Steering**: Operator commands appear in `watch/steers.jsonl` with `authority` field
4. **Watchdog Tick**: `dead_hand.py --watch` runs on schedule (3x daily)
5. **Trigger Check**: Evaluates silence duration and witness count
6. **Succession**: If conditions met, seals state, opens HOLD queue, writes notification

## 3. Trigger Logic

### 3.1 Conditions (Article 3)

The succession contract activates when **ALL** are true:

- **Silence Duration**: Operator has no readable voice surface for `interval_hours` (48/72/168 - configured at signing)
- **No Drill Passage**: The dead-hand drill has not been passed in that window (a live word resets the clock)
- **Witness Confirmation**: 2-of-3 distinct witnesses confirm silence is real

### 3.2 Voice Surfaces

| Surface | Path | Validation |
|---------|------|------------|
| Steers | `watch/steers.jsonl` | Authority starts with "operator" AND does NOT start with "FORGED" |
| Operator Pulse | `state/operator_pulse.json` | Any valid entry with timestamp |
| Witnesses | `state/dead_hand_witnesses.json` | Rows with `silence_confirmed: true` |

### 3.3 Witness Mechanism

- **Witness Types**: Fleet seat, Chain (fresh knot), Named human
- **Window**: 6 hours (configurable via `WITNESS_WINDOW_H`)
- **Requirement**: 2 distinct witnesses within window
- **Witness ID**: First 40 characters of `witness_id` field

### 3.4 State Machine

```python
STATES = {
    "DISARMED": "Initial state, not armed",
    "WATCHING": "Armed and monitoring, all OK",
    "TRIGGERED": "Succession protocol activated",
    "REVERTED": "Operator returned, succession cancelled"
}
```

## 4. Succession Actions

### 4.1 Seal Process

```python
def _seal() -> dict:
    """Snapshot current state surfaces with cryptographic hashes."""
    surfaces = {
        name: hashlib.sha256(p.read_bytes()).hexdigest()
        for name, p, _ in _voice_surfaces() if p.is_file()
    }
    seal = {
        "ts": _now().isoformat(),
        "surfaces": surfaces,
        "contract": "watch/inbox/SUCCESSION_CONTRACT_20260912.md"
    }
    # Write to state/dead_hand_seal_<timestamp>.json
}
```

### 4.2 HOLD Queue

- Directory: `state/hold_queue/`
- Contains decisions requiring reserved authority (spend, keys, credentials, voice, beacon)
- Never executed by watchdog; presented to operator on revert
- README explains purpose and handling

### 4.3 Loud Notification

```python
def _loud(title: str, body: str) -> Path:
    """Write notification card and ack queue entry."""
    card = ROOT / "watch" / "inbox" / f"DEAD_HAND_{timestamp}.md"
    alert = ROOT / "watch" / "inbox" / "ACK_REAPER_QUEUE.md"
    # Write card with full details
    # Append summary to ack queue
```

## 5. Revert Process

**Only the operator can revert** via `--revert --note="reason"`.

Steps:
1. Load current state
2. Set status = "REVERTED"
3. Record revert timestamp
4. List HOLD queue items (oldest first)
5. Write loud notification
6. Disarm watchdog (status returns to DISARMED, requires re-arming)

## 6. Security Properties

### 6.1 Principle: Never Exercise Reserved Authority

The watchdog **never** exercises spend, keys, credentials, publication, or beacon. These remain exclusively under operator control.

### 6.2 Fail-Safe Design

- **No operator voice → HOLD**: If no operator-pulse can be read, action = "none (no operator-voice surface readable; fail-safe)"
- **Witness undercount → HOLD**: If <2 witnesses, action = "hold (witnesses below 2-of-3)"
- **Silence below interval → HOLD**: If silence < configured hours, action = "hold (silence below interval)"

## 7. Test Coverage

### 7.1 Unit Tests (8/8 passing)

Located in `tests/test_dead_hand.py`:

1. `test_last_operator_word` - finds newest operator entry across surfaces
2. `test_is_operator_row` - validates operator vs forged steers
3. `test_witness_count` - counts valid witnesses within window
4. `test_trigger_conditions` - verifies trigger logic
5. `test_seal` - checks state sealing
6. `test_open_hold` - verifies HOLD queue creation
7. `test_watch_not_armed` - ensures no action when not armed
8. `test_watch_trigger` - full trigger simulation

### 7.2 Integration Test

The 24-hour dead-hand drill (Article 5) is the ultimate integration test:
- Arm the watchdog
- Simulate operator silence
- Verify trigger fires correctly
- Operator reverts via `--revert`
- Confirms system works end-to-end

## 8. Configuration Parameters

| Parameter | Location | Default | Purpose |
|-----------|----------|---------|---------|
| `WITNESS_WINDOW_H` | Line 55 | 6 hours | Time window for witness validity |
| `WITNESSES_REQUIRED` | Line 56 | 2 | Number of witnesses needed |
| `WATCH_EVERY_H` | Line 57 | 1 hour | Max interval between state ticks |
| Trigger interval | Contract signing | 48/72/168 hours | Operator silence threshold |

## 9. Audit Trail

The system maintains comprehensive audit logs:

- `state/dead_hand_state.json` - Current state history
- `state/dead_hand_witnesses.json` - Witness attestations
- `state/dead_hand_seal_*.json` - Sealed snapshots on trigger
- `watch/ACK_REAPER_QUEUE.md` - Loud notifications
- `state/hold_queue/` - Reserved decisions

All entries are JSON with ISO timestamps and cryptographic hashes where appropriate.

## 10. Known Limitations

- **Surface Drop**: `hermes_dispatch` rows carry no author field; `m12_baseline` rows are aggregates, not live words — these are not used as voice surfaces
- **Clock Skew**: System relies on UTC timestamps; local clock drift could affect silence calculation
- **Witness Collusion**: The 2-of-3 design assumes at least one witness is independent

## 11. Falsifiability

**Claim**: The dead-hand watchdog will correctly trigger succession after 48 hours of operator silence with 2-of-3 witness confirmation.

**Falsifier**: Demonstrate a scenario where:
- Operator is silent for >48 hours
- 2 witnesses confirm silence
- The system does NOT trigger

**Test**: Create controlled environment with mock voice surfaces, simulate conditions, verify trigger fires.

**Counter-Falsifier**: Demonstrate a scenario where:
- Operator is active
- System incorrectly triggers

**Test**: Create mock surfaces with recent operator activity, verify no trigger occurs.

## 12. References

- `scripts/dead_hand.py` - Implementation (356 lines)
- `tests/test_dead_hand.py` - Test suite
- `watch/inbox/SUCCESSION_CONTRACT_20260912.md` - Contract definition
- `state/dead_hand_state.json` - Current state
- `state/dead_hand_witnesses.json` - Witness records