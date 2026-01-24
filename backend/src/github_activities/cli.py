"""CLI for GitHub Activities collector."""

from datetime import date, datetime
from typing import Optional

import click
from sqlalchemy import select

from .config import settings
from .models import User, Activity, init_db, get_session
from .collector import Collector


@click.group()
def cli():
    """GitHub Activities Collector CLI."""
    init_db()


@cli.command()
@click.option("--date", "-d", "target_date", type=click.DateTime(formats=["%Y-%m-%d"]),
              help="Collect data for specific date")
@click.option("--from", "-f", "from_date", type=click.DateTime(formats=["%Y-%m-%d"]),
              help="Start date for collection")
@click.option("--to", "-t", "to_date", type=click.DateTime(formats=["%Y-%m-%d"]),
              help="End date for collection")
@click.option("--user", "-u", "username", help="Collect for specific user only")
def collect(
    target_date: Optional[datetime],
    from_date: Optional[datetime],
    to_date: Optional[datetime],
    username: Optional[str],
):
    """Collect GitHub activities."""
    settings.validate()

    # Determine date range
    start: Optional[date] = None
    end: Optional[date] = None

    if target_date:
        start = end = target_date.date()
    else:
        if from_date:
            start = from_date.date()
        if to_date:
            end = to_date.date()

    with Collector() as collector:
        if username:
            count = collector.collect_for_user(username, start, end)
            click.echo(f"Collected {count} activities for {username}")
        else:
            if not settings.target_users:
                click.echo("No target users configured. Set TARGET_USERS in .env")
                return
            results = collector.collect_all(start, end)
            total = sum(results.values())
            click.echo(f"Collected {total} activities for {len(results)} users")
            for user, count in results.items():
                click.echo(f"  {user}: {count}")


@cli.command("add-user")
@click.argument("username")
@click.option("--backfill-from", "-b", type=click.DateTime(formats=["%Y-%m-%d"]),
              help="Backfill data from this date")
def add_user(username: str, backfill_from: Optional[datetime]):
    """Add a new user to track."""
    settings.validate()

    with get_session() as session:
        existing = session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()

        if existing:
            click.echo(f"User {username} already exists")
        else:
            user = User(username=username)
            session.add(user)
            session.commit()
            click.echo(f"Added user: {username}")

    if backfill_from:
        click.echo(f"Backfilling from {backfill_from.date()}...")
        with Collector() as collector:
            count = collector.collect_for_user(username, backfill_from.date())
            click.echo(f"Collected {count} activities")


@cli.command("remove-user")
@click.argument("username")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def remove_user(username: str, yes: bool):
    """Remove a user and their activities."""
    with get_session() as session:
        user = session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()

        if not user:
            click.echo(f"User {username} not found")
            return

        if not yes:
            click.confirm(f"Remove {username} and all their activities?", abort=True)

        session.delete(user)
        session.commit()
        click.echo(f"Removed user: {username}")


@cli.command()
def status():
    """Show collection status for all users."""
    with get_session() as session:
        users = session.execute(select(User).order_by(User.username)).scalars().all()

        if not users:
            click.echo("No users registered")
            return

        click.echo(f"{'Username':<20} {'From':<12} {'Last Collected':<20} {'Activities'}")
        click.echo("-" * 70)

        for user in users:
            activity_count = session.execute(
                select(Activity).where(Activity.user_id == user.id)
            ).scalars().all()

            from_date = user.collect_from_date.isoformat() if user.collect_from_date else "N/A"
            last = user.last_collected_at.strftime("%Y-%m-%d %H:%M") if user.last_collected_at else "Never"

            click.echo(f"{user.username:<20} {from_date:<12} {last:<20} {len(activity_count)}")


@cli.command()
def users():
    """List all configured target users."""
    click.echo("Target users from .env:")
    for username in settings.target_users:
        click.echo(f"  - {username}")

    click.echo("\nRegistered users in database:")
    with get_session() as session:
        db_users = session.execute(select(User).order_by(User.username)).scalars().all()
        for user in db_users:
            click.echo(f"  - {user.username}")


@cli.command("init-db")
def init_database():
    """Initialize the database."""
    init_db()
    click.echo("Database initialized")


@cli.command("rate-limit")
def rate_limit():
    """Check GitHub API rate limit status."""
    settings.validate()

    from .github_client import GitHubClient
    with GitHubClient() as client:
        limits = client.get_rate_limit()

        core = limits.get("resources", {}).get("core", {})
        search = limits.get("resources", {}).get("search", {})

        click.echo("GitHub API Rate Limits:")
        click.echo(f"  Core:   {core.get('remaining', 0):>5} / {core.get('limit', 0)}")
        click.echo(f"  Search: {search.get('remaining', 0):>5} / {search.get('limit', 0)}")


if __name__ == "__main__":
    cli()
