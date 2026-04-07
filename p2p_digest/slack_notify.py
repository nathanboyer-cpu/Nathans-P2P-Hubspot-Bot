from __future__ import annotations

import httpx

from p2p_digest.config import Settings

SLACK_API = "https://slack.com/api"


def post_slack_webhook(webhook_url: str, text: str) -> None:
    payload = {"text": text}
    with httpx.Client(timeout=30.0) as client:
        r = client.post(webhook_url, json=payload)
        r.raise_for_status()


def _chunk_mrkdwn(text: str, max_len: int = 2900) -> list[str]:
    """Split long text into chunks under Slack mrkdwn section limits."""
    text = text.strip()
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_len, len(text))
        if end < len(text):
            break_at = text.rfind("\n", start, end)
            if break_at <= start:
                break_at = end
            end = break_at
        chunks.append(text[start:end].strip())
        start = end
    return [c for c in chunks if c]


SLACK_MAX_BLOCKS_PER_MESSAGE = 50


def post_slack_chat_api(bot_token: str, channel_id: str, text: str) -> None:
    """Post a mrkdwn message via chat.postMessage (Bot User OAuth token xoxb-...)."""
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    chunks = _chunk_mrkdwn(text)
    with httpx.Client(timeout=120.0) as client:
        for start in range(0, len(chunks), SLACK_MAX_BLOCKS_PER_MESSAGE):
            batch = chunks[start : start + SLACK_MAX_BLOCKS_PER_MESSAGE]
            if start > 0:
                batch = [
                    f"_…continued ({start // SLACK_MAX_BLOCKS_PER_MESSAGE + 1})…_\n\n{batch[0]}"
                ] + batch[1:]
            blocks: list[dict] = []
            for part in batch:
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": part}})
            preview = text[:3000] if start == 0 else f"(continued) {batch[0][:2900]}"
            body = {"channel": channel_id, "text": preview, "blocks": blocks}
            r = client.post(f"{SLACK_API}/chat.postMessage", headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
            if not data.get("ok"):
                raise RuntimeError(
                    f"Slack API error: {data.get('error', 'unknown')} (needed scopes often: chat:write)"
                )


def post_slack(settings: Settings, text: str) -> None:
    """Send using webhook, or bot token + channel (and optional second channel)."""
    if settings.slack_bot_token and settings.slack_channel_id:
        post_slack_chat_api(settings.slack_bot_token, settings.slack_channel_id, text)
        if settings.slack_dm_channel_id:
            post_slack_chat_api(settings.slack_bot_token, settings.slack_dm_channel_id, text)
        return
    if settings.slack_webhook_url:
        post_slack_webhook(settings.slack_webhook_url, text)
        return
    raise ValueError(
        "Configure either SLACK_WEBHOOK_URL or SLACK_BOT_TOKEN + SLACK_CHANNEL_ID."
    )
