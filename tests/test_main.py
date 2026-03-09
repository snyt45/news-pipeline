import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta, date


def test_fetch_feeds_returns_articles_from_yaml(tmp_path):
    """feeds.yamlを読み込んでフィードから記事を取得する"""
    feeds_yaml = tmp_path / "feeds.yaml"
    feeds_yaml.write_text(
        "feeds:\n"
        '  - name: "Test Feed"\n'
        '    url: "https://example.com/feed"\n'
        '    lang: "ja"\n'
    )

    now = datetime.now(timezone.utc)
    mock_entry = MagicMock()
    mock_entry.title = "テスト記事"
    mock_entry.link = "https://example.com/article"
    mock_entry.get.return_value = "テスト要約"
    mock_entry.published_parsed = (now - timedelta(hours=1)).timetuple()

    mock_feed = MagicMock()
    mock_feed.entries = [mock_entry]
    mock_feed.bozo = False

    with patch("main.feedparser.parse", return_value=mock_feed):
        from main import fetch_feeds
        articles = fetch_feeds(str(feeds_yaml))

    assert len(articles) == 1
    assert articles[0]["title"] == "テスト記事"
    assert articles[0]["url"] == "https://example.com/article"
    assert articles[0]["source"] == "Test Feed"
    assert articles[0]["lang"] == "ja"


def test_fetch_feeds_skips_old_articles(tmp_path):
    """24時間以上前の記事はスキップする"""
    feeds_yaml = tmp_path / "feeds.yaml"
    feeds_yaml.write_text(
        "feeds:\n"
        '  - name: "Test Feed"\n'
        '    url: "https://example.com/feed"\n'
        '    lang: "ja"\n'
    )

    old_time = datetime.now(timezone.utc) - timedelta(hours=25)
    mock_entry = MagicMock()
    mock_entry.title = "古い記事"
    mock_entry.link = "https://example.com/old"
    mock_entry.get.return_value = ""
    mock_entry.published_parsed = old_time.timetuple()

    mock_feed = MagicMock()
    mock_feed.entries = [mock_entry]
    mock_feed.bozo = False

    with patch("main.feedparser.parse", return_value=mock_feed):
        from main import fetch_feeds
        articles = fetch_feeds(str(feeds_yaml))

    assert len(articles) == 0


def test_fetch_feeds_skips_failed_feed(tmp_path):
    """フィード取得失敗時はスキップして続行する"""
    feeds_yaml = tmp_path / "feeds.yaml"
    feeds_yaml.write_text(
        "feeds:\n"
        '  - name: "Bad Feed"\n'
        '    url: "https://example.com/bad"\n'
        '    lang: "en"\n'
    )

    mock_feed = MagicMock()
    mock_feed.entries = []
    mock_feed.bozo = True

    with patch("main.feedparser.parse", return_value=mock_feed):
        from main import fetch_feeds
        articles = fetch_feeds(str(feeds_yaml))

    assert len(articles) == 0


def test_parse_curate_response_with_json_fence():
    """JSONフェンス付きレスポンスをパースできる"""
    from main import parse_curate_response
    text = '```json\n[{"title": "Test"}]\n```'
    result = parse_curate_response(text)
    assert result == [{"title": "Test"}]


def test_parse_curate_response_without_fence():
    """フェンスなしの生JSONもパースできる"""
    from main import parse_curate_response
    text = '[{"title": "Test"}]'
    result = parse_curate_response(text)
    assert result == [{"title": "Test"}]


def test_parse_curate_response_invalid_json():
    """不正なテキストは空リストを返す"""
    from main import parse_curate_response
    result = parse_curate_response("これはJSONではない")
    assert result == []


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

    with patch.dict("os.environ", {"SPREADSHEET_ID": "test-sheet-id"}):
        from main import append_to_spreadsheet
        append_to_spreadsheet(mock_service, curated)

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


def test_build_docs_service_creates_service():
    """Google Docs APIサービスが構築される"""
    mock_creds = MagicMock()

    with patch("main.ServiceAccountCredentials.from_service_account_file", return_value=mock_creds) as mock_from_file, \
         patch("main.build") as mock_build, \
         patch.dict("os.environ", {"GOOGLE_CREDENTIALS_PATH": "./credentials.json"}):
        from main import build_docs_service
        build_docs_service()

    mock_build.assert_called_once()
    call_args = mock_build.call_args
    assert call_args[0][0] == "docs"
    assert call_args[0][1] == "v1"


def test_read_today_rows_returns_today_rows():
    """今日の日付の行だけを返す"""
    today = date.today().isoformat()

    all_rows = [
        ["日付", "カテゴリ", "タイトル", "URL", "要約", "ソース"],
        [today, "AI/LLM", "今日の記事", "https://example.com/1", "要約1", "Zenn"],
        ["2026-03-01", "DevTools", "古い記事", "https://example.com/2", "要約2", "HN"],
        [today, "DevTools", "今日の記事2", "https://example.com/3", "要約3", "HN"],
    ]

    from main import read_today_rows
    rows = read_today_rows(all_rows)

    assert len(rows) == 2
    assert rows[0][2] == "今日の記事"
    assert rows[1][2] == "今日の記事2"


def test_write_to_google_docs_formats_by_category():
    """本文がある記事のみカテゴリ別に構造化してDocsに書き出す"""
    today = date.today().isoformat()

    rows = [
        [today, "AI/LLM", "AI記事1", "https://example.com/1", "AI要約1", "Zenn"],
        [today, "AI/LLM", "AI記事2", "https://example.com/2", "AI要約2", "HN"],
        [today, "DevTools", "ツール記事", "https://example.com/3", "ツール要約", "Zenn"],
    ]

    contents = {
        "https://example.com/1": "AI記事1の本文です",
        "https://example.com/3": "ツール記事の本文です",
    }

    mock_docs_service = MagicMock()
    mock_docs_service.documents.return_value.get.return_value.execute.return_value = {
        "body": {"content": [{"endIndex": 1}]}
    }

    with patch.dict("os.environ", {"GOOGLE_DOC_ID": "test-doc-id"}):
        from main import write_to_google_docs
        write_to_google_docs(mock_docs_service, rows, contents)

    mock_docs_service.documents.return_value.batchUpdate.assert_called()
    call_args = mock_docs_service.documents.return_value.batchUpdate.call_args
    body = call_args[1]["body"] if "body" in call_args[1] else call_args.kwargs["body"]
    requests = body["requests"]

    insert_texts = [r["insertText"]["text"] for r in requests if "insertText" in r]
    full_text = "".join(insert_texts)
    # 本文がある記事は載る
    assert "AI記事1" in full_text
    assert "AI記事1の本文です" in full_text
    assert "ツール記事" in full_text
    assert "ツール記事の本文です" in full_text
    # 本文がないAI記事2は載らない
    assert "AI記事2" not in full_text
    # 要約は載らない
    assert "AI要約1" not in full_text


def test_write_to_google_docs_skips_when_no_rows():
    """行がない場合はAPI呼び出しをスキップする"""
    mock_docs_service = MagicMock()

    with patch.dict("os.environ", {"GOOGLE_DOC_ID": "test-doc-id"}):
        from main import write_to_google_docs
        write_to_google_docs(mock_docs_service, [], {})

    mock_docs_service.documents.return_value.batchUpdate.assert_not_called()


def test_write_to_google_docs_skips_when_no_contents():
    """本文が1件も取れなかった場合はAPI呼び出しをスキップする"""
    today = date.today().isoformat()
    rows = [
        [today, "AI/LLM", "記事1", "https://example.com/1", "要約1", "Zenn"],
    ]

    mock_docs_service = MagicMock()

    with patch.dict("os.environ", {"GOOGLE_DOC_ID": "test-doc-id"}):
        from main import write_to_google_docs
        write_to_google_docs(mock_docs_service, rows, {})

    mock_docs_service.documents.return_value.batchUpdate.assert_not_called()


def test_fetch_article_contents_returns_content():
    """URLから記事本文を取得して辞書で返す"""
    from main import fetch_article_contents

    with patch("main.trafilatura.fetch_url", return_value="<html><body><p>記事の本文です</p></body></html>") as mock_fetch, \
         patch("main.trafilatura.extract", return_value="記事の本文です") as mock_extract:
        result = fetch_article_contents(["https://example.com/article1"])

    assert result == {"https://example.com/article1": "記事の本文です"}
    mock_fetch.assert_called_once_with("https://example.com/article1")


def test_fetch_article_contents_skips_failed_urls():
    """本文取得に失敗したURLはスキップする"""
    from main import fetch_article_contents

    with patch("main.trafilatura.fetch_url", return_value=None):
        result = fetch_article_contents(["https://example.com/fail"])

    assert result == {}


def test_fetch_article_contents_skips_empty_extract():
    """extractがNoneを返した場合はスキップする"""
    from main import fetch_article_contents

    with patch("main.trafilatura.fetch_url", return_value="<html></html>"), \
         patch("main.trafilatura.extract", return_value=None):
        result = fetch_article_contents(["https://example.com/empty"])

    assert result == {}


def test_fetch_article_contents_mixed_results():
    """成功と失敗が混在する場合、成功分だけ返す"""
    from main import fetch_article_contents

    def mock_fetch(url):
        if "good" in url:
            return "<html><body><p>本文</p></body></html>"
        return None

    with patch("main.trafilatura.fetch_url", side_effect=mock_fetch), \
         patch("main.trafilatura.extract", return_value="本文"):
        result = fetch_article_contents([
            "https://example.com/good",
            "https://example.com/bad",
        ])

    assert len(result) == 1
    assert "https://example.com/good" in result


def test_fetch_article_contents_continues_on_exception():
    """例外が発生しても残りのURLの処理を続行する"""
    from main import fetch_article_contents

    def mock_fetch(url):
        if "error" in url:
            raise ConnectionError("接続エラー")
        return "<html><body><p>本文</p></body></html>"

    with patch("main.trafilatura.fetch_url", side_effect=mock_fetch), \
         patch("main.trafilatura.extract", return_value="本文"):
        result = fetch_article_contents([
            "https://example.com/error",
            "https://example.com/ok",
        ])

    assert len(result) == 1
    assert "https://example.com/ok" in result
