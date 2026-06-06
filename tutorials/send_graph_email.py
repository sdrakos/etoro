#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Send the signals tutorial PDF via Microsoft Graph (client-credentials flow).
Creds from back/.env: CLIENT_ID, CLIENT_SECRET, TENANT_ID, USER_EMAIL (sender).
The PDF is base64-encoded inside Python (never leaves this process)."""
import os, base64, requests

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, "..", "back", ".env")
PDF = os.path.join(HERE, "signals_tutorial_GR.pdf")
TO = "stefanos.drakos@gmail.com"

env = {}
for line in open(ENV, encoding="utf-8"):
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

CID, CSEC, TEN, SENDER = env["CLIENT_ID"], env["CLIENT_SECRET"], env["TENANT_ID"], env["USER_EMAIL"]

tok = requests.post(
    f"https://login.microsoftonline.com/{TEN}/oauth2/v2.0/token",
    data={"client_id": CID, "client_secret": CSEC,
          "scope": "https://graph.microsoft.com/.default",
          "grant_type": "client_credentials"}, timeout=30)
if tok.status_code >= 400:
    print("TOKEN ERROR", tok.status_code, tok.text[:300]); raise SystemExit(1)
access = tok.json()["access_token"]

with open(PDF, "rb") as f:
    content = base64.b64encode(f.read()).decode()

body = ("Συνημμένο το φροντιστήριο αρχαρίων για τα σήματα μετοχών "
        "(IC, IR, Newey-West t, gate, συνδυασμός σημάτων με sqrt(N), risk parity), "
        "με αριθμητικά παραδείγματα από τα δικά μας PEAD runs (S&P 2015-2024).\n\n— QuantIQ / AGEL AI")
msg = {"message": {
        "subject": "Φροντιστήριο: Σήματα μετοχών (QuantIQ)",
        "body": {"contentType": "Text", "content": body},
        "toRecipients": [{"emailAddress": {"address": TO}}],
        "attachments": [{"@odata.type": "#microsoft.graph.fileAttachment",
                         "name": "signals_tutorial_GR.pdf",
                         "contentType": "application/pdf",
                         "contentBytes": content}]},
       "saveToSentItems": True}

r = requests.post(f"https://graph.microsoft.com/v1.0/users/{SENDER}/sendMail",
                  headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
                  json=msg, timeout=60)
if r.status_code in (200, 202):
    print(f"SENT -> {TO} (from {SENDER}, PDF {os.path.getsize(PDF)//1024} KB)")
else:
    print("SENDMAIL ERROR", r.status_code, r.text[:400])
