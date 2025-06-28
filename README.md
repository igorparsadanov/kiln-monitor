# Kiln Monitor Home Assistant Integration

This custom integration allows you to monitor your Bartinst Kiln using Home Assistant. It connects to the Bartinst cloud API, retrieves kiln data, and exposes it as sensors in your Home Assistant instance.

## Features

- Monitors kiln temperature, status, firmware version, number of firings, and zone count.
- Uses Home Assistant's config flow for easy setup.
- Periodically polls the Bartinst cloud API for updates.

## Installation (via HACS)

1. Make sure you have [HACS](https://hacs.xyz/) installed in your Home Assistant.
2. In HACS, go to **Integrations**.
3. Click the three dots in the top right and select **Custom repositories**.
4. Add this repository:  
   ```
   https://github.com/igorparsadanov/kiln-monitor
   ```
   as an **Integration**.
5. Search for "Kiln Monitor" in HACS and install it.
6. Restart Home Assistant.

## Configuration

1. In Home Assistant, go to **Settings > Devices & Services > Integrations**.
2. Click **Add Integration** and search for "Kiln Monitor".
3. Enter your Bartinst Kiln email and password credentials.
4. Complete the setup wizard.

## Sensors Provided

- **Temperature** (°F)
- **Status**
- **Firmware Version**
- **Number of Firings**
- **Zone Count**

## Troubleshooting

- If you see errors about connection or authentication, double-check your credentials.
- Check Home Assistant logs for more details.



