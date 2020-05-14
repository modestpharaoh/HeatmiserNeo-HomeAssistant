"""
homeassistant.components.climate.heatmiserneo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Heatmiser NeoStat control via Heatmiser Neo-hub
Code largely taken from MindrustUK/Heatmiser-for-home-assistant
and added custom services to support Heatmiser Neostat hold/standby features
"""

from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
import logging
import voluptuous as vol
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    DOMAIN,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    HVAC_MODES,
    SUPPORT_AUX_HEAT,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_HUMIDITY,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
    HVAC_MODE_AUTO,
)
from homeassistant.const import (ATTR_ATTRIBUTION,
                                 ATTR_ENTITY_ID,
                                 ATTR_TEMPERATURE,
                                 CONF_HOST,
                                 CONF_NAME,
                                 CONF_PORT,
                                 STATE_OFF,
                                 STATE_ON,
                                 TEMP_CELSIUS,
                                 TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv

import socket
import json

_LOGGER = logging.getLogger(__name__)

VERSION = '2.0.2'

SUPPORT_FLAGS = 0

ATTRIBUTION = "Data provided by Heatmiser Neo"

COMPONENT_DOMAIN = "heatmiserneo"
SERVICE_HOLD_TEMP = "hold_temp"

SERVICE_NEO_UPDATE = "neo_update"

# New
SERVICE_HOLD_TEMPERATURE = "hold_temperature"
SERVICE_HOLD_TEMPERATURE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required("hold_temperature"): cv.string,
    vol.Required("hold_hours"): cv.string,
    vol.Required("hold_minutes"): cv.string,
    }
)

SERVICE_CANCEL_HOLD = "cancel_hold"
SERVICE_CANCEL_HOLD_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    }
)

SERVICE_ACTIVATE_FROST = "activate_frost"
SERVICE_ACTIVATE_FROST_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    }
)

SERVICE_CANCEL_FROST = "cancel_frost"
SERVICE_CANCEL_FROST_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    }
)

SERVICE_SET_FROST_TEMP = "set_frost_temperature"
SERVICE_SET_FROST_TEMP_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required("frost_temperature"): cv.string,
    }
)

# End New


SERVICE_HOLD_TEMP_SCHEMA = vol.Schema(
    {vol.Required("hold_temperature"): cv.string,
    vol.Required("hold_hours"): cv.string,
    vol.Required("hold_minutes"): cv.string,
    vol.Required("thermostat"): cv.string,
    }
)





# Heatmiser does support all lots more stuff, but only heat for now.
#hvac_modes=[HVAC_MODE_HEAT_COOL, HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_OFF]
# Heatmiser doesn't really have an off mode - standby is a preset - implement later
hvac_modes = [HVAC_MODE_HEAT]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
    }
)

# Fix this when I figure out why my config won't read in. Voluptuous schma thing.
# Excludes time clocks from being included if set to True
ExcludeTimeClock = False

def get_entity_from_domain(hass, domain, entity_id):
    component = hass.data.get(domain)
    if component is None:
        raise HomeAssistantError("{} component not set up".format(domain))

    entity = component.get_entity(entity_id)
    if entity is None:
        raise HomeAssistantError("{} not found".format(entity_id))

    return entity


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up a Heatmiser Neo-Hub And Returns Neostats"""
    host = config.get(CONF_HOST, None)
    port = config.get(CONF_PORT, 4242)

    thermostats = []

    NeoHubJson = HeatmiserNeostat(TEMP_CELSIUS, False, host, port).json_request({"INFO": 0})

    _LOGGER.debug(NeoHubJson)

    for device in NeoHubJson['devices']:
        if device['DEVICE_TYPE'] != 6:
            name = device['device']
            tmptempfmt = device['TEMPERATURE_FORMAT']
            if (tmptempfmt == False) or (tmptempfmt.upper() == "C"):
                temperature_unit = TEMP_CELSIUS
            else:
                temperature_unit = TEMP_FAHRENHEIT
            away = device['AWAY']
            current_temperature = device['CURRENT_TEMPERATURE']
            set_temperature = device['CURRENT_SET_TEMPERATURE']
            on_hold = device['TEMP_HOLD']

            _LOGGER.info("Thermostat Name: %s " % name)
            _LOGGER.info("Thermostat Away Mode: %s " % away)
            _LOGGER.info("Thermostat Current Temp: %s " % current_temperature)
            _LOGGER.info("Thermostat Set Temp: %s " % set_temperature)
            _LOGGER.info("Thermostat Unit Of Measurement: %s " % temperature_unit)
            _LOGGER.info("Thermostat is on hold: %r " % on_hold)

            if (('TIMECLOCK' in device['STAT_MODE']) and (ExcludeTimeClock == True)):
              _LOGGER.debug("Found a Neostat configured in timer mode named: %s skipping" % device['device'])
            else:
              thermostats.append(HeatmiserNeostat(temperature_unit, away, host, port, name))

        elif device['DEVICE_TYPE'] == 6:
            _LOGGER.debug("Found a Neoplug named: %s skipping" % device['device'])

    async def async_hold_temperature(call):
        """Call hold temperature service handler."""
        await async_handle_hold_temperature_service(hass, call)

    hass.services.register(
        COMPONENT_DOMAIN, SERVICE_HOLD_TEMPERATURE, async_hold_temperature, schema=SERVICE_HOLD_TEMPERATURE_SCHEMA
    )

    async def async_cancel_hold(call):
        """Call cancel hold service handler."""
        await async_handle_cancel_hold_service(hass, call)

    hass.services.register(
        COMPONENT_DOMAIN, SERVICE_CANCEL_HOLD, async_cancel_hold, schema=SERVICE_CANCEL_HOLD_SCHEMA
    )

    async def async_activate_frost(call):
        """Call activate frost service handler."""
        await async_handle_activate_frost_service(hass, call)

    hass.services.register(
        COMPONENT_DOMAIN, SERVICE_ACTIVATE_FROST, async_activate_frost, schema=SERVICE_ACTIVATE_FROST_SCHEMA
    )

    async def async_cancel_frost(call):
        """Call cancel frost service handler."""
        await async_handle_cancel_frost_service(hass, call)

    hass.services.register(
        COMPONENT_DOMAIN, SERVICE_CANCEL_FROST, async_cancel_frost, schema=SERVICE_CANCEL_FROST_SCHEMA
    )

    async def async_set_frost_temp(call):
        """Call set frost temp service handler."""
        await async_handle_set_frost_temp_service(hass, call)

    hass.services.register(
        COMPONENT_DOMAIN, SERVICE_SET_FROST_TEMP, async_set_frost_temp, schema=SERVICE_SET_FROST_TEMP_SCHEMA
    )

    async def async_neo_update(call):
        """Call neo update service handler."""
        await async_handle_neo_update_service(hass, call, host, port)

    hass.services.register(
        COMPONENT_DOMAIN, SERVICE_NEO_UPDATE, async_neo_update)



    _LOGGER.info("Adding Thermostats: %s " % thermostats)
    add_devices(thermostats)

async def async_handle_hold_temperature_service(hass, call):
    """Handle hold temp service calls."""
    entity_id = call.data[ATTR_ENTITY_ID]
    hold_temperature = int(float(call.data["hold_temperature"]))
    hold_hours = int(float(call.data["hold_hours"]))
    hold_minutes = int(float(call.data["hold_minutes"]))
    thermostat = get_entity_from_domain(hass, DOMAIN, entity_id)
    response = thermostat.json_request({"HOLD":[{"temp":hold_temperature, "id":"hass","hours":hold_hours,"minutes":hold_minutes}, str(thermostat.name)]})
    
    if response:
        _LOGGER.info("hold_temperature response: %s " % response)
        # Need check for success here
        # {'result': 'temperature on hold'}
        success = False
        try:
            if response['result'] == 'temperature on hold':
                success = True
        except Exception as e:
            _LOGGER.info('Failed to parse response')
        if success:
            if hold_hours == 0 and hold_minutes == 0 :
                thermostat._on_hold = STATE_OFF
                thermostat._hold_time ='0:00'
            if hold_hours > 0 or hold_minutes > 0 :
                thermostat._on_hold = STATE_ON
                thermostat._hold_time = str(hold_hours) + ':' + str(hold_minutes).zfill(2)
                thermostat._target_temperature = hold_temperature

            thermostat._hold_temperature = hold_temperature
        thermostat.update_without_throttle = True
        thermostat.schedule_update_ha_state()
        if hold_hours == 0 and hold_minutes == 0 :
            thermostat.update()

async def async_handle_cancel_hold_service(hass, call):
    """Handle cancel hold service calls."""
    entity_id = call.data[ATTR_ENTITY_ID]
    thermostat = get_entity_from_domain(hass, DOMAIN, entity_id)
    hold_temperature = int(float(thermostat._hold_temperature))
    response = thermostat.json_request({"HOLD":[{"temp":hold_temperature, "id":"hass","hours":0,"minutes":0}, str(thermostat.name)]})

    if response:
        _LOGGER.info("cancel_hold response: %s " % response)
        # Need check for success here
        # {'result': 'temperature on hold'}
        success = False
        try:
            if response['result'] == 'temperature on hold':
                success = True
        except Exception as e:
            _LOGGER.info('Failed to parse response')
        if success:
            thermostat._on_hold = STATE_OFF
            thermostat._hold_time ='0:00'
        thermostat.update_without_throttle = True
        thermostat.schedule_update_ha_state()
        thermostat.update()


async def async_handle_activate_frost_service(hass, call):
    """Handle activate frost service calls."""
    entity_id = call.data[ATTR_ENTITY_ID]
    thermostat = get_entity_from_domain(hass, DOMAIN, entity_id)
    response = thermostat.json_request({"FROST_ON": str(thermostat.name)})

    if response:
        _LOGGER.info("activate_frost response: %s " % response)
        # Need check for success here
        # {"result":"frost on"}
        success = False
        try:
            if response['result'] == 'frost on':
                success = True
        except Exception as e:
            _LOGGER.info('Failed to parse response')
        if success:
            thermostat._on_standby = STATE_ON
            thermostat._target_temperature = thermostat._frost_temperature
        thermostat.update_without_throttle = True
        thermostat.schedule_update_ha_state()
        if not success :
            thermostat.update()

async def async_handle_cancel_frost_service(hass, call):
    """Handle cancel frost service calls."""
    entity_id = call.data[ATTR_ENTITY_ID]
    thermostat = get_entity_from_domain(hass, DOMAIN, entity_id)
    response = thermostat.json_request({"FROST_OFF": str(thermostat.name)})

    if response:
        _LOGGER.info("cancel_frost response: %s " % response)
        # Need check for success here
        #{"result":"frost off"}
        success = False
        try:
            if response['result'] == 'frost off':
                success = True
        except Exception as e:
            _LOGGER.info('Failed to parse response')
        if success:
            thermostat._on_standby = STATE_OFF
        thermostat.update_without_throttle = True
        thermostat.schedule_update_ha_state()
        thermostat.update()


async def async_handle_set_frost_temp_service(hass, call):
    """Handle set frost temp service calls."""
    entity_id = call.data[ATTR_ENTITY_ID]
    thermostat = get_entity_from_domain(hass, DOMAIN, entity_id)
    frost_temperature = int(float(call.data["frost_temperature"]))
    response = thermostat.json_request({"SET_FROST": [frost_temperature, str(thermostat.name)]})

    if response:
        _LOGGER.info("set_frost_temp response: %s " % response)
        # Need check for success here
        # {"result":"temperature was set"}
        success = False
        try:
            if response['result'] == 'temperature was set':
                success = True
        except Exception as e:
            _LOGGER.info('Failed to parse response')
        if success:
            thermostat._frost_temperature = frost_temperature
        thermostat.update_without_throttle = True
        thermostat.schedule_update_ha_state()
        if not success :
            thermostat.update()

async def async_handle_neo_update_service(hass, call, host, port):
    """Handle neo update service calls."""
    hub = HeatmiserNeostat(TEMP_CELSIUS, False, host, port)
    hub.update()


class HeatmiserNeostat(ClimateDevice):
    """ Represents a Heatmiser Neostat thermostat. """
    def __init__(self, unit_of_measurement, away, host, port, name="Null"):
        self._name = name
        self._unit_of_measurement = unit_of_measurement
        self._away = away
        self._host = host
        self._port = port
        #self._type = type Neostat vs Neostat-e
        self._hvac_action = None
        self._hvac_mode = None
        self._current_temperature = None
        self._target_temperature = None
        self.update_without_throttle = False
        self._on_hold = None
        self._hold_temperature = None
        self._hold_time = None
        self._on_standby = None
        self._frost_temperature = None
        self._switching_differential = None
        self._output_delay = None
        self._hvac_modes = hvac_modes
        self._support_flags = SUPPORT_FLAGS
        self._support_flags = self._support_flags | SUPPORT_TARGET_TEMPERATURE
        self.update()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def should_poll(self):
        """ No polling needed for a demo thermostat. """
        return True

    @property
    def name(self):
        """ Returns the name. """
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """ Returns the current temperature. """
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._current_humidity

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._target_humidity

    #@property
    #def target_temperature(self):
    #    """ Returns the temperature we try to reach. """
    #    return self._target_temperature

    @property
    def hvac_action(self):
        """Return current activity ie. currently heating, cooling, idle."""
        return self._hvac_action

    @property
    def hvac_mode(self):
        """Return current operation mode ie. heat, cool, off."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return self._hvac_modes

    @property
    def on_hold(self):
        """Return if Temp on hold."""
        return self._on_hold

    @property
    def hold_temperature(self):
        """Return hold temperature."""
        return self._hold_temperature

    @property
    def hold_time(self):
        """Return the current hold time."""
        return self._hold_time

    @property
    def on_standby(self):
        """Return if thermostat on standby."""
        return self._on_standby

    @property
    def frost_temperature(self):
        """Return frost temperature."""
        return self._frost_temperature
    @property
    def switching_differential(self):
        """Return Switching Differential."""
        return self._switching_differential

    @property
    def output_delay(self):
        """Return frost temperature."""
        return self._output_delay




    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "on_hold": self._on_hold,
            "hold_temperature": self._hold_temperature,
            "hold_time": self._hold_time,
            "on_standby": self._on_standby,
            "frost_temperature": self._frost_temperature,
            "switching_differential": self._switching_differential,
            "output_delay": self._output_delay,
        }

    # @property
    # def preset_mode(self):
    #     """Return preset mode."""
    #     return self._preset

    # @property
    # def preset_modes(self):
    #     """Return preset modes."""
    #     return self._preset_modes


    def set_temperature(self, **kwargs):
        """ Set new target temperature. """
        response = self.json_request({"SET_TEMP": [int(kwargs.get(ATTR_TEMPERATURE)), self._name]})
        if response:
            _LOGGER.info("set_temperature response: %s " % response)
            # Need check for success here
            # {'result': 'temperature was set'}

    def set_temperature_e(self, **kwargs):
        """ Set new target temperature. """
        response = self.json_request({"SET_TEMP": [int(kwargs.get(ATTR_TEMPERATURE)), self._name]})
        if response:
            _LOGGER.info("set_temperature response: %s " % response)
            # Need check for success here
            # {'result': 'temperature was set'}

    def update(self):
        """ Get Updated Info. """
        if self.update_without_throttle:
            self.update_without_throttle = False
        _LOGGER.debug("Entered update(self)")
        response = self.json_request({"INFO": 0})
        engResponse = self.json_request({"ENGINEERS_DATA": 0})
        if response:
            # Add handling for mulitple thermostats here
            _LOGGER.debug("update() json response: %s " % response)
            # self._name = device['device']
            for device in response['devices']:
              if self._name == device['device']:
                tmptempfmt = device["TEMPERATURE_FORMAT"]
                if (tmptempfmt == False) or (tmptempfmt.upper() == "C"):
                  self._temperature_unit = TEMP_CELSIUS
                else:
                  self._temperature_unit = TEMP_FAHRENHEIT
                self._away = device['AWAY']
                self._target_temperature =  round(float(device["CURRENT_SET_TEMPERATURE"]), 2)
                self._current_temperature = round(float(device["CURRENT_TEMPERATURE"]), 2)
                self._current_humidity = round(float(device["HUMIDITY"]), 2)
                if device["TEMP_HOLD"]:
                    self._on_hold = STATE_ON
                else:
                    self._on_hold = STATE_OFF
                self._hold_temperature = round(float(device["HOLD_TEMPERATURE"]), 2)
                self._hold_time = device["HOLD_TIME"]
                if device["STANDBY"]:
                    self._on_standby = STATE_ON
                else:
                    self._on_standby = STATE_OFF

                # Figure out the current mode based on whether cooling is enabled - should verify that this is correct
                if device["COOLING_ENABLED"] == True:
                    self._hvac_mode = HVAC_MODE_COOL
                else:
                    self._hvac_mode = HVAC_MODE_HEAT

                # Figure out current action based on Heating / Cooling flags
                if device["HEATING"] == True:
                    self._hvac_action = CURRENT_HVAC_HEAT
                    _LOGGER.debug("Heating")
                elif device["COOLING"] == True:
                    self._hvac_action = CURRENT_HVAC_COOL
                    _LOGGER.debug("Cooling")
                else:
                    self._hvac_action = CURRENT_HVAC_IDLE
                    _LOGGER.debug("Idle")
            if engResponse:
                _LOGGER.debug("update() json engResponse: %s " % engResponse)
                self._frost_temperature = round(float(engResponse[device["device"]]["FROST TEMPERATURE"]), 2)
                self._switching_differential = round(float(engResponse[device["device"]]["SWITCHING DIFFERENTIAL"]), 2)
                self._output_delay = round(float(engResponse[device["device"]]["OUTPUT DELAY"]), 2)


    def json_request(self, request=None, wait_for_response=False):
        """ Communicate with the json server. """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)

        try:
            sock.connect((self._host, self._port))
        except OSError:
            sock.close()
            return False

        if not request:
            # no communication needed, simple presence detection returns True
            sock.close()
            return True

        _LOGGER.debug("json_request: %s " % request)

        sock.send(bytearray(json.dumps(request) + "\0\r", "utf-8"))
        try:
            buf = sock.recv(4096)
        except socket.timeout:
            # something is wrong, assume it's offline
            sock.close()
            return False

        # read until a newline or timeout
        buffering = True
        while buffering:
            if "\n" in str(buf, "utf-8"):
                response = str(buf, "utf-8").split("\n")[0]
                buffering = False
            else:
                try:
                    more = sock.recv(4096)
                except socket.timeout:
                    more = None
                if not more:
                    buffering = False
                    response = str(buf, "utf-8")
                else:
                    buf += more

        sock.close()

        response = response.rstrip('\0')

        _LOGGER.debug("json_response: %s " % response)

        return json.loads(response, strict=False)
