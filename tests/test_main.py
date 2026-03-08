import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta


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


def test_build_prompt_includes_interests_and_excludes(tmp_path):
    """profile.yamlの内容がプロンプトに反映される"""
    profile_yaml = tmp_path / "profile.yaml"
    profile_yaml.write_text(
        'role: "テストエンジニア"\n'
        'model: "gemini-2.5-flash-lite"\n'
        'language: "ja"\n'
        "articles_per_day: 10\n"
        "interests:\n"
        '  - "AI活用"\n'
        '  - "開発ツール"\n'
        "exclude:\n"
        '  - "初心者向け"\n'
        '  - "広告記事"\n'
    )

    from main import build_prompt
    prompt = build_prompt(str(profile_yaml), [])

    assert "テストエンジニア" in prompt
    assert "AI活用" in prompt
    assert "開発ツール" in prompt
    assert "初心者向け" in prompt
    assert "広告記事" in prompt
    assert "10" in prompt
    assert "ja" in prompt or "日本語" in prompt



def test_curate_returns_parsed_articles(tmp_path):
    """Gemini APIのレスポンスをパースして記事リストを返す"""
    profile_yaml = tmp_path / "profile.yaml"
    profile_yaml.write_text(
        'role: "テストエンジニア"\n'
        'model: "gemini-2.5-flash-lite"\n'
        'language: "ja"\n'
        "articles_per_day: 2\n"
        "interests:\n"
        '  - "AI活用"\n'
        "exclude:\n"
        '  - "広告"\n'
    )

    articles = [
        {"title": "Article 1", "url": "https://example.com/1", "summary": "Summary 1", "source": "Test", "lang": "en"},
        {"title": "Article 2", "url": "https://example.com/2", "summary": "Summary 2", "source": "Test", "lang": "ja"},
    ]

    curated = [
        {"title": "Article 1", "url": "https://example.com/1", "summary_ja": "要約1", "source": "Test", "category": "AI/LLM"},
    ]
    api_response_text = f"```json\n{json.dumps(curated, ensure_ascii=False)}\n```"

    mock_response = MagicMock()
    mock_response.text = api_response_text

    from main import GEMINI_API_KEY_ENV
    with patch("main.genai") as mock_genai, \
         patch.dict("os.environ", {GEMINI_API_KEY_ENV: "test-key"}):
        mock_genai.Client.return_value.models.generate_content.return_value = mock_response
        from main import curate
        result = curate(articles, str(profile_yaml))

    assert len(result) == 1
    assert result[0]["title"] == "Article 1"
    assert result[0]["summary_ja"] == "要約1"
    assert result[0]["category"] == "AI/LLM"


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
