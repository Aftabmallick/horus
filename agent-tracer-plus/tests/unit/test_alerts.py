from agent_tracer_plus.alerts.channels import AlertChannel
from agent_tracer_plus.alerts.rules import AlertEngine, AlertRule


class MockChannel(AlertChannel):
    def __init__(self):
        self.messages = []
    def send(self, title, message):
        self.messages.append(message)

def test_alert_rule_debouncing():
    channel = MockChannel()
    rule = AlertRule(
        condition=lambda s: s.get("error_rate", 0) > 0.1,
        channels=[channel],
        message_template="Error rate is {error_rate}",
        cooldown_seconds=10
    )

    engine = AlertEngine()
    engine.add_rule(rule)

    # Fire first time
    engine.evaluate({"error_rate": 0.2})
    assert len(channel.messages) == 1

    # Fire second time immediately (should be debounced)
    engine.evaluate({"error_rate": 0.2})
    assert len(channel.messages) == 1

    # Simulate time passing
    rule.last_fired -= 15

    # Fire again after cooldown
    engine.evaluate({"error_rate": 0.2})
    assert len(channel.messages) == 2
