"""Auto-instrumentation for Kafka clients."""

import logging
from typing import Any

from agent_tracer_plus import current_trace
from agent_tracer_plus.core.tracer import AgentTracerPlus

logger = logging.getLogger(__name__)


def instrument(tracer: AgentTracerPlus) -> None:
    """Instrument aiokafka and confluent_kafka."""
    _instrument_aiokafka(tracer)
    _instrument_confluent_kafka(tracer)


def _instrument_aiokafka(tracer: AgentTracerPlus) -> None:
    try:
        from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
    except ImportError:
        logger.debug("aiokafka not found, skipping.")
        return

    original_send = AIOKafkaProducer.send

    async def wrapped_send(self, topic, value=None, key=None, partition=None, timestamp_ms=None, headers=None):
        trace = current_trace()
        with trace.span("aiokafka.send", span_type="EXTERNAL") as span:
            span.set_attribute("messaging.system", "kafka")
            span.set_attribute("messaging.destination", str(topic))
            if key:
                span.set_attribute("messaging.kafka.message_key", str(key))
            if partition is not None:
                span.set_attribute("messaging.kafka.partition", partition)
                
            try:
                if hasattr(value, "decode"):
                    span.input = value.decode("utf-8", errors="replace")
                else:
                    span.input = str(value)
            except Exception:
                span.input = "<binary payload>"
                
            try:
                res = await original_send(self, topic, value=value, key=key, partition=partition, timestamp_ms=timestamp_ms, headers=headers)
                return res
            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                raise

    AIOKafkaProducer.send = wrapped_send
    
    # Wrap consumer getmany
    original_getmany = AIOKafkaConsumer.getmany
    
    async def wrapped_getmany(self, *partitions, timeout_ms=0):
        trace = current_trace()
        with trace.span("aiokafka.consume", span_type="EXTERNAL") as span:
            span.set_attribute("messaging.system", "kafka")
            span.set_attribute("messaging.operation", "receive")
            try:
                res = await original_getmany(self, *partitions, timeout_ms=timeout_ms)
                msg_count = sum(len(msgs) for msgs in res.values())
                span.set_attribute("messaging.message_count", msg_count)
                return res
            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                raise

    AIOKafkaConsumer.getmany = wrapped_getmany


def _instrument_confluent_kafka(tracer: AgentTracerPlus) -> None:
    try:
        from confluent_kafka import Producer, Consumer
    except ImportError:
        logger.debug("confluent_kafka not found, skipping.")
        return

    original_produce = Producer.produce

    def wrapped_produce(self, topic, value=None, key=None, **kwargs):
        trace = current_trace()
        with trace.span("confluent_kafka.produce", span_type="EXTERNAL") as span:
            span.set_attribute("messaging.system", "kafka")
            span.set_attribute("messaging.destination", str(topic))
            if key:
                span.set_attribute("messaging.kafka.message_key", str(key))
                
            try:
                res = original_produce(self, topic, value=value, key=key, **kwargs)
                return res
            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                raise

    Producer.produce = wrapped_produce
