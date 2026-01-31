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
        """Collect activities from Events API (recent 90 days).

        Note: Commits are collected separately via Commits API since
        Events API doesn't return commit details for private repos.
        """
        print(f"Collecting events for {username}...")

        events = self.github.get_all_user_events(username)
        activities = extract_activities_from_events(events, settings.github_org)

        # Filter out commits - they're collected via Commits API
        activities = [a for a in activities if a["activity_type"] != "commit"]

        if not activities:
            print(f"  No activities found for {username}")
            return 0

        count = self._save_activities(username, activities)
        print(f"  Saved {count} activities for {username}")
        return count

    def collect_commits(
        self,
        username: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> int:
        """Collect commits using Commits API.

        Strategy:
        1. Get all repos in the organization
        2. For each repo, fetch commits by user via Commits API
        3. Group by date and save
        """
        print(f"Collecting commits for {username}...")

        # Get recently active repos in the organization (pushed within 20 days)
        repos = self.github.get_org_repos(pushed_within_days=20)
        if not repos:
            print(f"  No recently active repos found in organization")
            return 0

        print(f"  Checking {len(repos)} recently active repos...")

        activities = []
        for repo in repos:
            commits = self.github.get_repo_commits(
                repo=repo,
                author=username,
                since=from_date,
                until=to_date,
            )

            if not commits:
                continue

            # Group commits by date
            commits_by_date: dict[date, int] = {}
            for commit in commits:
                commit_date_str = commit.get("commit", {}).get("author", {}).get("date", "")
                if commit_date_str:
                    commit_date = datetime.fromisoformat(
                        commit_date_str.replace("Z", "+00:00")
                    ).date()
                    commits_by_date[commit_date] = commits_by_date.get(commit_date, 0) + 1

            # Create activities
            for commit_date, count in commits_by_date.items():
                activities.append({
                    "activity_type": "commit",
                    "repository": repo,
                    "activity_date": commit_date,
                    "count": count,
                })

            print(f"    {repo}: {len(commits)} commits")

        if not activities:
            print(f"  No commits found for {username}")
            return 0

        count = self._save_activities(username, activities)
        print(f"  Saved {count} commit records for {username}")
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
        events_count = 0

        # Use Events API for recent data (within 90 days)
        # Note: This collects PRs, reviews, issues - NOT commits
        if to_date >= ninety_days_ago:
            events_count = self.collect_from_events(username)
            total += events_count

        # Collect commits via Commits API (works for private repos)
        total += self.collect_commits(username, from_date, to_date)

        # Use Search API for older data OR if Events API returned nothing
        # (Events API doesn't work for other users' private repo activities)
        if from_date < ninety_days_ago:
            search_end = min(to_date, ninety_days_ago - timedelta(days=1))
            total += self.collect_from_search(username, from_date, search_end)

        # Fallback: If Events API returned nothing, use Search API for recent data
        if events_count == 0 and to_date >= ninety_days_ago:
            search_start = max(from_date, ninety_days_ago)
            total += self.collect_from_search(username, search_start, to_date)

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
