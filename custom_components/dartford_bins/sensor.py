"""Sensor platform for Dartford Bin Collections."""
from __future__ import annotations

from datetime import datetime, date
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, DartfordBinsCoordinator

_LOGGER = logging.getLogger(__name__)

BIN_CONFIG = {
    "REFUSE": {
        "friendly": "Refuse",
        "icon": "mdi:trash-can",
        "picture": "/local/dartford_bins/bin_refuse.png",
        "color": "#2e7d32",
    },
    "RECYCLING": {
        "friendly": "Recycling",
        "icon": "mdi:recycle",
        "picture": "/local/dartford_bins/bin_recycling.png",
        "color": "#424242",
    },
    "GARDEN": {
        "friendly": "Garden Waste",
        "icon": "mdi:leaf",
        "picture": "/local/dartford_bins/bin_garden.png",
        "color": "#558b2f",
    },
    "FOOD": {
        "friendly": "Food Waste",
        "icon": "mdi:food-apple",
        "picture": "/local/dartford_bins/bin_leaf.png",
        "color": "#6d4c41",
    },
}

DEFAULT_ICON = "mdi:trash-can-outline"


def days_until_label(days: int) -> str:
    """Return human readable countdown."""
    if days == 0:
        return "Today"
    if days == 1:
        return "Tomorrow"
    return f"In {days} days"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors — one date sensor + one countdown sensor per bin type."""
    coordinator: DartfordBinsCoordinator = hass.data[DOMAIN][entry.entry_id]

    bin_types = sorted({b["type"].upper() for b in (coordinator.data or [])})
    _LOGGER.warning("Dartford Bins: setting up sensors for bin types: %s", bin_types)

    entities = []
    for bin_type in bin_types:
        date_sensor = DartfordBinDateSensor(coordinator, bin_type, entry.entry_id)
        countdown_sensor = DartfordBinCountdownSensor(coordinator, bin_type, entry.entry_id)
        entities.append(date_sensor)
        entities.append(countdown_sensor)
        _LOGGER.warning(
            "Dartford Bins: creating sensors '%s' and '%s'",
            date_sensor.name,
            countdown_sensor.name,
        )

    _LOGGER.warning("Dartford Bins: total sensors to register: %d", len(entities))
    async_add_entities(entities, update_before_add=True)


class _DartfordBinBase(CoordinatorEntity, SensorEntity):
    """Shared base for Dartford bin sensors."""

    def __init__(
        self,
        coordinator: DartfordBinsCoordinator,
        bin_type: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._bin_type = bin_type
        self._entry_id = entry_id
        cfg = BIN_CONFIG.get(bin_type.upper(), {})
        self._friendly = cfg.get("friendly", bin_type.title())
        self._attr_icon = cfg.get("icon", DEFAULT_ICON)
        self._attr_entity_picture = cfg.get("picture")
        self._color = cfg.get("color", "#607d8b")

    def _next_date(self) -> date | None:
        """Return nearest upcoming collection date for this bin type."""
        bins = self.coordinator.data or []
        today = datetime.now().date()
        dates = []
        for b in bins:
            if b["type"].upper() == self._bin_type:
                try:
                    d = datetime.strptime(b["collectionDate"], "%d/%m/%Y").date()
                    if d >= today:
                        dates.append(d)
                except ValueError:
                    continue
        return min(dates) if dates else None

    def _upcoming_dates(self) -> list[str]:
        """Return all upcoming collection dates for this bin type."""
        bins = self.coordinator.data or []
        today = datetime.now().date()
        result = []
        for b in bins:
            if b["type"].upper() == self._bin_type:
                try:
                    d = datetime.strptime(b["collectionDate"], "%d/%m/%Y").date()
                    if d >= today:
                        result.append(b["collectionDate"])
                except ValueError:
                    continue
        return result

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": f"Dartford Bin Collections ({self.coordinator.postcode})",
            "manufacturer": "Dartford Borough Council",
            "model": "Bin Collection Schedule",
        }


class DartfordBinDateSensor(_DartfordBinBase):
    """
    Shows the next collection date for a bin type.
    State: DD/MM/YYYY
    """

    def __init__(self, coordinator: DartfordBinsCoordinator, bin_type: str, entry_id: str) -> None:
        super().__init__(coordinator, bin_type, entry_id)
        self._attr_name = f"Dartford {self._friendly} Next Collection"
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{bin_type.lower()}_date"

    @property
    def native_value(self) -> str | None:
        d = self._next_date()
        return d.strftime("%d/%m/%Y") if d else None

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "bin_type": self._bin_type,
            "upcoming_collections": self._upcoming_dates(),
            "color": self._color,
        }


class DartfordBinCountdownSensor(_DartfordBinBase):
    """
    Shows how many days until the next collection.
    State: Today / Tomorrow / In N days
    """

    def __init__(self, coordinator: DartfordBinsCoordinator, bin_type: str, entry_id: str) -> None:
        super().__init__(coordinator, bin_type, entry_id)
        self._attr_name = f"Dartford {self._friendly} Collection Countdown"
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{bin_type.lower()}_countdown"

    @property
    def native_value(self) -> str | None:
        d = self._next_date()
        if d is None:
            return None
        days = (d - datetime.now().date()).days
        return days_until_label(days)

    @property
    def extra_state_attributes(self) -> dict:
        d = self._next_date()
        days = (d - datetime.now().date()).days if d else None
        return {
            "bin_type": self._bin_type,
            "next_collection_date": d.strftime("%d/%m/%Y") if d else None,
            "days_until_collection": days,
            "color": self._color,
        }
