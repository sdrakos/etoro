---
name: google
description: Manage Google Workspace — Gmail, Calendar, Sheets, YouTube, Drive, Google Ads. Use when user asks about email, calendar events, spreadsheets, YouTube, file management, or ad campaigns via Google services.
---

# Google Workspace Skill

Unified access to all Google APIs via MCP server `mcp__google__*` tools + `mcp__google-ads__*` for ads.

## Available Tools

### Gmail (mcp__google__gmail_*)
- `gmail_search` — Search emails: `query="is:unread"`, `query="from:user@example.com subject:invoice"`
- `gmail_read` — Read full email by message ID
- `gmail_send` — Send email: `to`, `subject`, `body`, optional `cc`, `bcc`, `html=true`
- `gmail_reply` — Reply to thread: `thread_id`, `body`, `reply_all=true`
- `gmail_labels` — List labels with unread counts

### Calendar (mcp__google__calendar_*)
- `calendar_list_events` — List events: `date_from="2026-03-25"`, `date_to="2026-03-31"`
- `calendar_create_event` — Create: `title`, `start="2026-03-26T10:00:00"`, `end`, `attendees="a@b.com,c@d.com"`
- `calendar_update_event` — Update by event ID
- `calendar_delete_event` — Delete by event ID

### Sheets (mcp__google__sheets_*)
- `sheets_read` — Read: `spreadsheet_id`, `range="Sheet1!A1:D10"`
- `sheets_write` — Write: `values='[["A","B"],["1","2"]]'`
- `sheets_create` — Create new: `title`, `sheet_names="Sheet1,Sheet2"`

### YouTube (mcp__google__youtube_*)
- `youtube_search` — Search videos: `query`, `max_results`
- `youtube_channel_stats` — Channel info: subscribers, views, videos
- `youtube_video_stats` — Video info: views, likes, comments, duration

### Drive (mcp__google__drive_*)
- `drive_list` — List files: `query='name contains "report"'`, `folder_id`
- `drive_upload` — Upload local file
- `drive_download` — Download to local path

### Google Ads (mcp__google-ads__*)
- `list_campaigns`, `get_campaign_metrics`, `list_keywords`
- `update_budget`, `pause_campaign`, `add_keywords`, `add_negative_keywords`
- `daily_performance_report` — Excel + email

## Usage Patterns

### Email workflows
```
1. gmail_search query="is:unread" → get message IDs
2. gmail_read message_id="..." → read content
3. gmail_reply thread_id="..." body="..." → reply
```

### Calendar scheduling
```
1. calendar_list_events date_from="2026-03-25" → check availability
2. calendar_create_event title="Meeting" start="2026-03-26T14:00:00" end="..." attendees="..."
```

### Data to Sheets
```
1. sheets_create title="Report Q1" → get spreadsheet_id
2. sheets_write spreadsheet_id="..." range="A1" values='[["Month","Revenue"],["Jan","5000"]]'
```

## Credentials
All tools use the same OAuth2 token from config.yaml (`google_ads_refresh_token`).
Scopes: adwords, gmail.modify, gmail.send, calendar, youtube, spreadsheets, drive.file.
