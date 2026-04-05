"""
飞书文档爬虫
- 通过飞书开放平台 API 读取实时更新的实习表格
- 文档: https://dcnb3gfq7cll.feishu.cn/wiki/C4X6wYOFqiYzcxk5gipcCem5nwe

配置步骤（一次性）:
  1. 打开 https://open.feishu.cn/app → 创建自建应用
  2. 权限管理 → 添加: wiki:wiki:readonly + sheets:spreadsheet:readonly
  3. 版本管理 → 创建并发布版本
  4. 将 App ID / App Secret 填入 config.py
  5. 文档右上角「分享」→ 添加应用为协作者（或开启「组织内可访问」）
"""

import httpx
from job_scraper.models import Job
from job_scraper import config

FEISHU_HOST   = "https://open.feishu.cn"
WIKI_TOKEN    = "C4X6wYOFqiYzcxk5gipcCem5nwe"   # 从 URL 提取
SHEET_ID      = "0d46ae"                           # URL 中 sheet= 的值

# 金融/经济相关关键词（用于过滤表格中的非相关行）
FINANCE_KEYWORDS = [
    "金融", "finance", "经济", "economics", "投资", "investment",
    "PE", "VC", "私募", "基金", "fund", "银行", "bank",
    "证券", "资管", "资产", "行研", "研究", "analyst",
    "实习", "intern",
]


def _get_token() -> str:
    """获取飞书 tenant_access_token"""
    resp = httpx.post(
        f"{FEISHU_HOST}/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": config.FEISHU_APP_ID, "app_secret": config.FEISHU_APP_SECRET},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"飞书认证失败: {data.get('msg')}")
    return data["tenant_access_token"]


def _get_sheet_token(access_token: str) -> str:
    """通过 wiki token 获取实际的 spreadsheet token"""
    resp = httpx.get(
        f"{FEISHU_HOST}/open-apis/wiki/v2/spaces/get_node",
        params={"token": WIKI_TOKEN},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取 Wiki 节点失败: {data.get('msg')}")
    return data["data"]["node"]["obj_token"]


def _read_sheet(access_token: str, sheet_token: str) -> list[list]:
    """读取表格全部内容，返回二维数组"""
    resp = httpx.get(
        f"{FEISHU_HOST}/open-apis/sheets/v3/spreadsheets/{sheet_token}/values/{SHEET_ID}!A1:Z500",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"读取表格失败: {data.get('msg')}")
    return data["data"]["valueRange"]["values"]


def _is_finance(row: list) -> bool:
    """判断某行是否与金融/经济实习相关"""
    text = " ".join(str(cell) for cell in row if cell).lower()
    return any(kw.lower() in text for kw in FINANCE_KEYWORDS)


def _parse_row(row: list, headers: list) -> Job | None:
    """将表格一行解析为 Job 对象"""
    try:
        # 构建列名 → 值的映射
        cells = {headers[i]: str(row[i]).strip() if i < len(row) and row[i] else ""
                 for i in range(len(headers))}

        # 自动识别常见列名
        def find(candidates):
            for c in candidates:
                for h, v in cells.items():
                    if c in str(h).lower():
                        return v
            return ""

        title   = find(["职位", "岗位", "position", "job title", "title"])
        company = find(["公司", "机构", "company", "firm", "employer"])
        location= find(["地点", "城市", "location", "city"])
        url     = find(["链接", "投递", "apply", "link", "i列", "url"])
        deadline= find(["截止", "deadline", "ddl", "due"])
        category= find(["类型", "方向", "category", "type"])

        # 也尝试按列索引取（I列=第9列=index 8）
        if not url and len(row) > 8:
            url = str(row[8]).strip()

        if not title and not company:
            return None

        # 用公司+标题生成唯一 ID
        import hashlib
        raw_id = f"{company}_{title}_{url}"
        job_id = "fs_" + hashlib.md5(raw_id.encode()).hexdigest()[:10]

        return Job(
            title    = title or f"{company} 实习",
            company  = company or "未知机构",
            location = location or "未知",
            platform = "飞书文档",
            url      = url or "",
            job_id   = job_id,
            posted_date = deadline,
            description = category,
            visa_friendly = "n/a",
        )
    except Exception as e:
        print(f"  [飞书] 解析行出错: {e}")
        return None


def scrape() -> list[Job]:
    """
    对外接口：从飞书文档读取金融实习职位

    返回:
        Job 列表
    """
    if not getattr(config, "FEISHU_APP_ID", "") or not getattr(config, "FEISHU_APP_SECRET", ""):
        print("[飞书] 未配置 FEISHU_APP_ID / FEISHU_APP_SECRET，跳过")
        return []

    try:
        print("[飞书] 获取访问令牌...")
        token = _get_token()

        print("[飞书] 获取文档 token...")
        sheet_token = _get_sheet_token(token)

        print(f"[飞书] 读取表格 (sheet={SHEET_ID})...")
        rows = _read_sheet(token, sheet_token)

        if not rows:
            print("[飞书] 表格为空")
            return []

        # 第一行为表头
        headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(rows[0])]
        print(f"[飞书] 共 {len(rows)-1} 行，列名: {headers[:10]}")

        jobs = []
        seen = set()
        for row in rows[1:]:
            if not _is_finance(row):
                continue
            job = _parse_row(row, headers)
            if job and job.job_id not in seen:
                seen.add(job.job_id)
                jobs.append(job)

        print(f"[飞书] 完成，找到 {len(jobs)} 个金融相关实习")
        return jobs

    except Exception as e:
        print(f"[飞书] 出错: {e}")
        return []
