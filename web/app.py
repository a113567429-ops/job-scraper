"""
Flask 网页 Demo — 金融实习职位看板
运行: python web/app.py
访问: http://localhost:5000
"""

import sys, os, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, render_template, jsonify, request, Response
from job_scraper.storage import database

app = Flask(__name__)

# ── 密码保护 ──────────────────────────────────────────────
WEB_USER     = os.getenv("WEB_USER",     "admin")
WEB_PASSWORD = os.getenv("WEB_PASSWORD", "")   # 空 = 本地不需要密码

def _check_auth(username, password):
    return username == WEB_USER and password == WEB_PASSWORD

def _require_auth():
    return Response(
        "请输入用户名和密码", 401,
        {"WWW-Authenticate": 'Basic realm="Job Scraper"'}
    )

@app.before_request
def auth_guard():
    if not WEB_PASSWORD:          # 本地运行不拦截
        return
    auth = request.authorization
    if not auth or not _check_auth(auth.username, auth.password):
        return _require_auth()


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
    intl_count  = sum(1 for j in jobs if j.get("visa_friendly") == "yes")
    saved_count = sum(1 for j in jobs if j.get("status") == "saved")
    applied_count = sum(1 for j in jobs if j.get("status") == "applied")
    last_seen = jobs[0]["first_seen"][:16] if jobs else "—"
    return render_template("index.html",
                           jobs=jobs,
                           companies=companies,
                           platforms=platforms,
                           filename=f"数据库 · 最新抓取 {last_seen}",
                           total=len(jobs),
                           intl_count=intl_count,
                           saved_count=saved_count,
                           applied_count=applied_count)


@app.route("/api/status", methods=["POST"])
def update_status():
    data = request.get_json()
    job_id = data.get("job_id")
    status = data.get("status")
    if job_id and status in ("new", "saved", "applied"):
        database.update_status(job_id, status)
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 400


@app.route("/api/jobs")
def api_jobs():
    company  = request.args.get("company", "")
    platform = request.args.get("platform", "")
    visa     = request.args.get("visa", "")
    status   = request.args.get("status", "")
    q        = request.args.get("q", "").lower()

    jobs = load_jobs()
    if company:  jobs = [j for j in jobs if j["company"] == company]
    if platform: jobs = [j for j in jobs if j["platform"] == platform]
    if visa:     jobs = [j for j in jobs if j["visa_friendly"] == visa]
    if status:   jobs = [j for j in jobs if j["status"] == status]
    if q:        jobs = [j for j in jobs if q in j["title"].lower() or q in j["company"].lower()]
    return jsonify(jobs)


@app.route("/api/stats")
def api_stats():
    return jsonify(database.stats())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
