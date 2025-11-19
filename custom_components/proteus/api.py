"""Proteus API client."""
import json
import logging
from typing import Any
from urllib.parse import urlencode

import requests

from .const import API_HOST, API_TENANT_ID

_LOGGER = logging.getLogger(__name__)


class ProteusAPI:
    """Proteus API client."""

    def __init__(
        self,
        email: str,
        password: str,
        inverter_id: str | None = None,
        household_id: str | None = None,
    ) -> None:
        """Initialize API client."""
        self.email = email
        self.password = password
        self.inverter_id = inverter_id
        self.household_id = household_id
        self.session_cookie = None
        self.csrf_token = None
        self.session = requests.Session()

    def login(self) -> bool:
        """Login to Proteus."""
        url = f"https://{API_HOST}/api/trpc/users.loginWithEmailAndPassword"

        payload = {
            "json": {
                "email": self.email,
                "password": self.password,
                "tenantId": API_TENANT_ID,
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Origin": f"https://{API_HOST}",
            "Referer": f"https://{API_HOST}/cs/auth/login/email-and-password",
        }

        try:
            response = self.session.post(url, json=payload, headers=headers)
            response.raise_for_status()

            # Získej cookies
            if "proteus_session" in self.session.cookies:
                self.session_cookie = self.session.cookies["proteus_session"]
            if "proteus_csrf" in self.session.cookies:
                self.csrf_token = self.session.cookies["proteus_csrf"]

            if self.session_cookie and self.csrf_token:
                _LOGGER.info("Successfully logged in to Proteus")
                return True
            else:
                _LOGGER.error("Login succeeded but cookies not found")
                return False

        except requests.RequestException as err:
            _LOGGER.error("Login failed: %s", err)
            return False

    def _call_trpc(self, procedures: str | list[str], inputs: list[dict]) -> list:
        """Call TRPC API."""
        if not self.session_cookie or not self.csrf_token:
            raise Exception("Not logged in")

        # Vytvoř procedure string
        if isinstance(procedures, list):
            procedure_str = ",".join(procedures)
        else:
            procedure_str = procedures

        # Vytvoř batch input
        batch_input = {str(i): inp for i, inp in enumerate(inputs)}

        # URL encode
        query = urlencode({"batch": "1", "input": json.dumps(batch_input)})
        url = f"https://{API_HOST}/api/trpc/{procedure_str}?{query}"

        headers = {
            "x-proteus-csrf": self.csrf_token,
            "trpc-accept": "application/jsonl",
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Referer": f"https://{API_HOST}/",
        }

        try:
            response = self.session.get(url, headers=headers)
            response.raise_for_status()

            # Parse JSONL response (každý řádek je JSON)
            lines = response.text.strip().split("\n")
            results = []
            for line in lines:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    results.append(line)

            return results

        except requests.RequestException as err:
            _LOGGER.error("API call failed: %s", err)
            raise

    def get_user_inverters(self) -> list[dict[str, Any]]:
        """Get list of all inverters for the logged-in user."""

        try:
            # Call users.me to get user profile with inverters
            results = self._call_trpc("users.me", [{"json": {}}])

            inverters = []
            # Extract inverter data from response
            for result in results:
                if isinstance(result, dict) and "json" in result:
                    json_data = result["json"]
                    if isinstance(json_data, list) and len(json_data) >= 3:
                        nested_data = json_data[2]
                        if isinstance(nested_data, list) and len(nested_data) > 0:
                            if isinstance(nested_data[0], list) and len(nested_data[0]) > 0:
                                user_data = nested_data[0][0]
                                if isinstance(user_data, dict):
                                    # Look for households with inverters
                                    households = user_data.get("households", [])
                                    for household in households:
                                        household_id = household.get("id")
                                        household_inverters = household.get("inverters", [])
                                        for inverter in household_inverters:
                                            inverters.append({
                                                "inverter_id": inverter.get("id"),
                                                "household_id": household_id,
                                                "name": inverter.get("name") or f"Inverter {inverter.get('id', 'Unknown')[:8]}",
                                                "manufacturer": inverter.get("manufacturer", "Unknown"),
                                            })

            _LOGGER.info("Found %d inverters", len(inverters))
            return inverters

        except Exception as err:
            _LOGGER.error("Failed to get user inverters: %s", err)
            return []

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get all dashboard data at once (batch API)."""
        procedures = [
            "linkBoxes.connectionState",      # 0
            "inverters.detail",               # 1
            "commands.current",               # 2
            "inverters.currentStep",          # 3
            "prices.currentDistributionPrices", # 4
            "users.wsToken",                  # 5
            "inverters.extendedDetail",       # 6
            "inverters.lastState",            # 7
            "inverters.flexibilityRewardsSummary", # 8
            "controlPlans.active",            # 9
        ]

        inputs = [
            {"json": {"householdId": self.household_id}},
            {"json": {"inverterId": self.inverter_id}},
            {"json": {"inverterId": self.inverter_id}},
            {"json": {"inverterId": self.inverter_id}},
            {"json": {"inverterId": self.inverter_id}},
            {"json": {}},
            {"json": {"inverterId": self.inverter_id}},
            {"json": {"inverterId": self.inverter_id}},
            {"json": {"inverterId": self.inverter_id}},
            {"json": {"inverterId": self.inverter_id}},
        ]

        results = self._call_trpc(procedures, inputs)

        # Parse výsledky do strukturovaného dictionary
        # Extrahuj data pro každou proceduru podle indexu
        data = {
            "linkbox_state": self._extract_by_index(results, 0),
            "inverter_detail": self._extract_by_index(results, 1),
            "current_commands": self._extract_by_index(results, 2),
            "current_step": self._extract_by_index(results, 3),
            "distribution_prices": self._extract_by_index(results, 4),
            "ws_token": self._extract_by_index(results, 5),
            "extended_detail": self._extract_by_index(results, 6),
            "last_state": self._extract_by_index(results, 7),
            "rewards_summary": self._extract_by_index(results, 8),
            "control_plans": self._extract_by_index(results, 9),
        }
        return data

    def _extract_by_index(self, results: list, index: int) -> list:
        """Extract all JSONL lines for a specific procedure index.

        Returns a filtered list containing only items that belong to the given procedure.
        This prevents mixing data from different procedures.

        If no items are found for the index, returns the entire results list as fallback
        for backward compatibility.
        """
        filtered = []
        for result in results:
            if isinstance(result, dict) and "json" in result:
                json_data = result["json"]
                # Check if this item belongs to our procedure index
                if isinstance(json_data, list) and len(json_data) >= 1:
                    # Format: [index, 0, [[data]]] - check both int and string
                    first_elem = json_data[0]
                    if first_elem == index or first_elem == str(index):
                        filtered.append(result)

        _LOGGER.debug(f"_extract_by_index: index={index}, found {len(filtered)} items from {len(results)} total")

        # Fallback: if no items found for this index, return all results
        # This ensures backward compatibility if TRPC response format changes
        if not filtered:
            _LOGGER.warning(f"_extract_by_index: No items found for index {index}, returning all {len(results)} results as fallback")
            return results

        return filtered

    def _extract_data(self, results: list, index: int) -> Any:
        """Extract data from JSONL response."""
        # JSONL format je složitý - každý response má více řádků
        # Potřebujeme najít správný data object
        for result in results:
            if isinstance(result, dict):
                json_data = result.get("json")
                if json_data:
                    # Může být ve formátu [index, 0, [[data]]]
                    if isinstance(json_data, list) and len(json_data) >= 3:
                        if json_data[0] == index:
                            # Extrahuj vlastní data
                            if len(json_data[2]) > 0 and len(json_data[2][0]) > 0:
                                return json_data[2][0][0]
                    # Nebo může být přímo ve formátu {"index": data}
                    elif isinstance(json_data, dict) and str(index) in json_data:
                        return json_data[str(index)]
        return None

    def get_control_plan_events(self) -> list[dict]:
        """Get control plan as calendar events."""
        data = self.get_dashboard_data()
        control_plans = data.get("control_plans")

        if not control_plans:
            return []

        # Najdi activePlan
        active_plan = None
        if isinstance(control_plans, dict) and "activePlan" in control_plans:
            active_plan = control_plans["activePlan"]

        if not active_plan or "payload" not in active_plan:
            return []

        steps = active_plan["payload"].get("steps", [])

        events = []
        for step in steps:
            # Vytvoř calendar event ze step
            event = {
                "summary": self._step_to_summary(step),
                "start": step["startAt"],
                "duration": step["durationMinutes"],
                "description": self._step_to_description(step),
                "uid": step["id"],
            }
            events.append(event)

        return events

    def _step_to_summary(self, step: dict) -> str:
        """Convert step to calendar summary."""
        action = step["metadata"]["flexalgoBattery"]
        target_soc = step["metadata"]["targetSoC"]

        action_map = {
            "charge_from_grid": f"⚡ Nabíjení ({target_soc}%)",
            "discharge_to_household": f"🔋 Vybíjení ({target_soc}%)",
            "do_not_discharge": f"⏸️  Žádné vybíjení ({target_soc}%)",
            "charge_from_pv": f"☀️ Nabíjení z PV ({target_soc}%)",
            "default": f"🔄 Normální režim ({target_soc}%)",
        }

        return action_map.get(action, f"Režim: {action} ({target_soc}%)")

    def _step_to_description(self, step: dict) -> str:
        """Convert step to calendar description."""
        metadata = step["metadata"]

        desc = []
        desc.append(f"Režim baterie: {metadata['flexalgoBattery']}")
        desc.append(f"Cíl SoC: {metadata['targetSoC']}%")
        desc.append(f"Cena: {metadata['priceMwh']:.2f} Kč/MWh")
        desc.append(f"Spotřeba (predikce): {metadata['predictedConsumption']:.0f} Wh")
        desc.append(f"Výroba (predikce): {metadata['predictedProduction']:.0f} Wh")

        if "state" in step:
            if "startedAt" in step["state"]:
                desc.append(f"Zahájeno: {step['state']['startedAt']}")
            if "finishedAt" in step["state"]:
                desc.append(f"Dokončeno: {step['state']['finishedAt']}")

        return "\n".join(desc)
