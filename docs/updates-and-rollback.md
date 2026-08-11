<!-- Global context: idempotent update and recoverable scoped rollback procedures that preserve unrelated integrations and Codex settings. -->

# Updates and rollback

## Routine update using reviewed pins

Save/close important Live work, then from this companion repository:

```powershell
git pull --ff-only
uv sync --locked
.\manage.ps1 doctor
.\manage.ps1 update --dry-run --accept-risk
.\manage.ps1 update --accept-risk
.\manage.ps1 validate pre-live
```

The update command requires a clean managed upstream checkout, uses only the
identities in `config/versions.json`, reruns tests before installing, updates the
Remote Script idempotently, and updates only the managed Codex MCP section.

Complete the same manual Live restart/Control Surface checkpoint as installation,
then run:

```powershell
.\manage.ps1 validate post-live
```

Restart Codex desktop after an MCP command, policy, or schema change.

If you use a nonstandard approval mode, pass the same mode on update or set it in
`.env`. Only `approve` requires `--accept-risk`.

## Reviewing a future upstream pin

Normal users should not edit `config/versions.json`. Maintainers must use a
dedicated pull request that:

1. identifies the proposed upstream base and whether PR #15 is already included;
2. verifies commit, parent, and tree from public Git objects;
3. reviews the diff and upstream license/metadata;
4. runs the full suite on Windows;
5. records zero failures or changes the accepted failure list with justification;
6. repeats STDIO and pre-Live integration checks;
7. updates source citations, experiment report, lockfile, and release notes;
8. completes the manual Live release checklist before tagging.

Do not automatically cherry-pick PR #15 when upstream already contains an
equivalent fix. Review the upstream implementation and pin the resulting tree.

## Scoped rollback

Rollback is recoverable and narrowly targeted. It restores/removes only this
setup's Codex MCP section and moves—never deletes—the managed Remote Script.

1. Save or close important Live work.
2. Preview:

   ```powershell
   .\manage.ps1 rollback --dry-run
   ```

3. Confirm the preview names `ableton-live-mcp` and `Ableton_Live_MCP`, never
   `AbletonMCP`.
4. Close Live.
5. Run:

   ```powershell
   .\manage.ps1 rollback
   ```

6. If `Ableton_Live_MCP` existed before the companion managed it, the saved
   preinstall snapshot is restored. Otherwise the installed folder is moved to a
   timestamped backup outside active `Remote Scripts`.
7. Open Live Settings and set only the `Ableton Live MCP` Control Surface row to
   **None**. Leave the existing `AbletonMCP` row unchanged.
8. Restart Codex desktop and run `codex mcp list`.

Running rollback again should be idempotent: it must not delete backups, remove an
unrelated section, or touch the older integration.

## Manual fallback

Use this only if the wrapper cannot start and after copying the current Codex
config:

```powershell
codex mcp remove ableton-live-mcp
```

With Live closed, move `Ableton_Live_MCP` out of the active `Remote Scripts`
directory to a clearly named backup location. Do not delete it and do not touch
`AbletonMCP`.

Avoid replacing the whole current `~/.codex/config.toml` with an old backup; that
can erase settings created after installation. Restore only the saved managed
section whenever possible.

## What rollback cannot do

Rollback does not undo clips, devices, automation, files, or settings already
changed inside Live. Use independent set backups and Live's own recovery model for
content restoration.
