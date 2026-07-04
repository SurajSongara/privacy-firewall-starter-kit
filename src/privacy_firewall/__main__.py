from typing import Annotated

import typer

app = typer.Typer(
    name="privacy-firewall",
    help="Offline-first PII Detection & Redaction Engine",
    pretty_exceptions_enable=False,
)


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    version_flag: Annotated[  # noqa: FBT001
        bool, typer.Option("--version", help="Show the version and exit.")
    ] = False,
) -> None:
    if version_flag:
        from importlib.metadata import version

        typer.echo(version("privacy_firewall"))
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo("Offline-first PII Detection & Redaction Engine")


def entry_point() -> None:
    app()


if __name__ == "__main__":
    entry_point()
