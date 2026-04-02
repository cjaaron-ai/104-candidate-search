"""
104 人力銀行企業端人才搜尋爬蟲

透過 Playwright 模擬登入 104 企業端，
依據 JD 條件搜尋人才資料庫並擷取候選人資料。
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field

from playwright.async_api import async_playwright, Page, Browser

logger = logging.getLogger(__name__)


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

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.browser: Browser | None = None
        self.page: Page | None = None

    async def start(self):
        pw = await async_playwright().start()
        self.browser = await pw.chromium.launch(headless=True)
        self.page = await self.browser.new_page()
        logger.info("Browser started")

    async def login(self) -> bool:
        """登入 104 企業端"""
        try:
            await self.page.goto(f"{self.BASE_URL}/login")
            await self.page.wait_for_load_state("networkidle")

            # 填入帳密
            await self.page.fill('input[name="username"], input[type="email"], #username', self.username)
            await self.page.fill('input[name="password"], input[type="password"], #password', self.password)

            # 點擊登入按鈕
            await self.page.click('button[type="submit"], .login-btn, #loginBtn')
            await self.page.wait_for_load_state("networkidle")

            # 驗證是否登入成功（檢查是否有企業端 dashboard 元素）
            try:
                await self.page.wait_for_selector('.dashboard, .main-content, [class*="member"]', timeout=10000)
                logger.info("Login successful")
                return True
            except Exception:
                logger.warning("Login verification uncertain, proceeding anyway")
                return True

        except Exception as e:
            logger.error(f"Login failed: {e}")
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
        """搜尋 104 人才資料庫"""
        candidates = []
        keyword_str = " ".join(keywords)

        try:
            # 前往人才搜尋頁面
            await self.page.goto(f"{self.BASE_URL}/vip/headhunting/search")
            await self.page.wait_for_load_state("networkidle")

            # 輸入搜尋關鍵字
            search_input = await self.page.wait_for_selector(
                'input[name="keyword"], input[type="search"], .search-input, #keyword',
                timeout=10000,
            )
            await search_input.fill(keyword_str)

            # 設定地區篩選
            if location:
                await self._set_filter(self.page, "location", location)

            # 設定經歷篩選
            if experience_min is not None or experience_max is not None:
                await self._set_experience_filter(self.page, experience_min, experience_max)

            # 設定學歷篩選
            if education:
                await self._set_filter(self.page, "education", education)

            # 執行搜尋
            await self.page.click('button[type="submit"], .search-btn, #searchBtn')
            await self.page.wait_for_load_state("networkidle")

            # 逐頁擷取結果
            for page_num in range(1, max_pages + 1):
                logger.info(f"Scraping page {page_num}...")
                page_candidates = await self._parse_search_results(self.page)
                candidates.extend(page_candidates)

                # 嘗試翻到下一頁
                if page_num < max_pages:
                    has_next = await self._goto_next_page(self.page)
                    if not has_next:
                        break

        except Exception as e:
            logger.error(f"Search failed: {e}")

        logger.info(f"Found {len(candidates)} candidates")
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
                logger.warning(f"Failed to parse candidate card: {e}")

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
            logger.warning(f"Could not set filter {filter_type}={value}: {e}")

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
            logger.warning(f"Could not set experience filter: {e}")

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
        if self.browser:
            await self.browser.close()
            logger.info("Browser closed")
