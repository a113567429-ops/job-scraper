"""
SEEK 爬虫（澳洲）— 使用 Playwright 模拟真实浏览器
- 绕过 Cloudflare 反爬保护
- 解析 Next.js 内嵌的 JSON 数据
"""

import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from job_scraper.models import Job
from job_scraper import config

BASE_URL = "https://www.seek.com.au/jobs"


def _build_url(keyword: str, location: str, page: int) -> str:
    from urllib.parse import urlencode
    params = {
        "keywords": keyword,
        "where": location,
        "dateRange": str(config.DAYS_RANGE),
        "page": str(page),
        "sortmode": "ListedDate",
    }
    return f"{BASE_URL}?{urlencode(params)}"


def _extract_jobs_from_html(html: str) -> list[Job]:
    """从页面 HTML 中提取职位数据"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if not script_tag:
        return []

    try:
        data = json.loads(script_tag.string)
    except (json.JSONDecodeError, TypeError):
        return []

    page_props = data.get("props", {}).get("pageProps", {})

    # 尝试多种路径定位职位列表
    jobs_raw = []
    for path in [["jobsProps", "jobs"], ["jobs"], ["searchResults", "jobs"]]:
        result = page_props
        for key in path:
            result = result.get(key, {}) if isinstance(result, dict) else {}
        if isinstance(result, list) and result:
            jobs_raw = result
            break

    jobs = []
    for item in jobs_raw:
        job = _parse_job(item)
        if job:
            jobs.append(job)
    return jobs


def _parse_job(item: dict) -> Job | None:
    try:
        job_id = str(item.get("id", ""))
        title = item.get("title", "").strip()
        company = item.get("advertiser", {}).get("description", "未知公司").strip()
        location_info = item.get("suburb") or item.get("area") or config.LOCATION_AU
        salary = item.get("salary", "")
        posted = item.get("listingDate", "")[:10] if item.get("listingDate") else ""
        description = item.get("teaser", "")

        if not job_id or not title:
            return None

        return Job(
            title=title,
            company=company,
            location=location_info,
            platform="SEEK",
            url=f"https://www.seek.com.au/job/{job_id}",
            job_id=f"seek_{job_id}",
            posted_date=posted,
            description=description,
            salary=salary,
        )
    except Exception:
        return None


def scrape(keywords: list[str] = None, location: str = None) -> list[Job]:
    """
    对外接口：用 Playwright 抓取 SEEK 职位

    参数：
        keywords: 搜索词列表，默认用 config.KEYWORDS_AU
        location: 地区，默认用 config.LOCATION_AU
    返回：
        Job 列表（已去重）
    """
    keywords = keywords or config.KEYWORDS_AU
    location = location or config.LOCATION_AU

    all_jobs: list[Job] = []
    seen_ids: set[str] = set()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,     # 改为 False 可以看到浏览器界面，方便调试
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-AU",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        for keyword in keywords:
            print(f"\n[SEEK] 搜索: '{keyword}' @ {location}")

            for pg in range(1, config.MAX_PAGES + 1):
                url = _build_url(keyword, location, pg)

                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    # 等待 Next.js 数据注入完毕
                    page.wait_for_selector("#__NEXT_DATA__", timeout=15000)
                except PWTimeout:
                    print(f"  第 {pg} 页：加载超时，跳过")
                    break
                except Exception as e:
                    print(f"  第 {pg} 页：出错 — {e}")
                    break

                jobs = _extract_jobs_from_html(page.content())

                if not jobs:
                    print(f"  第 {pg} 页：无结果，停止翻页")
                    break

                new_count = 0
                for job in jobs:
                    if job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        all_jobs.append(job)
                        new_count += 1

                print(f"  第 {pg} 页：获取 {len(jobs)} 条，新增 {new_count} 条")

                if len(jobs) < 20:
                    break

                time.sleep(config.REQUEST_DELAY)

            time.sleep(config.REQUEST_DELAY)

        browser.close()

    print(f"\n[SEEK] 完成，共获取 {len(all_jobs)} 个不重复职位")
    return all_jobs
