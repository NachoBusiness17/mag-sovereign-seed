"""mag/hydro_xor_sim.py — deterministic two-bucket hydraulic XOR simulator.

Sim side of falsifier section 4.5 for receipt C18_HYDRAULIC_THIRD_CHANNEL ("BOTH VALVES
SIPHON", pulsed two-bucket XOR). Encodes the in-MUD hydraulic laws of
memory/game_modules/water_computer.v1.json ("The Clear Pipes"):

  - "Engine owns heights." States are continuous levels (mL) integrated over fixed dt.
  - "Closed, nothing flows. Open, gravity takes a mark each wait." One mark = MARK_ML per
    TICK_S-second open valve (one Pump-Janitor tick).
  - "Check valve holds. I will not fill OUT from a bucket." One-way flow; no WORK->SOURCE
    term exists (backflow_occurred is an assertion channel, false by construction).
  - "Open only after water has arrived, or both valves siphon." The crest siphon on WORK is
    the NOT(A AND B): it primes at CREST_ML and dumps to waste until the intake breaks.
  - DISPUTED anti-cheat: output arrives only through pipes; there is no pour API.

Sim passing is NOT substrate evidence (falsifier section 4.5); it fixes the predictions the
water is graded against. The graded contract is p_report() against C18 Appendix B (P1-P8)
and the read bands fixed in C18 section 4.

Skew semantics (P7): the trial window is fixed -- valves open 0 and |skew_s| seconds apart
and BOTH close at t = TICK_S, so skew shortens the trailing valve's pulse. This is the only
reading under which C18's P7 is satisfiable: with per-valve 60 s pulses, the trailing valve
adds ~8 mL after the siphon breaks and the (1,1) residual lands ~37 mL, outside the
pre-registered [0, 30] band. Closing-time skew matters as much as opening-time skew; the
physical protocol must pin both (see C18 M7).

Draft by stealth/union-alpha (OpenRouter, $0, 2026-09-16); edited and corrected by the
ZCode editor seat (P8 drain slope, P5 single-input filter, all_hold, series sampling,
inflow limiting, fixed-window skew). Stdlib only; deterministic float ops.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- params


@dataclass(frozen=True)
class SimParams:
    """Physical constants fixed by C18 before any water runs."""

    TICK_S: float = 60.0          # one Pump-Janitor tick; trial window (both valves close here)
    MARK_ML: float = 100.0        # "gravity takes a mark each wait" (per open line, calibrated)
    CREST_ML: float = 150.0       # siphon crest height (1.5 marks)
    SIPHON_RATE_ML_S: float = 20.0  # dump rate while primed (C18: "20+ mL/s out once primed")
    INTAKE_BREAK_ML: float = 5.0  # level at which the V-notch intake breaks the siphon
    T_READ: float = TICK_S + 90.0  # C18: read W at t_read = T + 90 s
    S0_ML: float = 300.0          # "the only full tank at dawn" (>= 3 marks)
    DT_S: float = 0.05            # sub-step

    # read bands fixed in C18 section 4 (pre-registered)
    BIT1_LO: float = 70.0
    BIT1_HI: float = 130.0
    BIT0_HI: float = 30.0

    def line_rate_ml_s(self) -> float:
        return self.MARK_ML / self.TICK_S


# --------------------------------------------------------------------------- result


@dataclass
class SimResult:
    case: Tuple[int, int]
    w_at_t_read: float
    s_at_t_read: float
    waste_ml: float
    primed: bool
    prime_time_s: Optional[float]
    max_w_ml: float
    min_crossing_ml: Optional[float]   # level at the instant the crest was crossed
    post_prime_drain_rate_ml_s: Optional[float]  # |least-squares slope| over the primed drain
    s_monotonic_decreasing: bool
    backflow_occurred: bool            # assertion channel; false by construction
    mass_residual_ml: float            # S0 + W0 - (S_end + W_end + waste)
    w_series: List[Tuple[float, float]] = field(default_factory=list)
    bit: str = "FAIL"                  # "0" | "1" | "FAIL"
    read_band: str = ""


# --------------------------------------------------------------------------- engine


def _read_band(level: float, p: SimParams) -> Tuple[str, str]:
    """C18 pre-registered read bands: bit 1 = [70,130]; bit 0 = [0,30]; else FAIL."""
    if p.BIT1_LO <= level <= p.BIT1_HI:
        return "1", "bit1 [70,130]"
    if 0.0 <= level <= p.BIT0_HI:
        return "0", "bit0 [0,30]"
    if p.BIT0_HI < level < p.BIT1_LO:
        return "FAIL", "FAIL 31-69 (under-delivery / partial dump)"
    if p.BIT1_HI < level < 170.0:
        return "FAIL", "FAIL 131-169 (siphon primed but did not break)"
    return "FAIL", "FAIL >=170 (siphon never primed)"


def _lsq_slope(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    var = sum((x - mx) ** 2 for x in xs)
    return cov / var if var > 0 else 0.0


def simulate(a: int, b: int, *, skew_s: float = 0.0, params: SimParams | None = None,
             noise_seed: int | None = None) -> SimResult:
    """One trial. a/b in {0,1}; valves open 0 and |skew_s| s apart, both close at TICK_S.

    noise_seed=None (default) -> bit-for-bit deterministic. With a seed, per-sub-step
    inflow noise (u in [-0.03, 0.03] per open line, drawn A then B) and a +/-2 mL sensor
    noise on w_at_t_read are applied via a dedicated random.Random(seed).
    """
    p = params or SimParams()
    if a not in (0, 1) or b not in (0, 1):
        raise ValueError("inputs must be 0 or 1")
    rng = random.Random(noise_seed) if noise_seed is not None else None

    n_steps = int(round(p.T_READ / p.DT_S))
    a_open_t = 0.0 if skew_s >= 0 else abs(skew_s)   # signed skew: positive = B trails,
    b_open_t = abs(skew_s) if skew_s >= 0 else 0.0   # negative = A trails; both close TICK_S

    s = p.S0_ML
    w = 0.0
    waste = 0.0
    primed = False
    prime_time_s: Optional[float] = None
    min_crossing_ml: Optional[float] = None
    max_w_ml = 0.0
    drain_ts: List[float] = []
    drain_ws: List[float] = []
    w_series: List[Tuple[float, float]] = []
    s_monotonic = True
    backflow = False
    s_prev = s

    rate = p.line_rate_ml_s() * p.DT_S  # mL delivered per open line per sub-step
    for i in range(n_steps + 1):
        t = i * p.DT_S
        inflow = 0.0
        if a and a_open_t <= t < p.TICK_S:
            step = min(rate, s)
            if rng is not None:
                step *= 1.0 + rng.uniform(-0.03, 0.03)
            inflow += step
        if b and b_open_t <= t < p.TICK_S:
            step = min(rate, s - inflow)
            if rng is not None:
                step *= 1.0 + rng.uniform(-0.03, 0.03)
            inflow += step

        s -= inflow
        w += inflow

        if not primed and w >= p.CREST_ML:
            primed = True
            prime_time_s = t
            min_crossing_ml = w
        max_w_ml = max(max_w_ml, w)

        if primed:
            out = min(p.SIPHON_RATE_ML_S * p.DT_S, w)
            w -= out
            waste += out
            drain_ts.append(t)
            drain_ws.append(w)
            if w <= p.INTAKE_BREAK_ML:
                primed = False  # V-notch break; cannot re-prime below the crest

        if i % 20 == 0:  # sample every 1.0 s
            w_series.append((t, w))
        if s > s_prev + 1e-12:
            backflow = True  # only a WORK->SOURCE term could do this; none exists
        s_monotonic = s_monotonic and s <= s_prev + 1e-12
        s_prev = s
        if w < -1e-9:
            backflow = True

    w_phys = max(w, 0.0)
    mass_residual_ml = p.S0_ML - (s + w_phys + waste)
    w_at_t_read = w_phys + (rng.uniform(-2.0, 2.0) if rng is not None else 0.0)
    drain_rate = -_lsq_slope(drain_ts, drain_ws) if len(drain_ts) >= 2 else None

    bit, band = _read_band(w_at_t_read, p)
    return SimResult(
        case=(a, b), w_at_t_read=w_at_t_read, s_at_t_read=s, waste_ml=waste,
        primed=prime_time_s is not None, prime_time_s=prime_time_s, max_w_ml=max_w_ml,
        min_crossing_ml=min_crossing_ml, post_prime_drain_rate_ml_s=drain_rate,
        s_monotonic_decreasing=s_monotonic, backflow_occurred=backflow,
        mass_residual_ml=mass_residual_ml, w_series=w_series, bit=bit, read_band=band,
    )


def truth_table(params: SimParams | None = None) -> Dict[Tuple[int, int], SimResult]:
    """The four input cases, noise off."""
    p = params or SimParams()
    return {(a, b): simulate(a, b, params=p) for a in (0, 1) for b in (0, 1)}


# --------------------------------------------------------------------------- P1-P8


def p_report(params: SimParams | None = None) -> Dict[str, object]:
    """Measured analogs for C18 Appendix B P1-P8 (noise off). The graded contract."""
    p = params or SimParams()
    tt = truth_table(p)

    singles = [tt[(1, 0)], tt[(0, 1)]]
    dbl = tt[(1, 1)]
    zero = tt[(0, 0)]

    p1 = {"(1,0)": singles[0].w_at_t_read, "(0,1)": singles[1].w_at_t_read}
    p2 = {f"({a},{b})": {"w_at_t_read": tt[(a, b)].w_at_t_read, "primed": tt[(a, b)].primed}
          for a, b in ((1, 0), (0, 1))}
    p3 = {"primed": dbl.primed, "prime_time_s": dbl.prime_time_s,
          "w_at_t_read": dbl.w_at_t_read}
    p4 = {"w_at_t_read": zero.w_at_t_read}
    p5 = {"max_single_input_ml": max(r.max_w_ml for r in singles),
          "min_double_crossing_ml": dbl.min_crossing_ml}
    p6 = {"s_monotonic_decreasing": all(r.s_monotonic_decreasing for r in tt.values()),
          "backflow_occurred": any(r.backflow_occurred for r in tt.values()),
          "max_abs_mass_residual_ml": max(abs(r.mass_residual_ml) for r in tt.values())}

    p7: Dict[str, str] = {}
    base_bits = {c: tt[c].bit for c in ((1, 0), (0, 1), (1, 1))}
    p7_ok = True
    for skew in (5.0, -5.0):
        for (a, b) in ((1, 0), (0, 1), (1, 1)):
            got = simulate(a, b, skew_s=skew, params=p).bit
            p7[f"({a},{b})|skew{skew:+.0f}"] = got
            p7_ok = p7_ok and got == base_bits[(a, b)]
    p8 = {"drain_rate_ml_s": dbl.post_prime_drain_rate_ml_s}

    report: Dict[str, object] = {
        "P1": {"claim": "unit transfer: one open line, one tick -> W gains 100 +/- 20 mL",
               "spec": "100 +/- 20 mL", "measured": p1,
               "hold": all(80.0 <= v <= 120.0 for v in p1.values())},
        "P2": {"claim": "single input = bit 1, siphon never primes",
               "spec": "W in [70,130] and no prime, both cases", "measured": p2,
               "hold": all(70.0 <= d["w_at_t_read"] <= 130.0 and not d["primed"]
                           for d in p2.values())},
        "P3": {"claim": "double input = bit 0: primes within 90 s, W <= 30 at t_read",
               "spec": "prime <= 90 s and W <= 30 mL", "measured": p3,
               "hold": bool(p3["primed"] and p3["prime_time_s"] <= 90.0
                            and p3["w_at_t_read"] <= 30.0)},
        "P4": {"claim": "zero input = bit 0", "spec": "W <= 30 mL", "measured": p4,
               "hold": p4["w_at_t_read"] <= 30.0},
        "P5": {"claim": "threshold margin: single-input envelope vs dump threshold",
               "spec": "max single <= 130 and min crossing >= 140", "measured": p5,
               "hold": bool(p5["max_single_input_ml"] <= 130.0
                            and p5["min_double_crossing_ml"] is not None
                            and p5["min_double_crossing_ml"] >= 140.0)},
        "P6": {"claim": "check valve holds / conservation",
               "spec": "S only decreases, no backflow, |residual| <= 10 mL", "measured": p6,
               "hold": bool(p6["s_monotonic_decreasing"] and not p6["backflow_occurred"]
                            and p6["max_abs_mass_residual_ml"] <= 10.0)},
        "P7": {"claim": "timing skew immunity: +/-5 s valve offset changes no read-band outcome",
               "spec": "skew bits == skew-0 bits for (1,0),(0,1),(1,1)", "measured": p7,
               "hold": p7_ok},
        "P8": {"claim": "post-prime drain >= 3 mL/s (the scripted fault, quantified)",
               "spec": "drain rate >= 3 mL/s", "measured": p8,
               "hold": p8["drain_rate_ml_s"] is not None and p8["drain_rate_ml_s"] >= 3.0},
    }
    report["all_hold"] = all(report[k]["hold"] for k in
                             ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8"))
    return report


# --------------------------------------------------------------------------- cli


def main() -> None:
    tt = truth_table()
    print("=== two-bucket XOR truth table (C18 protocol, noise off) ===")
    print(f"{'A':>2} {'B':>2}  {'W@t_read':>9}  {'prime@':>7}  {'waste':>7}  bit  band")
    for (a, b), r in sorted(tt.items()):
        prime = f"{r.prime_time_s:.1f}s" if r.prime_time_s is not None else "-"
        print(f"{a:>2} {b:>2}  {r.w_at_t_read:9.2f}  {prime:>7}  {r.waste_ml:7.2f}  "
              f"{r.bit:>3}  {r.read_band}")
    print()
    print("=== P1-P8 sim-vs-spec (C18 Appendix B) ===")
    rep = p_report()
    for key in ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8"):
        entry = rep[key]
        print(f"{key}: hold={entry['hold']}  measured={entry['measured']}")
    print(f"all_hold: {rep['all_hold']}")


if __name__ == "__main__":
    main()
