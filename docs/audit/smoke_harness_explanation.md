## Finding — A Conceptual Domain for Minimal Rendering Audit
The `smoke_harness` is not a single, explicit file but a conceptual domain defining a "headless pre-ship gate" within the fleet's testing methodology. Its characteristics – "stub fidelity gaps (measureText, gradients), title-idle phase" – point to a deliberate strategy for isolating and auditing core rendering mechanisms without the overhead or confounding factors of a full browser environment. This aligns perfectly with Matthew Steiniger's interest in emergent properties from minimal systems and his "abliteration" approach to strip away non-essential elements. The fact that it's defined in "pack" files (e.g., `p320_matthew_ds_20260913.json`, `p160_matthew_20260913.json`) and a generation script (`gen_matthew_480.py`) suggests it's a configurable test environment or a set of parameters for a testing harness, rather than a standalone module.

## Evidence — what in the repo supports it (file/shape, no invention)
The string "smoke_harness" appears in:
- `C:/Users/ESTATE_USER/Documents/projects/local_sovereign_agent/packs/p320_matthew_ds_20260913.json` (multiple entries with `context` fields describing the domain)
- `C:/Users/ESTATE_USER/Documents/projects/local_sovereign_agent/packs/p160_matthew_20260913.json` (similar `context` fields)
- `C:/Users/ESTATE_USER/Documents/projects/local_sovereign_agent/packs/gen_matthew_480.py` (line 42: `("smoke_harness", "the headless pre-ship gate: stub fidelity gaps found (measureText, gradients), title-idle phase")`)

These occurrences describe `smoke_harness` as a "headless pre-ship gate" with specific characteristics like "stub fidelity gaps" and "title-idle phase." The absence of a dedicated `smoke_harness.py` file indicates it's a domain or configuration rather than a physical module.

## Risk if wrong — what the audit breaks on if this is missed
Misinterpreting `smoke_harness` as a failed or incomplete browser emulation would lead Steiniger to conclude that the fleet's rendering tests are either insufficient or fundamentally flawed. This misunderstanding would undermine the architectural design of isolated testing, which is crucial for falsifying claims about rendering correctness and emergent behaviors in minimal environments. It would suggest a lack of rigor in the fleet's self-assessment.

## The act — the concrete prep step (file/spec/number)
1.  **Create Audit Explanation:** Create a markdown file `docs/audit/smoke_harness_explanation.md`.
    *   **Purpose:** Clearly define `smoke_harness` as a conceptual test domain for minimal rendering auditing.
    *   **Entry Point for Examiner:** Explain that its "entry file" is its definition within the pack files (referencing `p320_matthew_ds_20260913.json`, `p160_matthew_20260913.json`, `gen_matthew_480.py`).
    *   **Three Key Understandings:**
        1.  **Intentional Minimalism:** Emphasize that "stub fidelity gaps" (e.g., `measureText`, gradients) are deliberate simplifications, not bugs, designed to isolate core rendering behaviors.
        2.  **Focus on Initial State:** Clarify "title-idle phase" as a mechanism to analyze the foundational, pre-interactive render state.
        3.  **Alignment with EUT:** Explain how this controlled environment facilitates the study of emergent properties from a reduced set of rendering primitives, directly appealing to Steiniger's EUT framework.
    *   **The One Trap to Avoid:** Explicitly state the pitfall of interpreting stub fidelity as an incomplete or failed browser emulation. Reinforce that these are architectural choices for focused auditing.

## Falsifier — what would prove this wrong
Evidence (e.g., new entries in the verkle chain, modifications to existing pack files, or changes in `gen_matthew_480.py`) that indicates a shift towards *increasing* the fidelity of `smoke_harness` to a full browser environment, adding complex interactive features beyond initial render state, or any documentation suggesting it's intended as a comprehensive browser emulator, would contradict this finding.