# ============================================================
# 配置文件 — 关键词、地区、通知设置
# 本地运行：直接填下面的值
# GitHub Actions：通过环境变量注入（Secrets），优先级更高
# ============================================================

import os

# ---------- 澳洲搜索关键词（英文）----------
KEYWORDS_AU = [
    "private equity intern",
    "venture capital intern",
    "fund management intern",
    "investment analyst intern",
    "research analyst intern",
    "asset management intern",
    "equity research intern",
    "financial analyst intern",
]

# ---------- 中国搜索关键词（中文）----------
KEYWORDS_CN = [
    "PE实习",
    "VC实习",
    "私募实习",
    "基金实习",
    "行业研究实习",
    "投研实习",
    "股权投资实习",
    "风险投资实习",
]

# ---------- 地区设置 ----------
LOCATION_AU = "Melbourne VIC"

LOCATIONS_CN = ["上海", "北京", "深圳"]

# ---------- 爬虫设置 ----------
DAYS_RANGE    = 7   # 只获取最近 N 天发布的职位
REQUEST_DELAY = 2   # 每次请求间隔秒数
MAX_PAGES     = 5   # 每个关键词最多抓几页

# ---------- 通知设置（本地默认值，GitHub Actions 用 Secrets 覆盖）----------
EMAIL_SENDER   = os.getenv("EMAIL_SENDER",   "a113567429@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "dzdq latb yvvz wewk")

# 收件人：环境变量用逗号分隔，本地直接填列表
_receivers_env = os.getenv("EMAIL_RECEIVERS", "")
EMAIL_RECEIVERS = (
    [r.strip() for r in _receivers_env.split(",") if r.strip()]
    if _receivers_env
    else [
        "a113567429@gmail.com",
        "zhongc372@gmail.com",
    ]
)

WECHAT_WEBHOOK = os.getenv("WECHAT_WEBHOOK", "SCT334014TKgt1eub7prteLz4SaFagHDDj")

# ---------- 飞书 API（读取实时实习表格）----------
FEISHU_APP_ID     = os.getenv("FEISHU_APP_ID",     "")   # 创建应用后填入
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")   # 创建应用后填入
