"""
LinkedIn 爬虫（澳洲）
- 使用 LinkedIn Guest Jobs API（无需登录）
- 覆盖 PE/VC/基金/行研/IB 等在 GradConnection 上没有的职位
- 每页10条，分页抓取
"""

import re
import time
import httpx
from bs4 import BeautifulSoup

from job_scraper.models import Job
from job_scraper import config

# LinkedIn 墨尔本的 geoId
MELBOURNE_GEO_ID = "104769905"
AUSTRALIA_GEO_ID = "101452733"

GUEST_API = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
    "Referer": "https://www.linkedin.com/",
}

# 每批搜索关键词（LinkedIn 每次只返回10条，多关键词覆盖更广）
KEYWORDS = [
    "private equity intern",
    "venture capital intern",
    "investment analyst intern",
    "equity research intern",
    "fund management intern",
    "investment banking intern",
    "financial analyst intern",
    "asset management intern",
    "research analyst finance",
]

# 用于二次过滤：标题必须含其中之一
TITLE_MUST = [
    "private equity", "venture capital", "investment", "equity research",
    "fund", "asset management", "financial analyst", "research analyst",
    "banking", "capital market", "portfolio", "pe ", "vc ",
    "intern", "graduate", "vacationer",
]

# 标题含这些词则排除
TITLE_EXCLUDE = [
    "engineer", "software", "developer", "marketing", "hr", "legal",
    "supply chain", "nurse", "teacher", "construction",
]

# 签证接受信号
_VISA_ACCEPT = [
    "international student", "student visa", "485 visa", "temporary graduate",
    "working holiday", "temporary work", "all visa", "open to international",
    "welcome international", "graduate visa", "subclass 485",
]
_VISA_REJECT = [
    "australian citizens only", "must be australian citizen",
    "must hold australian citizenship", "australian citizenship required",
    "citizens and permanent residents only", "security clearance required",
]


def _fetch_page(keyword: str, start: int, geo_id: str) -> list[dict]:
    """抓取一页搜索结果，返回原始数据列表"""
    params = {
        "keywords": keyword,
        "geoId": geo_id,
        "f_E": "1",              # internship experience level
        "f_TPR": "r2592000",     # 最近30天
        "start": str(start),
    }
    try:
        resp = httpx.get(GUEST_API, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"  [LinkedIn] 请求失败: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.find_all("li")


def _parse_card(card) -> Job | None:
    """解析单个 LinkedIn 职位卡片"""
    try:
        title_tag = card.select_one(".base-search-card__title")
        company_tag = card.select_one(".base-search-card__subtitle")
        location_tag = card.select_one(".job-search-card__location")
        date_tag = card.select_one("time")
        link_tag = card.select_one("a.base-card__full-link")
        urn_tag = card.select_one("[data-entity-urn]")

        if not title_tag or not link_tag:
            return None

        title = title_tag.get_text(strip=True)
        company = company_tag.get_text(strip=True) if company_tag else "未知公司"
        location = location_tag.get_text(strip=True) if location_tag else "Australia"
        posted = date_tag.get("datetime", "") if date_tag else ""

        href = link_tag.get("href", "")
        # 提取纯净 URL（去掉 tracking 参数）
        clean_url = re.sub(r'\?.*', '', href)

        # 从 URN 或 URL 提取 job ID
        urn = urn_tag.get("data-entity-urn", "") if urn_tag else ""
        job_id = urn.split(":")[-1] if urn else re.search(r'-(\d+)$', clean_url.rstrip('/') or '')
        if hasattr(job_id, 'group'):
            job_id = job_id.group(1)

        if not job_id or not title:
            return None

        return Job(
            title=title,
            company=company,
            location=location,
            platform="LinkedIn",
            url=clean_url,
            job_id=f"li_{job_id}",
            posted_date=posted,
        )
    except Exception as e:
        print(f"  [LinkedIn] 解析卡片出错: {e}")
        return None


def _matches(title: str) -> bool:
    t = title.lower()
    return (
        any(kw in t for kw in TITLE_MUST)
        and not any(kw in t for kw in TITLE_EXCLUDE)
    )


def _check_visa(url: str) -> str:
    """访问职位详情页检测签证要求"""
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        text = BeautifulSoup(resp.text, "html.parser").get_text(separator=" ", strip=True).lower()
        if any(s in text for s in _VISA_ACCEPT):
            return "yes"
        if any(s in text for s in _VISA_REJECT):
            return "no"
        return "unknown"
    except Exception:
        return "unknown"


def scrape(geo_id: str = None) -> list[Job]:
    """
    对外接口：抓取 LinkedIn 金融实习职位

    参数:
        geo_id: 地区 ID，默认墨尔本；传入 AUSTRALIA_GEO_ID 可扩大到全澳
    返回:
        Job 列表（含 visa_friendly 字段）
    """
    geo_id = geo_id or MELBOURNE_GEO_ID
    geo_label = "墨尔本" if geo_id == MELBOURNE_GEO_ID else "澳洲"

    all_jobs: list[Job] = []
    seen_ids: set[str] = set()

    # ── 第一阶段：抓取列表 ──
    for keyword in KEYWORDS:
        print(f"\n[LinkedIn] 搜索: '{keyword}' @ {geo_label}")

        for page in range(config.MAX_PAGES):
            start = page * 10
            cards = _fetch_page(keyword, start, geo_id)

            if not cards:
                print(f"  start={start}：无结果，停止翻页")
                break

            new_count = 0
            for card in cards:
                job = _parse_card(card)
                if job and _matches(job.title) and job.job_id not in seen_ids:
                    seen_ids.add(job.job_id)
                    all_jobs.append(job)
                    new_count += 1

            print(f"  start={start}：获取 {len(cards)} 条，新增 {new_count} 条")

            if len(cards) < 10:
                break

            time.sleep(config.REQUEST_DELAY)

        time.sleep(config.REQUEST_DELAY)

    print(f"\n[LinkedIn] 列表抓取完成，共 {len(all_jobs)} 个不重复职位")

    # ── 第二阶段：检测签证要求 ──
    if all_jobs:
        print(f"[LinkedIn] 检测签证要求...")
        for i, job in enumerate(all_jobs, 1):
            job.visa_friendly = _check_visa(job.url)
            status = {"yes": "✅", "no": "❌", "unknown": "❓"}[job.visa_friendly]
            print(f"  [{i:02d}/{len(all_jobs)}] {status}  {job.title[:50]}")
            time.sleep(1)

    yes_count = sum(1 for j in all_jobs if j.visa_friendly == "yes")
    print(f"\n[LinkedIn] 完成：{len(all_jobs)} 个职位，其中 {yes_count} 个接受国际学生")
    return all_jobs
