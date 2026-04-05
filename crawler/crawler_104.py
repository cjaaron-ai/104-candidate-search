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
from playwright_stealth import stealth_async

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
    # V2: 完整履歷欄位
    certifications: list[str] = field(default_factory=list)
    languages: list[dict] = field(default_factory=list)
    work_history: list[dict] = field(default_factory=list)
    autobiography: str = ""


@dataclass
class JobPostingData:
    """從 104 公開職缺頁面解析的結構化資料"""
    source: str = "104"
    source_id: str = ""
    source_url: str = ""
    title: str = ""
    company: str = ""
    industry: str = ""
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    min_experience_years: int = 0
    max_experience_years: int | None = None
    education_level: str = ""
    location: str = ""
    salary_min: int = 0
    salary_max: int = 0
    salary_type: str = ""
    benefits: list[str] = field(default_factory=list)
    description: str = ""
    full_description: str = ""
    raw_data: str = ""


class Crawler104:
    BASE_URL = "https://vip.104.com.tw"
    PUBLIC_URL = "https://www.104.com.tw"
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
        # 套用 stealth 插件，隱藏自動化特徵
        await stealth_async(self.page)
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

    # === V2: 新增方法 ===

    async def _ensure_browser(self):
        """確保瀏覽器已啟動"""
        if not self.browser:
            await self.start()

    async def _ensure_logged_in(self):
        """確保已登入企業端"""
        await self._ensure_browser()
        if not self.page:
            return False
        try:
            current_url = self.page.url
            if self.BASE_URL in current_url and "login" not in current_url.lower():
                return True
        except Exception:
            pass
        return await self.login()

    async def scrape_job_posting(self, job_url: str) -> JobPostingData:
        """
        爬取 104 公開職缺頁面。
        URL 格式: https://www.104.com.tw/job/xxxxx
        策略: 優先嘗試 AJAX API，失敗則 fallback 到 HTML 解析。
        """
        import re
        import httpx

        # 從 URL 提取 job ID
        match = re.search(r"/job/([a-zA-Z0-9]+)", job_url)
        if not match:
            raise ValueError(f"無效的 104 職缺 URL: {job_url}")

        job_id = match.group(1)
        result = JobPostingData(source_url=job_url, source_id=job_id)

        # 嘗試 AJAX API
        try:
            ajax_url = f"{self.PUBLIC_URL}/job/ajax/content/{job_id}"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    ajax_url,
                    headers={
                        "Referer": job_url,
                        "User-Agent": random.choice(_USER_AGENTS),
                    },
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    result = self._parse_job_ajax(data, job_url, job_id)
                    logger.info(f"AJAX 解析成功: {result.title}")
                    return result
        except Exception as e:
            logger.info(f"AJAX 解析失敗，改用 HTML: {e}")

        # Fallback: Playwright HTML 解析
        await self._ensure_browser()
        page = await self.context.new_page()
        try:
            await page.goto(job_url)
            await page.wait_for_load_state("networkidle")
            await self._random_delay()

            result.title = await self._safe_text(page, 'h1, [class*="job-header"] h1, .job-title')
            result.company = await self._safe_text(page, '[class*="company-name"], .company-name a')
            result.location = await self._safe_text(page, '[class*="job-address"], .job-address')
            result.industry = await self._safe_text(page, '[class*="category"], .category')

            salary_text = await self._safe_text(page, '[class*="salary"], .salary')
            result.salary_min, result.salary_max, result.salary_type = self._parse_salary_text(salary_text)

            exp_text = await self._safe_text(page, '[class*="experience"], .experience')
            result.min_experience_years = self._parse_experience(exp_text)

            edu_text = await self._safe_text(page, '[class*="education"], .education')
            result.education_level = self._parse_education_level(edu_text)

            skill_els = await page.query_selector_all('[class*="tag"], .tools .tag, .skill-tag')
            for el in skill_els:
                text = (await el.inner_text()).strip()
                if text:
                    result.required_skills.append(text)

            benefit_els = await page.query_selector_all('[class*="welfare"] .tag, .welfare-tag')
            for el in benefit_els:
                text = (await el.inner_text()).strip()
                if text:
                    result.benefits.append(text)

            desc_el = await page.query_selector('[class*="job-description"], .job-description')
            if desc_el:
                result.description = (await desc_el.inner_text()).strip()
                result.full_description = await desc_el.inner_html()

            result.raw_data = await page.content()
            logger.info(f"HTML 解析成功: {result.title}")
        finally:
            await page.close()

        return result

    @staticmethod
    def _parse_job_ajax(data: dict, job_url: str, job_id: str) -> JobPostingData:
        """從 104 AJAX API 回應解析職缺資料"""
        header = data.get("header", {})
        condition = data.get("condition", {})
        welfare = data.get("welfare", {})

        result = JobPostingData(
            source_url=job_url,
            source_id=job_id,
            title=header.get("jobName", ""),
            company=header.get("custName", ""),
            industry=condition.get("industry", ""),
            location=condition.get("addressRegion", "") or header.get("areaDesc", ""),
            education_level=Crawler104._parse_education_level(
                " ".join(condition.get("edu", []) if isinstance(condition.get("edu"), list) else [str(condition.get("edu", ""))])
            ),
            description=data.get("jobDetail", {}).get("jobDescription", ""),
            full_description=data.get("jobDetail", {}).get("jobDescription", ""),
        )

        # 技能
        for skill in condition.get("skill", []):
            if isinstance(skill, dict):
                result.required_skills.append(skill.get("description", ""))
            elif isinstance(skill, str):
                result.required_skills.append(skill)
        for spec in condition.get("specialty", []):
            if isinstance(spec, dict):
                result.required_skills.append(spec.get("description", ""))

        # 薪資
        salary_info = header.get("salary", "")
        if isinstance(salary_info, str):
            result.salary_min, result.salary_max, result.salary_type = Crawler104._parse_salary_text(salary_info)

        # 經驗
        exp_info = condition.get("workExp", "")
        if isinstance(exp_info, str):
            result.min_experience_years = Crawler104._parse_experience(exp_info)

        # 福利
        well_tags = welfare.get("welfare", "")
        if isinstance(well_tags, str) and well_tags:
            result.benefits = [w.strip() for w in well_tags.split("、") if w.strip()]
        elif isinstance(well_tags, list):
            result.benefits = well_tags

        return result

    @staticmethod
    def _parse_salary_text(text: str) -> tuple[int, int, str]:
        """解析薪資文字，回傳 (min, max, type)"""
        import re
        if not text:
            return 0, 0, "negotiable"

        salary_type = "monthly"
        if "年薪" in text:
            salary_type = "annual"
        elif "面議" in text or "待遇面議" in text:
            return 0, 0, "negotiable"

        numbers = re.findall(r"[\d,]+", text.replace(",", ""))
        nums = [int(n) for n in numbers if n]
        if len(nums) >= 2:
            return nums[0], nums[1], salary_type
        elif len(nums) == 1:
            return nums[0], nums[0], salary_type
        return 0, 0, "negotiable"

    async def _safe_text(self, page: Page, selector: str) -> str:
        """安全取得元素文字"""
        try:
            el = await page.query_selector(selector)
            if el:
                return (await el.inner_text()).strip()
        except Exception:
            pass
        return ""

    async def scrape_candidate_profile(self, profile_url: str) -> CandidateData:
        """
        爬取企業端候選人完整履歷頁面（需登入）。
        填充 V1 未取得的欄位：industry, salary, major, certifications, work_history 等。
        """
        await self._ensure_logged_in()

        await self._random_delay(2.0, 4.0)
        await self.page.goto(profile_url)
        await self.page.wait_for_load_state("networkidle")
        await self._random_delay()
        await self._random_scroll()

        if await self._check_captcha():
            raise RuntimeError("履歷頁面偵測到 CAPTCHA")

        candidate = CandidateData(profile_url=profile_url)
        candidate.source_id = profile_url.split("/")[-1].split("?")[0]

        # 基本資料
        candidate.name = await self._safe_text(self.page, '.name, [class*="name"], h2, h3')
        candidate.title = await self._safe_text(self.page, '.job-title, [class*="title"]')
        candidate.location = await self._safe_text(self.page, '.location, [class*="location"]')

        # 產業
        candidate.industry = await self._safe_text(
            self.page, '.industry, [class*="industry"], [class*="category"]'
        )

        # 工作經驗
        exp_text = await self._safe_text(self.page, '.experience, [class*="exp-year"]')
        candidate.experience_years = self._parse_experience(exp_text)

        # 學歷
        edu_text = await self._safe_text(self.page, '.education, [class*="edu"]')
        candidate.education_level = self._parse_education_level(edu_text)
        candidate.education_school = edu_text

        major_text = await self._safe_text(self.page, '[class*="major"], .major')
        candidate.education_major = major_text

        # 技能
        skill_els = await self.page.query_selector_all('.skill-tag, [class*="skill"] .tag, .expertise .tag')
        candidate.skills = []
        for el in skill_els:
            text = (await el.inner_text()).strip()
            if text:
                candidate.skills.append(text)

        # 薪資期望
        salary_text = await self._safe_text(self.page, '[class*="salary"], .expected-salary')
        candidate.expected_salary_min, candidate.expected_salary_max, _ = self._parse_salary_text(salary_text)

        # 工作歷史
        candidate.work_history = []
        work_items = await self.page.query_selector_all(
            '[class*="work-experience"] .item, .work-history .item, [class*="job-history"] li'
        )
        for item in work_items:
            entry = {}
            entry["company"] = await self._safe_text_el(item, '.company, [class*="company"]')
            entry["title"] = await self._safe_text_el(item, '.title, [class*="title"]')
            entry["duration"] = await self._safe_text_el(item, '.duration, [class*="duration"], .period')
            entry["description"] = await self._safe_text_el(item, '.description, [class*="desc"]')
            if entry.get("company") or entry.get("title"):
                candidate.work_history.append(entry)

        # 證照
        candidate.certifications = []
        cert_els = await self.page.query_selector_all('[class*="certificate"] .item, .certification li')
        for el in cert_els:
            text = (await el.inner_text()).strip()
            if text:
                candidate.certifications.append(text)

        # 語言
        candidate.languages = []
        lang_els = await self.page.query_selector_all('[class*="language"] .item, .language li')
        for el in lang_els:
            text = (await el.inner_text()).strip()
            if text:
                candidate.languages.append({"language": text, "level": ""})

        # 自傳
        candidate.autobiography = await self._safe_text(
            self.page, '[class*="autobiography"], .autobiography, .self-introduction'
        )

        candidate.raw_data = await self.page.content()
        logger.info(f"完整履歷爬取成功: {candidate.name}")
        return candidate

    async def _safe_text_el(self, parent, selector: str) -> str:
        """從父元素中安全取得子元素文字"""
        try:
            el = await parent.query_selector(selector)
            if el:
                return (await el.inner_text()).strip()
        except Exception:
            pass
        return ""

    async def search_jobs(
        self,
        keywords: list[str],
        industry: str | None = None,
        location: str | None = None,
        max_pages: int = 3,
    ) -> list[JobPostingData]:
        """
        搜尋 104 公開職缺列表（用於競爭分析）。
        URL: https://www.104.com.tw/jobs/search/?keyword=...
        """
        import urllib.parse

        await self._ensure_browser()

        keyword_str = " ".join(keywords)
        params = {"keyword": keyword_str, "order": 12}  # 12 = 日期排序
        if location:
            params["area"] = location
        if industry:
            params["indcat"] = industry

        search_url = f"{self.PUBLIC_URL}/jobs/search/?{urllib.parse.urlencode(params)}"
        job_postings = []

        page = await self.context.new_page()
        try:
            await page.goto(search_url)
            await page.wait_for_load_state("networkidle")
            await self._random_delay()

            for page_num in range(1, max_pages + 1):
                logger.info(f"搜尋公開職缺第 {page_num} 頁...")
                await self._random_scroll()

                # 解析職缺卡片
                cards = await page.query_selector_all(
                    '.job-list-item, [class*="job-item"], article[class*="job"]'
                )
                for card in cards:
                    try:
                        link_el = await card.query_selector("a[href*='/job/']")
                        if not link_el:
                            continue
                        href = await link_el.get_attribute("href")
                        if not href:
                            continue
                        job_url = href if href.startswith("http") else f"{self.PUBLIC_URL}{href}"
                        job_url = job_url.split("?")[0]

                        await self._random_delay(3.0, 7.0)
                        try:
                            posting = await self.scrape_job_posting(job_url)
                            job_postings.append(posting)
                        except Exception as e:
                            logger.warning(f"爬取職缺失敗 {job_url}: {e}")
                    except Exception as e:
                        logger.warning(f"解析職缺卡片失敗: {e}")

                # 翻頁
                if page_num < max_pages:
                    await self._random_delay(2.0, 4.0)
                    next_btn = await page.query_selector(
                        'a.next, [class*="next"], button:has-text("下一頁")'
                    )
                    if not next_btn:
                        break
                    disabled = await next_btn.get_attribute("disabled")
                    if disabled:
                        break
                    await next_btn.click()
                    await page.wait_for_load_state("networkidle")

        finally:
            await page.close()

        logger.info(f"共找到 {len(job_postings)} 筆競爭職缺")
        return job_postings

    async def close(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._pw:
            await self._pw.stop()
        logger.info("瀏覽器已關閉")
