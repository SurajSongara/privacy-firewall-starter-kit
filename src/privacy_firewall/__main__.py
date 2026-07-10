"""Entry-point module for the privacy-firewall CLI."""

from typing import Annotated

import typer

from privacy_firewall.cli import (
    detect_cmd,
    diagnostics_cmd,
    doctor_cmd,
    redact_cmd,
    review_cmd,
    scan_cmd,
)

app = typer.Typer(
    name="privacy-firewall",
    help="Offline-first PII Detection & Redaction Engine",
    pretty_exceptions_enable=False,
)

app.command(name="scan")(scan_cmd)
app.command(name="detect")(detect_cmd)
app.command(name="redact")(redact_cmd)
app.command(name="diagnostics")(diagnostics_cmd)
app.command(name="doctor")(doctor_cmd)
app.command(name="review")(review_cmd)


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    version_flag: Annotated[  # noqa: FBT001
        bool, typer.Option("--version", help="Show the version and exit.")
    ] = False,
) -> None:
    """CLI callback that shows version info or the default banner.

    Args:
        ctx: The Typer context.
        version_flag: When True, prints the installed package version and exits.
    """
    if version_flag:
        from importlib.metadata import version

        typer.echo(version("privacy_firewall"))
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo("Offline-first PII Detection & Redaction Engine")


def entry_point() -> None:
    """Console-script entry point that runs the Typer application."""
    app()


if __name__ == "__main__":
    entry_point()
