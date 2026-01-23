# GitHub Activities Dashboard - Design Document

## Overview

GitHub アクティビティを収集し、ブラウザでグラフ表示するローカルアプリケーション。

### 目的
- 自身のアクティビティの状況確認
- 他メンバーのアクティビティの状況確認
- 自身と他メンバーのアクティビティ比較
- 開発の滞りを早期発見し、サポートに入れるようにする

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (localhost:3000)              │
│  ┌─────────────────────────────────────────────────┐    │
│  │            React + Tremor (Dashboard)            │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                 Python Backend (FastAPI)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  REST API    │  │  Collector   │  │  Aggregator  │  │
│  │  (Display)   │  │  (GitHub API)│  │  (Weekly/    │  │
│  │              │  │              │  │   Monthly)   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    SQLite (data.db)                      │
│  - activities (raw data)                                 │
│  - Aggregation via SQL queries                          │
└─────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React + TypeScript + Tremor |
| Backend | Python + FastAPI + SQLAlchemy |
| Database | SQLite |
| Package Manager | uv (Python), pnpm (Node.js) |

## Directory Structure

```
github-activities-v2/
├── backend/
│   ├── pyproject.toml
│   ├── src/
│   │   └── github_activities/
│   │       ├── __init__.py
│   │       ├── main.py           # FastAPI entry point
│   │       ├── cli.py            # Data collection CLI
│   │       ├── models.py         # SQLAlchemy models
│   │       ├── github_client.py  # GitHub API client
│   │       ├── collector.py      # Data collection logic
│   │       └── routers/
│   │           ├── activities.py
│   │           └── users.py
│   ├── tests/
│   └── data/
│       └── .gitkeep
│
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── ActivityChart.tsx
│   │   │   └── UserComparison.tsx
│   │   └── api/
│   │       └── client.ts
│   └── ...
│
├── package.json                  # Root (concurrently)
├── .env.example
├── .env                          # gitignore
└── README.md
```

## Configuration

```bash
# .env
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_ORG=your-organization-name
TARGET_USERS=user1,user2,user3
```

## Data Model

```sql
-- Users
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT,
    last_collected_at TIMESTAMP,
    collect_from_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Activities (raw data)
CREATE TABLE activities (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    activity_type TEXT NOT NULL,  -- 'commit', 'pr_opened', 'pr_merged', 'review', 'issue_opened', 'issue_closed'
    repository TEXT NOT NULL,
    activity_date DATE NOT NULL,
    count INTEGER DEFAULT 1,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, activity_type, repository, activity_date)
);

CREATE INDEX idx_activities_user_date ON activities(user_id, activity_date);
CREATE INDEX idx_activities_type ON activities(activity_type);
```

## Activity Types

| Type | Description |
|------|-------------|
| commit | Commit count |
| pr_opened | PR created |
| pr_merged | PR merged |
| review | Code review |
| issue_opened | Issue created |
| issue_closed | Issue closed |

## GitHub API

### Endpoints Used

| Activity | API Endpoint |
|----------|--------------|
| All events (90 days) | `GET /users/{username}/events` |
| PR (older than 90 days) | `GET /search/issues?q=author:{user}+org:{org}+type:pr` |
| Issues (older than 90 days) | `GET /search/issues?q=author:{user}+org:{org}+type:issue` |

### Rate Limits

- Events API: 5000 req/hour (sufficient for a few users)
- Search API: 30 req/minute (for backfill only)

### Limitations

- Events API: max 90 days, max 300 events per request
- For older data: use Search API

## CLI Commands

```bash
# Collect data for today
python -m github_activities.cli collect

# Collect data for specific date
python -m github_activities.cli collect --date 2025-01-24

# Collect data for date range
python -m github_activities.cli collect --from 2025-01-01 --to 2025-01-24

# Add new user with backfill
python -m github_activities.cli add-user sasaki --backfill-from 2024-01-01

# Check collection status
python -m github_activities.cli status
```

## REST API

```
GET /api/users
  → User list with collection status

GET /api/activities/weekly?user={username}&from=2025-01-01&to=2025-01-24
  → Weekly aggregated data

GET /api/activities/monthly?user={username}&year=2025
  → Monthly aggregated data

GET /api/activities/comparison?users=sasaki,tanaka&period=weekly&from=2025-01-01
  → Multi-user comparison data

GET /api/activities/summary?user={username}
  → Dashboard summary (this week/month)
```

### Response Example (Weekly)

```json
{
  "user": "sasaki",
  "period": "weekly",
  "data": [
    {
      "week": "2025-W03",
      "start_date": "2025-01-13",
      "commit": 23,
      "pr_opened": 4,
      "pr_merged": 3,
      "review": 12,
      "issue_opened": 2,
      "issue_closed": 5,
      "total": 49
    }
  ]
}
```

## Frontend UI

```
┌─────────────────────────────────────────────────────────────┐
│  GitHub Activities Dashboard          [User Select ▼]       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────┐ │
│  │This Week│ │This     │ │Commits  │ │PRs      │ │Reviews│ │
│  │Total    │ │Month    │ │(Week)   │ │(Week)   │ │(Week) │ │
│  │ 49      │ │ 182     │ │ 23      │ │  4      │ │  12   │ │
│  │ +12 WoW │ │ +8 MoM  │ │ +5 WoW  │ │ +2 WoW  │ │-3 WoW │ │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └───────┘ │
│                        KPI Cards                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Weekly Activity Trend        [Weekly ▼] [Date Range]       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Line Chart (Tremor LineChart)               │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Activity Breakdown                                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Bar Chart (Tremor BarChart)                 │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Member Comparison           [Select users ☑☑☑]            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Horizontal Bar Chart                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Development

```bash
# Start both frontend and backend
npm run dev

# Or separately
npm run dev:backend   # http://localhost:8000
npm run dev:frontend  # http://localhost:3000
```
