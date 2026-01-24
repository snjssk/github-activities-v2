# CLAUDE.md

このファイルはClaude Codeがプロジェクトを理解するためのガイドです。

## プロジェクト概要

GitHub アクティビティを収集し、ダッシュボードで可視化するローカルアプリケーション。

**目的:**
- 自身・他メンバーの開発アクティビティを週次/月次で確認
- 開発の滞りを早期発見

## ドキュメント

**必ず `/docs` ディレクトリを確認してください:**
- `docs/plans/` - 設計ドキュメント
- `docs/2026-01-24-development-notes.md` - 開発時の問題と解決策

## 技術スタック

| Layer | Technology |
|-------|------------|
| Backend | Python 3.13 + FastAPI + SQLAlchemy + SQLite |
| Frontend | React 18 + TypeScript + Tremor + Vite |
| Styling | Tailwind CSS 3.4 |

## 開発コマンド

```bash
# 両方同時起動
npm run dev

# バックエンドのみ
cd backend && source .venv/bin/activate && uvicorn github_activities.main:app --reload --port 8000

# フロントエンドのみ
cd frontend && pnpm dev

# データ収集CLI
cd backend && source .venv/bin/activate
python -m github_activities.cli add-user USERNAME --backfill-from 2025-01-01
python -m github_activities.cli collect
python -m github_activities.cli status
```

## 環境設定

`.env` ファイルをルートに作成（`.env.example` を参照）:
```
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_ORG=your-organization-name
TARGET_USERS=user1,user2,user3
```

## コーディング規約

### コミット
- **細かくコミットする** - 機能単位で分割
- Co-Authored-By を含める

### ドキュメント
- ファイル名は `YYYY-MM-DD-<topic>.md` 形式

### フロントエンド
- Tremor コンポーネントを使用
- 色は `tailwind.config.js` の safelist に追加が必要な場合あり

## 既知の問題・制限

### GitHub API
- **Events API**: 90日分のみ、commits フィールドが空で返る場合あり
- **Search API**: PR/Issue のみ、コミットは取得不可
- **Rate Limit**: Core 5000/時間、Search 30/分

### データ
- コミット数が取得できない（Events API の制限）
- 90日以上前のデータはPR/Issueのみ

### Tailwind + Tremor
- 動的クラスは `safelist` に追加が必要
- 例: `stroke-indigo-500`, `fill-blue-500` など

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
