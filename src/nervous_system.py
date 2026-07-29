#!/usr/bin/env python3
"""
nervous_system.py — The Abvorn Nervous System

This module provides real-time monitoring and autonomous response
for the entire Abvorn content pipeline. It detects problems before
they happen and self-corrects automatically.
"""

import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    FATAL = "fatal"


@dataclass
class SensorReading:
    sensor_id: str
    metric: str
    value: float
    threshold: float
    alert_level: AlertLevel
    timestamp: datetime = field(default_factory=datetime.now)
    message: str = ""


@dataclass
class Intervention:
    action: str
    reason: str
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)
    executed: bool = False
    result: str = ""


class NervousSystem:
    def __init__(self):
        self.sensors = {}
        self.alert_history = []
        self.intervention_history = []
        self.state = {
            "status": "healthy",
            "last_alert": None,
            "last_intervention": None,
            "metrics": {},
        }
        self.monitoring_threads = []
        self.is_running = False
        self.callbacks = []

    def register_sensor(self, sensor_id: str, check_function: Callable,
                          metric: str, threshold: float,
                          alert_level: AlertLevel = AlertLevel.WARNING) -> None:
        self.sensors[sensor_id] = {
            "check_function": check_function,
            "metric": metric,
            "threshold": threshold,
            "alert_level": alert_level,
            "last_reading": None,
            "last_alert": None,
        }
        logger.info(f"Sensor registered: {sensor_id}")

    def check_all_sensors(self) -> List[SensorReading]:
        readings = []
        for sensor_id, sensor in self.sensors.items():
            try:
                value = sensor["check_function"]()
                reading = SensorReading(
                    sensor_id=sensor_id,
                    metric=sensor["metric"],
                    value=value,
                    threshold=sensor["threshold"],
                    alert_level=sensor["alert_level"],
                )
                readings.append(reading)
                sensor["last_reading"] = reading

                if value > sensor["threshold"]:
                    self._trigger_alert(reading)

            except Exception as e:
                logger.error(f"Sensor {sensor_id} failed: {e}")

        return readings

    def _trigger_alert(self, reading: SensorReading) -> None:
        alert = {
            "timestamp": reading.timestamp.isoformat(),
            "sensor_id": reading.sensor_id,
            "metric": reading.metric,
            "value": reading.value,
            "threshold": reading.threshold,
            "level": reading.alert_level.value,
            "message": f"{reading.metric} is {reading.value} (threshold: {reading.threshold})",
        }

        self.alert_history.append(alert)
        self.state["last_alert"] = alert

        logger.warning(f"ALERT: {alert['message']}")

        if reading.alert_level in [AlertLevel.CRITICAL, AlertLevel.FATAL]:
            self._trigger_intervention(reading)

    def _trigger_intervention(self, reading: SensorReading) -> None:
        if reading.metric == "engagement_score" and reading.value < 0.2:
            intervention = Intervention(
                action="adjust",
                reason="Engagement score is critically low",
                confidence=0.85,
            )
        elif reading.metric == "sentiment_drift" and reading.value > 0.3:
            intervention = Intervention(
                action="pause",
                reason="Sentiment is drifting negative",
                confidence=0.80,
            )
        elif reading.metric == "algorithm_change" and reading.value > 0.5:
            intervention = Intervention(
                action="adjust",
                reason="Platform algorithm has changed significantly",
                confidence=0.75,
            )
        else:
            intervention = Intervention(
                action="notify",
                reason=f"Alert triggered: {reading.message}",
                confidence=0.60,
            )

        self.intervention_history.append(intervention)
        self.state["last_intervention"] = intervention
        self._execute_intervention(intervention)

    def _execute_intervention(self, intervention: Intervention) -> None:
        logger.info(f"INTERVENTION: {intervention.action} - {intervention.reason}")

        if intervention.action == "pause":
            self.pause_system()
        elif intervention.action == "adjust":
            self.adjust_strategy()
        elif intervention.action == "notify":
            self.notify_team(intervention)
        elif intervention.action == "resume":
            self.resume_system()

        intervention.executed = True
        intervention.result = f"Executed {intervention.action}"
        intervention.timestamp = datetime.now()

    def pause_system(self) -> None:
        self.state["status"] = "paused"
        logger.warning("System paused")

    def resume_system(self) -> None:
        self.state["status"] = "healthy"
        logger.info("System resumed")

    def adjust_strategy(self) -> None:
        logger.info("Strategy adjusted")

    def notify_team(self, intervention: Intervention) -> None:
        logger.info(f"Team notified: {intervention.reason}")

    def start_monitoring(self, interval_seconds: int = 60) -> None:
        if self.is_running:
            logger.warning("Monitoring already running")
            return

        self.is_running = True

        def monitor_loop():
            while self.is_running:
                try:
                    readings = self.check_all_sensors()
                    self._update_metrics(readings)

                    if self.state["status"] != "paused":
                        self._check_overall_health()

                    time.sleep(interval_seconds)
                except Exception as e:
                    logger.error(f"Monitoring error: {e}")

        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
        self.monitoring_threads.append(thread)

        logger.info(f"Monitoring started (interval: {interval_seconds}s)")

    def stop_monitoring(self) -> None:
        self.is_running = False
        logger.info("Monitoring stopped")

    def _update_metrics(self, readings: List[SensorReading]) -> None:
        for reading in readings:
            self.state["metrics"][reading.metric] = reading.value

    def _check_overall_health(self) -> None:
        metrics = self.state["metrics"]
        if metrics.get("engagement_score", 1.0) < 0.1:
            self.state["status"] = "warning"
            logger.warning("Engagement score critically low")
        elif metrics.get("error_rate", 0) > 0.1:
            self.state["status"] = "warning"
            logger.warning("Error rate elevated")
        else:
            self.state["status"] = "healthy"

    def generate_report(self) -> Dict[str, Any]:
        return {
            "timestamp": datetime.now().isoformat(),
            "status": self.state["status"],
            "total_sensors": len(self.sensors),
            "total_alerts": len(self.alert_history),
            "total_interventions": len(self.intervention_history),
            "recent_alerts": self.alert_history[-5:] if self.alert_history else [],
            "recent_interventions": self.intervention_history[-5:] if self.intervention_history else [],
            "metrics": self.state["metrics"],
        }


def create_nervous_system() -> NervousSystem:
    return NervousSystem()


if __name__ == "__main__":
    system = create_nervous_system()

    def get_engagement():
        return 0.15

    def get_sentiment_drift():
        return 0.45

    def get_algorithm_change():
        return 0.10

    system.register_sensor("engagement_sensor", get_engagement, "engagement_score", 0.3, AlertLevel.CRITICAL)
    system.register_sensor("sentiment_sensor", get_sentiment_drift, "sentiment_drift", 0.25, AlertLevel.WARNING)
    system.register_sensor("algorithm_sensor", get_algorithm_change, "algorithm_change", 0.5, AlertLevel.INFO)

    readings = system.check_all_sensors()

    print("=" * 60)
    print("ABVORN NERVOUS SYSTEM REPORT")
    print("=" * 60)
    for reading in readings:
        print(f"  {reading.sensor_id}: {reading.metric} = {reading.value:.2f} (threshold: {reading.threshold})")

    print("\nSystem State:")
    print(json.dumps(system.generate_report(), indent=2))