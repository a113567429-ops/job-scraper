"""
GradConnection 爬虫（澳洲实习专用平台）
- 专注应届生/实习职位
- 服务端渲染 HTML，无需 Playwright
- 墨尔本金融类实习：https://au.gradconnection.com/internships/finance/melbourne/
"""

import time
import httpx
from bs4 import BeautifulSoup

from job_scraper.models import Job
from job_scraper import config

BASE_URL = "https://au.gradconnection.com"

# 金融相关分类路径（GradConnection 分类导航）
FINANCE_PATHS = [
    "/internships/banking-finance/melbourne/",
    "/internships/accounting/melbourne/",
    "/internships/investment/melbourne/",
    "/internships/finance/melbourne/",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
    "Referer": "https://au.gradconnection.com/",
}

# 职位标题必须包含其中至少一个词（越具体越好）
TITLE_MUST_INCLUDE = [
    "finance", "financial", "investment", "banking",
    "fund", "asset", "equity", "capital", "accounting",
    "analyst", "research", "treasury", "risk", "quant",
    "private equity", "venture", "portfolio",
    "audit", "tax", "economic", "derivatives",
]

# 职位标题包含这些词则排除（非金融岗位）
TITLE_EXCLUDE = [
    "engineer", "engineering", "construction", "health", "safety",
    "surveyor", "architecture", "legal", "it ", "software",
    "marketing", "hr ", "human resource", "supply chain", "logistics",
]


# ── 签证检测关键词 ──────────────────────────────────────────
# 出现任意一个 → 接受国际学生
_VISA_ACCEPT = [
    "international student", "student visa", "temporary graduate",
    "temporary work", "working holiday", "welcome international",
    "open to international", "all visa types", "any valid visa",
    "485 visa", "subclass 485", "graduate visa",
]
# 出现任意一个（且无接受信号）→ 可能不接受
_VISA_REJECT = [
    "australian citizens only", "citizens and permanent residents only",
    "must be an australian citizen", "must hold australian citizenship",
    "security clearance", "australian citizenship required",
]


def _check_visa(url: str) -> str:
    """
    访问职位详情页，判断是否接受国际学生签证持有人。
    返回: "yes" / "no" / "unknown"
    """
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        text = BeautifulSoup(resp.text, "html.parser").get_text(separator=" ", strip=True).lower()

        has_accept = any(s in text for s in _VISA_ACCEPT)
        has_reject = any(s in text for s in _VISA_REJECT)

        if has_accept:
            return "yes"
        if has_reject:
            return "no"
        return "unknown"
    except Exception:
        return "unknown"


def _matches_keywords(title: str, description: str) -> bool:
    """
    检查职位是否与金融/PE/VC/研究方向相关
    规则：标题含金融词 AND 标题不含明显非金融词
    """
    title_lower = title.lower()
    has_finance = any(kw in title_lower for kw in TITLE_MUST_INCLUDE)
    is_excluded = any(kw in title_lower for kw in TITLE_EXCLUDE)
    return has_finance and not is_excluded


def _fetch_listing_page(path: str, page: int = 1) -> list[Job]:
    """抓取分类列表页，返回职位列表"""
    url = f"{BASE_URL}{path}"
    if page > 1:
        url = f"{url}?page={page}"

    try:
        resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"  [GradConnection] 请求失败: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # GradConnection 职位卡片容器
    job_cards = soup.select("div.campaign-listing-box")

    if not job_cards:
        print(f"  未找到职位卡片（路径: {path}，第 {page} 页）")
        return []

    jobs = []
    for card in job_cards:
        job = _parse_card(card)
        if job and _matches_keywords(job.title, job.description):
            jobs.append(job)

    return jobs


def _parse_card(card) -> Job | None:
    """解析单个职位卡片"""
    try:
        # 职位标题和链接
        title_tag = card.select_one("a.box-header-title")
        if not title_tag:
            return None

        title = title_tag.get("title", "").replace("View ", "").strip()
        if not title:
            title = title_tag.get_text(strip=True)
        href = title_tag.get("href", "")
        url = href if href.startswith("http") else f"{BASE_URL}{href}"

        # 从 URL 提取 ID（取路径最后两段作为唯一标识）
        job_id = "-".join(href.strip("/").split("/")[-2:]) or href

        # 公司名
        company_tag = card.select_one(".box-employer-name a, .box-employer-name p")
        company = company_tag.get_text(strip=True) if company_tag else "未知公司"

        # 地点：GradConnection 按城市分类，默认 Melbourne
        location = "Melbourne, VIC"

        # 描述：listing页无完整描述，用标题代替（详情在链接内）
        description = ""

        # 关闭日期（如 "Closing in 7 hours" / "Closing in 3 days"）
        closing_tag = card.select_one(".box-closing-interval span")
        posted = closing_tag.get_text(strip=True) if closing_tag else ""

        if not title or not job_id:
            return None

        return Job(
            title=title,
            company=company,
            location=location,
            platform="GradConnection",
            url=url,
            job_id=f"gc_{job_id}",
            posted_date=posted[:10] if len(posted) >= 10 else posted,
            description=description,
        )
    except Exception as e:
        print(f"  [GradConnection] 解析卡片出错: {e}")
        return None


def scrape() -> list[Job]:
    """
    对外接口：抓取 GradConnection 金融实习职位，并检测签证要求。

    返回：
        Job 列表（已去重，含 visa_friendly 字段）
    """
    all_jobs: list[Job] = []
    seen_ids: set[str] = set()

    # ── 第一阶段：抓取列表页 ──
    for path in FINANCE_PATHS:
        print(f"\n[GradConnection] 分类: {path}")

        for pg in range(1, config.MAX_PAGES + 1):
            jobs = _fetch_listing_page(path, pg)

            if not jobs:
                print(f"  第 {pg} 页：无符合条件职位，停止翻页")
                break

            new_count = 0
            for job in jobs:
                if job.job_id not in seen_ids:
                    seen_ids.add(job.job_id)
                    all_jobs.append(job)
                    new_count += 1

            print(f"  第 {pg} 页：获取 {len(jobs)} 条，新增 {new_count} 条")
            time.sleep(config.REQUEST_DELAY)

    # ── 第二阶段：逐个检测签证要求 ──
    print(f"\n[GradConnection] 检测签证要求（共 {len(all_jobs)} 个职位）...")
    for i, job in enumerate(all_jobs, 1):
        job.visa_friendly = _check_visa(job.url)
        status = {"yes": "✅ 接受", "no": "❌ 不接受", "unknown": "❓ 未知"}[job.visa_friendly]
        print(f"  [{i:02d}/{len(all_jobs)}] {status}  {job.title[:45]}")
        time.sleep(1)  # 礼貌间隔

    yes_count = sum(1 for j in all_jobs if j.visa_friendly == "yes")
    print(f"\n[GradConnection] 完成：{len(all_jobs)} 个职位，其中 {yes_count} 个接受国际学生")
    return all_jobs
