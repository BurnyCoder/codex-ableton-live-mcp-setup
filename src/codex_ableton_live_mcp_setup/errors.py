"""Global context: domain errors keep expected setup failures concise and actionable."""


class SetupError(RuntimeError):
    """Represent a fail-closed setup or validation error suitable for CLI output."""
