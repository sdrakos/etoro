#!/usr/bin/env python3
"""
Outlook Email Digest - Automated Email Summarization
Reads emails from Outlook, creates AI summary, sends via Gmail
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import msal
    import requests
    from openai import OpenAI
    import schedule
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("\nInstall required packages:")
    print("pip install msal requests openai schedule python-dotenv")
    sys.exit(1)

# ============================================
# CONFIGURATION (reads from .env)
# ============================================

# Load .env — search upward for proactive/.env
_env_loaded = False
_d = Path(__file__).resolve().parent
for _ in range(8):
    _d = _d.parent
    _candidate = _d / "proactive" / ".env"
    if _candidate.exists():
        load_dotenv(_candidate)
        _env_loaded = True
        break
if not _env_loaded:
    load_dotenv()

# Outlook/Azure AD Configuration
CLIENT_ID = os.getenv("OUTLOOK_CLIENT_ID", "9a5606f8-b532-493c-aa37-3a4ec11378b1")
CLIENT_SECRET = os.getenv("OUTLOOK_CLIENT_SECRET", "REDACTED_OUTLOOK_CLIENT_SECRET")
TENANT_ID = os.getenv("OUTLOOK_TENANT_ID", "661ad5b1-4b06-4c63-9bc0-70019b3bee46")
USER_EMAIL = os.getenv("OUTLOOK_USER_EMAIL", "sdrakos@agel.ai")

# Gmail Configuration
GMAIL_SENDER = os.getenv("GMAIL_SENDER", "stefanos.drakos@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
GMAIL_RECIPIENT = os.getenv("GMAIL_RECIPIENT", "stefanos.drakos@gmail.com")

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Schedule Configuration
SCHEDULE_TIME = "08:00"  # Run daily at 8:00 AM

# Microsoft Graph API endpoints
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"

# ============================================
# OUTLOOK AUTHENTICATION
# ============================================

def get_access_token():
    """Get access token using client credentials flow"""
    print("🔐 Authenticating with Microsoft Graph API...")

    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET,
    )

    result = app.acquire_token_for_client(scopes=SCOPES)

    if "access_token" in result:
        print("✅ Authentication successful")
        return result["access_token"]
    else:
        error = result.get("error_description", result.get("error"))
        print(f"❌ Authentication failed: {error}")
        raise Exception(f"Could not authenticate: {error}")

# ============================================
# EMAIL FETCHING
# ============================================

def fetch_emails(access_token, hours_ago=24):
    """Fetch emails from Outlook from the last N hours"""
    print(f"📧 Fetching emails from last {hours_ago} hours...")

    # Calculate time threshold
    time_threshold = (datetime.utcnow() - timedelta(hours=hours_ago)).isoformat() + "Z"

    # Build Graph API query
    endpoint = f"{GRAPH_API_ENDPOINT}/users/{USER_EMAIL}/messages"

    params = {
        "$filter": f"receivedDateTime ge {time_threshold}",
        "$select": "subject,from,receivedDateTime,bodyPreview,importance,isRead",
        "$orderby": "receivedDateTime desc",
        "$top": 50  # Limit to 50 emails
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    response = requests.get(endpoint, headers=headers, params=params)

    if response.status_code == 200:
        emails = response.json().get("value", [])
        print(f"✅ Found {len(emails)} emails")
        return emails
    else:
        print(f"❌ Failed to fetch emails: {response.status_code}")
        print(response.text)
        return []

# ============================================
# AI SUMMARIZATION
# ============================================

def summarize_emails(emails):
    """Use OpenAI to create a smart email digest"""
    if not emails:
        return "Δεν υπάρχουν νέα emails."

    if not OPENAI_API_KEY:
        print("⚠️  OpenAI API key not set. Using basic summary.")
        return create_basic_summary(emails)

    print("🤖 Creating AI-powered summary...")

    # Prepare email data for AI
    email_data = []
    for email in emails:
        email_data.append({
            "from": email["from"]["emailAddress"]["name"],
            "email": email["from"]["emailAddress"]["address"],
            "subject": email["subject"],
            "preview": email["bodyPreview"][:200],
            "time": email["receivedDateTime"],
            "importance": email.get("importance", "normal"),
            "isRead": email.get("isRead", False)
        })

    # Create prompt for OpenAI
    prompt = f"""Είσαι έξυπνος email assistant. Ανάλυσε τα παρακάτω {len(email_data)} emails και δημιούργησε μια σύντομη, καλά δομημένη περίληψη στα Ελληνικά.

Κατηγοριοποίησε τα emails σε:
- 🔴 ΕΠΕΙΓΟΝ (urgent/important)
- 🟡 ΣΗΜΑΝΤΙΚΑ (important but not urgent)
- 🟢 FYI (informational)

Για κάθε κατηγορία:
- Γράψε τον αποστολέα και το θέμα
- Μια σύντομη περίληψη 1-2 προτάσεων
- Προτεινόμενη ενέργεια (αν χρειάζεται)

Email Data:
{json.dumps(email_data, indent=2, ensure_ascii=False)}

Κράτα την περίληψη σύντομη (max 500 λέξεις) και εύκολη στην ανάγνωση."""

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Είσαι έξυπνος email assistant που δημιουργεί σύντομες, χρήσιμες περιλήψεις."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )

        summary = response.choices[0].message.content
        print("✅ AI summary created")
        return summary

    except Exception as e:
        print(f"⚠️  OpenAI error: {e}")
        print("Falling back to basic summary...")
        return create_basic_summary(emails)

def create_basic_summary(emails):
    """Create a simple summary without AI"""
    lines = [f"📧 **Περίληψη {len(emails)} Emails**\n"]

    for i, email in enumerate(emails[:10], 1):  # Limit to 10
        sender = email["from"]["emailAddress"]["name"]
        subject = email["subject"]
        preview = email["bodyPreview"][:100]
        lines.append(f"{i}. **{sender}**: {subject}\n   {preview}...\n")

    if len(emails) > 10:
        lines.append(f"\n... και {len(emails) - 10} ακόμα emails")

    return "\n".join(lines)

# ============================================
# EMAIL SENDING
# ============================================

def send_gmail(subject, body_html):
    """Send digest via Gmail SMTP"""
    print("📤 Sending digest via Gmail...")

    if not GMAIL_APP_PASSWORD:
        print("❌ Gmail App Password not set!")
        print("Please set GMAIL_APP_PASSWORD environment variable")
        print("Get it from: https://myaccount.google.com/apppasswords")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = GMAIL_SENDER
        msg["To"] = GMAIL_RECIPIENT
        msg["Subject"] = subject

        # Create HTML email
        html_part = MIMEText(body_html, "html", "utf-8")
        msg.attach(html_part)

        # Send via Gmail SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            server.send_message(msg)

        print(f"✅ Email sent to {GMAIL_RECIPIENT}")
        return True

    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False

def format_html_email(summary, email_count):
    """Format summary as nice HTML email"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 10px 10px 0 0;
                text-align: center;
            }}
            .content {{
                background: #f9f9f9;
                padding: 20px;
                border-radius: 0 0 10px 10px;
                border: 1px solid #e0e0e0;
            }}
            .footer {{
                text-align: center;
                color: #999;
                font-size: 12px;
                margin-top: 20px;
            }}
            h1 {{
                margin: 0;
                font-size: 24px;
            }}
            .summary {{
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin-top: 10px;
                white-space: pre-wrap;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📧 Outlook Email Digest</h1>
            <p>{datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        </div>
        <div class="content">
            <p><strong>Βρέθηκαν {email_count} emails από χθες</strong></p>
            <div class="summary">
{summary}
            </div>
        </div>
        <div class="footer">
            <p>Αυτόματη περίληψη από το Outlook Email Digest System</p>
            <p>Powered by Claude Agent SDK + OpenAI</p>
        </div>
    </body>
    </html>
    """
    return html

# ============================================
# MAIN LOGIC
# ============================================

def run_digest():
    """Main function to run the email digest"""
    print("\n" + "="*50)
    print(f"🚀 Starting Email Digest - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)

    try:
        # 1. Authenticate
        token = get_access_token()

        # 2. Fetch emails
        emails = fetch_emails(token, hours_ago=24)

        # 3. Create summary
        summary = summarize_emails(emails)

        # 4. Format as HTML
        html_body = format_html_email(summary, len(emails))
        subject = f"📧 Outlook Digest - {len(emails)} emails ({datetime.now().strftime('%d/%m/%Y')})"

        # 5. Send email
        success = send_gmail(subject, html_body)

        if success:
            print("\n✅ Digest completed successfully!")
        else:
            print("\n⚠️  Digest created but email sending failed")

        # Save summary to file as backup
        backup_file = f"digest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        with open(backup_file, "w", encoding="utf-8") as f:
            f.write(html_body)
        print(f"💾 Backup saved to: {backup_file}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

# ============================================
# CLI
# ============================================

def main():
    parser = argparse.ArgumentParser(description="Outlook Email Digest Automation")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--schedule", action="store_true", help="Run on daily schedule")
    parser.add_argument("--time", type=str, default=SCHEDULE_TIME, help="Schedule time (HH:MM)")

    args = parser.parse_args()

    if args.schedule:
        schedule_time = args.time
        schedule_daily_at(schedule_time)
    else:
        # Run once (default)
        run_digest()

def schedule_daily_at(schedule_time):
    """Schedule the digest to run daily at specified time"""
    print(f"⏰ Scheduling daily digest at {schedule_time}")
    schedule.every().day.at(schedule_time).do(run_digest)

    print(f"✅ Scheduler started. Waiting for {schedule_time}...")
    print("Press Ctrl+C to stop")

    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()