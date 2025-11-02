"""Calendar platform for Proteus control plan."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
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
    """Set up Proteus calendar."""
    coordinator: ProteusDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ProteusControlPlanCalendar(coordinator)])


class ProteusControlPlanCalendar(CoordinatorEntity, CalendarEntity):
    """Calendar entity for Proteus control plan."""

    def __init__(self, coordinator: ProteusDataUpdateCoordinator) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator)
        self._attr_name = "Proteus Control Plan"
        self._attr_unique_id = f"{coordinator.api.inverter_id}_control_plan"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.api.inverter_id)},
            "name": "Proteus Inverter",
            "manufacturer": "Proteus",
            "model": "Inverter",
        }

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next event."""
        events = self._get_events()
        if not events:
            return None

        now = dt_util.now()

        # Find current or next event
        for event in events:
            if event.start <= now < event.end:
                return event
            if event.start > now:
                return event

        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        events = self._get_events()

        # Filter events within the requested range
        return [
            event
            for event in events
            if event.start < end_date and event.end > start_date
        ]

    def _get_events(self) -> list[CalendarEvent]:
        """Get all control plan events."""
        control_plans = self.coordinator.data.get("control_plans")
        if not control_plans:
            return []

        # Extract active plan
        active_plan = self._extract_from_jsonl(control_plans, "activePlan")
        if not active_plan or not isinstance(active_plan, dict):
            return []

        payload = active_plan.get("payload", {})
        steps = payload.get("steps", [])

        events = []
        for step in steps:
            event = self._step_to_event(step)
            if event:
                events.append(event)

        return events

    def _extract_from_jsonl(self, data: list, key: str) -> Any:
        """Extract data from JSONL response."""
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

    def _step_to_event(self, step: dict) -> CalendarEvent | None:
        """Convert control plan step to calendar event."""
        try:
            start_at = step.get("startAt")
            duration_minutes = step.get("durationMinutes", 60)
            metadata = step.get("metadata", {})

            if not start_at:
                return None

            # Parse start time
            start = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
            end = start + timedelta(minutes=duration_minutes)

            # Create event summary and description
            summary = self._create_summary(metadata)
            description = self._create_description(step)

            return CalendarEvent(
                start=start,
                end=end,
                summary=summary,
                description=description,
                uid=step.get("id", ""),
            )
        except (ValueError, KeyError):
            return None

    def _create_summary(self, metadata: dict) -> str:
        """Create event summary from metadata."""
        action = metadata.get("flexalgoBattery", "")
        target_soc = metadata.get("targetSoC", 0)
        price = metadata.get("priceMwh", 0)

        action_map = {
            "charge_from_grid": "⚡ Nabíjení ze sítě",
            "discharge_to_household": "🔋 Vybíjení",
            "do_not_discharge": "⏸️  Bez vybíjení",
            "charge_from_pv": "☀️ Nabíjení z PV",
            "default": "🔄 Normální režim",
        }

        action_text = action_map.get(action, f"Režim: {action}")
        return f"{action_text} ({target_soc}%) @ {price:.0f} Kč/MWh"

    def _create_description(self, step: dict) -> str:
        """Create event description from step."""
        metadata = step.get("metadata", {})
        state = step.get("state", {})

        lines = []
        lines.append(f"Režim baterie: {metadata.get('flexalgoBattery', 'N/A')}")
        lines.append(f"Cílový SoC: {metadata.get('targetSoC', 0)}%")
        lines.append(f"Cena: {metadata.get('priceMwh', 0):.2f} Kč/MWh")
        lines.append(
            f"Cena spotřeba: {metadata.get('priceMwhConsumption', 0):.2f} Kč/MWh"
        )
        lines.append(
            f"Cena produkce: {metadata.get('priceMwhProduction', 0):.2f} Kč/MWh"
        )
        lines.append(
            f"Predikovaná spotřeba: {metadata.get('predictedConsumption', 0):.0f} Wh"
        )
        lines.append(
            f"Predikovaná výroba: {metadata.get('predictedProduction', 0):.0f} Wh"
        )

        # Price components
        components = metadata.get("priceComponents", {})
        if components:
            lines.append("\nCenové složky:")
            if "distributionPrice" in components:
                lines.append(f"  Distribuce: {components['distributionPrice']:.2f} Kč")
            if "distributionTariffType" in components:
                lines.append(f"  Tarif: {components['distributionTariffType']}")
            if "systemServices" in components:
                lines.append(f"  Systémové služby: {components['systemServices']:.2f} Kč")
            if "poze" in components:
                lines.append(f"  POZE: {components['poze']:.2f} Kč")

        # State information
        if state:
            lines.append("\nStav:")
            if "startedAt" in state:
                started = datetime.fromisoformat(state["startedAt"].replace("Z", "+00:00"))
                lines.append(f"  Zahájeno: {started.strftime('%d.%m.%Y %H:%M')}")
            if "finishedAt" in state:
                finished = datetime.fromisoformat(state["finishedAt"].replace("Z", "+00:00"))
                lines.append(f"  Dokončeno: {finished.strftime('%d.%m.%Y %H:%M')}")

        return "\n".join(lines)
