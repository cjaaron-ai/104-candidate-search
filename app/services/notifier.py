"""
Telegram 通知服務

搜尋完成後發送結果摘要至 Telegram，
包含各 JD 的候選人統計與前三名候選人資訊。
"""

import logging
from datetime import datetime

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _mask_name(name: str) -> str:
    """姓名遮罩：保留姓氏，其餘以 X 取代"""
    if not name:
        return "未知"
    if len(name) <= 1:
        return name
    return name[0] + "X" * (len(name) - 1)


def _rank_emoji(rank: int) -> str:
    """排名 emoji"""
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")


def format_search_results(all_results: list[dict]) -> str:
    """將搜尋結果格式化為 Telegram 訊息（繁體中文）"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"📋 104 人選搜尋報告",
        f"📅 {now}",
        f"{'─' * 20}",
        "",
    ]

    if not all_results:
        lines.append("本次排程未找到任何結果。")
        return "\n".join(lines)

    total_new = 0
    total_above = 0

    for result in all_results:
        job_title = result.get("job_title", "未知職缺")
        total_candidates = result.get("total_candidates", 0)
        above_threshold = result.get("above_threshold", 0)
        candidates = result.get("candidates", [])

        total_new += total_candidates
        total_above += above_threshold

        lines.append(f"💼 {job_title}")
        lines.append(f"   新增人選：{total_candidates} 位｜達標：{above_threshold} 位")

        # 前三名候選人
        top3 = candidates[:3]
        for i, c in enumerate(top3, 1):
            candidate = c.get("candidate")
            scores = c.get("scores", {})
            if not candidate:
                continue
            name = getattr(candidate, "name", "") if hasattr(candidate, "name") else str(candidate)
            masked = _mask_name(name)
            total_score = scores.get("total_score", 0)
            exp_years = getattr(candidate, "experience_years", 0) if hasattr(candidate, "experience_years") else 0
            skills = getattr(candidate, "skills", []) if hasattr(candidate, "skills") else []
            skill_str = "、".join(skills[:3]) if skills else "無"

            lines.append(
                f"   {_rank_emoji(i)} {masked}｜{total_score:.1f} 分｜"
                f"{exp_years} 年經驗｜{skill_str}"
            )

        lines.append("")

    lines.append(f"{'─' * 20}")
    lines.append(f"📊 總計：{total_new} 位新人選，{total_above} 位達標")
    lines.append("")
    lines.append("🔗 完整結果請至系統後台查看 /docs")

    return "\n".join(lines)


def format_error_message(error: str) -> str:
    """格式化錯誤通知訊息"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        f"⚠️ 104 搜尋系統錯誤通知\n"
        f"📅 {now}\n"
        f"{'─' * 20}\n"
        f"❌ {error}\n"
        f"\n請檢查系統狀態。"
    )


def format_captcha_alert() -> str:
    """格式化 CAPTCHA 偵測通知"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        f"🔒 104 CAPTCHA 偵測警告\n"
        f"📅 {now}\n"
        f"{'─' * 20}\n"
        f"爬蟲偵測到 CAPTCHA 驗證頁面，自動搜尋已暫停。\n"
        f"請手動登入 104 企業端完成驗證後再重新啟動排程。"
    )


async def send_telegram(message: str) -> bool:
    """透過 Telegram Bot API 發送訊息"""
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id

    if not token or not chat_id:
        logger.warning("Telegram 設定不完整（缺少 BOT_TOKEN 或 CHAT_ID），跳過通知")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("Telegram 通知發送成功")
                return True
            else:
                logger.error(f"Telegram API 回應錯誤: {resp.status_code} {resp.text}")
                return False
    except Exception as e:
        logger.error(f"Telegram 通知發送失敗: {e}")
        return False


async def notify_search_results(all_results: list[dict]):
    """發送搜尋結果通知"""
    message = format_search_results(all_results)
    await send_telegram(message)


async def notify_error(error: str):
    """發送錯誤通知"""
    message = format_error_message(error)
    await send_telegram(message)


async def notify_captcha():
    """發送 CAPTCHA 偵測警告"""
    message = format_captcha_alert()
    await send_telegram(message)
