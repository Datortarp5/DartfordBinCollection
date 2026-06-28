"""Sensor platform for Dartford Bin Collections."""
from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, DartfordBinsCoordinator

_LOGGER = logging.getLogger(__name__)

# Map council bin type names to friendly names + icons
BIN_CONFIG = {
    "REFUSE": {
        "friendly": "Refuse",
        "icon": "mdi:trash-can",
    },
    "RECYCLING": {
        "friendly": "Recycling",
        "icon": "mdi:recycle",
    },
    "GARDEN": {
        "friendly": "Garden Waste",
        "icon": "mdi:leaf",
    },
    "FOOD": {
        "friendly": "Food Waste",
        "icon": "mdi:food-apple",
    },
}

DEFAULT_ICON = "mdi:trash-can-outline"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Dartford Bin sensors from a config entry."""
    coordinator: DartfordBinsCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Wait for first refresh, then build one sensor per unique bin type
    bin_types = {b["type"] for b in (coordinator.data or [])}

    async_add_entities(
        DartfordBinSensor(coordinator, bin_type, entry.entry_id)
        for bin_type in bin_types
    )


class DartfordBinSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the next collection date for a bin type."""

    def __init__(
        self,
        coordinator: DartfordBinsCoordinator,
        bin_type: str,
        entry_id: str,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._bin_type = bin_type
        self._entry_id = entry_id

        cfg = BIN_CONFIG.get(bin_type.upper(), {})
        friendly = cfg.get("friendly", bin_type.title())

        self._attr_name = f"Dartford {friendly} Collection"
        self._attr_unique_id = f"dartford_bins_{entry_id}_{bin_type.lower()}"
        self._attr_icon = cfg.get("icon", DEFAULT_ICON)

    @property
    def native_value(self) -> str | None:
        """Return the next collection date as a string (DD/MM/YYYY)."""
        next_date = self._next_date()
        return next_date.strftime("%d/%m/%Y") if next_date else None

    @property
    def extra_state_attributes(self) -> dict:
        """Return all upcoming dates for this bin type."""
        bins = self.coordinator.data or []
        upcoming = [
            b["collectionDate"]
            for b in bins
            if b["type"].upper() == self._bin_type.upper()
        ]
        return {
            "upcoming_collections": upcoming,
            "bin_type": self._bin_type,
        }

    def _next_date(self) -> datetime | None:
        """Return the nearest upcoming collection date."""
        bins = self.coordinator.data or []
        today = datetime.now().date()
        dates = []
        for b in bins:
            if b["type"].upper() == self._bin_type.upper():
                try:
                    d = datetime.strptime(b["collectionDate"], "%d/%m/%Y").date()
                    if d >= today:
                        dates.append(d)
                except ValueError:
                    continue
        return datetime.combine(min(dates), datetime.min.time()) if dates else None

    @property
    def device_info(self) -> dict:
        """Group all bin sensors under one device."""
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": f"Dartford Bin Collections ({self.coordinator.postcode})",
            "manufacturer": "Dartford Borough Council",
            "model": "Bin Collection Schedule",
        }
