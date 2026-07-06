"""Dartford Borough Council Bin Collections integration."""
from __future__ import annotations

import logging
import pathlib
import re
from datetime import timedelta

import requests
from bs4 import BeautifulSoup

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.http import StaticPathConfig
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

DOMAIN = "dartford_bins"
PLATFORMS = [Platform.SENSOR]

BASE_URL = "https://windmz.dartford.gov.uk/ufs/WS_CHECK_COLLECTIONS.eb"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.5",
    "Content-Type": "application/x-www-form-urlencoded",
}


def fetch_bin_data(uprn: str, postcode: str) -> list[dict]:
    """
    Fetch bin collection data from Dartford Borough Council portal.

    Two-step Verj.io e-form flow:
      1. GET the UPRN URL — establishes JSESSIONID session cookie and ebz token.
      2. POST the postcode in the same session — returns the results page.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    r1 = session.get(BASE_URL, params={"UPRN": uprn}, timeout=15)
    r1.raise_for_status()

    soup1 = BeautifulSoup(r1.text, "html.parser")
    form = soup1.find("form", {"name": "RW"})
    if not form:
        raise UpdateFailed("Could not find form on Dartford portal — site may have changed")

    action = form.get("action", "")
    ebz_match = re.search(r"ebz=(1_\d+)", action)
    if not ebz_match:
        raise UpdateFailed("Could not extract ebz token from Dartford portal")

    ebz = ebz_match.group(1)

    r2 = session.post(
        f"{BASE_URL}?ebz={ebz}",
        data={
            "CTRL:KseGry05:_:A": postcode,
            "CTRL:2nvfUnaN:_": "Find",
        },
        timeout=15,
    )
    r2.raise_for_status()

    soup2 = BeautifulSoup(r2.text, "html.parser")
    table = soup2.find(
        "table", {"class": lambda c: c and "eb-EVDNdR1G-tableContent" in c}
    )
    if not table:
        raise UpdateFailed(
            "No bin data table found — postcode may be wrong, or the portal has changed"
        )

    bins = []
    for row in table.find_all("tr", class_=lambda c: c and "eb-EVDNdR1G-tableRow" in c):
        columns = row.find_all("td")
        if len(columns) >= 4:
            collection_type = columns[1].get_text(strip=True)
            collection_date = columns[3].get_text(strip=True)
            if re.match(r"\d{2}/\d{2}/\d{4}", collection_date):
                bins.append({"type": collection_type, "collectionDate": collection_date})

    return bins


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register static www path for bin icons."""
    www_path = pathlib.Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/local/dartford_bins", str(www_path), cache_headers=True)]
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dartford Bins from a config entry."""
    uprn = entry.data["uprn"]
    postcode = entry.data["postcode"]

    # SelectSelector returns strings, so convert to int; default 12h
    refresh_hours = int(
        entry.options.get("refresh_interval",
        entry.data.get("refresh_interval", "12"))
    )

    _LOGGER.warning("Dartford Bins: starting with refresh interval %sh", refresh_hours)

    coordinator = DartfordBinsCoordinator(hass, uprn, postcode, refresh_hours)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


class DartfordBinsCoordinator(DataUpdateCoordinator):
    """Coordinator to poll the council website on a schedule."""

    def __init__(
        self,
        hass: HomeAssistant,
        uprn: str,
        postcode: str,
        refresh_hours: int = 12,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=refresh_hours),
        )
        self.uprn = uprn
        self.postcode = postcode

    async def _async_update_data(self) -> list[dict]:
        try:
            return await self.hass.async_add_executor_job(
                fetch_bin_data, self.uprn, self.postcode
            )
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Error fetching Dartford bin data: {err}") from err
