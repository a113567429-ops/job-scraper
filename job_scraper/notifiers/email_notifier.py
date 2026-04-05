"""
邮件通知
- 使用 SMTP（支持 Gmail / QQ邮箱 / 163邮箱）
- 发送 HTML 格式邮件，含职位卡片
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from job_scraper.models import Job
from job_scraper import config


def _build_html(jobs: list[Job]) -> str:
    visa_badge = {
        "yes":     '<span style="background:#d5f5e3;color:#1e8449;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600;">✅ 接受国际学生</span>',
        "no":      '<span style="background:#fadbd8;color:#922b21;padding:2px 8px;border-radius:12px;font-size:12px;">❌ 仅PR/公民</span>',
        "unknown": '<span style="background:#f2f3f4;color:#717d7e;padding:2px 8px;border-radius:12px;font-size:12px;">❓ 待确认</span>',
    }

    cards = ""
    for job in jobs:
        badge = visa_badge.get(job.visa_friendly, visa_badge["unknown"])
        cards += f"""
        <div style="border:1px solid #e0e0e0;border-radius:10px;padding:16px 20px;
                    margin-bottom:14px;border-left:4px solid
                    {'#00b894' if job.visa_friendly=='yes' else '#bdc3c7'};">
          <div style="font-size:16px;font-weight:600;color:#1a1a2e;margin-bottom:6px;">
            {job.title}
          </div>
          <div style="color:#555;font-size:14px;margin-bottom:8px;">🏢 {job.company}</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
            <span style="background:#e8f4fd;color:#1565c0;padding:2px 8px;border-radius:12px;font-size:12px;">
              📍 {job.location}
            </span>
            <span style="background:#fce4ec;color:#c62828;padding:2px 8px;border-radius:12px;font-size:12px;">
              {job.platform}
            </span>
            {badge}
          </div>
          <a href="{job.url}" style="background:#1a1a2e;color:white;padding:8px 16px;
             border-radius:6px;text-decoration:none;font-size:13px;display:inline-block;">
            查看 &amp; 申请 →
          </a>
        </div>
        """

    intl_count = sum(1 for j in jobs if j.visa_friendly == "yes")

    return f"""
    <html><body style="font-family:-apple-system,sans-serif;max-width:640px;margin:0 auto;padding:20px;">
      <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);color:white;
                  padding:20px 24px;border-radius:12px;margin-bottom:20px;">
        <h1 style="margin:0;font-size:20px;">金融实习岗位 — 新职位通知</h1>
        <p style="margin:6px 0 0;color:#aaa;font-size:13px;">
          共 <b style="color:white;">{len(jobs)}</b> 个新职位，
          其中 <b style="color:#00b894;">{intl_count}</b> 个接受国际学生
        </p>
      </div>
      {cards}
      <p style="color:#bbb;font-size:12px;text-align:center;margin-top:20px;">
        自动抓取 · 签证要求请以官网为准
      </p>
    </body></html>
    """


def send(jobs: list[Job]) -> bool:
    """
    发送新职位邮件给所有收件人。
    返回 True 表示至少发送成功一封。
    """
    receivers = getattr(config, "EMAIL_RECEIVERS", [])
    # 兼容旧版单收件人字段
    if not receivers and getattr(config, "EMAIL_RECEIVER", ""):
        receivers = [config.EMAIL_RECEIVER]

    if not all([config.EMAIL_SENDER, config.EMAIL_PASSWORD]) or not receivers:
        print("[邮件] 未配置邮箱信息，跳过（请在 config.py 填写）")
        return False

    # 自动选择 SMTP 服务器
    sender = config.EMAIL_SENDER.lower()
    if "gmail" in sender:
        host, port = "smtp.gmail.com", 587
    elif "qq.com" in sender:
        host, port = "smtp.qq.com", 587
    elif "163.com" in sender:
        host, port = "smtp.163.com", 465
    elif "126.com" in sender:
        host, port = "smtp.126.com", 465
    else:
        host, port = "smtp.gmail.com", 587

    html = _build_html(jobs)
    success = False

    try:
        with smtplib.SMTP(host, port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)

            for receiver in receivers:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"【金融实习】{len(jobs)} 个新职位 🔔"
                msg["From"]    = config.EMAIL_SENDER
                msg["To"]      = receiver
                msg.attach(MIMEText(html, "html", "utf-8"))
                smtp.sendmail(config.EMAIL_SENDER, receiver, msg.as_string())
                print(f"[邮件] 已发送至 {receiver}")

            success = True
    except Exception as e:
        print(f"[邮件] 发送失败: {e}")

    return success
