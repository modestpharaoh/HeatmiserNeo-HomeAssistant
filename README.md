# HeatmiserNeo-HomeAssistant
Heatmiser Neostat custom component for Home Assistant.

## References

The code is largely taken from MindrustUK/Heatmiser-for-home-assistant project,
but I added the support for Heatmiser hold/standby features based on the hub API
docomentation in RJ/heatmiser-neohub.py

## Supported Features
* Only support heating profile.
* It includes the following parameters in the climate entity for each thermostat.
   * current_temperature: current temperature.
   * temperature: current set temperature.
   * hvac_action: current heating Operation (idle, heating)
   * on_hold: if the thermostat is on hold (off, on)
   * hold_temperature: current hold temperature.
   * on_frost: if the thermostat is on standby (off, on)
   * frost_temperature: current frost temperature.
   * output_delay: delay set on thermostat before it update.
* Supports hold/cancel the temperature of neostat thermostat to certain degree and time by custom services.
* Supports to activate/cancel the standby mode on the neostat thermostat by custom services.
* Supports force query of neo-hub by custom service.

## Installation

Navigate to the custom_components directory for Home Assistant
```
cd /config/custom_components
git clone https://github.com/modestpharaoh/HeatmiserNeo-HomeAssistant
mv HeatmiserNeo-HomeAssistant heatmiserneo
```

As per example_configuration.yaml, add the following to the configuration.yaml in your /config directory.

```yaml
climate:
  - platform: heatmiserneo
    host: <Insert IP Address / Hostname>
    port: 4242
```

## Custom Services Example
Check services.yaml for examples of the following custom services:
* heatmiser.activate_frost
* heatmiser.cancel_frost
* heatmiser.cancel_hold
* heatmiser.hold_temp
* heatmiser.neo_update
* heatmiser.set_frost_temp
