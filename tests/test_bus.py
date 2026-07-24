import pytest, time, threading
from abvorn.core.bus import AgentBus

def test_publish_subscribe():
    bus = AgentBus(":memory:")
    received = []
    def handler(msg):
        received.append(msg)
    bus.subscribe("test.topic", handler)
    bus.publish("test.topic", {"data": "hello"})
    time.sleep(0.1)
    assert len(received) == 1
    assert received[0]["data"] == "hello"

def test_topic_filtering():
    bus = AgentBus(":memory:")
    received = []
    bus.subscribe("content.drafted", received.append)
    bus.publish("content.researched", {"niche": "test"})
    time.sleep(0.1)
    assert len(received) == 0  # wrong topic
    bus.publish("content.drafted", {"niche": "test"})
    time.sleep(0.1)
    assert len(received) == 1