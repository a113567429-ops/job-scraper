"""
Flask 网页 Demo — 金融实习职位看板
运行: python web/app.py
访问: http://localhost:5000
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, render_template, jsonify, request
from job_scraper.storage import database

app = Flask(__name__)


def load_jobs():
    try:
        database.init_db()
        return database.get_all_jobs()
    except Exception:
        return []


@app.route("/")
def index():
    jobs = load_jobs()
    companies = sorted(set(j["company"] for j in jobs))
    platforms = sorted(set(j["platform"] for j in jobs))
    intl_count = sum(1 for j in jobs if j.get("visa_friendly") == "yes")
    last_seen = jobs[0]["first_seen"][:16] if jobs else "—"
    return render_template("index.html",
                           jobs=jobs,
                           companies=companies,
                           platforms=platforms,
                           filename=f"数据库 · 最新抓取 {last_seen}",
                           total=len(jobs),
                           intl_count=intl_count)


@app.route("/api/jobs")
def api_jobs():
    company  = request.args.get("company", "")
    platform = request.args.get("platform", "")
    visa     = request.args.get("visa", "")
    q        = request.args.get("q", "").lower()

    jobs = load_jobs()
    if company:  jobs = [j for j in jobs if j["company"] == company]
    if platform: jobs = [j for j in jobs if j["platform"] == platform]
    if visa:     jobs = [j for j in jobs if j["visa_friendly"] == visa]
    if q:        jobs = [j for j in jobs if q in j["title"].lower() or q in j["company"].lower()]

    return jsonify(jobs)


@app.route("/api/stats")
def api_stats():
    return jsonify(database.stats())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
