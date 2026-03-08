# Spreadsheet追記機能 実装プラン

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** キュレーション結果をGoogle Spreadsheetの最終行に追記する。

**Architecture:** main.pyに`append_to_spreadsheet()`関数を追加。Google Sheets APIのサービスアカウント認証で接続し、curate()の結果を1行1記事でappendする。`--dry-run`でないときにこの関数を呼ぶ。

**Tech Stack:** google-auth, google-api-python-client（追加）、既存のPython 3.13, pytest

---

### Task 1: 依存パッケージ追加

**Files:**
- Modify: `~/work/news-pipeline/requirements.txt`

**Step 1: requirements.txtにパッケージ追加**

```
feedparser
pyyaml
python-dotenv
google-genai
google-auth
google-api-python-client
pytest
```

**Step 2: インストール**

Run: `cd ~/work/news-pipeline && source .venv/bin/activate && pip install -r requirements.txt`

**Step 3: コミット**

```bash
git add requirements.txt
git commit -m "Spreadsheet連携用のパッケージを追加"
```

---

### Task 2: 定数追加

**Files:**
- Modify: `~/work/news-pipeline/main.py`

**Step 1: main.pyの定数セクションに追加**

既存の定数の後に追加:

```python
SPREADSHEET_ID_ENV = "SPREADSHEET_ID"
CREDENTIALS_PATH_ENV = "GOOGLE_CREDENTIALS_PATH"
DEFAULT_CREDENTIALS_PATH = "./credentials.json"
SPREADSHEET_RANGE = "Sheet1"
```

**Step 2: コミット**

```bash
git add main.py
git commit -m "Spreadsheet関連の定数を追加"
```

---

### Task 3: append_to_spreadsheet テスト

**Files:**
- Modify: `~/work/news-pipeline/tests/test_main.py`

**Step 1: テストを追加**

```python
def test_append_to_spreadsheet_sends_correct_data():
    """キュレーション結果が正しい形式でSpreadsheetに追記される"""
    curated = [
        {
            "title": "Test Article",
            "url": "https://example.com/1",
            "summary_ja": "テスト要約",
            "source": "Test Feed",
            "category": "AI/LLM",
        },
    ]

    mock_service = MagicMock()
    mock_sheet = mock_service.spreadsheets.return_value.values.return_value
    mock_sheet.append.return_value.execute.return_value = {}

    from main import SPREADSHEET_ID_ENV, CREDENTIALS_PATH_ENV
    with patch("main.build") as mock_build, \
         patch("main.ServiceAccountCredentials.from_service_account_file") as mock_creds, \
         patch.dict("os.environ", {SPREADSHEET_ID_ENV: "test-sheet-id", CREDENTIALS_PATH_ENV: "./credentials.json"}):
        mock_build.return_value = mock_service
        from main import append_to_spreadsheet
        append_to_spreadsheet(curated)

    mock_sheet.append.assert_called_once()
    call_kwargs = mock_sheet.append.call_args
    body = call_kwargs[1]["body"] if "body" in call_kwargs[1] else call_kwargs.kwargs["body"]
    rows = body["values"]
    assert len(rows) == 1
    assert rows[0][1] == "AI/LLM"
    assert rows[0][2] == "Test Article"
    assert rows[0][3] == "https://example.com/1"
    assert rows[0][4] == "テスト要約"
    assert rows[0][5] == "Test Feed"


def test_append_to_spreadsheet_skips_empty_list():
    """空リストの場合はAPI呼び出しをスキップする"""
    with patch("main.build") as mock_build:
        from main import append_to_spreadsheet
        append_to_spreadsheet([])
    mock_build.assert_not_called()
```

**Step 2: テストが失敗することを確認**

Run: `cd ~/work/news-pipeline && source .venv/bin/activate && python -m pytest tests/test_main.py::test_append_to_spreadsheet_sends_correct_data -v`

Expected: FAIL（append_to_spreadsheetがない）

---

### Task 4: append_to_spreadsheet 実装

**Files:**
- Modify: `~/work/news-pipeline/main.py`

**Step 1: importを追加**

ファイル先頭のimportセクションに追加:

```python
from datetime import datetime, timezone, timedelta, date
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build
```

既存の`from datetime import datetime, timezone, timedelta`を上の行に置き換える。

**Step 2: append_to_spreadsheet関数を追加**

`parse_curate_response`関数の後、`main`関数の前に追加:

```python
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def append_to_spreadsheet(curated):
    if not curated:
        return

    spreadsheet_id = os.environ[SPREADSHEET_ID_ENV]
    credentials_path = os.environ.get(CREDENTIALS_PATH_ENV, DEFAULT_CREDENTIALS_PATH)

    creds = ServiceAccountCredentials.from_service_account_file(
        credentials_path, scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=creds)

    today = date.today().isoformat()
    rows = []
    for a in curated:
        rows.append([
            today,
            a.get("category", ""),
            a["title"],
            a["url"],
            a.get("summary_ja", ""),
            a.get("source", ""),
        ])

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=SPREADSHEET_RANGE,
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()

    print(f"Spreadsheetに{len(rows)}件追記しました")
```

**Step 3: main()のTODOを置き換え**

main関数内の以下を:

```python
    # Phase 2: Google出力（後で実装）
    print("[TODO] Spreadsheet追記 + Google Docs上書き")
```

これに置き換え:

```python
    print("Spreadsheetに追記中...")
    append_to_spreadsheet(curated)
```

**Step 4: テストがパスすることを確認**

Run: `cd ~/work/news-pipeline && source .venv/bin/activate && python -m pytest tests/test_main.py -v`

Expected: ALL passed

**Step 5: コミット**

```bash
git add main.py tests/test_main.py
git commit -m "Spreadsheet追記機能を実装（append_to_spreadsheet）"
```

---

### Task 5: READMEにセットアップ手順を追記

**Files:**
- Modify: `~/work/news-pipeline/README.md`

**Step 1: READMEの「必要なもの」セクションと「セットアップ」セクションを更新**

「必要なもの」に追加:

```markdown
- GCPサービスアカウント（Google Sheets API用）
```

「セットアップ」の後に「Google Spreadsheet連携」セクションを追加:

```markdown
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

```.env
SPREADSHEET_ID=取得したSpreadsheetのID
GOOGLE_CREDENTIALS_PATH=./credentials.json
```
```

**Step 2: コミット**

```bash
git add README.md
git commit -m "READMEにSpreadsheet連携のセットアップ手順を追記"
```

---

### Task 6: 動作確認 + push

**Step 1: 実際にSpreadsheetへの追記を確認**

Run: `cd ~/work/news-pipeline && source .venv/bin/activate && python main.py`

Expected: RSS取得 → Geminiキュレーション → Spreadsheetに追記 → 「Spreadsheetに15件追記しました」

※ .envにSPREADSHEET_IDとGOOGLE_CREDENTIALS_PATHが設定済み、credentials.jsonが配置済み、Spreadsheetにサービスアカウントが共有されている必要がある。

**Step 2: push**

```bash
git push origin main
```
