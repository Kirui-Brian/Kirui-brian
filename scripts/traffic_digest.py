"""
Daily GitHub Traffic Digest
Queries GitHub Traffic API for repository views, unique visitors, clones, and referrers,
and emails a daily report via SMTP.
"""

import os
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
import requests

GITHUB_TOKEN = os.getenv("TRAFFIC_TOKEN") or os.getenv("GITHUB_TOKEN")
OWNER = os.getenv("GITHUB_REPOSITORY_OWNER", "Kirui-brian")
CUSTOM_REPOS = os.getenv("TRACKED_REPOS")  # comma-separated list, e.g. "Kirui-brian,repo2"

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
TO_EMAIL = os.getenv("TO_EMAIL") or SMTP_USER

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
}


def get_target_repos():
    if CUSTOM_REPOS:
        return [r.strip() for r in CUSTOM_REPOS.split(",") if r.strip()]

    # Fetch user's public repos automatically
    url = f"https://api.github.com/users/{OWNER}/repos?per_page=100&sort=pushed"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            repos = [repo["name"] for repo in r.json() if not repo.get("fork")]
            return repos or ["Kirui-brian"]
    except Exception as e:
        print(f"Warning: Failed to fetch repos list: {e}")

    return ["Kirui-brian"]


def fetch_repo_traffic(repo_name):
    base_url = f"https://api.github.com/repos/{OWNER}/{repo_name}/traffic"
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    traffic = {
        "repo": repo_name,
        "views_today": 0,
        "uniques_today": 0,
        "clones_today": 0,
        "top_referrers": [],
    }

    # Fetch views
    v_res = requests.get(f"{base_url}/views", headers=HEADERS, timeout=15)
    if v_res.status_code == 200:
        views_data = v_res.json()
        for v in views_data.get("views", []):
            if v.get("timestamp", "").startswith(today_str):
                traffic["views_today"] = v.get("count", 0)
                traffic["uniques_today"] = v.get("uniques", 0)
                break

    # Fetch clones
    c_res = requests.get(f"{base_url}/clones", headers=HEADERS, timeout=15)
    if c_res.status_code == 200:
        clones_data = c_res.json()
        for c in clones_data.get("clones", []):
            if c.get("timestamp", "").startswith(today_str):
                traffic["clones_today"] = c.get("count", 0)
                break

    # Fetch top referrers (last 14 days)
    ref_res = requests.get(f"{base_url}/popular/referrers", headers=HEADERS, timeout=15)
    if ref_res.status_code == 200:
        traffic["top_referrers"] = ref_res.json()[:3]

    return traffic


def build_html_report(results, report_date):
    rows = []
    total_views = 0
    total_uniques = 0

    for item in results:
        v = item["views_today"]
        u = item["uniques_today"]
        c = item["clones_today"]
        total_views += v
        total_uniques += u

        refs = ", ".join([f"{ref['referrer']} ({ref['count']})" for ref in item.get("top_referrers", [])]) or "None"

        # Highlight repos that had activity today
        bg_style = "background-color: #f6f8fa;" if (v > 0 or c > 0) else ""

        rows.append(f"""
        <tr style="{bg_style}">
            <td style="padding: 8px 12px; border: 1px solid #ddd;"><b>{item['repo']}</b></td>
            <td style="padding: 8px 12px; border: 1px solid #ddd; text-align: center;">{v}</td>
            <td style="padding: 8px 12px; border: 1px solid #ddd; text-align: center;">{u}</td>
            <td style="padding: 8px 12px; border: 1px solid #ddd; text-align: center;">{c}</td>
            <td style="padding: 8px 12px; border: 1px solid #ddd; font-size: 13px;">{refs}</td>
        </tr>
        """)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #24292f; margin: 0; padding: 20px;">
        <div style="max-width: 680px; margin: 0 auto; border: 1px solid #d0d7de; border-radius: 8px; overflow: hidden;">
            <div style="background-color: #0969da; color: #ffffff; padding: 16px 20px;">
                <h2 style="margin: 0; font-size: 20px;">Daily GitHub Activity Digest</h2>
                <p style="margin: 4px 0 0; font-size: 14px; opacity: 0.9;">Account: <b>@{OWNER}</b> | Date: {report_date} (UTC)</p>
            </div>
            <div style="padding: 20px;">
                <div style="display: flex; margin-bottom: 20px;">
                    <div style="padding: 12px 16px; background-color: #f6f8fa; border-radius: 6px; margin-right: 12px; flex: 1;">
                        <span style="font-size: 12px; color: #57606a;">TOTAL VIEWS TODAY</span><br>
                        <b style="font-size: 24px; color: #0969da;">{total_views}</b>
                    </div>
                    <div style="padding: 12px 16px; background-color: #f6f8fa; border-radius: 6px; flex: 1;">
                        <span style="font-size: 12px; color: #57606a;">UNIQUE VISITORS TODAY</span><br>
                        <b style="font-size: 24px; color: #1a7f37;">{total_uniques}</b>
                    </div>
                </div>

                <h3 style="font-size: 16px; border-bottom: 1px solid #d0d7de; padding-bottom: 8px;">Repository Traffic Breakdown</h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 14px; margin-top: 10px;">
                    <thead>
                        <tr style="background-color: #f6f8fa;">
                            <th style="padding: 8px 12px; border: 1px solid #ddd; text-align: left;">Repository</th>
                            <th style="padding: 8px 12px; border: 1px solid #ddd; text-align: center;">Views</th>
                            <th style="padding: 8px 12px; border: 1px solid #ddd; text-align: center;">Uniques</th>
                            <th style="padding: 8px 12px; border: 1px solid #ddd; text-align: center;">Clones</th>
                            <th style="padding: 8px 12px; border: 1px solid #ddd; text-align: left;">Top Referrers</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>

                <p style="margin-top: 24px; font-size: 12px; color: #57606a; border-top: 1px solid #eaeef2; padding-top: 12px;">
                    ℹ️ <i>Note: GitHub Traffic API keeps individual visitor identities and locations anonymous by design. Outbound link clicks can be tracked via your custom analytics/redirector.</i>
                </p>
            </div>
        </div>
    </body>
    </html>
    """


def send_email(subject, html_content):
    if not (SMTP_USER and SMTP_PASS and TO_EMAIL):
        print("SMTP credentials not fully configured. Report generated successfully without sending email.")
        print(f"Subject: {subject}")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = TO_EMAIL
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, TO_EMAIL, msg.as_string())
        print(f"Successfully sent daily traffic digest to {TO_EMAIL}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}", file=sys.stderr)
        return False


def main():
    if not GITHUB_TOKEN:
        print("ERROR: GITHUB_TOKEN or TRAFFIC_TOKEN environment variable is required.", file=sys.stderr)
        sys.exit(1)

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"Fetching traffic for @{OWNER} on {today_str}...")

    repos = get_target_repos()
    print(f"Scanning repositories: {', '.join(repos)}")

    results = []
    for repo in repos:
        traffic = fetch_repo_traffic(repo)
        results.append(traffic)

    html_report = build_html_report(results, today_str)
    subject = f"📊 GitHub Daily Activity Report: @{OWNER} ({today_str})"

    send_email(subject, html_report)


if __name__ == "__main__":
    main()
