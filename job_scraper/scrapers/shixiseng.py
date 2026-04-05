"""
实习僧爬虫（中国实习专用平台）
- 覆盖 PE/VC/私募/基金/行业研究 实习
- 支持上海、北京、深圳
- 服务端渲染，无需 Playwright
"""

import re
import time
import httpx
from bs4 import BeautifulSoup

from job_scraper.models import Job
from job_scraper import config

BASE_URL = "http://www.shixiseng.com/interns"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "http://www.shixiseng.com/",
}

TITLE_MUST = [
    "pe", "vc", "私募", "基金", "投资", "股权", "风险投资",
    "资产管理", "行业研究", "投研", "研究员", "分析师",
    "investment", "equity", "capital", "fund",
    "财务", "金融", "证券", "资本",
]

TITLE_EXCLUDE = [
    "it", "软件", "前端", "后端", "开发", "运营", "市场",
    "人力", "行政", "法务", "设计", "销售",
]


def _clean(text: str) -> str:
    """清除实习僧字体混淆字符（Unicode私用区 U+E000–U+F8FF）"""
    return re.sub(r"[\uE000-\uF8FF]", "", text).strip()


def _matches(title: str) -> bool:
    t = title.lower()
    return (
        any(kw in t for kw in TITLE_MUST)
        and not any(kw in t for kw in TITLE_EXCLUDE)
    )


def _clean_title(tag) -> str:
    """取元素文本并过滤字体混淆字符"""
    return _clean(tag.get_text(strip=True))


def _fetch_page(keyword: str, city: str, page: int) -> list[Job]:
    params = {"keyword": keyword, "city": city, "page": page}
    try:
        resp = httpx.get(BASE_URL, params=params, headers=HEADERS,
                         timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"  [实习僧] 请求失败: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select("div.intern-item")

    jobs = []
    for card in cards:
        job = _parse_card(card, city)
        if job and _matches(job.title):
            jobs.append(job)
    return jobs


def _parse_card(card, city: str) -> Job | None:
    try:
        job_id = card.get("data-intern-id", "")
        if not job_id:
            return None

        # 职位标题（左侧栏）
        title_tag = card.select_one("div.intern-detail__job a.title")
        title = _clean_title(title_tag) if title_tag else ""

        # 公司名称（右侧栏）
        company_tag = card.select_one("div.intern-detail__company a.title")
        company = _clean(company_tag.get("title", "")) or (
            _clean_title(company_tag) if company_tag else "未知公司"
        )

        # 薪资：实习僧用自定义字体混淆数字，爬取结果为乱码，统一显示"见详情"
        salary = "见详情"

        # 城市
        city_tag = card.select_one("span.city")
        location = _clean(city_tag.get_text(strip=True)) if city_tag else city

        # 链接
        link_tag = card.select_one("div.intern-detail__job a.title")
        href = link_tag.get("href", "") if link_tag else ""
        url = href.split("?")[0]  # 去掉 tracking 参数

        if not title or not url:
            return None

        return Job(
            title=title,
            company=company,
            location=location,
            platform="实习僧",
            url=url,
            job_id=f"sxs_{job_id}",
            posted_date="",
            salary=salary,
            visa_friendly="n/a",  # 国内岗位不涉及签证
        )
    except Exception as e:
        print(f"  [实习僧] 解析出错: {e}")
        return None


def scrape(
    keywords: list[str] = None,
    cities: list[str] = None,
) -> list[Job]:
    """
    对外接口：抓取实习僧金融实习职位

    返回：
        Job 列表（已去重）
    """
    keywords = keywords or config.KEYWORDS_CN
    cities   = cities   or config.LOCATIONS_CN

    all_jobs: list[Job] = []
    seen_ids: set[str]  = set()

    for city in cities:
        for keyword in keywords:
            print(f"\n[实习僧] {city} · '{keyword}'")

            for page in range(1, config.MAX_PAGES + 1):
                jobs = _fetch_page(keyword, city, page)

                if not jobs:
                    print(f"  第 {page} 页：无结果")
                    break

                new_count = 0
                for job in jobs:
                    if job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        all_jobs.append(job)
                        new_count += 1

                print(f"  第 {page} 页：{len(jobs)} 条，新增 {new_count}")

                if len(jobs) < 10:
                    break

                time.sleep(config.REQUEST_DELAY)

            time.sleep(config.REQUEST_DELAY)

    print(f"\n[实习僧] 完成，共 {len(all_jobs)} 个不重复职位")
    return all_jobs
