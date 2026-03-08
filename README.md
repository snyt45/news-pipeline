# news-pipeline

RSS + LLMキュレーション + Google Spreadsheet + NotebookLMラジオのパイプライン。

散歩中にNotebookLMラジオで自分向けの技術ニュースを聴くための仕組み。

## 必要なもの

- Python 3.13+
- [Gemini API Key](https://aistudio.google.com/apikey)（Google AI Studio で取得）

## セットアップ

```bash
cp .env.example .env
# .env にGEMINI_API_KEYを設定
make setup
```

## コマンド

```bash
make help      # コマンド一覧を表示
make dry-run   # キュレーション結果をターミナルに出力
make run       # 全パイプライン実行（Spreadsheet + Google Docs出力）
make test      # テスト実行
```

## カスタマイズ

- `config/feeds.yaml` — RSSフィードURLを追加・変更
- `config/profile.yaml` — 興味・嗜好・除外基準を変更
- `.env` — APIキー・Google リソースIDを設定
