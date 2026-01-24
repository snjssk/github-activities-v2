"""GitHub API client."""

from datetime import date, datetime
from typing import Optional
import httpx

from .config import settings


class GitHubClient:
    """Client for interacting with GitHub API."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None, org: Optional[str] = None):
        self.token = token or settings.github_token
        self.org = org or settings.github_org
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=30.0,
            )
        return self._client

    def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def get_user_events(self, username: str, page: int = 1, per_page: int = 100) -> list[dict]:
        """Get user events (max 300 events, 90 days)."""
        response = self.client.get(
            f"/users/{username}/events",
            params={"page": page, "per_page": per_page},
        )
        response.raise_for_status()
        return response.json()

    def get_all_user_events(self, username: str) -> list[dict]:
        """Get all available user events (up to 300)."""
        all_events = []
        for page in range(1, 4):  # Max 3 pages * 100 = 300 events
            events = self.get_user_events(username, page=page)
            if not events:
                break
            all_events.extend(events)
            if len(events) < 100:
                break
        return all_events

    def search_prs(
        self,
        username: str,
        from_date: date,
        to_date: date,
        state: str = "all",
    ) -> list[dict]:
        """Search PRs created by user in org within date range."""
        query = f"author:{username} org:{self.org} type:pr created:{from_date}..{to_date}"
        if state != "all":
            query += f" is:{state}"
        return self._search_issues(query)

    def search_issues(
        self,
        username: str,
        from_date: date,
        to_date: date,
        state: str = "all",
    ) -> list[dict]:
        """Search issues created by user in org within date range."""
        query = f"author:{username} org:{self.org} type:issue created:{from_date}..{to_date}"
        if state != "all":
            query += f" is:{state}"
        return self._search_issues(query)

    def search_reviews(
        self,
        username: str,
        from_date: date,
        to_date: date,
    ) -> list[dict]:
        """Search PRs reviewed by user in org within date range."""
        query = f"reviewed-by:{username} org:{self.org} type:pr updated:{from_date}..{to_date}"
        return self._search_issues(query)

    def _search_issues(self, query: str) -> list[dict]:
        """Execute search query with pagination."""
        all_items = []
        page = 1
        per_page = 100

        while True:
            response = self.client.get(
                "/search/issues",
                params={"q": query, "page": page, "per_page": per_page},
            )
            response.raise_for_status()
            data = response.json()
            items = data.get("items", [])
            all_items.extend(items)

            if len(items) < per_page or len(all_items) >= data.get("total_count", 0):
                break
            page += 1

        return all_items

    def get_rate_limit(self) -> dict:
        """Get current rate limit status."""
        response = self.client.get("/rate_limit")
        response.raise_for_status()
        return response.json()


def parse_event_date(event: dict) -> date:
    """Parse event created_at to date."""
    created_at = event.get("created_at", "")
    return datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()


def is_org_event(event: dict, org: str) -> bool:
    """Check if event belongs to organization."""
    repo = event.get("repo", {})
    repo_name = repo.get("name", "")
    return repo_name.startswith(f"{org}/")


def extract_activities_from_events(
    events: list[dict],
    org: str,
) -> list[dict]:
    """Extract activities from GitHub events.

    Returns list of dicts with: activity_type, repository, activity_date, count
    """
    activities: dict[tuple, int] = {}

    for event in events:
        if not is_org_event(event, org):
            continue

        event_type = event.get("type", "")
        repo_name = event.get("repo", {}).get("name", "")
        event_date = parse_event_date(event)

        activity_type = None
        count = 1

        if event_type == "PushEvent":
            activity_type = "commit"
            # Count commits in push
            count = len(event.get("payload", {}).get("commits", []))

        elif event_type == "PullRequestEvent":
            action = event.get("payload", {}).get("action", "")
            if action == "opened":
                activity_type = "pr_opened"
            elif action == "closed":
                pr = event.get("payload", {}).get("pull_request", {})
                if pr.get("merged"):
                    activity_type = "pr_merged"

        elif event_type == "PullRequestReviewEvent":
            # Only count approved reviews (not comments)
            review = event.get("payload", {}).get("review", {})
            if review.get("state") == "approved":
                activity_type = "review"

        elif event_type == "IssuesEvent":
            action = event.get("payload", {}).get("action", "")
            if action == "opened":
                activity_type = "issue_opened"
            elif action == "closed":
                activity_type = "issue_closed"

        if activity_type:
            key = (activity_type, repo_name, event_date)
            activities[key] = activities.get(key, 0) + count

    return [
        {
            "activity_type": key[0],
            "repository": key[1],
            "activity_date": key[2],
            "count": count,
        }
        for key, count in activities.items()
    ]
