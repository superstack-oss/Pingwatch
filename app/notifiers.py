from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

log = logging.getLogger("pingwatch.notify")

CHANNELS = ("teams", "slack", "webhook", "pagerduty", "discord", "telegram", "whatsapp")
PAGERDUTY_URL = "https://events.pagerduty.com/v2/enqueue"
WHATSAPP_API = "https://graph.facebook.com/v21.0/%s/messages"
USER_AGENT = "Pingwatch/1.2.0"

COLOR_DOWN = "D83A52"
COLOR_UP = "2DA44E"


@dataclass
class AlertEvent:
    kind: str
    subject: str
    body: str
    device_id: Optional[int] = None
    device_name: str = ""
    device_host: str = ""
    monitor_type: str = ""
    incident_number: str = ""
    priority: str = ""
    occurred_at: str = field(default_factory=lambda: datetime.utcnow().replace(microsecond=0).isoformat() + "Z")

    @property
    def is_down(self) -> bool:
        return self.kind != "recovered"


def _flag(config: Dict[str, str], key: str) -> bool:
    return str(config.get(key) or "").lower() in {"1", "true", "yes", "on"}


def _secret(config: Dict[str, str], key: str) -> str:
    return (config.get(key) or "").strip()


def https_url(value: str) -> bool:
    parsed = urlparse((value or "").strip())
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password


def http_url(value: str) -> bool:
    parsed = urlparse((value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and not parsed.username and not parsed.password


def webhook_payload(event: AlertEvent) -> Dict[str, Any]:
    return {
        "source": "pingwatch",
        "event": event.kind,
        "subject": event.subject,
        "message": event.body,
        "occurred_at": event.occurred_at,
        "device": {
            "id": event.device_id,
            "name": event.device_name,
            "host": event.device_host,
            "monitor_type": event.monitor_type or None,
        },
        "incident": {
            "number": event.incident_number or None,
            "priority": event.priority or None,
        },
    }


def hmac_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return "sha256=" + digest


def post_json(url: str, payload: Dict[str, Any], extra_headers: Optional[Dict[str, str]] = None, timeout: int = 8) -> str:
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        "Content-Length": str(len(body)),
    }
    if extra_headers:
        headers.update(extra_headers)
    req = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as response:
            response.read()
            status = getattr(response, "status", 200) or 200
            if status >= 400:
                return "HTTP %s" % status
        return "ok"
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:400]
            parsed = json.loads(detail)
            message = ((parsed.get("error") or {}).get("message") if isinstance(parsed, dict) else None)
            if message:
                return str(message)
        except Exception:
            pass
        return "HTTP %s" % exc.code
    except URLError as exc:
        return str(exc.reason or exc)
    except Exception as exc:
        return str(exc)


def _dedup_key(event: AlertEvent) -> str:
    if event.device_id:
        return "pingwatch-device-%s" % event.device_id
    if event.device_host:
        return "pingwatch-host-%s" % event.device_host.lower()
    return "pingwatch-test"


def deliver_teams(config: Dict[str, str], event: AlertEvent) -> str:
    url = _secret(config, "notify_teams_webhook")
    if not https_url(url):
        return "Microsoft Teams webhook URL is required (https)"
    payload = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "themeColor": COLOR_DOWN if event.is_down else COLOR_UP,
        "summary": event.subject,
        "title": event.subject,
        "text": event.body,
    }
    return post_json(url, payload)


def deliver_slack(config: Dict[str, str], event: AlertEvent) -> str:
    url = _secret(config, "notify_slack_webhook")
    if not https_url(url):
        return "Slack webhook URL is required (https)"
    payload = {
        "text": event.subject,
        "attachments": [
            {
                "color": "danger" if event.is_down else "good",
                "text": event.body,
                "mrkdwn_in": ["text"],
            }
        ],
    }
    return post_json(url, payload)


def deliver_webhook(config: Dict[str, str], event: AlertEvent) -> str:
    url = _secret(config, "notify_webhook_url")
    if not http_url(url):
        return "Webhook URL is required"
    payload = webhook_payload(event)
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    headers = {}
    secret = _secret(config, "notify_webhook_secret")
    if secret:
        headers["X-Pingwatch-Signature"] = hmac_signature(secret, body)
    return post_json(url, payload, headers)


def deliver_pagerduty(config: Dict[str, str], event: AlertEvent) -> str:
    key = _secret(config, "notify_pagerduty_routing_key")
    if not key:
        return "PagerDuty routing key is required"
    severity = "critical" if event.is_down else "info"
    action = "trigger" if event.is_down else "resolve"
    payload = {
        "routing_key": key,
        "event_action": action,
        "dedup_key": _dedup_key(event),
        "payload": {
            "summary": event.subject[:1024],
            "source": event.device_host or event.device_name or "pingwatch",
            "severity": severity,
            "component": event.device_name or "monitor",
            "group": event.monitor_type or "pingwatch",
            "class": event.kind,
            "custom_details": {
                "message": event.body,
                "host": event.device_host,
                "incident": event.incident_number,
                "priority": event.priority,
            },
        },
    }
    return post_json(PAGERDUTY_URL, payload)


def deliver_discord(config: Dict[str, str], event: AlertEvent) -> str:
    url = _secret(config, "notify_discord_webhook")
    if not https_url(url):
        return "Discord webhook URL is required (https)"
    color = int(COLOR_DOWN, 16) if event.is_down else int(COLOR_UP, 16)
    payload = {
        "username": "Pingwatch",
        "embeds": [
            {
                "title": event.subject[:256],
                "description": (event.body or "")[:4000],
                "color": color,
            }
        ],
    }
    return post_json(url, payload)


def deliver_telegram(config: Dict[str, str], event: AlertEvent) -> str:
    token = _secret(config, "notify_telegram_bot_token")
    chat_id = _secret(config, "notify_telegram_chat_id")
    if not token or ":" not in token:
        return "Telegram bot token is required"
    if not chat_id:
        return "Telegram chat ID is required"
    url = "https://api.telegram.org/bot%s/sendMessage" % token
    text = "%s\n\n%s" % (event.subject, event.body)
    payload = {
        "chat_id": chat_id,
        "text": text[:4000],
        "disable_web_page_preview": True,
    }
    result = post_json(url, payload)
    if result != "ok" and token in result:
        return result.replace(token, "…")
    return result


def _digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def deliver_whatsapp(config: Dict[str, str], event: AlertEvent) -> str:
    token = _secret(config, "notify_whatsapp_token")
    phone_id = _secret(config, "notify_whatsapp_phone_id")
    to = _digits(_secret(config, "notify_whatsapp_to"))
    if not token:
        return "WhatsApp access token is required"
    if not phone_id:
        return "WhatsApp phone number ID is required"
    if not to:
        return "WhatsApp recipient number is required"
    template = _secret(config, "notify_whatsapp_template")
    lang = _secret(config, "notify_whatsapp_template_lang") or "en_US"
    text = ("%s\n\n%s" % (event.subject, event.body))[:4096]
    if template:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template,
                "language": {"code": lang},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": (event.subject or "Pingwatch")[:1024]},
                            {"type": "text", "text": (event.body or "-")[:1024]},
                        ],
                    }
                ],
            },
        }
    else:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text, "preview_url": False},
        }
    result = post_json(
        WHATSAPP_API % phone_id,
        payload,
        {"Authorization": "Bearer %s" % token},
    )
    if token in result:
        return result.replace(token, "…")
    return result


DELIVER = {
    "teams": deliver_teams,
    "slack": deliver_slack,
    "webhook": deliver_webhook,
    "pagerduty": deliver_pagerduty,
    "discord": deliver_discord,
    "telegram": deliver_telegram,
    "whatsapp": deliver_whatsapp,
}


def send_channel(name: str, config: Dict[str, str], event: AlertEvent) -> str:
    handler = DELIVER.get(name)
    if handler is None:
        return "Unknown channel"
    return handler(config, event)


def enabled_channels(config: Dict[str, str]) -> tuple:
    return tuple(name for name in CHANNELS if _flag(config, "notify_%s_enabled" % name))


async def dispatch_alert(config: Dict[str, str], event: AlertEvent) -> Dict[str, str]:
    names = enabled_channels(config)
    if not names:
        return {}

    async def _run(name: str) -> tuple:
        try:
            result = await asyncio.to_thread(send_channel, name, config, event)
        except Exception as exc:
            result = str(exc)
        if result != "ok":
            log.warning("Alert channel %s failed: %s", name, result)
        return name, result

    pairs = await asyncio.gather(*[_run(name) for name in names])
    return {name: result for name, result in pairs}


async def test_channel(name: str, config: Dict[str, str]) -> str:
    if name not in DELIVER:
        return "Unknown channel"
    event = AlertEvent(
        kind="test",
        subject="Pingwatch test notification",
        body="This is a test from Pingwatch. If you received it, this channel is configured correctly.",
        device_name="Pingwatch",
        device_host="test",
        monitor_type="ping",
    )
    return await asyncio.to_thread(send_channel, name, config, event)
