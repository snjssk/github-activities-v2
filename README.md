# GitHub Activities Dashboard

GitHub アクティビティを収集し、ダッシュボードで可視化するローカルアプリケーション。

## 目的

- 自身・他メンバーの開発アクティビティを週次/月次で確認
- 開発の滞りを早期発見

## 技術スタック

| Layer | Technology |
|-------|------------|
| Backend | Python 3.13 + FastAPI + SQLAlchemy + SQLite |
| Frontend | React 18 + TypeScript + Tremor + Vite |
| Styling | Tailwind CSS 3.4 |

## セットアップ

### 環境変数

`.env` ファイルをルートに作成:

```
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_ORG=your-organization-name
TARGET_USERS=user1,user2,user3
```

### 起動

```bash
# 両方同時起動
npm run dev

# バックエンドのみ
cd backend && source .venv/bin/activate && uvicorn github_activities.main:app --reload --port 8000

# フロントエンドのみ
cd frontend && pnpm dev
```

### データ収集

```bash
cd backend && source .venv/bin/activate

# ユーザー追加
python -m github_activities.cli add-user USERNAME

# データ収集（直近90日）
python -m github_activities.cli collect

# 過去データも含めて収集
python -m github_activities.cli collect --from 2025-01-01

# ステータス確認
python -m github_activities.cli status
```

## GitHub API 使用詳細

本アプリケーションは以下のGitHub APIを使用してデータを収集します。

### 使用するAPI一覧

| API | エンドポイント | 用途 | 日付制限 |
|-----|---------------|------|---------|
| Organization Repos API | `GET /orgs/{org}/repos` | 組織内リポジトリ一覧取得 | なし |
| Commits API | `GET /repos/{owner}/{repo}/commits` | コミット履歴取得 | なし |
| Events API | `GET /users/{username}/events` | ユーザーイベント取得 | 90日 |
| Search API | `GET /search/issues` | PR/Issue検索 | なし |

### データ収集フロー

```
┌─────────────────────────────────────────────────────────────────┐
│                    collect コマンド実行                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. Events API (自分のみ有効)                                     │
│    GET /users/{username}/events                                  │
│    → PR opened/merged, Review, Issue opened/closed               │
│    → 他人のprivateリポジトリイベントは取得不可                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Commits API (組織リポジトリ経由)                               │
│    GET /orgs/{org}/repos → リポジトリ一覧取得                     │
│    GET /repos/{org}/{repo}/commits?author={username}             │
│    → 組織内全リポジトリからユーザーのコミットを取得                  │
│    → 他メンバーのコミットも取得可能                                │
│    → フィルタ: archived=false, pushed_within_days=20              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Search API (Events APIが空の場合 or 90日以上前)                │
│    GET /search/issues?q=author:{user}+org:{org}+type:pr          │
│    GET /search/issues?q=author:{user}+org:{org}+type:issue       │
│    GET /search/issues?q=reviewed-by:{user}+org:{org}+type:pr     │
│    → 組織内のPR/Issue/Reviewを検索                               │
│    → 他メンバーのデータも取得可能                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 自分 vs 他メンバーのデータ取得

| データ種別 | 自分 | 他メンバー | 使用API |
|-----------|------|-----------|---------|
| コミット | ✅ | ✅ | Commits API (org経由) |
| PR opened/merged | ✅ | ✅ | Events API / Search API |
| Review | ✅ | ✅ | Events API / Search API |
| Issue opened/closed | ✅ | ✅ | Events API / Search API |

**ポイント:**
- 他メンバーのEvents APIはprivateリポジトリのイベントを返さない
- そのため、Events APIが空の場合は自動的にSearch APIにフォールバック
- Commits APIは組織のリポジトリに直接アクセスするため、他メンバーのコミットも取得可能

### API最適化

リクエスト数削減のため、以下のフィルタを適用:

1. **archived=false**: アーカイブされたリポジトリを除外
2. **pushed_within_days=20**: 20日以内にpushされたリポジトリのみ対象

例: 433リポジトリ → 86リポジトリ（約80%削減）

### Rate Limit

| API | 制限 |
|-----|------|
| Core API (Events/Commits/Repos) | 5,000 リクエスト/時間 |
| Search API | 30 リクエスト/分 |

1回のcollectで約100リクエスト程度（ユーザー1人あたり）。

## 収集されるアクティビティ

| 種別 | 説明 |
|------|------|
| commit | コミット数 |
| pr_opened | オープンしたPR数 |
| pr_merged | マージされたPR数 |
| review | 承認(approved)したレビュー数 |
| issue_opened | オープンしたIssue数 |
| issue_closed | クローズしたIssue数 |

## ディレクトリ構成

```
github-activities-v2/
├── backend/
│   ├── src/github_activities/
│   │   ├── main.py          # FastAPI エントリーポイント
│   │   ├── cli.py           # データ収集CLI
│   │   ├── models.py        # SQLAlchemy モデル
│   │   ├── collector.py     # データ収集ロジック
│   │   ├── github_client.py # GitHub API クライアント
│   │   └── routers/         # REST API エンドポイント
│   └── data/                # SQLite DB (gitignore)
├── frontend/
│   └── src/
│       ├── components/      # React コンポーネント
│       └── api/             # API クライアント
├── docs/                    # ドキュメント
└── .env                     # 環境変数 (gitignore)
```
