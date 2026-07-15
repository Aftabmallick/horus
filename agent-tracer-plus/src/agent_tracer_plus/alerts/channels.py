"""Alerting channels (Async implementations)."""

import json
import logging
import urllib.request
import urllib.error
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any

logger = logging.getLogger(__name__)


class AlertChannel(ABC):
    """Base class for alert delivery channels."""

    @abstractmethod
    async def send(self, subject: str, message: str, trace_data: Dict[str, Any] = None) -> None:
        """Send an alert asynchronously."""
        pass


class WebhookChannel(AlertChannel):
    """Sends alerts to a generic webhook asynchronously."""
    def __init__(self, url: str):
        self.url = url

    async def send(self, subject: str, message: str, trace_data: Dict[str, Any] = None) -> None:
        payload = {"subject": subject, "message": message, "trace": trace_data or {}}
        
        def _post():
            req = urllib.request.Request(
                self.url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            try:
                urllib.request.urlopen(req, timeout=5.0)
            except Exception as e:
                logger.error(f"Failed to send webhook alert: {e}")
                
        await asyncio.to_thread(_post)


class SlackChannel(AlertChannel):
    """Sends alerts to a Slack Incoming Webhook asynchronously."""
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, subject: str, message: str, trace_data: Dict[str, Any] = None) -> None:
        trace_id = trace_data.get('trace_id') if trace_data else 'unknown'
        payload = {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": subject}},
                {"type": "section", "text": {"type": "mrkdwn", "text": message}},
                {"type": "context", "elements": [{"type": "mrkdwn", "text": f"*Trace ID:* `{trace_id}`"}]}
            ]
        }
        
        def _post():
            req = urllib.request.Request(
                self.webhook_url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            try:
                urllib.request.urlopen(req, timeout=5.0)
            except Exception as e:
                logger.error(f"Failed to send Slack alert: {e}")
                
        await asyncio.to_thread(_post)


class PagerDutyChannel(AlertChannel):
    """Triggers an incident in PagerDuty via the Events API v2 asynchronously."""
    def __init__(self, routing_key: str):
        self.routing_key = routing_key
        self.url = "https://events.pagerduty.com/v2/enqueue"

    async def send(self, subject: str, message: str, trace_data: Dict[str, Any] = None) -> None:
        trace_id = trace_data.get('trace_id') if trace_data else 'unknown'
        payload = {
            "routing_key": self.routing_key,
            "event_action": "trigger",
            "payload": {
                "summary": subject,
                "source": "Agent Tracer Plus",
                "severity": "critical",
                "custom_details": {
                    "message": message,
                    "trace_id": trace_id,
                    "trace_data": trace_data or {}
                }
            }
        }

        def _post():
            req = urllib.request.Request(
                self.url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            try:
                urllib.request.urlopen(req, timeout=5.0)
            except Exception as e:
                logger.error(f"Failed to send PagerDuty alert: {e}")

        await asyncio.to_thread(_post)
