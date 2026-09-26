import json
from unittest.mock import patch

from app.notifiers import (
    CHANNELS,
    AlertEvent,
    deliver_pagerduty,
    deliver_slack,
    deliver_whatsapp,
    enabled_channels,
    hmac_signature,
    https_url,
    webhook_payload,
)
from app.settings_store import MASKED_SECRET, redact_settings


def _event(**kwargs):
    data = dict(
        kind="down",
        subject="Pingwatch: edge-nas is down",
        body="CI edge-nas (10.0.0.8) is down.",
        device_id=12,
        device_name="edge-nas",
        device_host="10.0.0.8",
        monitor_type="ping",
        incident_number="INC00012",
        priority="P2",
        occurred_at="2026-09-25T12:00:00Z",
    )
    data.update(kwargs)
    return AlertEvent(**data)


def test_https_url_rejects_insecure_and_empty():
    assert https_url("https://hooks.slack.com/services/T/B/x")
    assert not https_url("http://hooks.slack.com/services/T/B/x")
    assert not https_url("javascript:alert(1)")
    assert not https_url("")


def test_webhook_payload_is_stable():
    payload = webhook_payload(_event())
    assert payload["source"] == "pingwatch"
    assert payload["event"] == "down"
    assert payload["device"]["name"] == "edge-nas"
    assert payload["incident"]["number"] == "INC00012"


def test_hmac_signature_matches_sha256_header():
    body = json.dumps({"ok": True}, ensure_ascii=True).encode("utf-8")
    assert hmac_signature("s3cret", body).startswith("sha256=")
    assert hmac_signature("s3cret", body) != hmac_signature("other", body)


def test_pagerduty_triggers_on_down_and_resolves_on_recovery():
    config = {"notify_pagerduty_routing_key": "R0UTING"}
    captured = []

    def fake_post(url, payload, extra_headers=None, timeout=8):
        captured.append((url, payload))
        return "ok"

    with patch("app.notifiers.post_json", side_effect=fake_post):
        assert deliver_pagerduty(config, _event()) == "ok"
        assert deliver_pagerduty(config, _event(kind="recovered", subject="recovered")) == "ok"
    assert captured[0][1]["event_action"] == "trigger"
    assert captured[1][1]["event_action"] == "resolve"
    assert captured[0][1]["dedup_key"] == captured[1][1]["dedup_key"]


def test_slack_requires_https_webhook():
    assert deliver_slack({"notify_slack_webhook": "http://example.com"}, _event()).startswith("Slack")


def test_enabled_channels_follow_toggles():
    config = {
        "notify_teams_enabled": "true",
        "notify_slack_enabled": "false",
        "notify_webhook_enabled": "true",
        "notify_pagerduty_enabled": "0",
        "notify_discord_enabled": "yes",
        "notify_telegram_enabled": "true",
    }
    assert enabled_channels(config) == ("teams", "webhook", "discord", "telegram")
    assert set(CHANNELS) == {"teams", "slack", "webhook", "pagerduty", "discord", "telegram", "whatsapp"}


def test_whatsapp_sends_template_to_e164_digits():
    captured = []

    def fake_post(url, payload, extra_headers=None, timeout=8):
        captured.append((url, payload, extra_headers))
        return "ok"

    with patch("app.notifiers.post_json", side_effect=fake_post):
        assert (
            deliver_whatsapp(
                {
                    "notify_whatsapp_token": "tok",
                    "notify_whatsapp_phone_id": "123456",
                    "notify_whatsapp_to": "+1 (555) 123-4567",
                    "notify_whatsapp_template": "pingwatch_alert",
                    "notify_whatsapp_template_lang": "en_US",
                },
                _event(),
            )
            == "ok"
        )
    assert captured[0][0].endswith("/123456/messages")
    assert captured[0][1]["to"] == "15551234567"
    assert captured[0][1]["type"] == "template"
    assert captured[0][1]["template"]["name"] == "pingwatch_alert"
    assert captured[0][2]["Authorization"] == "Bearer tok"


def test_whatsapp_requires_token():
    assert "token" in deliver_whatsapp({}, _event()).lower()


def test_redact_settings_masks_channel_secrets():
    raw = {
        "notify_slack_webhook": "https://hooks.slack.com/services/secret",
        "notify_telegram_chat_id": "-1001",
        "notify_email": "ops@company.com",
    }
    out = redact_settings(raw)
    assert out["notify_slack_webhook"] == MASKED_SECRET
    assert out["notify_telegram_chat_id"] == "-1001"
    assert out["notify_email"] == "ops@company.com"
