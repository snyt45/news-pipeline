# 記事本文抽出 - Google Docs向け設計

## 目的

NotebookLMでリッチなラジオを生成するために、Google Docsに記事の本文を載せる。
現状はGeminiの短い要約のみでラジオが薄い。

## 方針

- Spreadsheetは変更なし（要約のみ）
- Google Docsに書き出す際に、記事URLから本文を取得して載せる
- 本文取得にはtrafilaturaを使用（APIコストゼロ）
- 本文が取れなかった記事はDocsに載せない

## データフロー

```
fetch_feeds() → 記事リスト(数十件)
    ↓
curate() → 厳選15件
    ↓
append_to_spreadsheet() → 変更なし
    ↓
fetch_article_contents() → 厳選記事のURLから本文取得 [新規]
    ↓
write_to_google_docs() → 本文付きでDocs書き出し [変更]
```

## 変更箇所

### 1. fetch_article_contents(urls) - 新規関数

trafilaturaで記事URLから本文を取得する。
取得できなかったURLはスキップしてログ出力。
戻り値: {url: content} の辞書。

### 2. write_to_google_docs() - 変更

本文データ（辞書）を追加引数で受け取る。
本文がある記事のみ「タイトル + URL + 本文」で書き出す。
本文がない記事はDocsに載せない。

### 3. _write_docs_if_configured() / main - 変更

Docs書き出し前にfetch_article_contents()を呼ぶ。

### 4. requirements.txt

trafilaturaを追加。

## Docsの出力フォーマット

```
2026-03-09 技術ニュース

## AI/LLM

- 記事タイトル
  URL: https://...
  (記事本文)

## DevTools

- 記事タイトル
  URL: https://...
  (記事本文)
```

## エラー処理

- trafilatura取得失敗 → その記事をスキップ（ログ出力）
- 全記事の本文取得失敗 → Docs書き出しスキップ
