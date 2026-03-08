# Google Docs書き出し + Spreadsheetトークン警告 設計

## Goal

Spreadsheetから今日の日付の行を読み取り、Google Docsに上書きする。NotebookLMのソースとして使い、ラジオを生成する。

## データフロー

```
Spreadsheet（今日の日付の行）→ Google Docsに上書き（カテゴリ別に構造化）
```

パイプラインの結果を直接Docsに書くのではなく、Spreadsheetの今日分を読み取って書き出す。手動追記した行も含まれ、再実行しても冪等。

## Google Docs書き出し

- `GOOGLE_DOC_ID`環境変数で対象ドキュメントを指定
- Docsの中身を毎回全文書き換え（1日分のみ保持）
- カテゴリ別にセクション分けして構造化
- `--dry-run`時はスキップ
- Google Docs APIスコープ: `https://www.googleapis.com/auth/documents`

### 書き出しフォーマット

```
2026-03-09 技術ニュース

## AI/LLM

- タイトル1
  URL: https://...
  要約テキスト

- タイトル2
  URL: https://...
  要約テキスト

## DevTools

- タイトル3
  URL: https://...
  要約テキスト
```

## Spreadsheetトークン制限の警告

- NotebookLMのSpreadsheetソース制限: 10万トークン（ファイル単位）
- 追記前に全セルの文字数からトークン数を概算
- 8万トークン（80%）を超えていたら警告メッセージを出力
- ローテーションは手動（新規Spreadsheet作成 → .envのID差し替え）
- READMEに手順を記載

## 実装方針

- `build_sheets_service()`を拡張し、Docs APIのサービスも返す or 別関数で構築
- `read_today_from_spreadsheet(service)`: Spreadsheetから今日の行を読み取る
- `write_to_google_docs(docs_service, rows)`: Docsに上書き
- `check_spreadsheet_token_usage(service)`: トークン使用量を概算して警告

## 要約の充実化（将来検討）

ラジオの質が物足りない場合、Geminiに詳細要約（500-1000字/記事）を生成させるオプションを追加する。現時点では実装しない。

## 参考

- NotebookLM Spreadsheetソース制限: 10万トークン（ファイル単位、複数シートまとめて1ソース）
- NotebookLM Google Docsソース制限: 50万語
- NotebookLMソース数制限: 無料50個 / Plus 100個 / Pro 300個
