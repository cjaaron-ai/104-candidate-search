from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from app.services.notifier import (
    _mask_name,
    _rank_emoji,
    format_search_results,
    format_captcha_alert,
    format_error_message,
    send_telegram,
)


# === _mask_name ===

def test_mask_name_normal():
    assert _mask_name("王小明") == "王XX"


def test_mask_name_two_chars():
    assert _mask_name("王明") == "王X"


def test_mask_name_single_char():
    assert _mask_name("王") == "王"


def test_mask_name_empty():
    assert _mask_name("") == "未知"


# === _rank_emoji ===

def test_rank_emoji_top3():
    assert _rank_emoji(1) == "🥇"
    assert _rank_emoji(2) == "🥈"
    assert _rank_emoji(3) == "🥉"


def test_rank_emoji_beyond_3():
    assert _rank_emoji(4) == "#4"
    assert _rank_emoji(10) == "#10"


# === format_search_results ===

def test_format_search_results_empty():
    result = format_search_results([])
    assert "本次排程未找到任何結果" in result


def test_format_search_results_with_data():
    candidate = MagicMock()
    candidate.name = "王小明"
    candidate.experience_years = 5
    candidate.skills = ["Python", "SQL"]

    all_results = [{
        "job_title": "Backend Engineer",
        "total_candidates": 1,
        "above_threshold": 1,
        "candidates": [{"candidate": candidate, "scores": {"total_score": 85.0}}],
    }]
    result = format_search_results(all_results)
    assert "Backend Engineer" in result
    assert "王XX" in result
    assert "85.0" in result


# === format helpers ===

def test_format_error_message():
    result = format_error_message("login failed")
    assert "login failed" in result
    assert "錯誤" in result


def test_format_captcha_alert():
    result = format_captcha_alert()
    assert "CAPTCHA" in result


# === send_telegram ===

@pytest.mark.asyncio
async def test_send_telegram_missing_config():
    with patch("app.services.notifier.settings") as mock_settings:
        mock_settings.telegram_bot_token = ""
        mock_settings.telegram_chat_id = ""
        result = await send_telegram("test")
        assert result is False


@pytest.mark.asyncio
async def test_send_telegram_success():
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("app.services.notifier.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_settings.telegram_bot_token = "fake-token"
        mock_settings.telegram_chat_id = "123"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await send_telegram("hello")
        assert result is True
        mock_client.post.assert_called_once()
