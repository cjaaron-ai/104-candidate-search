"""
104 人力銀行企業端人才搜尋爬蟲

透過 Playwright 模擬登入 104 企業端，
依據 JD 條件搜尋人才資料庫並擷取候選人資料。
包含反偵測機制：stealth 插件、隨機延遲、UA 輪換、Cookie 持久化、重試邏輯。
"""

import asyncio
import json
import logging
import os
import random
from dataclasses import dataclass, field
from pathlib import Path

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

logger = logging.getLogger(__name__)

# 真實 Chrome User-Agent 列表，定期更新
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

# CAPTCHA 偵測關鍵字
_CAPTCHA_INDICATORS = ["captcha", "驗證碼", "人機驗證", "recaptcha", "hcaptcha", "verify"]


@dataclass
class CandidateData:
    source: str = "104"
    source_id: str = ""
    name: str = ""
    title: str = ""
    company: str = ""
    experience_years: int = 0
    education_level: str = ""
    education_school: str = ""
    education_major: str = ""
    skills: list[str] = field(default_factory=list)
    industry: str = ""
    location: str = ""
    expected_salary_min: int = 0
    expected_salary_max: int = 0
    profile_url: str = ""
    raw_data: str = ""


class Crawler104:
    BASE_URL = "https://pro.104.com.tw"
    MAX_RETRIES = 3

    def __init__(self, username: str, password: str, cookie_storage_path: str = "/tmp/104_session"):
        self.username = username
        self.password = password
        self.cookie_storage_path = Path(cookie_storage_path)
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self._pw = None
        # CAPTCHA 偵測回呼，由外部設定（例如發送 Telegram 通知）
        self.on_captcha_detected = None

    @staticmethod
    async def _apply_stealth(page: Page):
        """手動注入反偵測腳本，隱藏 Playwright 自動化特徵"""
        stealth_scripts = [
            # 隱藏 navigator.webdriver
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});",
            # 偽造 plugins
            """Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });""",
            # 偽造 languages
            """Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-TW', 'zh', 'en-US', 'en'],
            });""",
            # 隱藏 chrome runtime
            "window.chrome = { runtime: {} };",
            # 偽造 permissions
            """const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );""",
        ]
        for script in stealth_scripts:
            await page.add_init_script(script)

    async def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """隨機等待，模擬人類操作節奏"""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    async def _random_mouse_move(self):
        """隨機滑鼠移動，模擬人類行為"""
        if not self.page:
            return
        try:
            viewport = self.page.viewport_size or {"width": 1280, "height": 720}
            x = random.randint(100, viewport["width"] - 100)
            y = random.randint(100, viewport["height"] - 100)
            await self.page.mouse.move(x, y, steps=random.randint(5, 15))
        except Exception:
            pass

    async def _random_scroll(self):
        """隨機捲動頁面，模擬瀏覽行為"""
        if not self.page:
            return
        try:
            scroll_amount = random.randint(200, 600)
            await self.page.mouse.wheel(0, scroll_amount)
            await asyncio.sleep(random.uniform(0.3, 0.8))
        except Exception:
            pass

    async def _check_captcha(self) -> bool:
        """檢查頁面是否出現 CAPTCHA"""
        if not self.page:
            return False
        try:
            content = await self.page.content()
            content_lower = content.lower()
            for indicator in _CAPTCHA_INDICATORS:
                if indicator in content_lower:
                    logger.warning(f"偵測到 CAPTCHA（關鍵字：{indicator}）")
                    if self.on_captcha_detected:
                        await self.on_captcha_detected()
                    return True
        except Exception:
            pass
        return False

    def _get_cookie_file(self) -> Path:
        return self.cookie_storage_path / "cookies.json"

    async def _save_cookies(self):
        """儲存 Cookie 以便下次重複使用"""
        if not self.context:
            return
        try:
            self.cookie_storage_path.mkdir(parents=True, exist_ok=True)
            cookies = await self.context.cookies()
            cookie_file = self._get_cookie_file()
            cookie_file.write_text(json.dumps(cookies, ensure_ascii=False))
            logger.info(f"Cookie 已儲存至 {cookie_file}")
        except Exception as e:
            logger.warning(f"Cookie 儲存失敗: {e}")

    async def _load_cookies(self) -> bool:
        """載入先前儲存的 Cookie"""
        cookie_file = self._get_cookie_file()
        if not cookie_file.exists():
            return False
        try:
            cookies = json.loads(cookie_file.read_text())
            await self.context.add_cookies(cookies)
            logger.info("已載入先前儲存的 Cookie")
            return True
        except Exception as e:
            logger.warning(f"Cookie 載入失敗: {e}")
            return False

    async def start(self):
        """啟動瀏覽器（含反偵測設定）"""
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(headless=True)
        ua = random.choice(_USER_AGENTS)
        self.context = await self.browser.new_context(
            user_agent=ua,
            viewport={"width": 1280, "height": 720},
            locale="zh-TW",
            timezone_id="Asia/Taipei",
        )
        self.page = await self.context.new_page()
        # 手動注入反偵測腳本（取代 playwright-stealth）
        await self._apply_stealth(self.page)
        logger.info("瀏覽器已啟動（含反偵測）")

    async def login(self) -> bool:
        """登入 104 企業端（含 Cookie 重用與 CAPTCHA 偵測）"""
        # 嘗試用既有 Cookie 恢復登入
        cookie_loaded = await self._load_cookies()
        if cookie_loaded:
            try:
                await self.page.goto(f"{self.BASE_URL}/vip/headhunting/search")
                await self.page.wait_for_load_state("networkidle")
                if await self._check_captcha():
                    return False
                # 如果沒有被導向登入頁，表示 Cookie 仍有效
                if "login" not in self.page.url.lower():
                    logger.info("Cookie 登入成功，無需重新輸入帳密")
                    return True
            except Exception:
                logger.info("Cookie 無效，改用帳密登入")

        # 帳密登入（含重試）
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                await self._random_delay(1.0, 2.0)
                await self.page.goto(f"{self.BASE_URL}/login")
                await self.page.wait_for_load_state("networkidle")

                if await self._check_captcha():
                    return False

                await self._random_mouse_move()
                await self._random_delay(0.5, 1.5)

                # 填入帳密
                await self.page.fill('input[name="username"], input[type="email"], #username', self.username)
                await self._random_delay(0.5, 1.0)
                await self.page.fill('input[name="password"], input[type="password"], #password', self.password)
                await self._random_delay(0.5, 1.0)

                await self._random_mouse_move()

                # 點擊登入按鈕
                await self.page.click('button[type="submit"], .login-btn, #loginBtn')
                await self.page.wait_for_load_state("networkidle")

                if await self._check_captcha():
                    return False

                # 驗證是否登入成功
                try:
                    await self.page.wait_for_selector(
                        '.dashboard, .main-content, [class*="member"]', timeout=10000
                    )
                    logger.info("帳密登入成功")
                except Exception:
                    logger.warning("登入驗證不確定，繼續執行")

                # 登入成功，儲存 Cookie
                await self._save_cookies()
                return True

            except Exception as e:
                wait_sec = 2 ** attempt
                logger.error(f"登入失敗（第 {attempt} 次）: {e}，{wait_sec} 秒後重試")
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(wait_sec)

        logger.error("登入重試次數已用盡")
        return False

    async def search_candidates(
        self,
        keywords: list[str],
        location: str | None = None,
        experience_min: int | None = None,
        experience_max: int | None = None,
        education: str | None = None,
        max_pages: int = 5,
    ) -> list[CandidateData]:
        """搜尋 104 人才資料庫（含反偵測與重試）"""
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                return await self._do_search(keywords, location, experience_min, experience_max, education, max_pages)
            except Exception as e:
                wait_sec = 2 ** attempt
                logger.error(f"搜尋失敗（第 {attempt} 次）: {e}，{wait_sec} 秒後重試")
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(wait_sec)

        logger.error("搜尋重試次數已用盡，回傳空結果")
        return []

    async def _do_search(
        self,
        keywords: list[str],
        location: str | None,
        experience_min: int | None,
        experience_max: int | None,
        education: str | None,
        max_pages: int,
    ) -> list[CandidateData]:
        """實際執行搜尋邏輯"""
        candidates = []
        keyword_str = " ".join(keywords)

        # 模擬人類操作：先隨機移動滑鼠、捲動
        await self._random_mouse_move()
        await self._random_scroll()
        await self._random_delay()

        # 前往人才搜尋頁面
        await self.page.goto(f"{self.BASE_URL}/vip/headhunting/search")
        await self.page.wait_for_load_state("networkidle")

        if await self._check_captcha():
            raise RuntimeError("搜尋頁面偵測到 CAPTCHA")

        await self._random_delay()

        # 輸入搜尋關鍵字
        search_input = await self.page.wait_for_selector(
            'input[name="keyword"], input[type="search"], .search-input, #keyword',
            timeout=10000,
        )
        await self._random_mouse_move()
        await search_input.fill(keyword_str)

        # 設定地區篩選
        if location:
            await self._random_delay(0.5, 1.5)
            await self._set_filter(self.page, "location", location)

        # 設定經歷篩選
        if experience_min is not None or experience_max is not None:
            await self._random_delay(0.5, 1.5)
            await self._set_experience_filter(self.page, experience_min, experience_max)

        # 設定學歷篩選
        if education:
            await self._random_delay(0.5, 1.5)
            await self._set_filter(self.page, "education", education)

        await self._random_delay()
        await self._random_mouse_move()

        # 執行搜尋
        await self.page.click('button[type="submit"], .search-btn, #searchBtn')
        await self.page.wait_for_load_state("networkidle")

        if await self._check_captcha():
            raise RuntimeError("搜尋結果頁偵測到 CAPTCHA")

        # 逐頁擷取結果
        for page_num in range(1, max_pages + 1):
            logger.info(f"擷取第 {page_num} 頁...")
            await self._random_delay()
            await self._random_scroll()

            page_candidates = await self._parse_search_results(self.page)
            candidates.extend(page_candidates)

            # 嘗試翻到下一頁
            if page_num < max_pages:
                await self._random_delay(1.5, 3.0)
                has_next = await self._goto_next_page(self.page)
                if not has_next:
                    break

                if await self._check_captcha():
                    logger.warning("翻頁後偵測到 CAPTCHA，停止擷取")
                    break

        logger.info(f"共找到 {len(candidates)} 位候選人")
        return candidates

    async def _parse_search_results(self, page: Page) -> list[CandidateData]:
        """解析搜尋結果頁面"""
        candidates = []

        # 取得所有人選卡片（選擇器需根據實際頁面結構調整）
        cards = await page.query_selector_all(
            '.resume-card, .candidate-card, [class*="resume-item"], [class*="candidate"]'
        )

        for card in cards:
            try:
                candidate = CandidateData()

                # 姓名
                name_el = await card.query_selector('.name, [class*="name"], h3, h4')
                if name_el:
                    candidate.name = (await name_el.inner_text()).strip()

                # 目前職稱
                title_el = await card.query_selector('.job-title, [class*="title"], .position')
                if title_el:
                    candidate.title = (await title_el.inner_text()).strip()

                # 公司
                company_el = await card.query_selector('.company, [class*="company"]')
                if company_el:
                    candidate.company = (await company_el.inner_text()).strip()

                # 工作經驗
                exp_el = await card.query_selector('.experience, [class*="exp"]')
                if exp_el:
                    exp_text = await exp_el.inner_text()
                    candidate.experience_years = self._parse_experience(exp_text)

                # 學歷
                edu_el = await card.query_selector('.education, [class*="edu"]')
                if edu_el:
                    edu_text = await edu_el.inner_text()
                    candidate.education_level = self._parse_education_level(edu_text)
                    candidate.education_school = edu_text.strip()

                # 地區
                loc_el = await card.query_selector('.location, [class*="location"], [class*="area"]')
                if loc_el:
                    candidate.location = (await loc_el.inner_text()).strip()

                # 技能標籤
                skill_els = await card.query_selector_all('.skill-tag, [class*="skill"], .tag')
                candidate.skills = []
                for skill_el in skill_els:
                    skill_text = (await skill_el.inner_text()).strip()
                    if skill_text:
                        candidate.skills.append(skill_text)

                # 個人頁面連結
                link_el = await card.query_selector("a[href]")
                if link_el:
                    href = await link_el.get_attribute("href")
                    if href:
                        candidate.profile_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                        candidate.source_id = href.split("/")[-1].split("?")[0]

                # 儲存原始 HTML
                candidate.raw_data = await card.inner_html()

                if candidate.name:
                    candidates.append(candidate)

            except Exception as e:
                logger.warning(f"解析候選人卡片失敗: {e}")

        return candidates

    async def _set_filter(self, page: Page, filter_type: str, value: str):
        """設定篩選條件"""
        try:
            selector = f'select[name="{filter_type}"], [data-filter="{filter_type}"], #{filter_type}'
            el = await page.query_selector(selector)
            if el:
                tag = await el.evaluate("el => el.tagName.toLowerCase()")
                if tag == "select":
                    await el.select_option(label=value)
                else:
                    await el.click()
                    await page.click(f'text="{value}"')
        except Exception as e:
            logger.warning(f"篩選條件設定失敗 {filter_type}={value}: {e}")

    async def _set_experience_filter(self, page: Page, exp_min: int | None, exp_max: int | None):
        """設定經驗年資篩選"""
        try:
            if exp_min is not None:
                min_input = await page.query_selector('[name="experienceMin"], #experienceMin')
                if min_input:
                    await min_input.fill(str(exp_min))
            if exp_max is not None:
                max_input = await page.query_selector('[name="experienceMax"], #experienceMax')
                if max_input:
                    await max_input.fill(str(exp_max))
        except Exception as e:
            logger.warning(f"經驗篩選設定失敗: {e}")

    async def _goto_next_page(self, page: Page) -> bool:
        """翻到下一頁"""
        try:
            next_btn = await page.query_selector(
                '.next, [class*="next"], a:has-text("下一頁"), button:has-text(">")'
            )
            if next_btn:
                disabled = await next_btn.get_attribute("disabled")
                cls = await next_btn.get_attribute("class") or ""
                if disabled or "disabled" in cls:
                    return False
                await self._random_mouse_move()
                await next_btn.click()
                await page.wait_for_load_state("networkidle")
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _parse_experience(text: str) -> int:
        """從文字中解析經驗年資"""
        import re
        match = re.search(r"(\d+)", text)
        return int(match.group(1)) if match else 0

    @staticmethod
    def _parse_education_level(text: str) -> str:
        """從文字中解析學歷等級"""
        if "博士" in text:
            return "博士"
        if "碩士" in text:
            return "碩士"
        if "學士" in text or "大學" in text:
            return "學士"
        if "專科" in text:
            return "專科"
        if "高中" in text:
            return "高中"
        return ""

    async def close(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._pw:
            await self._pw.stop()
        logger.info("瀏覽器已關閉")
