"""Binary sensors for Proteus API integration."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import ProteusDataUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Proteus binary sensors."""
    coordinator: ProteusDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        ProteusCheapestHourBinarySensor(coordinator),
        ProteusCheapest4HBlockBinarySensor(coordinator),
    ]

    async_add_entities(entities)


class ProteusBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base binary sensor for Proteus."""

    def __init__(
        self,
        coordinator: ProteusDataUpdateCoordinator,
        sensor_id: str,
        name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_name = f"Proteus {name}"
        self._attr_unique_id = f"{coordinator.api.inverter_id}_{sensor_id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.api.inverter_id)},
            "name": "Proteus Inverter",
            "manufacturer": "Proteus",
            "model": "Inverter",
        }


class ProteusCheapestHourBinarySensor(ProteusBaseBinarySensor):
    """Binary sensor for cheapest hour detection."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "cheapest_hour", "Cheapest Hour")
        self._attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self) -> bool:
        """Return True if current hour is the cheapest."""
        control_plans = self.coordinator.data.get("control_plans")
        if not control_plans:
            return False

        # Find active plan
        active_plan = None
        for item in control_plans:
            if isinstance(item, dict) and "json" in item:
                json_data = item["json"]
                if isinstance(json_data, list) and len(json_data) >= 3:
                    data = json_data[2]
                    if isinstance(data, list) and len(data) > 0:
                        if isinstance(data[0], list) and len(data[0]) > 0:
                            plan_obj = data[0][0]
                            if isinstance(plan_obj, dict) and "activePlan" in plan_obj:
                                active_plan = plan_obj["activePlan"]
                                break

        if not active_plan or "payload" not in active_plan:
            return False

        steps = active_plan["payload"].get("steps", [])
        if not steps:
            return False

        # Get current hour
        now = dt_util.now()
        current_hour = now.replace(minute=0, second=0, microsecond=0)

        # Find cheapest step today
        cheapest_step = None
        min_price = float('inf')

        for step in steps:
            start_at = step.get("startAt", "")
            if not start_at:
                continue

            try:
                step_time = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
                # Only consider today's steps
                if step_time.date() == now.date():
                    metadata = step.get("metadata", {})
                    price = metadata.get("priceMwhConsumption", float('inf'))
                    if price < min_price:
                        min_price = price
                        cheapest_step = step_time
            except Exception:
                continue

        if not cheapest_step:
            return False

        # Check if current hour matches cheapest hour
        return current_hour == cheapest_step.replace(minute=0, second=0, microsecond=0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        control_plans = self.coordinator.data.get("control_plans")
        if not control_plans:
            return {}

        # Find active plan (same as above)
        active_plan = None
        for item in control_plans:
            if isinstance(item, dict) and "json" in item:
                json_data = item["json"]
                if isinstance(json_data, list) and len(json_data) >= 3:
                    data = json_data[2]
                    if isinstance(data, list) and len(data) > 0:
                        if isinstance(data[0], list) and len(data[0]) > 0:
                            plan_obj = data[0][0]
                            if isinstance(plan_obj, dict) and "activePlan" in plan_obj:
                                active_plan = plan_obj["activePlan"]
                                break

        if not active_plan or "payload" not in active_plan:
            return {}

        steps = active_plan["payload"].get("steps", [])
        now = dt_util.now()

        # Find cheapest step today
        cheapest_step = None
        min_price = float('inf')

        for step in steps:
            start_at = step.get("startAt", "")
            if not start_at:
                continue

            try:
                step_time = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
                if step_time.date() == now.date():
                    metadata = step.get("metadata", {})
                    price = metadata.get("priceMwhConsumption", float('inf'))
                    if price < min_price:
                        min_price = price
                        cheapest_step = step_time
                        cheapest_price = price
            except Exception:
                continue

        if not cheapest_step:
            return {}

        return {
            "cheapest_hour": cheapest_step.strftime("%H:%M"),
            "cheapest_price_kwh": round(cheapest_price / 1000, 2) if min_price != float('inf') else None,
        }


class ProteusCheapest4HBlockBinarySensor(ProteusBaseBinarySensor):
    """Binary sensor for cheapest 4-hour block detection."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "cheapest_4h_block", "Cheapest 4H Block")
        self._attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self) -> bool:
        """Return True if current hour is in the cheapest 4-hour block."""
        control_plans = self.coordinator.data.get("control_plans")
        if not control_plans:
            return False

        # Find active plan
        active_plan = None
        for item in control_plans:
            if isinstance(item, dict) and "json" in item:
                json_data = item["json"]
                if isinstance(json_data, list) and len(json_data) >= 3:
                    data = json_data[2]
                    if isinstance(data, list) and len(data) > 0:
                        if isinstance(data[0], list) and len(data[0]) > 0:
                            plan_obj = data[0][0]
                            if isinstance(plan_obj, dict) and "activePlan" in plan_obj:
                                active_plan = plan_obj["activePlan"]
                                break

        if not active_plan or "payload" not in active_plan:
            return False

        steps = active_plan["payload"].get("steps", [])
        if not steps:
            return False

        # Get current hour
        now = dt_util.now()
        current_hour = now.replace(minute=0, second=0, microsecond=0)

        # Build list of today's hourly prices
        hourly_prices = []
        for step in steps:
            start_at = step.get("startAt", "")
            if not start_at:
                continue

            try:
                step_time = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
                if step_time.date() == now.date():
                    metadata = step.get("metadata", {})
                    price = metadata.get("priceMwhConsumption", 0)
                    hourly_prices.append({
                        "time": step_time,
                        "price": price,
                    })
            except Exception:
                continue

        if len(hourly_prices) < 4:
            return False

        # Sort by time
        hourly_prices.sort(key=lambda x: x["time"])

        # Find cheapest 4-hour block (sliding window)
        min_avg_price = float('inf')
        cheapest_block_start = None

        for i in range(len(hourly_prices) - 3):
            block = hourly_prices[i:i+4]
            avg_price = sum(h["price"] for h in block) / 4

            if avg_price < min_avg_price:
                min_avg_price = avg_price
                cheapest_block_start = block[0]["time"]

        if not cheapest_block_start:
            return False

        # Check if current hour is in the cheapest 4-hour block
        cheapest_block_end = cheapest_block_start.replace(hour=(cheapest_block_start.hour + 3) % 24)
        current_hour_only = current_hour.replace(minute=0, second=0, microsecond=0)

        return (cheapest_block_start <= current_hour_only <
                cheapest_block_start.replace(hour=(cheapest_block_start.hour + 4) % 24))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        control_plans = self.coordinator.data.get("control_plans")
        if not control_plans:
            return {}

        # Find active plan (same as above)
        active_plan = None
        for item in control_plans:
            if isinstance(item, dict) and "json" in item:
                json_data = item["json"]
                if isinstance(json_data, list) and len(json_data) >= 3:
                    data = json_data[2]
                    if isinstance(data, list) and len(data) > 0:
                        if isinstance(data[0], list) and len(data[0]) > 0:
                            plan_obj = data[0][0]
                            if isinstance(plan_obj, dict) and "activePlan" in plan_obj:
                                active_plan = plan_obj["activePlan"]
                                break

        if not active_plan or "payload" not in active_plan:
            return {}

        steps = active_plan["payload"].get("steps", [])
        now = dt_util.now()

        # Build list of today's hourly prices
        hourly_prices = []
        for step in steps:
            start_at = step.get("startAt", "")
            if not start_at:
                continue

            try:
                step_time = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
                if step_time.date() == now.date():
                    metadata = step.get("metadata", {})
                    price = metadata.get("priceMwhConsumption", 0)
                    hourly_prices.append({
                        "time": step_time,
                        "price": price,
                    })
            except Exception:
                continue

        if len(hourly_prices) < 4:
            return {}

        # Sort by time
        hourly_prices.sort(key=lambda x: x["time"])

        # Find cheapest 4-hour block
        min_avg_price = float('inf')
        cheapest_block_start = None

        for i in range(len(hourly_prices) - 3):
            block = hourly_prices[i:i+4]
            avg_price = sum(h["price"] for h in block) / 4

            if avg_price < min_avg_price:
                min_avg_price = avg_price
                cheapest_block_start = block[0]["time"]

        if not cheapest_block_start:
            return {}

        end_hour = (cheapest_block_start.hour + 3) % 24
        return {
            "block_start": cheapest_block_start.strftime("%H:%M"),
            "block_end": f"{end_hour:02d}:00",
            "avg_price_kwh": round(min_avg_price / 1000, 2),
        }
