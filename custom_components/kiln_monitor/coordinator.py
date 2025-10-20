"""DataUpdateCoordinator for Kiln Monitor."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any
import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DATA_URL,
    LOGIN_URL,
    SETTINGS_URL,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class KilnDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Kiln API."""

    def __init__(
        self,
        hass: HomeAssistant,
        session,
        config_data: dict[str, str],
        update_interval_minutes: int = DEFAULT_UPDATE_INTERVAL,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name="Kiln API",
            update_interval=timedelta(minutes=update_interval_minutes),
        )
        self.session = session
        self.email = config_data[CONF_EMAIL]
        self.password = config_data[CONF_PASSWORD]
        self.token: str | None = None
        self.kiln_id: str | None = None
        self.serial_number: str | None = None
        self.kiln_name: str | None = None
        self._consecutive_failures = 0
        self._max_retries = 3
        self._retry_delay = 30  # seconds

    def update_interval_minutes(self, minutes: int) -> None:
        """Update the refresh interval."""
        self.update_interval = timedelta(minutes=minutes)
        _LOGGER.debug("Update interval changed to %d minutes", minutes)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        for attempt in range(self._max_retries):
            try:
                # Step 1: Ensure we have a valid token
                await self._ensure_authenticated()
                
                # Step 2: Get kiln settings if we don't have them yet
                if not self.kiln_id:
                    await self._fetch_kiln_settings()
                
                # Step 3: Fetch kiln data
                data = await self._fetch_kiln_data()
                
                # Reset failure counter on success
                self._consecutive_failures = 0
                return data
                
            except Exception as exc:
                self._consecutive_failures += 1
                _LOGGER.warning(
                    "Attempt %d/%d failed for kiln data fetch: %s", 
                    attempt + 1, self._max_retries, exc
                )
                
                # If this is a 500 error or auth issue, try to re-authenticate
                if "500" in str(exc) or "auth" in str(exc).lower():
                    _LOGGER.info("Clearing token due to potential auth issue")
                    self.token = None
                    self.kiln_id = None  # Force re-fetch of settings
                
                # If this isn't the last attempt, wait and retry
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_delay)
                    continue
                
                # If we've had too many consecutive failures, increase the update interval
                if self._consecutive_failures >= 5:
                    _LOGGER.warning(
                        "Too many consecutive failures (%d), temporarily increasing update interval",
                        self._consecutive_failures
                    )
                    # Temporarily increase interval to reduce load
                    self.update_interval = timedelta(minutes=max(15, self.update_interval.total_seconds() / 60))
                
                raise UpdateFailed(f"Kiln API error after {self._max_retries} attempts: {exc}") from exc

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid authentication token."""
        if not self.token:
            await self._authenticate()

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

        try:
            async with self.session.post(
                LOGIN_URL, 
                headers=login_headers, 
                json=login_payload,
                timeout=30
            ) as resp:
                if resp.status == 401:
                    raise UpdateFailed("Invalid credentials - check email and password")
                elif resp.status == 429:
                    raise UpdateFailed("Rate limited - too many login attempts")
                elif resp.status != 200:
                    raise UpdateFailed(f"Login failed with status {resp.status}")
                
                auth_data = await resp.json()
                self.token = auth_data.get("authentication_token")
                if not self.token:
                    raise UpdateFailed("Token not found in login response")
                    
                _LOGGER.debug("Successfully authenticated with Kiln API")
                
        except asyncio.TimeoutError:
            raise UpdateFailed("Login request timed out")
        except Exception as exc:
            _LOGGER.error("Authentication failed: %s", exc)
            raise UpdateFailed(f"Authentication error: {exc}") from exc

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

        try:
            async with self.session.post(
                SETTINGS_URL, 
                headers=settings_headers, 
                json={},
                timeout=30
            ) as resp:
                if resp.status == 401:
                    # Token might be expired, clear it to force re-auth
                    self.token = None
                    raise UpdateFailed("Authentication token expired")
                elif resp.status == 500:
                    raise UpdateFailed("Server error when fetching kiln settings")
                elif resp.status != 200:
                    raise UpdateFailed(f"Kiln settings fetch failed with status {resp.status}")
                
                settings_data = await resp.json()

            if isinstance(settings_data, list) and settings_data:
                first_kiln = settings_data[0]
                self.kiln_id = first_kiln.get("kiln_id")
                self.serial_number = first_kiln.get("serial_number")
                self.kiln_name = first_kiln.get("name", "Kiln")
                
                _LOGGER.debug(
                    "Fetched kiln settings - ID: %s, Serial: %s, Name: %s",
                    self.kiln_id, self.serial_number, self.kiln_name
                )
            else:
                raise UpdateFailed("No kiln settings data available")

            if not self.kiln_id:
                raise UpdateFailed("Kiln ID missing in settings response")
                
        except asyncio.TimeoutError:
            raise UpdateFailed("Kiln settings request timed out")

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

        try:
            async with self.session.post(
                DATA_URL, 
                headers=data_headers, 
                json=data_payload,
                timeout=30
            ) as resp:
                if resp.status == 401:
                    # Token might be expired, clear it to force re-auth
                    self.token = None
                    raise UpdateFailed("Authentication token expired during data fetch")
                elif resp.status == 404:
                    # Kiln might not exist or be accessible
                    raise UpdateFailed("Kiln not found - check if kiln is online")
                elif resp.status == 500:
                    raise UpdateFailed("Server error when fetching kiln data (status 500)")
                elif resp.status != 200:
                    raise UpdateFailed(f"Kiln data fetch failed with status {resp.status}")
                
                data = await resp.json()

            if not isinstance(data, list) or not data:
                raise UpdateFailed("Empty or invalid kiln data response")

            _LOGGER.debug("Successfully fetched kiln data")
            return data[0]
            
        except asyncio.TimeoutError:
            raise UpdateFailed("Kiln data request timed out")