"""
微信通知 — 通过 Server酱 (serverchan.com) 推送到微信
配置方法：
  1. 访问 https://sct.ftqq.com/ 用微信登录
  2. 复制 SendKey（格式：SCT开头的字符串）
  3. 填入 config.py 的 WECHAT_WEBHOOK
"""

import httpx
from job_scraper.models import Job
from job_scraper import config

SERVERCHAN_URL = "https://sctapi.ftqq.com/{key}.send"


def _build_message(jobs: list[Job]) -> tuple[str, str]:
    """返回 (title, content_markdown)"""
    intl_count = sum(1 for j in jobs if j.visa_friendly == "yes")
    title = f"💼 金融实习 | {len(jobs)} 个新职位（{intl_count} 个接受国际学生）"

    lines = []
    for job in jobs:
        visa_icon = {"yes": "✅", "no": "❌", "unknown": "❓"}.get(job.visa_friendly, "❓")
        lines.append(
            f"**{job.title}**  \n"
            f"🏢 {job.company} | 📍 {job.location} | {job.platform}  \n"
            f"{visa_icon} 签证 | [{' 查看职位 '}]({job.url})  \n"
        )

    content = "\n---\n".join(lines)
    content += "\n\n> 自动抓取 · 签证要求请以官网为准"
    return title, content


def send(jobs: list[Job]) -> bool:
    """
    通过 Server酱 推送到微信。
    返回 True 表示发送成功。
    """
    if not config.WECHAT_WEBHOOK:
        print("[微信] 未配置 WECHAT_WEBHOOK，跳过（请在 config.py 填写 Server酱 SendKey）")
        return False

    title, content = _build_message(jobs)

    try:
        url = SERVERCHAN_URL.format(key=config.WECHAT_WEBHOOK)
        resp = httpx.post(url, data={"title": title, "desp": content}, timeout=15)
        data = resp.json()
        if data.get("code") == 0:
            print(f"[微信] 已推送 {len(jobs)} 个新职位")
            return True
        else:
            print(f"[微信] 推送失败: {data.get('message', '未知错误')}")
            return False
    except Exception as e:
        print(f"[微信] 推送失败: {e}")
        return False
