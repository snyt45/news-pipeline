# news-pipeline

RSS + LLMキュレーション + Google Spreadsheet + NotebookLMラジオのパイプライン。

散歩中にNotebookLMラジオで自分向けの技術ニュースを聴くための仕組み。

## クイックスタート

### 1. 依存インストール

[mise](https://mise.jdx.dev/) が必要。

```bash
mise install
mise run setup
```

### 2. Gemini APIキー取得

[Google AI Studio](https://aistudio.google.com/apikey) でAPIキーを取得。

```bash
cp .env.example .env
```

`.env`の`GEMINI_API_KEY`に取得したキーを設定。

ここまでで`mise run dry-run`が動く（ターミナルにキュレーション結果を出力）。

### 3. GCPサービスアカウント作成

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. 「APIとサービス」→「ライブラリ」から **Google Sheets API** を有効化
3. 「APIとサービス」→「認証情報」→「認証情報を作成」→「サービスアカウント」で作成
4. 作成したサービスアカウントの「鍵」タブ →「鍵を追加」→「JSON」
5. ダウンロードしたJSONファイルをプロジェクトルートに `credentials.json` として配置

### 4. Spreadsheet準備

1. Google Spreadsheetを新規作成
2. 1行目にヘッダーを入力: `日付 | カテゴリ | タイトル | URL | 要約 | ソース`
3. サービスアカウントのメールアドレス（credentials.json内の`client_email`）をSpreadsheetの共有に追加（編集者権限）
4. SpreadsheetのURLから`SPREADSHEET_ID`を取得（`/d/`と`/edit`の間の文字列）

`.env`に追記:

```
SPREADSHEET_ID=取得したSpreadsheetのID
GOOGLE_CREDENTIALS_PATH=./credentials.json
```

ここまでで`mise run run`が動く（Spreadsheetに追記）。

## コマンド

```bash
mise tasks         # コマンド一覧を表示
mise run dry-run   # キュレーション結果をターミナルに出力
mise run run       # 全パイプライン実行（Spreadsheet出力）
mise run test      # テスト実行
```

## カスタマイズ

- `config/feeds.yaml` — RSSフィードURLを追加・変更
- `config/profile.yaml` — 興味・嗜好・除外基準を変更
- `.env` — APIキー・Google リソースIDを設定
