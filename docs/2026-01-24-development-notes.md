# GitHub Activities Dashboard - 開発メモ

## 環境構築

### うまくいった点
- **モノレポ構成**: `backend/` と `frontend/` のディレクトリ分離がシンプルで管理しやすい
- **concurrently による同時起動**: ルートの `npm run dev` で両方起動できて便利
- **pip + venv**: uv が未インストールでも標準の pip + venv で問題なく動作

### うまくいかなかった点
- **uv 未インストール**: 最初 uv を前提にしていたが、環境になかったため pip に切り替え
- **.env のパス計算ミス**: `Path(__file__).parent` の数を間違えて `.env` が読み込めなかった
  ```python
  # 誤: 5回 parent
  PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
  # 正: 4回 parent
  PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
  ```

---

## バックエンド (Python + FastAPI)

### うまくいった点
- **FastAPI + SQLAlchemy**: セットアップが簡単で、型ヒントとの相性も良い
- **CLI (Click)**: データ収集コマンドが直感的に作れた
- **CORS 設定**: フロントエンドとの連携がスムーズ

### うまくいかなかった点

#### 1. SQLAlchemy の `metadata` 予約語衝突
Activity モデルで `metadata` プロパティを定義したら、SQLAlchemy の `Base.metadata` と衝突してエラー。

```python
# 誤: metadata は予約語
@property
def metadata(self) -> Optional[dict]:
    ...

# 正: extra_data に変更
@property
def extra_data(self) -> Optional[dict]:
    ...
```

#### 2. GitHub Events API からコミット数が取得できない
PushEvent の `payload.commits` が空配列で返ってくる。

```python
# 期待した構造
{
  "type": "PushEvent",
  "payload": {
    "commits": [{"sha": "...", "message": "..."}]  # ← 実際は空
  }
}
```

**原因**: GitHub API の仕様で、Events API 経由だと commits 詳細が省略される場合がある。

**対応案**:
- GraphQL API を使う
- Commits API (`/repos/{owner}/{repo}/commits`) を別途呼ぶ

#### 3. データギャップの発生
- Events API: 90日分のみ取得可能
- Search API: PR/Issue は取得できるが、コミットは対象外
- 結果: 90日より古い期間のコミットデータが取得不可

#### 4. pr_merged が0件
Search API で merged の判定ロジックに問題がある可能性。要調査。

---

## フロントエンド (React + Tremor)

### うまくいった点
- **Tremor**: ダッシュボード向けコンポーネントが豊富で、見た目が整う
- **Vite**: 開発サーバーの起動が速い
- **API Client**: 型定義を共有して型安全に API を呼び出せた

### うまくいかなかった点

#### 1. Tremor のグラフが色なし（全部グレー）
Tailwind CSS の purge で Tremor が使う色クラスが削除されていた。

```javascript
// tailwind.config.js に safelist を追加
safelist: [
  {
    pattern: /^(bg|stroke|fill|text|border)-(slate|gray|...|rose)-(50|...|950)/,
  },
],
```

#### 2. LineChart が点だけで線が表示されない
データポイントが少ないと線が見えにくい。AreaChart に変更して解決。

```tsx
// 変更前
<LineChart ... />

// 変更後
<AreaChart
  curveType="monotone"
  showAnimation={true}
  ...
/>
```

#### 3. BarChart の色が1色しか適用されない
`categories` が1つだと最初の色しか使われない。BarList に変更して各項目に色を設定。

#### 4. 日付計算のズレ
バックエンドの `date.today()` がホットリロード後も古い値を返す問題。サーバー再起動で解決。

---

## まとめ

### 学んだこと
1. **SQLAlchemy の予約語に注意**: `metadata`, `query` などは避ける
2. **GitHub API の制限を理解する**: Events API は90日、commits 詳細は別 API
3. **Tailwind + UIライブラリの組み合わせ**: safelist で動的クラスを保護する必要あり
4. **モノレポの起動管理**: concurrently でシンプルに管理できる

### 残課題
- [ ] コミット数の取得（GraphQL API または Commits API）
- [ ] pr_merged の判定ロジック修正
- [ ] 期間選択 UI の追加
- [ ] データ再収集コマンドの改善

### 技術スタック確定版
| Layer | Technology |
|-------|------------|
| Frontend | React 18 + TypeScript + Tremor 3.18 + Vite |
| Backend | Python 3.13 + FastAPI + SQLAlchemy + SQLite |
| Styling | Tailwind CSS 3.4 |
| Package Manager | pnpm (frontend) + pip (backend) |
