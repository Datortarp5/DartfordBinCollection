# Dartford Bin Collections

A Home Assistant custom integration for Dartford Borough Council bin collection schedules.

## Installation via HACS

1. In HACS, go to **Integrations** → three-dot menu → **Custom repositories**
2. Add `https://github.com/Datortarp5/DartfordBinCollections` as category **Integration**
3. Click **Download**
4. Restart Home Assistant
5. Go to **Settings → Devices & Services → Add Integration**
6. Search for **Dartford Bin Collections**
7. Enter your **UPRN** and **Postcode**

## Finding your UPRN

Visit [findmyaddress.co.uk](https://www.findmyaddress.co.uk/) and enter your address.

## Sensors

The integration creates one sensor per bin type. As per example:

| Sensor | Description |
|--------|-------------|
| `sensor.dartford_refuse_collection` | Next refuse collection date |
| `sensor.dartford_recycling_collection` | Next recycling collection date |

Each sensor's state is the next collection date (`DD/MM/YYYY`).  
The `upcoming_collections` attribute lists all upcoming dates returned by the council.

## Manual Installation

Copy the `custom_components/dartford_bins` folder into your HA `/config/custom_components/` directory and restart.
