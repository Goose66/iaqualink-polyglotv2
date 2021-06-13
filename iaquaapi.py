#!/usr/bin/env python
"""
Python wrapper class for iAqualink Mobile App API
by Goose66 (W. Randy King) kingwrandy@gmail.com
"""

import sys
import logging 
import requests
import time

# Configure a module level logger for module testing
_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

# iAquaLink mobile app REST API
_API_APP_KEY = "EOOEMOW4YR6QNB07"
_API_HTTP_HEADERS = {
    "user-agent": "okhttp/3.14.7",
    "content-type": "application/json",
}
_API_LOGIN = {
    "url": "https://prod.zodiac-io.com/users/v1/login",
    "method": "POST"
}
_API_SYSTEMS = {
    "url": "https://r-api.iaqualink.net/devices.json",
    "method": "GET"
}
_API_SESSION = {
    "url": "https://p-api.iaqualink.net/v1/mobile/session.json",
    "method": "GET"
}

# Device names for system level devices (other than aux_n)
DEVICE_NAME_PUMP = "pool_pump"
DEVICE_NAME_SPA = "spa_pump"
DEVICE_NAME_POOL_HEAT = "pool_heater"
DEVICE_NAME_SPA_HEAT = "spa_heater"
DEVICE_NAME_SOLAR_HEAT = "solar_heater"

# Device types for aux devices
DEVICE_TYPE_DEFAULT = "0"
DEVICE_TYPE_DIMMABLE_RELAY = "1"
DEVICE_TYPE_COLOR_LIGHT = "2"

# factors for converting chemical numbers
WATER_PH_FACTOR = 0.1 # pH number
WATER_SALINITY_FACTOR = 50 # PPM
WATER_ORP_FACTOR = 10 # mV

# values for "temp_scale" property
TEMP_SCALE_F = "F"
TEMP_SCALE_C = "C"

# values for device state from iAquaLink
DEVICE_STATE_OFF = "0"
DEVICE_STATE_ON = "1"
DEVICE_STATE_ENABLED = "3"

# return codes for login function
LOGIN_SUCCESS = 1
LOGIN_BAD_AUTHENTICATION = 2
LOGIN_ERROR = 0

# Session API commands
_SESSION_COMMAND_GET_HOME = "get_home"
_SESSION_COMMAND_GET_DEVICES = "get_devices"
_SESSION_COMMAND_SET_POOL_PUMP = "set_pool_pump"    # Toggle Pump
_SESSION_COMMAND_SET_SPA_PUMP = "set_spa_pump"    # Toggle Pump
_SESSION_COMMAND_SET_AUX = "set_" 	# Toggle Aux N
_SESSION_COMMAND_SET_LIGHT = "set_light"
_SESSION_COMMAND_SET_POOL_HEATER = "set_pool_heater" # Toggle Heater
_SESSION_COMMAND_SET_SPA_HEATER = "set_spa_heater" # Toggle Heater
_SESSION_COMMAND_SET_SOLAR_HEATER = "set_solar_heater" # Toggle Heater
_SESSION_COMMAND_SET_TEMPS = "set_temps"

# Timeout durations for HTTP calls - defined here for easy tweaking
_HTTP_GET_TIMEOUT = 6.05
_HTTP_POST_TIMEOUT = 4.05

# default session TTL
_DEFAULT_SESSION_TTL = 3600  # 1 hour

# interface class for a particular Bond Bridge or SBB device
class iAqualinkConnection(object):

    _userID = ""
    _sessionID = ""
    _authToken = ""
    _userName = ""
    _password = ""
    _sessionTTL = 0
    _lastTokenUpdate = 0
    _iaqualinkSession = None
    _logger = None

    # Primary constructor method
    def __init__(self, sessionTTL=_DEFAULT_SESSION_TTL, logger=_LOGGER):

        self._sessionTTL = sessionTTL
        self._logger = logger

        # open an HTTP session
        self._iaqualinkSession = requests.Session()

    # Call the specified REST API
    def _call_api(self, api, params=None, payload=None):
      
        method = api["method"]
        url = api["url"]

        # uncomment the next line to dump HTTP request data to log file for debugging
        #self._logger.debug("HTTP %s data: %s", method + " " + url, payload if params is None else params)

        try:
            response = self._iaqualinkSession.request(
                method,
                url,
                json = payload,
                params = params, 
                headers = _API_HTTP_HEADERS, # same every call     
                timeout= _HTTP_POST_TIMEOUT if method == "POST" else _HTTP_GET_TIMEOUT
            )
            
            # raise any codes other than 200, 201, and 401 for error handling 
            if response.status_code not in (200, 201, 401):
                response.raise_for_status()

        # Allow timeout and connection errors to be ignored - log and return false
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            self._logger.warning("HTTP %s in _call_api() failed: %s", method, str(e))
            return None
        except:
            self._logger.error("Unexpected error occured: %s", sys.exc_info()[0])
            raise

        # uncomment the next line to dump HTTP response to log file for debugging
        #self._logger.debug("HTTP response code: %d data: %s", response.status_code, response.text)

        return response

    # Update the session ID and authentication tokens if the TTL has expired
    def _checkTokens(self):

        # check TTL time
        currentTime = time.time()
        if currentTime - self._lastTokenUpdate > self._sessionTTL:

            # close the current session and delay for a few seconds
            self._iaqualinkSession.close()
            time.sleep(2)

            # format payload
            payload = {
                "api_key": _API_APP_KEY,
                "email": self._userName,
                "password": self._password,
            } 

            # call the login API
            response  = self._call_api(_API_LOGIN, payload=payload)
        
            # if data returned, update the access tokens from the response data
            if response is not None:

                respData = response.json()

                if response.status_code == 200:

                    self._sessionID = respData["session_id"]
                    self._authToken = respData["authentication_token"]

                    self._lastTokenUpdate = time.time()
                
                else:
                    # otherwise just log it and try to keep going with current tokens
                    self._logger.error("Error retrieving security token: %d - %s", respData.get("code"), respData.get("description"))

            else:
                
                # logged in _call_api()
                pass

    # Login to the cloud service and retrieve session_id, user_id, and authentication_token
    # to access the remainder of the API
    def loginToService(self, userName, password):
        """Login to the iAquaLink service and retrieve the required access tokens.

        Parameters:
        username -- username (email address) for iAquaLink service (string)
        password -- password for iAquaLink service (string)

        Returns:
        code indicating login success: LOGIN_SUCCESS, LOGIN_BAD_AUTHENTICATION, LOGIN_ERROR
        """
        self._logger.debug("in API loginToService()...")

        # format payload
        payload = {
            "api_key": _API_APP_KEY,
            "email": userName,
            "password": password,
        } 

        # call the login API
        response  = self._call_api(_API_LOGIN, payload=payload)
        
        # if data returned, parse the access tokens and store in the instance variables
        if response is not None:
            
            respData = response.json()
            
            if response.status_code == 200:

                self._sessionID = respData["session_id"]
                self._authToken = respData["authentication_token"]
                self._userID = respData["id"]

                self._userName = userName
                self._password = password

                self._lastTokenUpdate = time.time()

                return LOGIN_SUCCESS


            # check for authentication error (bad credentials)
            elif response.status_code == 401:

                return LOGIN_BAD_AUTHENTICATION

            else:
                self._logger.warning("Authentication error logging into MyQ service: %d - %s", respData.get("code"), respData.get("description"))
                return LOGIN_ERROR

        else:
            return LOGIN_ERROR

    # Get a list of AquaLink systems for the user profile
    def getSystemsList(self):
        """Get list of AquaLink systems in user profile for logged-in user.

        Returns:
        array of dictionary of properties for each system (pool controller)
        """

        self._logger.debug("in API getSystemsList()...")

        # format url parameters
        params = {
            "api_key": _API_APP_KEY,
            "authentication_token": self._authToken,
            "user_id": self._userID
        } 

        # call the systems API
        response  = self._call_api(_API_SYSTEMS, params=params)
        
        # if data was returned, return the systems list
        if response is not None and response.status_code == 200:

            return response.json()

        # otherwise return error (False)
        else:
            return False

    # Get system state information by serial number
    def getSystemState(self, serialNum, internal=False):
        """Get state information for a specific system (pool controller)

        Parameters:
        serialNum -- serial number from systems list of pool controller (string)
        Returns:
        dictionary of state attributes for specified system
        """

        self._logger.debug("in API getSystemStatus()...")

        # check the auth tokens and TTL unless this is a get state call (a non-polling call)
        if not internal:
            self._checkTokens()

        # format url parameters
        params = {
           "actionID": "command",
           "command": _SESSION_COMMAND_GET_HOME,
           "serial": serialNum,
           "sessionID": self._sessionID,
        } 

        # call the session API with the parameters
        response  = self._call_api(_API_SESSION, params=params)
        
        # if data returned, format system state and return
        if response and response.status_code == 200:

            respData = response.json()
            return self._buildSystemState(respData)
            
        # otherwise return error (False)
        else:
            return False

    # Get device state information for a controller
    def getDevicesList(self, serialNum, internal=False):
        """Get state information for devices (aux relays) for specific system (pool controller)

        Parameters:
        serialNum -- serial number from systems list of pool controller (string)
        Returns:
        dictionary of devices (aux relays) with state attributes for each
        """

        self._logger.debug("in API getDevicesList()...")

        # check the auth tokens and TTL unless this is a get state call (a non-polling call)
        if not internal:
            self._checkTokens()

        # format url parameters
        params = {
           "actionID": "command",
           "command": _SESSION_COMMAND_GET_DEVICES,
           "serial": serialNum,
           "sessionID": self._sessionID,
        } 

        # call the session API with the parameters
        response  = self._call_api(_API_SESSION, params=params)
        
        # if data returned, format devices state and return
        if response and response.status_code == 200:

            respData = response.json()           
            return self._buildDevicesState(respData)

        # otherwise return empty dictionary (evaluates to false)
        else:
            return {}

    # Get device state a device
    def getDeviceState(self, serialNum, deviceName):
        """Get the state information for the specified device

        Parameters:
        serialNum -- serial number from systems list of pool controller (string)
        deviceName -- serial number from systems list of pool controller (string)
        Returns:
        state value for the device of "" if unknown or error (string) 
        """

        self._logger.debug("in API getDeviceState()...")

        # determine whether the device is a system device or an aux relay
        if deviceName in (DEVICE_NAME_PUMP, DEVICE_NAME_SPA, DEVICE_NAME_POOL_HEAT, DEVICE_NAME_SPA_HEAT, DEVICE_NAME_SOLAR_HEAT):
            
            # get the current system state
            systemState = self.getSystemState(serialNum, True)
            
            # return the current state for the device
            if systemState and deviceName in systemState:
                return systemState[deviceName]
            else:
                return "" # Unknown

        else:
            # get the device list with state
            devices = self.getDevicesList(serialNum, True)

            # return the current state for the device
            if devices and deviceName in devices:
                return devices[deviceName]["state"]
            else:
                return "" # Unknown
        
    # Toggle the state of a pump or heater - returns system state information
    def toggleDeviceState(self, serialNum, deviceName):
        """Toggle the state (0, 1) for specified system device

        Parameters:
        serialNum -- serial number from systems list of pool controller (string)
        deviceName -- name of the device to toggle state, e.g. "aux_3"
        Returns:
        dictionary of resulting state information for the specified system (pool controller)
        """

        self._logger.debug("in API toggleDeviceState()...")
       
        # set the correct command based on specified device
        if deviceName == DEVICE_NAME_PUMP:
            command = _SESSION_COMMAND_SET_POOL_PUMP
        elif deviceName == DEVICE_NAME_SPA:
            command = _SESSION_COMMAND_SET_SPA_PUMP
        elif deviceName == DEVICE_NAME_POOL_HEAT:
            command = _SESSION_COMMAND_SET_POOL_HEATER
        elif deviceName == DEVICE_NAME_SPA_HEAT:
            command = _SESSION_COMMAND_SET_SPA_HEATER
        elif deviceName == DEVICE_NAME_SOLAR_HEAT:
            command = _SESSION_COMMAND_SET_SOLAR_HEATER
        else:
            command = _SESSION_COMMAND_SET_AUX + deviceName

        # format url parameters
        params = {
           "actionID": "command",
           "command": command,
           "serial": serialNum,
           "sessionID": self._sessionID,
        } 

        # call the session API with the parameters
        response  = self._call_api(_API_SESSION, params=params)
        
        # too much latency in the status change to return the new state, so just ignore 
        if response and response.status_code == 200:

            return True

        else:
            return False
            
    # Set the temp setpoints for the pool and spa
    def setTemps(self, serialNum, temp1=None, temp2=None):
        """Set the pool and spa temperature setpoints

        Parameters:
        serialNum -- serial number from systems list of pool controller (string)
        temp1 -- temperature setpoint # 1 (spa, if it exists) (optional) (integer)
        temp2 -- temperature setpoint # 2 (pool) (optional) (integer)
        Returns:
        dictionary of resulting state information for all devices of the specified system (pool controller)
        """

        self._logger.debug("in API setTemps()...")

        # format url parameters
        params = {
           "actionID": "command",
           "command": _SESSION_COMMAND_SET_TEMPS,
           "serial": serialNum,
           "sessionID": self._sessionID,
        } 

        # add the temp1 and temp2 setpoint parameters if specified
        if temp1 is not None:
            params["temp1"] = temp1 
        if temp2 is not None:
            params["temp2"] = temp2

        # call the session API with the parameters
        response  = self._call_api(_API_SESSION, params=params)
        
        if response and response.status_code == 200:

            return True

        # otherwise return error (False)
        else:
            return False

    # Set the brightness for a dimmable light
    def setLightBrightness(self, serialNum, deviceName, brightness="100"):
        """Set the brightness level for a dimmable light

        Parameters:
        serialNum -- serial number from systems list of pool controller (string)
        deviceName -- aux relay for dimmable light ("aux_n")
        brightness -- brightness level for light 0%, 25%, 50%, 75%, or 100% (optional) (integer)
        Returns:
        dictionary of resulting state information for all devices of the specified system (pool controller)
        """

        self._logger.debug("in API setLightBrightness()...")

        # strip the number of aux relay off for the data payload
        aux = deviceName[deviceName.find("_")+1:]

        # format url parameters
        params = {
           "actionID": "command",
           "command": _SESSION_COMMAND_SET_LIGHT,
           "aux": aux,
           "light": brightness,
           "serial": serialNum,
           "sessionID": self._sessionID,
        } 

        # call the session API with the parameters
        response  = self._call_api(_API_SESSION, params=params)
        
        if response and response.status_code == 200:

            return True

        # otherwise return error (False)
        else:
            return False
            
    # Set the effect for a color light
    def setLightEffect(self, serialNum, deviceName, effect="1", lightType="1"):
        """Set the effect for a color light

        Parameters:
        serialNum -- serial number from systems list of pool controller (string)
        deviceName -- aux relay for color light ("aux_n")
        effect -- effect number to set light to (varies by type) (optional) (integer)
        lightType -- type of color light attached (from subtype of associated aux)
        Returns:
        dictionary of resulting state information for all devices of the specified system (pool controller)
        """

        self._logger.debug("in API setLightEffect()...")

        # strip the number of aux relay off for the data payload
        aux = deviceName[deviceName.find("_")+1:]

        # format url parameters
        params = {
           "actionID": "command",
           "command": _SESSION_COMMAND_SET_LIGHT,
           "aux": aux,
           "light": effect,
           "subtype": lightType,
           "serial": serialNum,
           "sessionID": self._sessionID,
        } 

        # call the session API with the parameters
        response  = self._call_api(_API_SESSION, params=params)
        
        if response and response.status_code == 200:

            return True

        # otherwise return error (False)
        else:
            return False

    # close any HTTP session
    def close(self):
        self._iaqualinkSession.close()
            
    # builds a system state dictionary from home screen response data
    @staticmethod
    def _buildSystemState(data):

        systemState = {}

        # return a single dictionary with state attributes
        for attr in data["home_screen"]:
            systemState.update(attr)
        
        return systemState

    # builds a device state dictionary from devices screen response data
    @staticmethod
    def _buildDevicesState(data):

        devices = {}

        # return a dictionary of devices with state subdictionary for each
        for device in data["devices_screen"][3:]:
            key = list(device.keys())[0]
            deviceState = {}
            for attr in device[key]:
                deviceState.update(attr)
            devices[key] = deviceState

        return devices