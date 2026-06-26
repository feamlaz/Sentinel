"""Alerts — send notifications when status changes."""

from typing import Optional

from .db import CheckResult, Target, STATUS_OK, STATUS_DOWN, STATUS_WARN
from .services import STATUS_EMOJI


class AlertManager:
    def __init__(self, telegram_token=None, telegram_chat=None):
        self.tg_token = telegram_token
        self.tg_chat = telegram_chat

    def send(self, target: Target, result: CheckResult, prev_status: str):
        """Send alert on status change."""
        if self.tg_token and self.tg_chat:
            self._send_telegram(target, result, prev_status)

    def send_trend(self, target: Target, trend: dict):
        """Send alert on trend degradation."""
        if self.tg_token and self.tg_chat:
            self._send_telegram_trend(target, trend)

    def _send_telegram(self, target: Target, result: CheckResult, prev_status: str):
        try:
            import httpx

            emoji = STATUS_EMOJI.get(result.status, "?")
            prev_emoji = STATUS_EMOJI.get(prev_status, "?")

            text = (
                "{emoji} <b>{name}</b> status changed\n"
                "{prev_emoji} {prev} \u2192 {emoji} {status}\n"
                "Type: {check_type}\n"
                "Message: {msg}"
            ).format(
                emoji=emoji,
                name=target.name,
                prev_emoji=prev_emoji,
                prev=prev_status.upper(),
                status=result.status.upper(),
                check_type=target.check_type,
                msg=result.message,
            )

            httpx.post(
                "https://api.telegram.org/bot{}/sendMessage".format(self.tg_token),
                json={
                    "chat_id": self.tg_chat,
                    "text": text,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
        except Exception:
            pass  # Silently fail — alerts shouldn't break monitoring

    def _send_telegram_trend(self, target: Target, trend: dict):
        try:
            import httpx
            level = trend.get("level", "unknown")
            msg = trend.get("message", "No details")
            text = (
                "\u26a0 <b>{name}</b> trend alert\n"
                "Level: <b>{level}</b>\n"
                "{msg}"
            ).format(name=target.name, level=level.upper(), msg=msg)

            httpx.post(
                "https://api.telegram.org/bot{}/sendMessage".format(self.tg_token),
                json={"chat_id": self.tg_chat, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )
        except Exception:
            pass
