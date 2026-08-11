# Global context: this is the single PowerShell entry point for the modular Python setup CLI.
# PowerShell strict mode catches misspelled variables before the wrapper starts any setup phase.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Resolve uv from PATH so the wrapper follows uv's documented project runner rather than pip.
$UvCommand = Get-Command uv -ErrorAction Stop
# Run the locked local project; uv creates/synchronizes the repository .venv when required.
& $UvCommand.Source run --project $PSScriptRoot --locked python -m codex_ableton_live_mcp_setup @args
# Preserve the Python CLI exit status for scripts and CI callers.
exit $LASTEXITCODE
