"""
主入口 — 爬取 → 去重 → 存库 → 通知
每天定时运行，只推送当天新出现的职位。
"""

import sys
import io
import csv
import os
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from job_scraper.scrapers import gradconnection, linkedin, shixiseng, feishu
from job_scraper.storage import database
from job_scraper.notifiers import email_notifier, wechat_notifier
from job_scraper.models import Job


def save_csv(jobs: list[Job], filename: str):
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "title", "company", "location", "platform",
            "posted_date", "salary", "visa_friendly", "url", "scraped_at",
        ])
        writer.writeheader()
        for job in jobs:
            writer.writerow({
                "title":        job.title,
                "company":      job.company,
                "location":     job.location,
                "platform":     job.platform,
                "posted_date":  job.posted_date,
                "salary":       job.salary,
                "visa_friendly": job.visa_friendly,
                "url":          job.url,
                "scraped_at":   job.scraped_at,
            })


def main():
    print("=" * 60)
    print(f"  金融实习岗位爬虫 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # ── 初始化数据库 ──
    database.init_db()

    # ── 爬取 ──
    all_jobs: list[Job] = []

    print("\n>>> GradConnection（墨尔本）")
    all_jobs.extend(gradconnection.scrape())

    print("\n>>> LinkedIn（墨尔本）")
    all_jobs.extend(linkedin.scrape())

    print("\n>>> 实习僧（上海/北京/深圳）")
    all_jobs.extend(shixiseng.scrape())

    print("\n>>> 飞书文档（实时实习表格）")
    all_jobs.extend(feishu.scrape())

    print(f"\n本次爬取合计：{len(all_jobs)} 个职位")

    # ── 去重入库，找出新职位 ──
    new_jobs = database.upsert_jobs(all_jobs)
    db_stats = database.stats()

    print(f"\n{'='*60}")
    print(f"  新职位：{len(new_jobs)} 个")
    print(f"  数据库累计：{db_stats['total']} 个（签证友好：{db_stats['visa_yes']} 个）")
    print("=" * 60)

    # ── 保存 CSV（当次全量）──
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    csv_file = f"{output_dir}/jobs_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    save_csv(all_jobs, csv_file)
    print(f"CSV 已保存: {csv_file}")

    # ── 通知（仅推送新职位）──
    if not new_jobs:
        print("\n没有新职位，跳过通知。")
        return

    print(f"\n发现 {len(new_jobs)} 个新职位，开始推送通知...")

    sent = False
    sent |= email_notifier.send(new_jobs)
    sent |= wechat_notifier.send(new_jobs)

    # 标记已通知
    if sent:
        database.mark_notified([j.job_id for j in new_jobs])

    print("\n完成。")


if __name__ == "__main__":
    main()
