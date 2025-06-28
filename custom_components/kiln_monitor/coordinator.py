"""DataUpdateCoordinator for Kiln Monitor."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_URL, LOGIN_URL, SCAN_INTERVAL, SETTINGS_URL, CONF_EMAIL, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)


class KilnDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Kiln API."""

    def __init__(self, hass: HomeAssistant, session, config_data: dict[str, str]) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name="Kiln API", update_interval=SCAN_INTERVAL)
        self.session = session
        self.email = config_data[CONF_EMAIL]
        self.password = config_data[CONF_PASSWORD]
        self.token: str | None = None
        self.kiln_id: str | None = None
        self.serial_number: str | None = None
        self.kiln_name: str | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # Step 1: Login and get token
            await self._authenticate()
            
            # Step 2: Get kiln settings if we don't have them yet
            if not self.kiln_id:
                await self._fetch_kiln_settings()
            
            # Step 3: Fetch kiln data
            return await self._fetch_kiln_data()
            
        except Exception as exc:
            raise UpdateFailed(f"Kiln API error: {exc}") from exc

    async def _authenticate(self) -> None:
        """Authenticate with the API and get token."""
        login_headers = {
            "Accept": "application/json",
            "kaid-version": "kaid-plus",
            "Sec-Fetch-Site": "cross-site",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Mode": "cors",
            "Content-Type": "application/json",
            "Origin": "ionic://localhost",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty"
        }

        login_payload = {
            "email": self.email,
            "password": self.password
        }

        async with self.session.post(LOGIN_URL, headers=login_headers, json=login_payload) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"Login failed: {resp.status}")
            auth_data = await resp.json()
            self.token = auth_data.get("authentication_token")
            if not self.token:
                raise UpdateFailed("Token not found in login response")

    async def _fetch_kiln_settings(self) -> None:
        """Fetch kiln settings to get kiln_id and serial_number."""
        settings_headers = {
            "content-type": "application/json",
            "accept": "application/json",
            "auth-token": f"binst-cookie={self.token}",
            "kaid-version": "kaid-plus",
            "sec-fetch-site": "cross-site",
            "accept-language": "en-US,en;q=0.9",
            "x-app-name-token": "kiln-aid",
            "sec-fetch-mode": "cors",
            "origin": "ionic://localhost",
            "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
            "email": self.email,
            "sec-fetch-dest": "empty"
        }

        async with self.session.post(SETTINGS_URL, headers=settings_headers, json={}) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"Kiln settings fetch failed: {resp.status}")
            settings_data = await resp.json()

        if isinstance(settings_data, list) and settings_data:
            first_kiln = settings_data[0]
            self.kiln_id = first_kiln.get("kiln_id")
            self.serial_number = first_kiln.get("serial_number")
            self.kiln_name = first_kiln.get("name", "Kiln")
        else:
            raise UpdateFailed("No kiln settings data available")

        if not self.kiln_id:
            raise UpdateFailed("Kiln ID missing in settings response")

    async def _fetch_kiln_data(self) -> dict[str, Any]:
        """Fetch kiln data using kiln_id."""
        data_headers = {
            "content-type": "application/json",
            "accept": "application/json",
            "auth-token": f"binst-cookie={self.token}",
            "kaid-version": "kaid-plus",
            "sec-fetch-site": "cross-site",
            "accept-language": "en-US,en;q=0.9",
            "x-app-name-token": "kiln-aid",
            "sec-fetch-mode": "cors",
            "origin": "ionic://localhost",
            "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
            "email": self.email,
            "sec-fetch-dest": "empty"
        }

        data_payload = {
            "externalIds": [self.kiln_id]
        }

        async with self.session.post(DATA_URL, headers=data_headers, json=data_payload) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"Kiln data fetch failed: {resp.status}")
            data = await resp.json()

        if not isinstance(data, list) or not data:
            raise UpdateFailed("Empty or invalid kiln data")

        return data[0]