# news-pipeline

RSS + LLMキュレーション + Google Spreadsheet + NotebookLMラジオのパイプライン。

散歩中にNotebookLMラジオで自分向けの技術ニュースを聴くための仕組み。

## 必要なもの

- [mise](https://mise.jdx.dev/)
- [Gemini API Key](https://aistudio.google.com/apikey)（Google AI Studio で取得）

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

## カスタマイズ

- `config/feeds.yaml` — RSSフィードURLを追加・変更
- `config/profile.yaml` — 興味・嗜好・除外基準を変更
- `.env` — APIキー・Google リソースIDを設定
