<!-- Global context: aggregate index and cross-experiment learnings for reproducibility studies in this companion repository. -->

# Experiment index

## Method

Each experiment starts with a falsifiable question and prior evidence, records a
hypothesis and controlled procedure, separates observations from interpretation,
states limitations, and refines the next hypothesis. Raw logs stay local; public
reports contain sanitized evidence only.

## Experiments

| Date | Environment | Question | Result | Report |
|---|---|---|---|---|
| 2026-08-11 | Windows 11, Live 12 Intro | Can the pinned upstream source plus reviewed Windows STDIO fix be installed beside an existing integration and used read-only from a fresh Codex client? | Supported: offline, protocol, runtime, visual, and fresh-client criteria passed; two known test-only assertions remained. | [Windows baseline](experiments/2026-08-11-windows-baseline.md) |

## Aggregate learnings

1. Pinning the base commit alone was insufficient on Windows: PR #15 was needed
   for UTF-8, LF-only framing, and server survival after malformed JSON.
2. Commit identity plus expected tree verification made the reviewed content
   explicit even when a local cherry-pick produced a different local commit ID.
3. The two PR #14 failures were assertion portability defects, not production
   backslash leaks; exact node-ID matching prevented broader failure waivers.
4. Source tests and installed file hashes were insufficient to prove Live loaded
   current code. Runtime freshness and mutation-safety signals were necessary.
5. An Ableton-only nonblank capture provided a useful independent visual check
   without granting a general screenshot surface.
6. Codex desktop/CLI configuration sharing still required a fresh process to
   prove that the running client loaded the new server and approval policy.
7. Tool exposure and Live edition capability are separate: Intro could expose all
   schemas but could not supply custom Max for Live functionality.
8. Coexisting integrations were technically possible, but sequential ownership
   of mutations remains an operational requirement.

## Next experiments

- Repeat the baseline on a clean Windows 11 account without a pre-existing MCP.
- Repeat on Live Standard and Suite while keeping core and M4L acceptance results
  separate.
- Test a future upstream commit after PR #15/#14 equivalents merge, using a pin
  update pull request rather than changing the expected result in place.
- Add a second Windows release/patch version to distinguish machine-specific from
  portable behavior.
