"""Global context: centralize subprocess execution, dry-run behavior, logging, and errors."""

from __future__ import annotations

import os
import shlex
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .errors import SetupError
from .logging_utils import SetupLogger


@dataclass(frozen=True)
class CommandResult:
    """Expose only deterministic subprocess fields needed by setup phases and tests."""

    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    planned: bool = False


class Runner:
    """Run commands with complete logs and suppress only explicitly mutating dry-run actions."""

    def __init__(self, logger: SetupLogger, dry_run: bool = False) -> None:
        """Bind one logger and dry-run policy to an entire workflow."""
        self.logger = logger
        self.dry_run = dry_run

    def run(
        self,
        args: Sequence[str | os.PathLike[str]],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        check: bool = True,
        mutating: bool = False,
        timeout: float | None = None,
        input_text: str | None = None,
    ) -> CommandResult:
        """Execute one argv-only command, preserving complete output and fail-closed semantics."""
        argv = tuple(str(item) for item in args)
        rendered = subprocess.list2cmdline(list(argv)) if os.name == "nt" else shlex.join(argv)
        location = f" (cwd={cwd})" if cwd else ""
        if self.dry_run and mutating:
            self.logger.log(f"DRY-RUN $ {rendered}{location}")
            return CommandResult(argv, 0, "", "", planned=True)
        self.logger.log(f"$ {rendered}{location}")
        try:
            process = subprocess.Popen(
                argv, cwd=cwd, env=dict(env) if env is not None else None,
                stdin=subprocess.PIPE if input_text is not None else None,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace",
            )
        except OSError as exc:
            raise SetupError(f"Command could not start: {rendered}: {exc}") from exc
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []

        def drain(stream, parts: list[str], label: str) -> None:
            """Stream one pipe line-by-line while retaining its exact decoded content."""
            for line in iter(stream.readline, ""):
                parts.append(line)
                self.logger.log(f"{label} | {line.rstrip(chr(10) + chr(13))}")
            stream.close()

        assert process.stdout is not None and process.stderr is not None
        threads = [
            threading.Thread(target=drain, args=(process.stdout, stdout_parts, "stdout"), daemon=True),
            threading.Thread(target=drain, args=(process.stderr, stderr_parts, "stderr"), daemon=True),
        ]
        for thread in threads:
            thread.start()
        if input_text is not None:
            assert process.stdin is not None
            self.logger.log(f"stdin:\n{input_text}")
            process.stdin.write(input_text)
            process.stdin.close()
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait()
            for thread in threads:
                thread.join()
            partial = "".join(stdout_parts + stderr_parts)
            raise SetupError(f"Command timed out after {timeout}s: {rendered}\nPartial output:\n{partial}") from exc
        for thread in threads:
            thread.join()
        stdout = "".join(stdout_parts)
        stderr = "".join(stderr_parts)
        self.logger.log(f"exit={returncode}")
        result = CommandResult(argv, returncode, stdout, stderr)
        if check and result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
            raise SetupError(f"Command failed ({result.returncode}): {rendered}\n{detail}")
        return result


def merged_environment(values: Mapping[str, str]) -> dict[str, str]:
    """Return a child environment without mutating the current process environment."""
    child = dict(os.environ)
    child.update(values)
    return child
