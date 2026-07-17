"""Gmail tools (scope: "gmail") over IMAP with an app password.

Deliberately draft-only: email_draft APPENDs to the Drafts folder, so
nothing ever leaves the account without the user pressing Send in Gmail.
All IMAP work is stdlib imaplib run in a thread; the pure helpers
(summaries, MIME construction) are separated for testability.
"""

import asyncio
import email
import email.policy
import imaplib
import json
import time
from email.message import EmailMessage

from jarvis.config import get_settings
from jarvis.core.registry import tool

IMAP_HOST = "imap.gmail.com"
DRAFTS = "[Gmail]/Drafts"
BODY_LIMIT = 4000


def _credentials() -> tuple[str, str]:
    s = get_settings()
    if not (s.gmail_address and s.gmail_app_password):
        raise RuntimeError("Gmail is not configured (GMAIL_ADDRESS / GMAIL_APP_PASSWORD)")
    return s.gmail_address, s.gmail_app_password


def _connect() -> imaplib.IMAP4_SSL:
    address, password = _credentials()
    conn = imaplib.IMAP4_SSL(IMAP_HOST)
    conn.login(address, password)
    return conn


# --- pure helpers (unit-tested without a network) ---


def summarize_headers(uid: str, raw_headers: bytes) -> dict:
    msg = email.message_from_bytes(raw_headers, policy=email.policy.default)
    return {
        "uid": uid,
        "from": str(msg.get("From", "")),
        "to": str(msg.get("To", "")),
        "subject": str(msg.get("Subject", "")),
        "date": str(msg.get("Date", "")),
    }


def extract_text_body(msg: email.message.Message) -> str:
    part = msg.get_body(preferencelist=("plain",)) if hasattr(msg, "get_body") else None
    if part is None:
        return "(no plain-text body)"
    return part.get_content().strip()[:BODY_LIMIT]


def build_draft_mime(
    from_addr: str,
    to: str,
    subject: str,
    body: str,
    orig_message_id: str = "",
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    if orig_message_id:
        msg["In-Reply-To"] = orig_message_id
        msg["References"] = orig_message_id
    msg.set_content(body)
    return msg


# --- sync IMAP operations (run in threads) ---


def _list_sync(unread_only: bool, limit: int) -> list[dict]:
    conn = _connect()
    try:
        conn.select("INBOX", readonly=True)
        _, data = conn.uid("search", None, "UNSEEN" if unread_only else "ALL")
        uids = data[0].split()[-limit:]
        summaries = []
        for uid in reversed(uids):  # newest first
            _, fetched = conn.uid(
                "fetch", uid, "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])"
            )
            if fetched and fetched[0]:
                summaries.append(summarize_headers(uid.decode(), fetched[0][1]))
        return summaries
    finally:
        conn.logout()


def _read_sync(uid: str) -> dict:
    conn = _connect()
    try:
        conn.select("INBOX", readonly=True)
        _, fetched = conn.uid("fetch", uid.encode(), "(BODY.PEEK[])")
        if not fetched or not fetched[0]:
            raise RuntimeError(f"no message with uid {uid}")
        msg = email.message_from_bytes(fetched[0][1], policy=email.policy.default)
        return {
            "uid": uid,
            "from": str(msg.get("From", "")),
            "to": str(msg.get("To", "")),
            "subject": str(msg.get("Subject", "")),
            "date": str(msg.get("Date", "")),
            "message_id": str(msg.get("Message-ID", "")),
            "body": extract_text_body(msg),
        }
    finally:
        conn.logout()


def _draft_sync(to: str, subject: str, body: str, reply_to_uid: str) -> str:
    address, _ = _credentials()
    orig_message_id = ""
    if reply_to_uid:
        original = _read_sync(reply_to_uid)
        orig_message_id = original["message_id"]
        if not subject:
            subject = f"Re: {original['subject'].removeprefix('Re: ')}"
    mime = build_draft_mime(address, to, subject, body, orig_message_id)
    conn = _connect()
    try:
        conn.append(DRAFTS, "", imaplib.Time2Internaldate(time.time()), mime.as_bytes())
    finally:
        conn.logout()
    return f"draft saved to Gmail Drafts (to={to}, subject={subject!r})"


# --- tools ---


@tool(scopes=("gmail",))
async def email_list(unread_only: bool = True, limit: int = 20) -> str:
    """List recent inbox emails (newest first) as JSON: uid, from, to, subject, date."""
    return json.dumps(await asyncio.to_thread(_list_sync, unread_only, limit), ensure_ascii=False)


@tool(scopes=("gmail",))
async def email_read(uid: str) -> str:
    """Read one email in full (headers + plain-text body) by its uid from email_list."""
    return json.dumps(await asyncio.to_thread(_read_sync, uid), ensure_ascii=False)


@tool(scopes=("gmail",))
async def email_draft(to: str, subject: str, body: str, reply_to_uid: str = "") -> str:
    """Save a draft reply/email into Gmail Drafts. NEVER sends. Pass reply_to_uid
    to thread the draft as a reply to an existing message (subject may then be
    left empty to reuse the original's)."""
    return await asyncio.to_thread(_draft_sync, to, subject, body, reply_to_uid)
