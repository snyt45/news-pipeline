# Phase 2a 設計: Google Spreadsheet追記

## Goal

キュレーション結果をGoogle Spreadsheetに追記する。日々の技術ニュースを蓄積し、後から振り返れるようにする。

## データフロー

```
curate() の結果 → append_to_spreadsheet() → Google Sheets API で最終行に追記
```

## カラム構成（1行1記事）

| A: 日付 | B: カテゴリ | C: タイトル | D: URL | E: 要約 | F: ソース |

## 認証

- GCPサービスアカウントのcredentials.jsonをプロジェクトルートに配置
- google-authとgoogle-api-python-clientを依存に追加
- .envのSPREADSHEET_IDとGOOGLE_CREDENTIALS_PATHを使う

## 実装方針

- main.pyにappend_to_spreadsheet(curated)関数を1つ追加
- main()の--dry-runでないルートでこの関数を呼ぶ
- ヘッダー行は手動で作っておく前提
- 既存の行の後ろにappendするだけ。上書きや重複チェックはしない

## エラー処理

- 認証エラー/API呼び出し失敗時はエラーメッセージを出して終了
- キュレーション結果はターミナルにも出力済みなのでデータは失われない

## テスト

- Google Sheets APIのモックでappendが正しい形式のデータで呼ばれることを検証
