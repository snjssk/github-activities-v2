"""Data collection logic."""

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from .config import settings
from .models import User, Activity, get_session, init_db
from .github_client import GitHubClient, extract_activities_from_events


class Collector:
    """Collects GitHub activities and stores them in database."""

    def __init__(self):
        self.github = GitHubClient()

    def ensure_user(self, username: str) -> User:
        """Ensure user exists in database."""
        with get_session() as session:
            user = session.execute(
                select(User).where(User.username == username)
            ).scalar_one_or_none()

            if not user:
                user = User(username=username)
                session.add(user)
                session.commit()
                session.refresh(user)

            return user

    def collect_from_events(self, username: str) -> int:
        """Collect activities from Events API (recent 90 days)."""
        print(f"Collecting events for {username}...")

        events = self.github.get_all_user_events(username)
        activities = extract_activities_from_events(events, settings.github_org)

        if not activities:
            print(f"  No activities found for {username}")
            return 0

        count = self._save_activities(username, activities)
        print(f"  Saved {count} activities for {username}")
        return count

    def collect_from_search(
        self,
        username: str,
        from_date: date,
        to_date: date,
    ) -> int:
        """Collect activities from Search API (for older data)."""
        print(f"Searching activities for {username} from {from_date} to {to_date}...")

        activities = []

        # Search PRs
        prs = self.github.search_prs(username, from_date, to_date)
        for pr in prs:
            repo_name = pr.get("repository_url", "").split("/")[-2:]
            repo_full = "/".join(repo_name) if len(repo_name) == 2 else pr.get("repository_url", "")
            created = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00")).date()

            activities.append({
                "activity_type": "pr_opened",
                "repository": repo_full,
                "activity_date": created,
                "count": 1,
            })

            if pr.get("pull_request", {}).get("merged_at"):
                merged = datetime.fromisoformat(
                    pr["pull_request"]["merged_at"].replace("Z", "+00:00")
                ).date()
                if from_date <= merged <= to_date:
                    activities.append({
                        "activity_type": "pr_merged",
                        "repository": repo_full,
                        "activity_date": merged,
                        "count": 1,
                    })

        # Search Issues
        issues = self.github.search_issues(username, from_date, to_date)
        for issue in issues:
            repo_name = issue.get("repository_url", "").split("/")[-2:]
            repo_full = "/".join(repo_name) if len(repo_name) == 2 else issue.get("repository_url", "")
            created = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00")).date()

            activities.append({
                "activity_type": "issue_opened",
                "repository": repo_full,
                "activity_date": created,
                "count": 1,
            })

            if issue.get("closed_at"):
                closed = datetime.fromisoformat(issue["closed_at"].replace("Z", "+00:00")).date()
                if from_date <= closed <= to_date:
                    activities.append({
                        "activity_type": "issue_closed",
                        "repository": repo_full,
                        "activity_date": closed,
                        "count": 1,
                    })

        if not activities:
            print(f"  No activities found for {username}")
            return 0

        count = self._save_activities(username, activities)
        print(f"  Saved {count} activities for {username}")
        return count

    def _save_activities(self, username: str, activities: list[dict]) -> int:
        """Save activities to database with upsert."""
        with get_session() as session:
            user = session.execute(
                select(User).where(User.username == username)
            ).scalar_one()

            count = 0
            for activity in activities:
                stmt = insert(Activity).values(
                    user_id=user.id,
                    activity_type=activity["activity_type"],
                    repository=activity["repository"],
                    activity_date=activity["activity_date"],
                    count=activity["count"],
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["user_id", "activity_type", "repository", "activity_date"],
                    set_={"count": stmt.excluded.count},
                )
                session.execute(stmt)
                count += 1

            user.last_collected_at = datetime.utcnow()
            session.commit()

        return count

    def collect_for_user(
        self,
        username: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> int:
        """Collect all activities for a user."""
        self.ensure_user(username)

        today = date.today()
        ninety_days_ago = today - timedelta(days=90)

        if from_date is None:
            from_date = ninety_days_ago
        if to_date is None:
            to_date = today

        total = 0

        # Use Events API for recent data (within 90 days)
        if to_date >= ninety_days_ago:
            total += self.collect_from_events(username)

        # Use Search API for older data
        if from_date < ninety_days_ago:
            search_end = min(to_date, ninety_days_ago - timedelta(days=1))
            total += self.collect_from_search(username, from_date, search_end)

        # Update collect_from_date
        with get_session() as session:
            user = session.execute(
                select(User).where(User.username == username)
            ).scalar_one()
            if user.collect_from_date is None or from_date < user.collect_from_date:
                user.collect_from_date = from_date
            session.commit()

        return total

    def collect_all(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> dict[str, int]:
        """Collect activities for all target users."""
        results = {}
        for username in settings.target_users:
            results[username] = self.collect_for_user(username, from_date, to_date)
        return results

    def close(self) -> None:
        """Close resources."""
        self.github.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
