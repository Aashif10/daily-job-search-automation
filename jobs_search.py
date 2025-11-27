#!/usr/bin/env python3
"""
jobs_search.py
Daily job search + email report using Google Custom Search JSON API.

Required environment variables:
- GCSE_API_KEY
- GCSE_CX
- RECIPIENT_EMAIL
- SENDER_EMAIL
- SMTP_HOST (default smtp.gmail.com)
- SMTP_PORT (default 587)
- SMTP_USER
- SMTP_PASS
- TOP_STARTUPS (optional comma-separated list, e.g. "stripe.com,notion.so,airbnb.com")
"""
import os
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
import html
import time

# --- Configuration from environment ---
API_KEY = os.environ.get("GCSE_API_KEY")
CX = os.environ.get("GCSE_CX")
RECIPIENT = os.environ.get("RECIPIENT_EMAIL")
SENDER = os.environ.get("SENDER_EMAIL")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER", SENDER)
SMTP_PASS = os.environ.get("SMTP_PASS")
TOP_STARTUPS_ENV = os.environ.get("TOP_STARTUPS", "")
TOP_STARTUPS = [s.strip() for s in TOP_STARTUPS_ENV.split(",") if s.strip()]

ROLES = [
    "Frontend Developer",
    "Backend Developer",
    "MERN Full Stack Developer",
    "Salesforce Developer"
]
MAX_PER_ROLE = 8   # results per role

def google_search(query, num=8):
    if not (API_KEY and CX):
        raise RuntimeError("GCSE_API_KEY and GCSE_CX environment variables are required.")
    params = {"key": API_KEY, "cx": CX, "q": query, "num": min(num, 10)}
    resp = requests.get("https://www.googleapis.com/customsearch/v1", params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()

def extract_items(search_json):
    items = []
    for it in search_json.get("items", []):
        title = it.get("title")
        link = it.get("link")
        snippet = it.get("snippet", "")
        items.append({"title": title, "link": link, "snippet": snippet})
    return items

def build_html_report(results_by_role):
    now = datetime.now(timezone.utc).astimezone()
    header = f"<h2>Job search results — {now.strftime('%Y-%m-%d %H:%M %Z')}</h2>"
    body = header
    for role, items in results_by_role.items():
        body += f"<h3>{html.escape(role)} — {len(items)} results</h3>\n<ul>"
        if not items:
            body += "<li>No results found.</li>"
        for it in items:
            title = html.escape(it['title'] or it['link'])
            link = it['link']
            snippet = html.escape(it.get('snippet',''))
            body += f"<li><a href='{link}'>{title}</a><br/><small>{snippet}</small></li>"
        body += "</ul>"
    body += "<hr/><p>Generated automatically.</p>"
    return f"<html><body>{body}</body></html>"

def send_email(subject, html_body):
    if not (SMTP_PASS and SENDER and RECIPIENT):
        raise RuntimeError("SMTP and email environment variables required.")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    msg.attach(MIMEText(html_body, "html"))

    s = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
    try:
        s.ehlo()
        if SMTP_PORT == 587:
            s.starttls()
            s.ehlo()
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SENDER, [RECIPIENT], msg.as_string())
    finally:
        s.quit()

def main():
    if not (API_KEY and CX and RECIPIENT and SENDER and SMTP_PASS):
        raise SystemExit("Missing required environment variables. See script header.")
    results = {}
    for role in ROLES:
        queries = []
        if TOP_STARTUPS:
            for d in TOP_STARTUPS:
                if "." in d:
                    queries.append(f'{role} site:{d}')
                else:
                    queries.append(f'{role} "{d}"')
        queries.append(f'{role} startup hiring')
        queries.append(f'{role} "we are hiring"')
        queries.append(f'{role} "hiring now"')
        seen = {}
        collected = []
        for q in queries:
            try:
                js = google_search(q, num=MAX_PER_ROLE)
            except Exception as e:
                print("Search error for query:", q, e)
                continue
            items = extract_items(js)
            for it in items:
                key = it.get("link") or (it.get("title","") + it.get("snippet",""))
                if key in seen:
                    continue
                seen[key] = True
                collected.append(it)
                if len(collected) >= MAX_PER_ROLE:
                    break
            if len(collected) >= MAX_PER_ROLE:
                break
            time.sleep(0.4)
        results[role] = collected

    html_report = build_html_report(results)
    subject = f"Daily job digest — {datetime.now().strftime('%Y-%m-%d')}"
    send_email(subject, html_report)
    print("Sent email to", RECIPIENT)

if __name__ == "__main__":
    main()
