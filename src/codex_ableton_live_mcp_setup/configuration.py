"""Global context: resolve reproducible settings with CLI > .env > discovery > defaults precedence."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .errors import SetupError


APPROVAL_MODES = ("auto", "prompt", "writes", "approve")
REMOTE_SCRIPT_NAME = "Ableton_Live_MCP"
FIXED_HOST = "127.0.0.1"


@dataclass(frozen=True)
class Settings:
    """Contain all resolved paths and supported runtime configuration."""

    checkout: Path
    user_library: Path
    python_version: str = "3.14"
    host: str = FIXED_HOST
    port: int = 8765
    server_name: str = "ableton-live-mcp"
    startup_timeout: int = 30
    tool_timeout: int = 120
    approval_mode: str = "approve"
    remote_script_name: str = REMOTE_SCRIPT_NAME
    codex_home: Path = Path.home() / ".codex"
    state_dir: Path = Path.home() / ".local" / "share" / "codex-ableton-live-mcp-setup"

    @property
    def remote_scripts_dir(self) -> Path:
        """Return Ableton's supported User Library Remote Scripts location."""
        return self.user_library / "Remote Scripts"

    @property
    def remote_script_target(self) -> Path:
        """Return the exact managed Remote Script directory."""
        return self.remote_scripts_dir / self.remote_script_name

    @property
    def runtime_env_path(self) -> Path:
        """Return the locally excluded upstream runtime configuration file."""
        return self.checkout / ".env"

    @property
    def venv_python(self) -> Path:
        """Return the Windows Python executable in the upstream local environment."""
        return self.checkout / ".venv" / "Scripts" / "python.exe"

    @property
    def server_executable(self) -> Path:
        """Return the exact editable-install MCP server executable."""
        return self.checkout / ".venv" / "Scripts" / "ableton-live-mcp.exe"

    @property
    def validator_executable(self) -> Path:
        """Return the upstream validation executable from the same environment."""
        return self.checkout / ".venv" / "Scripts" / "ableton-live-mcp-validate.exe"

    @property
    def installer_executable(self) -> Path:
        """Return the upstream Remote Script installer from the same environment."""
        return self.checkout / ".venv" / "Scripts" / "ableton-live-mcp-install-remote-script.exe"

    @property
    def capture_executable(self) -> Path:
        """Return the upstream Ableton-only visual capture executable."""
        return self.checkout / ".venv" / "Scripts" / "ableton-live-mcp-capture-window.exe"

    @property
    def codex_config_path(self) -> Path:
        """Return Codex's documented global configuration location."""
        return self.codex_home / "config.toml"

    @property
    def state_path(self) -> Path:
        """Return the local transaction state used for scoped rollback."""
        return self.state_dir / "state.json"


ENV_KEYS = {
    "checkout": "ABLETON_SETUP_CHECKOUT",
    "user_library": "ABLETON_USER_LIBRARY",
    "python_version": "ABLETON_SETUP_PYTHON",
    "port": "ABLETON_MCP_PORT",
    "server_name": "CODEX_MCP_SERVER_NAME",
    "startup_timeout": "CODEX_MCP_STARTUP_TIMEOUT_SEC",
    "tool_timeout": "CODEX_MCP_TOOL_TIMEOUT_SEC",
    "approval_mode": "CODEX_MCP_APPROVAL_MODE",
}


def load_settings(overrides: Mapping[str, object | None], env_file: Path | None = None) -> Settings:
    """Resolve, normalize, and validate settings using the documented precedence."""
    home = Path.home()
    dotenv = read_dotenv(env_file or repository_root() / ".env")
    checkout = _path_value(overrides.get("checkout"), dotenv.get(ENV_KEYS["checkout"]))
    user_library = _path_value(overrides.get("user_library"), dotenv.get(ENV_KEYS["user_library"]))
    resolved_checkout = checkout or home / "Documents" / "Codex" / "MCP" / "ableton-live-mcp"
    resolved_library = user_library or discover_user_library(home)
    local_app_data = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex")).expanduser().resolve()
    settings = Settings(
        checkout=resolved_checkout.expanduser().resolve(),
        user_library=resolved_library.expanduser().resolve(),
        python_version=_text_value(overrides.get("python_version"), dotenv.get(ENV_KEYS["python_version"]), "3.14"),
        port=_integer_value(overrides.get("port"), dotenv.get(ENV_KEYS["port"]), 8765, "port"),
        server_name=_text_value(overrides.get("server_name"), dotenv.get(ENV_KEYS["server_name"]), "ableton-live-mcp"),
        startup_timeout=_integer_value(overrides.get("startup_timeout"), dotenv.get(ENV_KEYS["startup_timeout"]), 30, "startup timeout"),
        tool_timeout=_integer_value(overrides.get("tool_timeout"), dotenv.get(ENV_KEYS["tool_timeout"]), 120, "tool timeout"),
        approval_mode=_text_value(overrides.get("approval_mode"), dotenv.get(ENV_KEYS["approval_mode"]), "approve"),
        codex_home=codex_home,
        state_dir=(local_app_data / "codex-ableton-live-mcp-setup").resolve(),
    )
    validate_settings(settings)
    return settings


def read_dotenv(path: Path) -> dict[str, str]:
    """Read a small non-interpolating UTF-8 dotenv subset with quoted spaces and Unicode."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SetupError(f"Invalid .env line {number} in {path}: expected KEY=VALUE")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = raw_value.strip()
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise SetupError(f"Invalid quoted value on .env line {number} in {path}") from exc
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        values[key] = value
    return values


def discover_user_library(home: Path) -> Path:
    """Discover one existing Windows User Library and fail when candidates are ambiguous."""
    candidates = [
        home / "Documents" / "Ableton" / "User Library",
        home / "OneDrive" / "Documents" / "Ableton" / "User Library",
    ]
    one_drive = os.environ.get("OneDrive")
    if one_drive:
        candidates.append(Path(one_drive) / "Documents" / "Ableton" / "User Library")
    unique_candidates = list(dict.fromkeys(path.resolve() for path in candidates))
    existing = [path for path in unique_candidates if path.is_dir()]
    if len(existing) > 1:
        formatted = "\n".join(f"  - {path}" for path in existing)
        raise SetupError(f"Multiple Ableton User Libraries were found; set ABLETON_USER_LIBRARY:\n{formatted}")
    return existing[0] if existing else unique_candidates[0]


def validate_settings(settings: Settings) -> None:
    """Reject unsupported or unsafe configuration before any mutating phase."""
    if settings.host != FIXED_HOST:
        raise SetupError("The Ableton bridge host is fixed to loopback 127.0.0.1")
    if not 1 <= settings.port <= 65535:
        raise SetupError("ABLETON_MCP_PORT must be between 1 and 65535")
    if settings.startup_timeout <= 0 or settings.tool_timeout <= 0:
        raise SetupError("Codex MCP timeouts must be positive integers")
    if settings.approval_mode not in APPROVAL_MODES:
        raise SetupError(f"Unsupported approval mode {settings.approval_mode!r}; choose {', '.join(APPROVAL_MODES)}")
    if not settings.server_name or any(character.isspace() for character in settings.server_name):
        raise SetupError("CODEX_MCP_SERVER_NAME must be non-empty and contain no whitespace")
    if not all(character.isalnum() or character in "_-" for character in settings.server_name):
        raise SetupError("CODEX_MCP_SERVER_NAME may contain only letters, numbers, underscore, and hyphen")
    try:
        settings.checkout.relative_to(repository_root())
    except ValueError:
        pass
    else:
        raise SetupError("The upstream checkout must be outside the public companion repository")


def repository_root() -> Path:
    """Return the companion checkout root for stable local inputs and path safety checks."""
    return Path(__file__).resolve().parents[2]


def _path_value(cli_value: object | None, env_value: str | None) -> Path | None:
    """Choose a CLI or dotenv path without inventing a third precedence layer."""
    selected = cli_value if cli_value is not None else env_value
    return Path(str(selected)) if selected not in (None, "") else None


def _text_value(cli_value: object | None, env_value: str | None, default: str) -> str:
    """Choose a string value using CLI, dotenv, then the explicit default."""
    selected = cli_value if cli_value is not None else env_value
    return str(selected) if selected not in (None, "") else default


def _integer_value(cli_value: object | None, env_value: str | None, default: int, label: str) -> int:
    """Choose and validate an integer value using the shared precedence."""
    selected = cli_value if cli_value is not None else env_value
    try:
        return int(selected) if selected not in (None, "") else default
    except (TypeError, ValueError) as exc:
        raise SetupError(f"Invalid {label}: {selected!r}") from exc
