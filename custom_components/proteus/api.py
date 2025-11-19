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
            # Call inverters.list to get all inverters
            # Input format: {"json": null, "meta": {"values": ["undefined"]}}
            list_results = self._call_trpc("inverters.list", [{"json": None, "meta": {"values": ["undefined"]}}])

            inverters = []
            # Extract inverter data from inverters.list response
            # Expected format: [{"json":[index, 0, [[[{inverter_data}]]]]}, ...]
            for idx, result in enumerate(list_results):
                if isinstance(result, dict) and "json" in result:
                    json_data = result["json"]

                    # Handle list format: [index, 0, [[[{inverter}]]]]
                    if isinstance(json_data, list) and len(json_data) >= 3:
                        nested_data = json_data[2]

                        # Navigate through nested arrays: [[[{inverter}]]]
                        if isinstance(nested_data, list) and len(nested_data) > 0:
                            if isinstance(nested_data[0], list) and len(nested_data[0]) > 0:
                                if isinstance(nested_data[0][0], list) and len(nested_data[0][0]) > 0:
                                    inverter_data = nested_data[0][0][0]

                                    if isinstance(inverter_data, dict) and "id" in inverter_data:
                                        inverter_id = inverter_data.get("id")

                                        inverters.append({
                                            "inverter_id": inverter_id,
                                            "household_id": None,  # Not needed - linkBoxes endpoint not used
                                            "name": inverter_data.get("name") or f"Inverter {inverter_id[:8]}",
                                            "manufacturer": inverter_data.get("vendor", "Unknown"),
                                            "control_mode": inverter_data.get("controlMode"),
                                            "control_enabled": inverter_data.get("controlEnabled"),
                                        })

            return inverters

        except Exception as err:
            _LOGGER.error("Failed to get user inverters: %s", err)
            return []

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get all dashboard data at once (batch API)."""
        # Note: linkBoxes.connectionState removed - requires household_id
        # Note: inverters.detail removed - causes rate limit
        # Note: prices.currentDistributionPrices removed - causes rate limit
        procedures = [
            "commands.current",               # 0
            "inverters.currentStep",          # 1
            "users.wsToken",                  # 2
            "inverters.extendedDetail",       # 3
            "inverters.lastState",            # 4
            "inverters.flexibilityRewardsSummary", # 5
            "controlPlans.active",            # 6
        ]

        inputs = [
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
        # Extrahuj data pro každou proceduru podle indexu (0-6)
        data = {
            "linkbox_state": [],  # Not fetched - would need household_id
            "inverter_detail": [],  # Not fetched - causes rate limit
            "current_commands": self._extract_by_index(results, 0),
            "current_step": self._extract_by_index(results, 1),
            "distribution_prices": [],  # Not fetched - causes rate limit
            "ws_token": self._extract_by_index(results, 2),
            "extended_detail": self._extract_by_index(results, 3),
            "last_state": self._extract_by_index(results, 4),
            "rewards_summary": self._extract_by_index(results, 5),
            "control_plans": self._extract_by_index(results, 6),
        }

        return data

    def _extract_by_index(self, results: list, index: int) -> list:
        """Extract all JSONL lines for a specific procedure index.

        Returns a filtered list containing only items that belong to the given procedure.
        This follows TRPC reference chains to collect all related data.

        If no items are found for the index, returns the entire results list as fallback
        for backward compatibility.
        """
        filtered = []
        indices_to_check = {index}  # Start with the requested index

        # Follow reference chains: index -> ref_index -> actual_data
        for result in results:
            if isinstance(result, dict) and "json" in result:
                json_data = result["json"]
                if isinstance(json_data, list) and len(json_data) >= 1:
                    first_elem = json_data[0]

                    # If this matches an index we're looking for
                    if first_elem in indices_to_check or str(first_elem) in indices_to_check:
                        filtered.append(result)

                        # Check if this contains a reference to another index
                        if len(json_data) >= 3 and isinstance(json_data[2], list):
                            nested = json_data[2]
                            if len(nested) > 1 and isinstance(nested[1], list) and len(nested[1]) >= 3:
                                # Reference format: ["result"|"data", 0, ref_index]
                                ref_index = nested[1][2]
                                if isinstance(ref_index, int):
                                    indices_to_check.add(ref_index)

        # Second pass to collect referenced indices
        for result in results:
            if isinstance(result, dict) and "json" in result:
                json_data = result["json"]
                if isinstance(json_data, list) and len(json_data) >= 1:
                    first_elem = json_data[0]
                    if first_elem in indices_to_check and result not in filtered:
                        filtered.append(result)

        # Fallback: if no items found for this index, return all results
        if not filtered:
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
