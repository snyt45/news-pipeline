# news-pipeline

RSS + LLMキュレーション + Google Spreadsheet + NotebookLMラジオのパイプライン。

散歩中にNotebookLMラジオで自分向けの技術ニュースを聴くための仕組み。

## 必要なもの

- [mise](https://mise.jdx.dev/)
- [Gemini API Key](https://aistudio.google.com/apikey)（Google AI Studio で取得）
- GCPサービスアカウント（Google Sheets API用）

## セットアップ

```bash
cp .env.example .env
# .env にGEMINI_API_KEYを設定
mise install
mise run setup
```

## コマンド

```bash
mise tasks     # コマンド一覧を表示
mise run dry-run   # キュレーション結果をターミナルに出力
mise run run       # 全パイプライン実行（Spreadsheet + Google Docs出力）
mise run test      # テスト実行
```

## Google Spreadsheet連携

### 1. GCPプロジェクト作成

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. 「APIとサービス」→「ライブラリ」から **Google Sheets API** を有効化

### 2. サービスアカウント作成

1. 「APIとサービス」→「認証情報」→「認証情報を作成」→「サービスアカウント」
2. 名前を入力して作成
3. 作成したサービスアカウントの「鍵」タブ →「鍵を追加」→「JSON」
4. ダウンロードしたJSONファイルをプロジェクトルートに `credentials.json` として配置

### 3. Spreadsheet準備

1. Google Spreadsheetを新規作成
2. 1行目にヘッダーを入力: `日付 | カテゴリ | タイトル | URL | 要約 | ソース`
3. サービスアカウントのメールアドレス（credentials.json内の`client_email`）をSpreadsheetの共有に追加（編集者権限）
4. SpreadsheetのURLから `SPREADSHEET_ID` を取得（`/d/` と `/edit` の間の文字列）

### 4. .env設定

```
SPREADSHEET_ID=取得したSpreadsheetのID
GOOGLE_CREDENTIALS_PATH=./credentials.json
```

## カスタマイズ

- `config/feeds.yaml` — RSSフィードURLを追加・変更
- `config/profile.yaml` — 興味・嗜好・除外基準を変更
- `.env` — APIキー・Google リソースIDを設定
