<!-- Global context: human-controlled Live restart and Control Surface activation checkpoint that automation must not bypass. -->

# Ableton Live activation checkpoint

Run this checkpoint only after `validate pre-live` passes. Remote Script files are
not loaded into an already-running Live process automatically.

Ableton's official
[third-party Remote Script instructions](https://help.ableton.com/hc/en-us/articles/209072009-Installing-third-party-remote-scripts)
place scripts under the User Library's `Remote Scripts` folder and select them as
a Control Surface in Preferences/Settings.

## Before launching or restarting

1. Save and back up important sets.
2. Close any set that should not be exposed to an agent.
3. Confirm that pre-Live validation passed.
4. Stop if Live displays a save, recovery, crash, or update dialog.

Handle every dialog yourself. Do not discard a set, decline recovery, terminate
Live, or interrupt an update solely to continue setup. If an automatic update
message asks you to close a dialog and relaunch later, acknowledge it only after
your work is safe, wait for the update to finish, and then relaunch normally.

## Add the new Control Surface

1. Launch Ableton Live with its default/empty set.
2. Open **Settings → Link, Tempo & MIDI**. Ableton's general article may call
   this Preferences → MIDI; Live 12 uses the current Settings label.
3. Find an unused Control Surface row.
4. Select **Ableton Live MCP**. The picker uses spaces; the installed folder and
   Live log use `Ableton_Live_MCP`.
5. Set **Input** to **None**.
6. Set **Output** to **None**.
7. Leave any existing `AbletonMCP` row unchanged.
8. Close Settings without adding MIDI ports.

This script communicates over loopback and does not require a MIDI device.

## Verify activation

Run:

```powershell
.\manage.ps1 validate post-live
```

The new Live-owned listener should be on `127.0.0.1:8765` unless configured
otherwise. A listener on 9877 is expected only if the older integration was
detected before installation. Both may coexist, but only one agent integration
should mutate a set at a time.

## If the script is missing from the picker

- Confirm the exact layout is
  `User Library/Remote Scripts/Ableton_Live_MCP/__init__.py`, not an extra nested
  folder.
- Rerun `validate pre-live` to compare installed hashes.
- Confirm the User Library selected during `doctor` is the one Live is using.
- Close and relaunch Live after file changes.
- Inspect the diagnostic summary for recent Remote Script/Python errors.

Do not copy the script into Live's application installation directory. The User
Library location survives Live upgrades and is the path Ableton recommends.
