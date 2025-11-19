"""Sensor platform for Proteus."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ProteusDataUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Proteus sensors."""
    coordinator: ProteusDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Baterie sensory
    entities.extend([
        ProteusBatterySocSensor(coordinator),
        ProteusBatteryPowerSensor(coordinator),
        ProteusBatteryTargetSocSensor(coordinator),
        ProteusBatteryModeSensor(coordinator),
    ])

    # Výkon sensory
    entities.extend([
        ProteusProductionPowerSensor(coordinator),
        ProteusConsumptionPowerSensor(coordinator),
        ProteusGridPowerSensor(coordinator),
    ])

    # Energie sensory
    entities.extend([
        ProteusDailyProductionSensor(coordinator),
        ProteusDailyConsumptionSensor(coordinator),
        ProteusDailyGridImportSensor(coordinator),
        ProteusDailyGridExportSensor(coordinator),
    ])

    # Ceny
    entities.extend([
        ProteusCurrentPriceSensor(coordinator),
        ProteusNextHourPriceSensor(coordinator),
        ProteusCheapestHourTodaySensor(coordinator),
    ])

    # Status
    entities.extend([
        ProteusConnectionStateSensor(coordinator),
        ProteusCurrentStepSensor(coordinator),
        ProteusFlexibilityRewardsSensor(coordinator),
        ProteusUpcomingScheduleSensor(coordinator),
    ])

    async_add_entities(entities)


class ProteusBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Proteus sensors."""

    def __init__(
        self,
        coordinator: ProteusDataUpdateCoordinator,
        sensor_type: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_name = f"Proteus {name}"
        self._attr_unique_id = f"{coordinator.api.inverter_id}_{sensor_type}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.api.inverter_id)},
            "name": "Proteus Inverter",
            "manufacturer": "Proteus",
            "model": "Inverter",
        }

    def _extract_from_jsonl(self, data: list, key: str) -> Any:
        """Extract data from JSONL response."""
        # Data structure: [{"json": [index, 0, [[actual_data]]]}]
        for item in data:
            if isinstance(item, dict) and "json" in item:
                json_data = item["json"]
                # Check for nested array structure
                if isinstance(json_data, list) and len(json_data) >= 3:
                    nested_data = json_data[2]
                    if isinstance(nested_data, list) and len(nested_data) > 0:
                        if isinstance(nested_data[0], list) and len(nested_data[0]) > 0:
                            actual_data = nested_data[0][0]
                            if isinstance(actual_data, dict) and key in actual_data:
                                return actual_data[key]
                # Also check for direct dict structure
                elif isinstance(json_data, dict) and key in json_data:
                    return json_data[key]
        return None


# ==================== BATERIE ====================


class ProteusBatterySocSensor(ProteusBaseSensor):
    """Battery State of Charge sensor."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "battery_soc", "Battery SoC")
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return battery SoC."""
        last_state = self.coordinator.data.get("last_state")
        if last_state:
            # Use same extraction method as other sensors
            value = self._extract_from_jsonl(last_state, "batteryStateOfCharge")
            return value if value is not None else None
        return None


class ProteusBatteryPowerSensor(ProteusBaseSensor):
    """Battery Power sensor (negative = discharging, positive = charging)."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "battery_power", "Battery Power")
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return battery power (negative = discharging, positive = charging)."""
        last_state = self.coordinator.data.get("last_state")
        if last_state:
            value = self._extract_from_jsonl(last_state, "batteryPower")
            return value if value is not None else None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = {}
        last_state = self.coordinator.data.get("last_state")
        if last_state:
            power = self._extract_from_jsonl(last_state, "batteryPower")
            if power is not None:
                if power < 0:
                    attrs["status"] = "Vybíjení"
                    attrs["status_icon"] = "🔋"
                elif power > 0:
                    attrs["status"] = "Nabíjení"
                    attrs["status_icon"] = "⚡"
                else:
                    attrs["status"] = "Nečinná"
                    attrs["status_icon"] = "⏸️"
        return attrs


class ProteusBatteryTargetSocSensor(ProteusBaseSensor):
    """Battery Target SoC sensor."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "battery_target_soc", "Battery Target SoC")
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return target SoC from current step."""
        current_step = self.coordinator.data.get("current_step")

        # TRPC uses reference pointers - search for item containing actual metadata
        if current_step and isinstance(current_step, list):
            for item in current_step:
                if isinstance(item, dict) and "json" in item:
                    json_data = item["json"]
                    if isinstance(json_data, list) and len(json_data) >= 3:
                        step_data = json_data[2]
                        if isinstance(step_data, list) and len(step_data) > 0:
                            if isinstance(step_data[0], list) and len(step_data[0]) > 0:
                                step_obj = step_data[0][0]
                                if isinstance(step_obj, dict) and "metadata" in step_obj:
                                    metadata = step_obj.get("metadata", {})
                                    if "targetSoC" in metadata:
                                        return metadata["targetSoC"]
        return None


class ProteusBatteryModeSensor(ProteusBaseSensor):
    """Battery Mode sensor."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "battery_mode", "Battery Mode")

    @property
    def native_value(self) -> str | None:
        """Return battery mode."""
        current_step = self.coordinator.data.get("current_step")

        # TRPC uses reference pointers - search for item containing actual metadata
        if current_step and isinstance(current_step, list):
            for item in current_step:
                if isinstance(item, dict) and "json" in item:
                    json_data = item["json"]
                    if isinstance(json_data, list) and len(json_data) >= 3:
                        step_data = json_data[2]
                        if isinstance(step_data, list) and len(step_data) > 0:
                            if isinstance(step_data[0], list) and len(step_data[0]) > 0:
                                step_obj = step_data[0][0]
                                if isinstance(step_obj, dict) and "metadata" in step_obj:
                                    metadata = step_obj.get("metadata", {})
                                    if "flexalgoBattery" in metadata:
                                        mode = metadata.get("flexalgoBattery", "unknown")

                                        # Převeď na čitelný text
                                        mode_map = {
                                            "charge_from_grid": "Nabíjení ze sítě",
                                            "discharge_to_household": "Vybíjení",
                                            "do_not_discharge": "Bez vybíjení",
                                            "charge_from_pv": "Nabíjení z PV",
                                            "default": "Automatický",
                                        }
                                        return mode_map.get(mode, mode)
        return None


# ==================== VÝKON ====================


class ProteusProductionPowerSensor(ProteusBaseSensor):
    """Production Power sensor."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "production_power", "Production Power")
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return production power."""
        last_state = self.coordinator.data.get("last_state")
        if last_state:
            return self._extract_from_jsonl(last_state, "photovoltaicPower")
        return None


class ProteusConsumptionPowerSensor(ProteusBaseSensor):
    """Consumption Power sensor."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "consumption_power", "Consumption Power")
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return consumption power."""
        last_state = self.coordinator.data.get("last_state")
        if last_state:
            return self._extract_from_jsonl(last_state, "consumptionPower")
        return None


class ProteusGridPowerSensor(ProteusBaseSensor):
    """Grid Power sensor (positive = import, negative = export)."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "grid_power", "Grid Power")
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return grid power."""
        last_state = self.coordinator.data.get("last_state")
        if last_state:
            return self._extract_from_jsonl(last_state, "gridPower")
        return None


# ==================== ENERGIE ====================


class ProteusDailyProductionSensor(ProteusBaseSensor):
    """Daily Production sensor."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "daily_production", "Daily Production")
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> float | None:
        """Return daily production."""
        last_state = self.coordinator.data.get("last_state")
        if last_state:
            energy_wh = self._extract_from_jsonl(last_state, "photovoltaicEnergy")
            if energy_wh is not None:
                return energy_wh / 1000  # Convert Wh to kWh
        return None


class ProteusDailyConsumptionSensor(ProteusBaseSensor):
    """Daily Consumption sensor."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "daily_consumption", "Daily Consumption")
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> float | None:
        """Return daily consumption."""
        last_state = self.coordinator.data.get("last_state")
        if last_state:
            energy_wh = self._extract_from_jsonl(last_state, "consumptionEnergy")
            if energy_wh is not None:
                return energy_wh / 1000  # Convert Wh to kWh
        return None


class ProteusDailyGridImportSensor(ProteusBaseSensor):
    """Daily Grid Import sensor."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "daily_grid_import", "Daily Grid Import")
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> float | None:
        """Return daily grid import."""
        last_state = self.coordinator.data.get("last_state")
        if last_state:
            energy_wh = self._extract_from_jsonl(last_state, "gridInEnergy")
            if energy_wh is not None:
                return energy_wh / 1000  # Convert Wh to kWh
        return None


class ProteusDailyGridExportSensor(ProteusBaseSensor):
    """Daily Grid Export sensor."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "daily_grid_export", "Daily Grid Export")
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> float | None:
        """Return daily grid export."""
        last_state = self.coordinator.data.get("last_state")
        if last_state:
            energy_wh = self._extract_from_jsonl(last_state, "gridOutEnergy")
            if energy_wh is not None:
                return energy_wh / 1000  # Convert Wh to kWh
        return None


# ==================== CENY ====================


class ProteusCurrentPriceSensor(ProteusBaseSensor):
    """Current Electricity Price sensor."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "current_price", "Current Price")
        self._attr_native_unit_of_measurement = "Kč/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return current price (consumption price in Kč/kWh)."""
        import logging
        _LOGGER = logging.getLogger(__name__)

        current_step = self.coordinator.data.get("current_step")

        # TRPC uses reference pointers - search for item containing actual metadata
        if current_step and isinstance(current_step, list):
            _LOGGER.debug(f"Current step data contains {len(current_step)} items")
            for item in current_step:
                if isinstance(item, dict) and "json" in item:
                    json_data = item["json"]
                    if isinstance(json_data, list) and len(json_data) >= 3:
                        step_data = json_data[2]
                        if isinstance(step_data, list) and len(step_data) > 0:
                            if isinstance(step_data[0], list) and len(step_data[0]) > 0:
                                step_obj = step_data[0][0]
                                if isinstance(step_obj, dict) and "metadata" in step_obj:
                                    metadata = step_obj.get("metadata", {})
                                    # Use consumption price and convert MWh to kWh
                                    if "priceMwhConsumption" in metadata:
                                        price_mwh = metadata["priceMwhConsumption"]
                                        price_kwh = round(price_mwh / 1000, 2)
                                        _LOGGER.debug(f"Found price in current_step metadata: {price_mwh} MWh = {price_kwh} Kč/kWh")
                                        return price_kwh  # MWh -> kWh
        _LOGGER.debug("No price found in current_step data")
        return None


class ProteusNextHourPriceSensor(ProteusBaseSensor):
    """Next Hour Price sensor."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "next_hour_price", "Next Hour Price")
        self._attr_native_unit_of_measurement = "Kč/kWh"

    @property
    def native_value(self) -> float | None:
        """Return next hour price (consumption price in Kč/kWh)."""
        from datetime import datetime, timedelta
        from homeassistant.util import dt as dt_util

        control_plans = self.coordinator.data.get("control_plans")
        if control_plans:
            active_plan = self._extract_from_jsonl(control_plans, "activePlan")
            if active_plan and isinstance(active_plan, dict):
                steps = active_plan.get("payload", {}).get("steps", [])

                # Find next hour's step
                now = dt_util.now()
                next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

                for step in steps:
                    start_at = step.get("startAt", "")
                    if start_at:
                        try:
                            step_time = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
                            if step_time >= next_hour:
                                price_mwh = step.get("metadata", {}).get("priceMwhConsumption")
                                if price_mwh is not None:
                                    return round(price_mwh / 1000, 2)  # MWh -> kWh
                                break
                        except:
                            pass
        return None


class ProteusCheapestHourTodaySensor(ProteusBaseSensor):
    """Cheapest Hour Today sensor."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "cheapest_hour_today", "Cheapest Hour Today")

    @property
    def native_value(self) -> str | None:
        """Return cheapest hour today."""
        from datetime import datetime, timedelta
        from homeassistant.util import dt as dt_util

        control_plans = self.coordinator.data.get("control_plans")
        if control_plans:
            active_plan = self._extract_from_jsonl(control_plans, "activePlan")
            if active_plan and isinstance(active_plan, dict):
                steps = active_plan.get("payload", {}).get("steps", [])

                # Find cheapest hour in next 24 hours
                now = dt_util.now()
                end_time = now + timedelta(hours=24)
                cheapest_step = None
                cheapest_price = float('inf')

                for step in steps:
                    start_at = step.get("startAt", "")
                    if start_at:
                        try:
                            step_time = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
                            # Only check next 24 hours
                            if now <= step_time < end_time:
                                price_mwh = step.get("metadata", {}).get("priceMwhConsumption", float('inf'))
                                if price_mwh < cheapest_price:
                                    cheapest_price = price_mwh
                                    cheapest_step = step
                        except:
                            pass

                if cheapest_step:
                    start_time = cheapest_step.get("startAt", "")
                    if start_time:
                        dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                        price_kwh = round(cheapest_price / 1000, 2)  # MWh -> kWh
                        return f"{dt.strftime('%H:%M')} ({price_kwh} Kč/kWh)"
        return None


# ==================== STATUS ====================


class ProteusConnectionStateSensor(ProteusBaseSensor):
    """Connection State sensor."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "connection_state", "Connection State")
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["connected", "disconnected", "unknown"]

    @property
    def native_value(self) -> str:
        """Return connection state."""
        linkbox_state = self.coordinator.data.get("linkbox_state")
        if linkbox_state:
            result = self._extract_from_jsonl(linkbox_state, "result")
            if result == 0:
                return "connected"
            else:
                return "disconnected"
        return "unknown"


class ProteusCurrentStepSensor(ProteusBaseSensor):
    """Current Step Description sensor."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "current_step_description", "Current Step")

    @property
    def native_value(self) -> str | None:
        """Return current step description."""
        current_step = self.coordinator.data.get("current_step")

        # TRPC uses reference pointers - search for item containing actual metadata
        if current_step and isinstance(current_step, list):
            for item in current_step:
                if isinstance(item, dict) and "json" in item:
                    json_data = item["json"]

                    # Look for actual step data (has metadata with flexalgoBattery)
                    if isinstance(json_data, list) and len(json_data) >= 3:
                        step_data = json_data[2]
                        if isinstance(step_data, list) and len(step_data) > 0:
                            if isinstance(step_data[0], list) and len(step_data[0]) > 0:
                                step_obj = step_data[0][0]
                                if isinstance(step_obj, dict) and "metadata" in step_obj:
                                    metadata = step_obj.get("metadata", {})

                                    # Check if this has the actual step data
                                    if "flexalgoBattery" in metadata:
                                        mode = metadata.get("flexalgoBattery", "")
                                        target_soc = metadata.get("targetSoC", 0)
                                        price_mwh = metadata.get("priceMwhConsumption", 0)
                                        price_kwh = round(price_mwh / 1000, 2) if price_mwh else 0

                                        mode_map = {
                                            "charge_from_grid": "⚡ Nabíjení ze sítě",
                                            "discharge_to_household": "🔋 Vybíjení",
                                            "do_not_discharge": "⏸️  Bez vybíjení",
                                            "charge_from_pv": "☀️ Nabíjení z PV",
                                            "default": "🔄 Normální",
                                        }

                                        mode_text = mode_map.get(mode, mode)
                                        return f"{mode_text} → {target_soc}% @ {price_kwh} Kč/kWh"

        return "Žádná data"


class ProteusFlexibilityRewardsSensor(ProteusBaseSensor):
    """Flexibility Rewards sensor."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "flexibility_rewards", "Flexibility Rewards")
        self._attr_native_unit_of_measurement = "Kč"
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> float | None:
        """Return total flexibility rewards."""
        rewards = self.coordinator.data.get("rewards_summary")
        if rewards:
            # Extract total rewards from rewards_summary
            summary = self._extract_from_jsonl(rewards, "totalRewardsCzk")
            if summary is not None:
                return summary
        return None


class ProteusUpcomingScheduleSensor(ProteusBaseSensor):
    """Upcoming Schedule sensor showing next steps."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "upcoming_schedule", "Upcoming Schedule")

    @property
    def native_value(self) -> str | None:
        """Return summary of upcoming schedule."""
        import logging
        from datetime import datetime
        from homeassistant.util import dt as dt_util

        _LOGGER = logging.getLogger(__name__)

        control_plans = self.coordinator.data.get("control_plans")
        _LOGGER.debug(f"Upcoming schedule: control_plans type={type(control_plans)}, len={len(control_plans) if control_plans else 0}")

        if control_plans:
            active_plan = self._extract_from_jsonl(control_plans, "activePlan")
            _LOGGER.debug(f"Upcoming schedule: active_plan found={active_plan is not None}")
            if active_plan and isinstance(active_plan, dict):
                steps = active_plan.get("payload", {}).get("steps", [])
                _LOGGER.debug(f"Upcoming schedule: steps count={len(steps)}")

                # Filter steps - only future steps
                now = dt_util.now()
                future_steps = []
                for step in steps:
                    start_at = step.get("startAt", "")
                    if start_at:
                        try:
                            # Parse UTC time and convert to local
                            step_time_utc = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
                            step_time = dt_util.as_local(step_time_utc)
                            # Include current hour and future
                            if step_time >= now.replace(minute=0, second=0, microsecond=0):
                                future_steps.append(step)
                        except:
                            pass

                if len(future_steps) > 0:
                    # Show first future step as summary
                    next_step = future_steps[0]
                    metadata = next_step.get("metadata", {})
                    mode = metadata.get("flexalgoBattery", "")
                    target = metadata.get("targetSoC", 0)
                    price_mwh = metadata.get("priceMwhConsumption", 0)
                    price_kwh = round(price_mwh / 1000, 2) if price_mwh else 0

                    mode_map = {
                        "charge_from_grid": "⚡ Nabíjení ze sítě",
                        "discharge_to_household": "🔋 Vybíjení",
                        "do_not_discharge": "⏸️  Bez vybíjení",
                        "charge_from_pv": "☀️ Nabíjení z PV",
                        "default": "🔄 Normální",
                    }

                    return f"{mode_map.get(mode, mode)} → {target}% @ {price_kwh} Kč/kWh"
        return "Žádný plán"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return ALL future hours schedule (from current hour onwards)."""
        from datetime import datetime
        from homeassistant.util import dt as dt_util

        attrs = {"steps": [], "total_future_steps": 0}
        control_plans = self.coordinator.data.get("control_plans")

        if control_plans:
            active_plan = self._extract_from_jsonl(control_plans, "activePlan")
            if active_plan and isinstance(active_plan, dict):
                steps = active_plan.get("payload", {}).get("steps", [])

                # Filter steps - only current and future steps
                now = dt_util.now()
                current_hour = now.replace(minute=0, second=0, microsecond=0)

                mode_map = {
                    "charge_from_grid": "⚡ Nabíjení ze sítě",
                    "discharge_to_household": "🔋 Vybíjení",
                    "do_not_discharge": "⏸️  Bez vybíjení",
                    "charge_from_pv": "☀️ Nabíjení z PV",
                    "default": "🔄 Normální",
                }

                for step in steps:
                    start_at = step.get("startAt", "")
                    if start_at:
                        try:
                            # Parse UTC time and convert to local
                            dt_utc = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
                            dt = dt_util.as_local(dt_utc)

                            # Only include current hour and future
                            if dt >= current_hour:
                                metadata = step.get("metadata", {})
                                mode = metadata.get("flexalgoBattery", "")
                                price_mwh = metadata.get("priceMwhConsumption", 0)
                                price_kwh = round(price_mwh / 1000, 2) if price_mwh else 0

                                step_info = {
                                    "time": dt.strftime("%d.%m %H:%M"),
                                    "day": dt.strftime("%A"),
                                    "mode": mode_map.get(mode, mode),
                                    "target_soc": metadata.get("targetSoC", 0),
                                    "price_kwh": price_kwh,
                                    "predicted_consumption": round(metadata.get("predictedConsumption", 0), 0),
                                    "predicted_production": round(metadata.get("predictedProduction", 0), 0),
                                }
                                attrs["steps"].append(step_info)
                        except Exception:
                            pass

                attrs["total_future_steps"] = len(attrs["steps"])

        return attrs
