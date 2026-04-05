"""
SQLite 存储层
- 记录所有历史职位，防止重复通知
- 追踪每个职位的状态（新发现 / 已通知 / 已投递）
"""

import sqlite3
import os
from datetime import datetime
from job_scraper.models import Job

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "jobs.db")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """建表（首次运行时执行）"""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id        TEXT PRIMARY KEY,
                title         TEXT NOT NULL,
                company       TEXT,
                location      TEXT,
                platform      TEXT,
                url           TEXT,
                posted_date   TEXT,
                salary        TEXT,
                visa_friendly TEXT DEFAULT 'unknown',
                first_seen    TEXT,
                notified      INTEGER DEFAULT 0,
                status        TEXT DEFAULT 'new'
            )
        """)
        conn.commit()


def upsert_jobs(jobs: list[Job]) -> list[Job]:
    """
    批量写入职位，返回本次新发现的职位列表（DB 中不存在的）。
    已存在的职位只更新 visa_friendly（可能经过了重新检测）。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_jobs = []

    with _connect() as conn:
        for job in jobs:
            existing = conn.execute(
                "SELECT job_id FROM jobs WHERE job_id = ?", (job.job_id,)
            ).fetchone()

            if existing is None:
                conn.execute("""
                    INSERT INTO jobs
                        (job_id, title, company, location, platform, url,
                         posted_date, salary, visa_friendly, first_seen, notified, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'new')
                """, (
                    job.job_id, job.title, job.company, job.location,
                    job.platform, job.url, job.posted_date, job.salary,
                    job.visa_friendly, now,
                ))
                new_jobs.append(job)
            else:
                # 更新签证状态（可能重新检测后有变化）
                conn.execute(
                    "UPDATE jobs SET visa_friendly = ? WHERE job_id = ?",
                    (job.visa_friendly, job.job_id),
                )
        conn.commit()

    return new_jobs


def mark_notified(job_ids: list[str]):
    """将指定职位标记为已通知"""
    with _connect() as conn:
        conn.executemany(
            "UPDATE jobs SET notified = 1 WHERE job_id = ?",
            [(jid,) for jid in job_ids],
        )
        conn.commit()


def get_all_jobs() -> list[dict]:
    """返回所有职位（供网页展示用）"""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY first_seen DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def stats() -> dict:
    """返回统计数据"""
    with _connect() as conn:
        total    = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        new      = conn.execute("SELECT COUNT(*) FROM jobs WHERE notified=0").fetchone()[0]
        intl     = conn.execute("SELECT COUNT(*) FROM jobs WHERE visa_friendly='yes'").fetchone()[0]
        by_plat  = conn.execute(
            "SELECT platform, COUNT(*) as n FROM jobs GROUP BY platform"
        ).fetchall()
    return {
        "total": total,
        "unnotified": new,
        "visa_yes": intl,
        "by_platform": {r["platform"]: r["n"] for r in by_plat},
    }
