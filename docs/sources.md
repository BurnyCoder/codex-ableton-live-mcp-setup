<!-- Global context: primary-source index grounding setup commands, product capabilities, safety claims, and release procedures. -->

# Primary sources

Reviewed on 2026-08-11. Product interfaces and upstream branches can change;
recheck time-sensitive claims before a release.

| Source | Claims grounded here |
|---|---|
| [`bschoepke/ableton-live-mcp` at the reviewed base](https://github.com/bschoepke/ableton-live-mcp/tree/70f7df9192b78d9bd9405f369c9e046c88f1610e) | Upstream source identity, package contents, license, and general capability. |
| [Pinned upstream `AGENTS.md`](https://github.com/bschoepke/ableton-live-mcp/blob/70f7df9192b78d9bd9405f369c9e046c88f1610e/AGENTS.md) | Remote Script installation/validation, loopback binding, runtime currency, modal/hang handling, visual-capture privacy, and mutation timeout discipline. |
| [Upstream PR #15](https://github.com/bschoepke/ableton-live-mcp/pull/15) | Windows UTF-8 pipe corruption, LF-only framing, malformed-JSON recovery, and public fix commit. |
| [Upstream PR #14](https://github.com/bschoepke/ableton-live-mcp/pull/14) | Exact two Windows test-only path failures and forward-slash rationale for Max. |
| [GitHub: check out pull requests locally](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/checking-out-pull-requests-locally?platform=windows) | Pull-request refs remain fetchable for local review and testing. The setup adds stricter SHA/parent/tree verification. |
| [OpenAI: Model Context Protocol](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) | Shared desktop/CLI/IDE configuration, `config.toml`, STDIO fields, timeouts, tool filters, required/enabled flags, approval modes, and restart behavior. |
| [OpenAI: Computer Use](https://learn.chatgpt.com/docs/computer-use) | Plugin install/enable steps, server and skill toggles, app access, Windows foreground behavior, and separation of app/system/task permissions. |
| [Ableton: Installing third-party Remote Scripts](https://help.ableton.com/hc/en-us/articles/209072009-Installing-third-party-remote-scripts) | User Library `Remote Scripts` location, launch/relaunch, and Control Surface selection. |
| [Ableton: Compare Live editions](https://www.ableton.com/en/live/compare-editions/) | Max for Live availability by edition and Windows 11 support context. |
| [`uv`: installation](https://docs.astral.sh/uv/getting-started/installation/) | Windows installation methods. |
| [`uv`: Python environments](https://docs.astral.sh/uv/pip/environments/) | `.venv`, Python selection, environment isolation, and `--python` behavior. |
| [`uv`: Python versions](https://docs.astral.sh/uv/concepts/python-versions/) | Managed Python discovery/download behavior. |
| [Python `tomllib`](https://docs.python.org/3/library/tomllib.html) | Semantic TOML parsing used after comment-preserving text updates. |
| [GitHub Actions token permissions](https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication) | Workflow-level least-privilege `GITHUB_TOKEN` permissions. |
| [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) | Required pull requests and status checks for `main`. |

## Source-selection method

Primary vendor/project documentation is used for product behavior. Public Git
object identities and the pinned checkout are used for reproducibility. The
baseline report distinguishes observed results from upstream or vendor claims.

No external source can guarantee that an arbitrary Live Set is safe to mutate.
That residual risk is managed through backups, staged read-only validation,
approval policy, and rollback of access—not by claiming mutations are reversible.
