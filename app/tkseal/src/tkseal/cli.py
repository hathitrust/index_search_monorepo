"""CLI interface for TKSeal."""

import click

from tkseal import __version__


@click.group()
def cli():
    """TKSeal - Kubernetes sealed secrets management tool."""
    pass


@cli.command()
def version():
    """Show the current version."""
    click.echo(__version__)

@cli.command()
def ready():
    """Check that the CLI dependencies are available in your shell."""
    from tkseal.kubectl import KubeCtl
    from tkseal.tk import TK
    from tkseal.kubeseal import KubeSeal

    if KubeCtl.exists():
        click.echo("✅ Kubectl is installed")
    else:
        click.echo("❌ Kubectl is NOT installed")

    if TK.exists():
        click.echo("✅ tk is installed")
    else:
        click.echo("❌ tk is NOT installed")

    if KubeSeal.exists():
        click.echo("✅ Kubeseal is installed")
    else:
        click.echo("❌ Kubeseal is NOT installed")


def main() -> None:
    """Entry point for the CLI application."""
    cli()


if __name__ == "__main__":
    main()

