#!/usr/bin/python3
"""
Polglot v2 NodeServer for iAquaLink 2.0 Pool Control Service  
by Goose66 (W. Randy King) kingwrandy@gmail.com
"""
try:
    import polyinterface
except ImportError:
    import pgc_interface as polyinterface
import sys
import re
import time
from math import ceil
import iaquaapi as api

LOGGER = polyinterface.LOGGER

# contstants for ISY Nodeserver interface
ISY_BOOL_UOM =2 # Used for reporting status values for Controller and system nodes
ISY_INDEX_UOM = 25 # Custom index UOM for translating direction values
ISY_PPM_UOM = 54 # PPM (for salinity)
ISY_MV_UOM = 43 # Milivolt (for ORP)
ISY_RAW_UOM = 56 # Raw value (for PH)
ISY_PERCENT_UOM = 51 # For light level, as a percentage
ISY_TEMP_F_UOM = 17 # UOM for temperatures (farenheit)
ISY_TEMP_C_UOM = 4 # UOM for temperatures (celcius)

# values for operation mode
IX_SYS_OPMODE_OFF = 0
IX_SYS_OPMODE_POOL = 1
IX_SYS_OPMODE_SPA = 2
IX_SYS_OPMODE_SERVICE = 3
IX_SYS_OPMODE_UNKNOWN = 4

# values for driver device state
IX_DEV_ST_UNKNOWN = -1
IX_DEV_ST_OFF = 0
IX_DEV_ST_ON = 1
IX_DEV_ST_ENABLED = 3

# Color Light Types and node IDs
DEVICE_COLOR_LIGHT_TYPES = {
    "1": "COLOR_LIGHT_JC",
    "2": "COLOR_LIGHT_SL",
    "4": "COLOR_LIGHT_JL",
    "5": "COLOR_LIGHT_IB",
    "6": "COLOR_LIGHT_HU",
}

# device labels for system-level devices
# the user can change these in ISY Admin Console, but provide the iAquaLink defaults
DEVICE_LABEL_PUMP = "Filter Pump"
DEVICE_LABEL_SPA = "Spa Mode"
DEVICE_LABEL_POOL_HEAT = "Pool Heater"
DEVICE_LABEL_SPA_HEAT = "Spa Heater"
DEVICE_LABEL_SOLAR_HEAT = "Solar Heater"

# Device address shortcuts (other than aux_n)
# These are necessary because the actual names for the devices in the iAquaLink
# system state data is too long to serve as addresses for ISY nodeservers.
DEVICE_ADDR_PUMP = "pump"
DEVICE_ADDR_SPA = "spa"
DEVICE_ADDR_POOL_HEAT = "poolht"
DEVICE_ADDR_SPA_HEAT = "spaht"
DEVICE_ADDR_SOLAR_HEAT = "solarht"


# custom parameter values for this nodeserver
PARAM_USERNAME = "username"
PARAM_PASSWORD = "password"
PARAM_SESSION_TTL = "sessionTTL"

DEFAULT_SESSION_TTL = 43200 # 12 hours

# Node class for devices (pumps and aux relays)
class Device(polyinterface.Node):

    id = "DEVICE"
    hint = [0x01, 0x04, 0x02, 0x00] # Residential/Relay/On/Off Power Switch
    deviceName = ""

    def __init__(self, controller, primary, addr, name, deviceName=None):
        super(Device, self).__init__(controller, primary, addr, name)
    
        # override the parent node with the system node (defaults to controller)
        self.parent = self.controller.nodes[self.primary]

        if deviceName is None:
    
            # retrieve the deviceName from polyglot custom data
            cData = controller.getCustomData(addr)
            self.deviceName = cData

        else:
            self.deviceName = deviceName

            # store instance variables in polyglot custom data
            cData = self.deviceName
            controller.addCustomData(addr, cData)

    # Turn on the device
    def cmd_don(self, command):

        LOGGER.info("Turn on %s in DON command handler: %s", self.deviceName, str(command))

        # retrieve the current state of the device since we are toggling
        currentState = self.controller.iaConn.getDeviceState(self.parent.serialNum, self.deviceName)

        # If the device is currently off, toggle the state
        # Note: if current device state comes back unknown, then no toggle will take place
        if currentState == api.DEVICE_STATE_OFF:

            # call the api to toggle the state of the device
            if self.controller.iaConn.toggleDeviceState(self.parent.serialNum, self.deviceName):

                # Update the state value
                self.setDriver("ST", IX_DEV_ST_ON)
            
            else:
                LOGGER.error("Call to API toggleDeviceState() failed in DON command handler.")

        # Place the controller in active polling mode
        self.controller.setActiveMode()

    # Turn off the device
    def cmd_dof(self, command):

        LOGGER.info("Turn off %s in DOF command handler: %s", self.deviceName, str(command))

        # retrieve the current state of the device since we are toggling
        currentState = self.controller.iaConn.getDeviceState(self.parent.serialNum, self.deviceName)

        # If the device is not off, toggle the state
        # Note: if current device state comes back unknown, then no toggle will take place
        if currentState in (api.DEVICE_STATE_ON, api.DEVICE_STATE_ENABLED):
            
            # call the api to toggle the state of the device
            if self.controller.iaConn.toggleDeviceState(self.parent.serialNum, self.deviceName):

                # Update the state value
                self.setDriver("ST", IX_DEV_ST_OFF)
            
            else:
                LOGGER.error("Call to API toggleDeviceState() failed in DOF command handler.")

        # Place the controller in active polling mode
        self.controller.setActiveMode()

    drivers = [{"driver": "ST", "value": IX_DEV_ST_UNKNOWN, "uom": ISY_INDEX_UOM}]
    commands = {
        "DON": cmd_don,
        "DOF": cmd_dof
    }

# Node class for dimmable ligt 
class DimmingLight(polyinterface.Node):

    id = "DIMMING_LIGHT"
    hint = [0x01, 0x02, 0x0a, 0x00] # Residential/Controller/Multi-level Switch
    deviceName = ""

    def __init__(self, controller, primary, addr, name, deviceName=None):
        super(DimmingLight, self).__init__(controller, primary, addr, name)
    
        # override the parent node with the system node (defaults to controller)
        self.parent = self.controller.nodes[self.primary]

        if deviceName is None:
    
            # retrieve the deviceName from polyglot custom data
            cData = controller.getCustomData(addr)
            self.deviceName = cData

        else:
            self.deviceName = deviceName

            # store instance variables in polyglot custom data
            cData = self.deviceName
            controller.addCustomData(addr, cData)

    # Turn on the device
    def cmd_don(self, command):

        LOGGER.info("Turn on %s in DON command handler: %s", self.deviceName, str(command))

        # if no brightness parameter was specified, assume 100%
        if command.get("value") is None:
            value = "100"
        else:
            # retrieve the parameter value (%) for the command - ensure it is divisible by 25 and max 100
            value = str(min(ceil(int(command.get("value")) /25), 4) * 25)

        # call the set_light API
        if self.controller.iaConn.setLightBrightness(self.parent.serialNum, self.deviceName, value):
        
            # update state driver to the brightness set
            self.setDriver("ST", int(value))

        else:
            LOGGER.warning("Call to setLightBrightness() failed in DON command handler.")

        # Place the controller in active polling mode
        self.controller.setActiveMode()

    # Turn off the device
    def cmd_dof(self, command):

        LOGGER.info("Turn off %s in DOF command handler: %s", self.deviceName, str(command))

        # call the set_light API
        if self.controller.iaConn.setLightBrightness(self.parent.serialNum, self.deviceName, "0"):
        
            # update state driver to the brightness set
            self.setDriver("ST", 0)

        else:
            LOGGER.warning("Call to setLightBrightness() failed in DOF command handler.")

        # Place the controller in active polling mode
        self.controller.setActiveMode()

    # Turn off the device
    def cmd_brt(self, command):

        LOGGER.info("Increase brightness for %s in BRT command handler: %s", self.deviceName, str(command))

        # calculate new value from current brightness
        # note values can only be 0, 25, 50, 75, and 100%
        x = int(self.getDriver("ST"))
        value = str(min(ceil(int(x) /25) + 1, 4) * 25)


        # call the set_light API
        if self.controller.iaConn.setLightBrightness(self.parent.serialNum, self.deviceName, value):
        
            # update state driver to the brightness set
            self.setDriver("ST", int(value))

        else:
            LOGGER.warning("Call to setLightBrightness() failed in BRT command handler.")

        # Place the controller in active polling mode
        self.controller.setActiveMode()

    # Turn off the device
    def cmd_dim(self, command):

        LOGGER.info("Decrease brightness for %s in DIM command handler: %s", self.deviceName, str(command))

        # calculate new value from current brightness
        # note values can only be 0, 25, 50, 75, and 100%
        x = int(self.getDriver("ST"))
        value = str(max(ceil(int(x) /25) - 1, 0) * 25)

        # call the set_light API
        if self.controller.iaConn.setLightBrightness(self.parent.serialNum, self.deviceName, value):
        
            # update state driver to the brightness set
            self.setDriver("ST", int(value))

        else:
            LOGGER.warning("Call to setLightBrightness() failed in DIM command handler.")

        # Place the controller in active polling mode
        self.controller.setActiveMode()
    
    drivers = [{"driver": "ST", "value": 0, "uom": ISY_PERCENT_UOM}]
    commands = {
        "DON": cmd_don,
        "DOF": cmd_dof,
        "DFON": cmd_don,
        "DFOF": cmd_dof,
        "BRT": cmd_brt,
        "DIM": cmd_dim
    }

# Node class for color ligt 
class ColorLight(polyinterface.Node):

    id = "COLOR_LIGHT"
    hint = [0x01, 0x04, 0x02, 0x00] # Residential/Relay/On/Off Power Switch
    deviceName = ""
    _lightType = ""

    def __init__(self, controller, primary, addr, name, deviceName=None, lightType=None):
    
        if deviceName is None:
    
            # retrieve the deviceName and the tempUnit from polyglot custom data
            # Note: use controller and addr parameters instead of self.controller and self.address
            # because parent class init() has not been called yet
            cData = controller.getCustomData(addr).split(";")
            self.deviceName = cData[0]
            self._lightType = cData[1]

        else:
            self.deviceName = deviceName
            self._lightType = lightType

        # determine the proper node ID based on the color light type
        self.id = DEVICE_COLOR_LIGHT_TYPES.get(self._lightType, "COLOR_LIGHT_JC")

        # Call the parent class init
        super(ColorLight, self).__init__(controller, primary, addr, name)

        # override the parent node with the system node (defaults to controller)
        self.parent = self.controller.nodes[self.primary]

        # store instance variables in polyglot custom data
        cData = ";".join([self.deviceName, self._lightType])
        self.controller.addCustomData(addr, cData)

    # Turn on the device
    def cmd_don(self, command):

        LOGGER.info("Turn on %s in DON command handler: %s", self.deviceName, str(command))

        # if no effect parameter was specified, just set to 1
        if command.get("value") is None:
            value = "1"
        else:
            # retrieve the effect parameter value for the command 
            value = str(command.get("value"))

        # call the set_effect API
        if self.controller.iaConn.setLightEffect(self.parent.serialNum, self.deviceName, value, self._lightType):
        
            # update state driver to reflect it was turned on
            self.setDriver("ST", IX_DEV_ST_ON)

        else:
            LOGGER.warning("Call to setLightEffect() failed in DON command handler.")

        # Place the controller in active polling mode
        self.controller.setActiveMode()

    # Turn off the device
    def cmd_dof(self, command):

        LOGGER.info("Turn off %s in DOF command handler: %s", self.deviceName, str(command))

        # call the set_effect API
        if self.controller.iaConn.setLightEffect(self.parent.serialNum, self.deviceName, "0", self._lightType):
        
            # update state driver to the brightness set
            self.setDriver("ST", IX_DEV_ST_OFF)

        else:
            LOGGER.warning("Call to setLightEffect() failed in DOF command handler.")

        # Place the controller in active polling mode
        self.controller.setActiveMode()

    drivers = [{"driver": "ST", "value": IX_DEV_ST_UNKNOWN, "uom": ISY_INDEX_UOM}]
    commands = {
        "DON": cmd_don,
        "DOF": cmd_dof,
        "DFON": cmd_don,
        "DFOF": cmd_dof
    }

# Node class for temperature controls (pool heat, spa heat, solar heat)
class TempControl(polyinterface.Node):

    id = "TEMP_CONTROL"
    hint = [0x01, 0x0C, 0x01, 0x00] # Residential/HVAC/Thermostat
    deviceName = ""
    _tempUnit = "F"
    
    # Override init to handle temp units
    def __init__(self, controller, primary, addr, name, deviceName=None, tempUnit=None):

        if deviceName is None:
    
            # retrieve the deviceName and the tempUnit from polyglot custom data
            # Note: use controller and addr parameters instead of self.controller and self.address
            # because parent class init() has not been called yet
            cData = controller.getCustomData(addr).split(";")
            self.deviceName = cData[0]
            self._tempUnit = cData[1]

        else:
            self.deviceName = deviceName
            self._tempUnit = tempUnit
        
        # setup the temperature unit for the node
        self.setTempUnit(self._tempUnit)

        # Call the parent class init
        super(TempControl, self).__init__(controller, primary, addr, name)

        # override the parent node with the system node (defaults to controller)
        self.parent = self.controller.nodes[self.primary]

        # store instance variables in polyglot custom data
        cData = ";".join([self.deviceName, self._tempUnit])
        self.controller.addCustomData(self.address, cData)

    # Setup the termostat node for the correct temperature unit (F or C)
    def setTempUnit(self, tempUnit):
        
        # set the id of the node for the ISY to use from the nodedef
        # this is so the editor (range) for the setpoint is correct
        if tempUnit == "C":
            self.id = "TEMP_CONTROL_C"
        else:
            self.id = "TEMP_CONTROL"
            
        # update the drivers in the node to the correct UOM
        # this is so the numbers show up in the Admin Console with the right unit
        for driver in self.drivers:
            if driver["driver"] in ("CLISPH", "CLITEMP"):
                driver["uom"] = ISY_TEMP_C_UOM if tempUnit == "C" else ISY_TEMP_F_UOM

    # Turn on the heater
    def cmd_don(self, command):

        LOGGER.info("Turn on %s in DON command handler: %s", self.deviceName, str(command))

        # retrieve the current state of the device since we are toggling
        currentState = self.controller.iaConn.getDeviceState(self.parent.serialNum, self.deviceName)

        # If the device is currently off, toggle the state
        # Note: if current device state comes back unknown, then no toggle will take place
        if currentState == api.DEVICE_STATE_OFF:

            # call the api to toggle the state of the device
            if self.controller.iaConn.toggleDeviceState(self.parent.serialNum, self.deviceName):

                # Update the state value
                self.setDriver("ST", IX_DEV_ST_ENABLED)
            
            else:
                LOGGER.error("Call to API toggleDeviceState() failed in DON command handler.")

        # Place the controller in active polling mode
        self.controller.setActiveMode()

    # Turn off the heater
    def cmd_dof(self, command):

        LOGGER.info("Turn off %s in DOF command handler: %s", self.deviceName, str(command))

        # retrieve the current state of the device since we are toggling
        currentState = self.controller.iaConn.getDeviceState(self.parent.serialNum, self.deviceName)

        # If the device is not on, toggle the state
        # Note: if current device state comes back unknown, then no toggle will take place
        if currentState in (api.DEVICE_STATE_ON, api.DEVICE_STATE_ENABLED):
            
            # call the api to toggle the state of the device
            if self.controller.iaConn.toggleDeviceState(self.parent.serialNum, self.deviceName):

                # Update the state value
                self.setDriver("ST", IX_DEV_ST_OFF)
            
            else:
                LOGGER.error("Call to API toggleDeviceState() failed in DOF command handler.")

         # Place the controller in active polling mode
        self.controller.setActiveMode()

    # Set setpoint temperature for heater
    def cmd_set_temp(self, command):
        
        LOGGER.info("Set setpoint for %s in SET_SPH command handler: %s", self.deviceName, str(command))

        value = int(command.get("value"))

        # determine setpoint to change based on device ID
        if self.deviceName == api.DEVICE_NAME_POOL_HEAT and self.parent.hasSpa:
            spName = "temp2"
        elif self.deviceName in (api.DEVICE_NAME_POOL_HEAT, api.DEVICE_NAME_SPA_HEAT):
            spName = "temp1"
        else:
            LOGGER.warning("No setpoint for %s - SET_SPH command ignored.", self.address)
            return

        # set the setpoint element
        if self.controller.iaConn.setTemps(self.parent.serialNum, **({spName: value})):

                # Update the state value
                self.setDriver("CLISPH", value)

        else:
            LOGGER.error("Call to API setTemps() failed in SET_SPH command handler.")

        # Place the controller in active polling mode
        self.controller.setActiveMode()

    drivers = [
        {"driver": "ST", "value": IX_DEV_ST_UNKNOWN, "uom": ISY_INDEX_UOM},
        {"driver": "CLITEMP", "value": 0, "uom": ISY_TEMP_F_UOM},
        {"driver": "CLISPH", "value": 0, "uom": ISY_TEMP_F_UOM}
    ]
    commands = {
        "DON": cmd_don,
        "DOF": cmd_dof,
        "SET_SPH": cmd_set_temp
    }

# Class for inidividual Pool Controller (System in the iAquaLink venacular)
class System(polyinterface.Node):

    id = "SYSTEM"
    hint = [0x01, 0x02, 0x08, 0x00] # Residential/Controller/Sub-system Controller
    serialNum = ""
    hasSpa = False
    _tempUnit = "F"

    def __init__(self, controller, primary, addr, name, serialNum=None):
        super(System, self).__init__(controller, addr, addr, name) # send its own address as primary

        # make the system a primary node
        self.isPrimary = True

        # if the node is being rebuilt in startup, then just set the instance variables
        if serialNum is None:
        
            # retrieve instance variables from polyglot custom data
            cData = controller.getCustomData(addr).split(";")
            self.serialNum = cData[0]
            self.hasSpa = (cData[1] == "True")
            self.tempUnit = cData[2]

        else:
            
            # set the serial number from the parameter
            # Note: the instance variables are saved to custom data in discoverDevices
            self.serialNum = serialNum


    # Update node states for this and child nodes
    def cmd_query(self, command):

        LOGGER.info("Updating node states for system %s in cmd_query()...", self.name)
        
        # Update all of the node values for the node and child nodes
        self.updateNodeStates(True)

        self.controller.setActiveMode()

    # build the child nodes from the system
    def discoverDevices(self):

        LOGGER.info("Building child nodes for system %s in discoverDevices()...", self.name)

        # get the system state from the API
        systemState = self.controller.iaConn.getSystemState(self.serialNum) 

        if systemState and systemState["status"] == "Online":

            # set the temperature unit for the system
            self._tempUnit = systemState["temp_scale"]
            clitempDriver = next(driver for driver in self.drivers if driver["driver"] == "CLITEMP")
            if self._tempUnit == "C":
                clitempDriver["uom"] = ISY_TEMP_C_UOM
            else:
                clitempDriver["uom"] = ISY_TEMP_F_UOM

            # add device node for main pump with this system as primary, if it doesn't exist
            devAddr = getValidNodeAddress(self.address + "_" + DEVICE_ADDR_PUMP)
            if devAddr not in self.controller.nodes: 
                node = Device(
                    self.controller,
                    self.address,
                    devAddr,
                    getValidNodeName(DEVICE_LABEL_PUMP),
                    api.DEVICE_NAME_PUMP
                )
                self.controller.addNode(node)

            # if the system has a pool heater, add a thermostat node for the pool heater
            if systemState[api.DEVICE_NAME_POOL_HEAT] != "":

                LOGGER.info("System %s has a pool heater.", self.name)

                devAddr = getValidNodeAddress(self.address + "_" + DEVICE_ADDR_POOL_HEAT)
                if devAddr not in self.controller.nodes: 
                    node = TempControl(
                        self.controller,
                        self.address,
                        devAddr,
                        getValidNodeName(DEVICE_LABEL_POOL_HEAT),
                        api.DEVICE_NAME_POOL_HEAT,
                        self._tempUnit
                    )
                    self.controller.addNode(node)

            # if the system has a spa, add the corresponding nodes
            if systemState[api.DEVICE_NAME_SPA] != "":

                LOGGER.info("System %s has a spa.", self.name)
                self.hasSpa = True

                # add device node for the spa with this system as primary
                devAddr = getValidNodeAddress(self.address + "_" + DEVICE_ADDR_SPA)
                if devAddr not in self.controller.nodes: 
                    node = Device(
                        self.controller,
                        self.address,
                        devAddr,
                        getValidNodeName(DEVICE_LABEL_SPA),
                        api.DEVICE_NAME_SPA
                    )
                    self.controller.addNode(node)

                # if the system has a spa heater, add a thermostat node for the spa heater
                if systemState[api.DEVICE_NAME_SPA_HEAT] != "":

                    devAddr = getValidNodeAddress(self.address + "_" + DEVICE_ADDR_SPA_HEAT)
                    if devAddr not in self.controller.nodes: 
                        node = TempControl(
                            self.controller,
                            self.address,
                            devAddr,
                            getValidNodeName(DEVICE_LABEL_SPA_HEAT),
                            api.DEVICE_NAME_SPA_HEAT,
                            self._tempUnit
                        )
                        self.controller.addNode(node)

            # if the system has a solar heater, add a device node for the solar heater
            if systemState[api.DEVICE_NAME_SOLAR_HEAT] != "":

                LOGGER.info("System %s has a solar heater.", self.name)

                devAddr = getValidNodeAddress(self.address + "_" + DEVICE_ADDR_SOLAR_HEAT)
                if devAddr not in self.controller.nodes: 
                    node = Device(
                        self.controller,
                        self.address,
                        devAddr,
                        getValidNodeName(DEVICE_LABEL_SOLAR_HEAT),
                        api.DEVICE_NAME_SOLAR_HEAT
                    )
                    self.controller.addNode(node)

            # get a listing of aux devices
            devices = self.controller.iaConn.getDevicesList(self.serialNum) 
            if not devices:
                LOGGER.warning("System %s getDevicesList() returned no devices.", self.name)

            else:

                # iterate devices
                for devID in devices:
                    device = devices[devID]

                    LOGGER.info("System %s has device %s labeled %s of type %s.", self.name, devID, device["label"], device["type"])

                    # If no node already exists for the device address, then add a node for the device
                    devAddr = getValidNodeAddress(self.address + "_" + devID)                         
                    if devAddr not in self.controller.nodes: 
                        
                        # add a dimmable relay node
                        if device["type"] == api.DEVICE_TYPE_DIMMABLE_RELAY:
                            node = DimmingLight(
                                self.controller,
                                self.address,
                                devAddr,
                                getValidNodeName(device["label"]),
                                devID
                            )
                        elif device["type"] == api.DEVICE_TYPE_COLOR_LIGHT:
                            node = ColorLight(
                                self.controller,
                                self.address,
                                devAddr,
                                getValidNodeName(device["label"]),
                                devID,
                                device["subtype"]
                            )
                        else:
                            node = Device(
                                self.controller,
                                self.address,
                                devAddr,
                                getValidNodeName(device["label"]),
                                devID
                            )

                        self.controller.addNode(node)

            # store instance variables in polyglot custom data
            cData = ";".join([self.serialNum, str(self.hasSpa), self._tempUnit])
            self.controller.addCustomData(self.address, cData)

            return True

        else:
            return False

    # update the state of all child nodes for this pool controller (system)
    def updateNodeStates(self, forceReport=False):
        
        # get the system state from the API
        systemState = self.controller.iaConn.getSystemState(self.serialNum) 

        if systemState:

            # Check that the system is online
            if systemState["status"] not in ("Online", "Service"):
                self.setDriver("ST", 0, True, forceReport)
                mode = IX_SYS_OPMODE_UNKNOWN
            else:
                self.setDriver("ST", 1, True, forceReport)
                if systemState["status"] == "Service":
                    mode = IX_SYS_OPMODE_SERVICE
                elif systemState[api.DEVICE_NAME_SPA] == api.DEVICE_STATE_ON:
                    mode = IX_SYS_OPMODE_SPA
                elif systemState[api.DEVICE_NAME_PUMP] == api.DEVICE_STATE_ON:
                    mode = IX_SYS_OPMODE_POOL
                else:
                    mode = IX_SYS_OPMODE_OFF
            
            # update the drivers for the system node
            self.setDriver("GV0", mode, True, forceReport)
            
            self.setDriver("CLITEMP", makeInt(systemState["air_temp"]), True, forceReport)
            self.setDriver("GV1", makeInt(systemState["freeze_protection"]), True, forceReport)
            self.setDriver("GV11", makeInt(systemState["pool_salinity"]) * api.WATER_SALINITY_FACTOR, True, forceReport) 
            self.setDriver("GV12", makeInt(systemState["ph"]) * api.WATER_PH_FACTOR, True, forceReport) 
            self.setDriver("GV13", makeInt(systemState["orp"]) * api.WATER_ORP_FACTOR, True, forceReport) 

            # get the devices state from the API
            devices = self.controller.iaConn.getDevicesList(self.serialNum) 

            # iterate through the nodes of the nodeserver
            for addr in self.controller.nodes:
        
                # ignore the controller and this system node
                if addr != self.address and addr != self.controller.address:

                    # if the device belongs to this system (node's primary is this nodes address),
                    # then update the state of the node's drivers
                    node = self.controller.nodes[addr] 
                    if node.primary == self.address:
                       
                        # Update drivers based on node type
                        if node.deviceName in (api.DEVICE_NAME_PUMP, api.DEVICE_NAME_SPA, api.DEVICE_NAME_SOLAR_HEAT):
                            node.setDriver("ST", translateState(systemState[node.deviceName]), True, forceReport)
                        elif node.deviceName == api.DEVICE_NAME_POOL_HEAT:
                            node.setDriver("ST", translateState(systemState[api.DEVICE_NAME_POOL_HEAT]), True, forceReport)
                            node.setDriver("CLISPH", makeInt(systemState["pool_set_point"]), True, forceReport)
                            node.setDriver("CLITEMP", makeInt(systemState["pool_temp"]), True, forceReport)
                        elif node.deviceName == api.DEVICE_NAME_SPA_HEAT:
                            node.setDriver("ST", translateState(systemState[api.DEVICE_NAME_SPA_HEAT]), True, forceReport)
                            node.setDriver("CLISPH", makeInt(systemState["spa_set_point"]), True, forceReport)
                            node.setDriver("CLITEMP", makeInt(systemState["spa_temp"]), True, forceReport)
                        elif node.deviceName in devices:
                            if node.id == "DIMMING_LIGHT":
                                node.setDriver("ST", int(devices[node.deviceName]["subtype"]), True, forceReport)
                            else:
                                node.setDriver("ST", translateState(devices[node.deviceName]["state"]), True, forceReport)
                        elif devices: # Don't change to UNKNOWN state unless device statuses were returned successfully but the node is not in the list
                            node.setDriver("ST", IX_DEV_ST_UNKNOWN, True, forceReport)
                        else:
                            pass # Just leave the state alone if no device statuses were retrieved

    drivers = [
        {"driver": "ST", "value": 0, "uom": ISY_BOOL_UOM},
        {"driver": "GV0", "value": 0, "uom": ISY_INDEX_UOM},
        {"driver": "CLITEMP", "value": 0, "uom": ISY_TEMP_F_UOM},
        {"driver": "GV1", "value": 0, "uom": ISY_BOOL_UOM},
        {"driver": "GV11", "value": 0, "uom": ISY_PPM_UOM},
        {"driver": "GV12", "value": 0, "uom": ISY_RAW_UOM},
        {"driver": "GV13", "value": 0, "uom": ISY_MV_UOM}
    ]
    commands = {
        "QUERY": cmd_query
    }

# Controller class
class Controller(polyinterface.Controller):

    id = "CONTROLLER"
    _customData = {}
    iaConn = None
    _activePolling = False
    _lastActive = 0  

    def __init__(self, poly):
        super(Controller, self).__init__(poly)
        self.name = "iAquaLink Nodeserver"

    # Set the active polling mode (short polling interval)
    def setActiveMode(self):
        self._activePolling = True
        self._lastActive =  time.time()

    # Start the node server
    def start(self):

        LOGGER.info("Started iAquaLink nodeserver...")

        # load custom data from polyglot
        self._customData = self.polyConfig["customData"]
        
        # If a logger level was stored for the controller, then use to set the logger level
        level = self.getCustomData("loggerlevel")
        if level is not None:
            LOGGER.setLevel(int(level))
        
        # remove all existing notices for the nodeserver
        self.removeNoticesAll()

        # get iAquaLink service credentials from custom configuration parameters
        try:
            customParams = self.polyConfig["customParams"]
            userName = customParams[PARAM_USERNAME]
            password = customParams[PARAM_PASSWORD]
        except KeyError:
            LOGGER.warning("Missing iAquaLink service credentials in configuration.")
            self.addNotice("The iAquaLink service credentials are missing in the configuration. Please check that both the 'username' and 'password' parameter values are specified in the Custom Configuration Parameters and restart the nodeserver.")
            self.addCustomParam({PARAM_USERNAME: "<email address>", PARAM_PASSWORD: "<password>"})
            return

        # get session TTL, if in the custom parameters 
        sessionTTL = int(customParams.get(PARAM_SESSION_TTL, DEFAULT_SESSION_TTL))

        # create a connection to the iAqualink cloud service
        conn = api.iAqualinkConnection(sessionTTL=sessionTTL, logger=LOGGER)

        # login using the provided credentials
        rc = conn.loginToService(userName, password)
        if rc == api.LOGIN_BAD_AUTHENTICATION:
            LOGGER.warning("Bad username or password specified.")
            self.addNotice("Could not login to the iAquaLink service with the specified credentials. Please check the 'username' and 'password' parameter values in the Custom Configuration Parameters and restart the nodeserver.")
            return
        elif rc == api.LOGIN_ERROR:
            LOGGER.error("Error logging into iAquaLink service.")
            return

        # load nodes previously saved to the polyglot database
        # Note: has to be done in two passes to ensure system (primary/parent) nodes exist
        # before device nodes
        # first pass for system nodes
        for addr in self._nodes:           
            node = self._nodes[addr]
            if node["node_def_id"] == "SYSTEM":
                
                LOGGER.info("Adding previously saved node - addr: %s, name: %s, type: %s", addr, node["name"], node["node_def_id"])
                self.addNode(System(self, node["primary"], addr, node["name"]))

        # second pass for device nodes
        for addr in self._nodes:         
            node = self._nodes[addr]    
            if node["node_def_id"] not in ("CONTROLLER", "SYSTEM"):

                LOGGER.info("Adding previously saved node - addr: %s, name: %s, type: %s", addr, node["name"], node["node_def_id"])

                # add device and temperature controller nodes
                if node["node_def_id"] == "DEVICE":
                    self.addNode(Device(self, node["primary"], addr, node["name"]))
                elif node["node_def_id"] == "DIMMING_LIGHT":
                    self.addNode(DimmingLight(self, node["primary"], addr, node["name"]))
                elif node["node_def_id"] in DEVICE_COLOR_LIGHT_TYPES.values():
                    self.addNode(ColorLight(self, node["primary"], addr, node["name"]))
                elif node["node_def_id"] in ("TEMP_CONTROL", "TEMP_CONTROL_C"):
                    self.addNode(TempControl(self, node["primary"], addr, node["name"]))

        # set the object level connection variable
        self.iaConn = conn

        # Set the nodeserver status flag to indicate nodeserver is running
        self.setDriver("ST", 1, True, True)

        # Report the logger level to the ISY
        self.setDriver("GV20", LOGGER.level, True, True)
 
        # update the driver values of all nodes (force report)
        self.updateNodeStates(True)

        # startup in active mode polling
        self.setActiveMode()

    # shutdown the nodeserver on stop
    def stop(self):
        if self.iaConn is not None:
            self.iaConn.close()

        # Set the nodeserver status flag to indicate nodeserver is not running
        self.setDriver("ST", 0, True, True)
    
    # Run discovery for Sony devices
    def cmd_discover(self, command):

        LOGGER.info("Discover devices in cmd_discover()...")
        
        self.discover()

    # Update the profile on the ISY
    def cmd_updateProfile(self, command):

        LOGGER.info("Install profile in cmd_updateProfile()...")
        
        self.poly.installprofile()
        
    # Update the profile on the ISY
    def cmd_setLogLevel(self, command):

        LOGGER.info("Set logging level in cmd_setLogLevel(): %s", str(command))

        # retrieve the parameter value for the command
        value = int(command.get("value"))
 
        # set the current logging level
        LOGGER.setLevel(value)

        # store the new loger level in custom data
        self.addCustomData("loggerlevel", value)
        self.saveCustomData(self._customData)
        
        # update the state driver to the level set
        self.setDriver("GV20", value)

    # called every longPoll seconds (default 30)
    def longPoll(self):

        # only run if iAquaLink connection is established
        if self.iaConn is not None:
            
            # if not in active polling mode, then update the node states
            if not self._activePolling:
                LOGGER.info("Updating node states in longPoll()...")
                self.updateNodeStates()          

    # called every shortPoll seconds (default 10)
    def shortPoll(self):

        # only run if iAquaLink connection is established
        if self.iaConn is not None:
            
            # if in active polling mode, then update the node states
            if self._activePolling:
                LOGGER.info("Updating node states in shortPoll()...")
                self.updateNodeStates()          

            # reset active flag if 5 minutes has passed
            if self._lastActive < (time.time() - 300):
                self._activePolling = False

    # discover systems and associated devices for iAquaLink account
    def discover(self):

        # retrieve a list of systems (pool controllers) from the user profile
        systems = self.iaConn.getSystemsList()

        for system in systems:

            # check to see if a node already exists for the system
            systemAddr = getValidNodeAddress(str(system["id"]))
            if systemAddr not in self.nodes:

                # create a node for the system
                node = System(self, self.address, systemAddr, getValidNodeName(system["name"]), system["serial_number"])
                self.addNode(node)
                
            else:
                node = self.nodes[systemAddr]

            # perform device discovery for the system (pool controller)
            if not node.discoverDevices():
                self.addNotice(f"Could not discover devices for system {node.name}. The pool controller may be offline or in service mode.")

        # send custom data added by new nodes to polyglot
        self.saveCustomData(self._customData)

        # update the driver values for the discovered systems and devices (force report)
        self.updateNodeStates(True)

    # update the node states for all system and device nodes
    def updateNodeStates(self, forceReport=False):

        LOGGER.debug("Polling iAquaLink service for node states in updateNodeState()...")
        
        self._lastPoll = time.time()
        
        # iterate through the nodes of the nodeserver
        for addr in self.nodes:
        
            # ignore the controller node
            if addr != self.address:

                # if the device is a system node, call the updateNodeStates method
                node = self.controller.nodes[addr]
                if node.id == "SYSTEM":
                    node.updateNodeStates(forceReport)

    # helper method for storing custom data
    def addCustomData(self, key, data):

        # add specififed data to custom data for specified key
        self._customData.update({key: data})

    # helper method for retrieve custom data
    def getCustomData(self, key):

        # return data from custom data for key
        return self._customData.get(key)
        
    drivers = [
        {"driver": "ST", "value": 0, "uom": ISY_BOOL_UOM},
        {"driver": "GV20", "value": 0, "uom": ISY_INDEX_UOM}
    ]
    commands = {
        "DISCOVER": cmd_discover,
        "UPDATE_PROFILE" : cmd_updateProfile,
        "SET_LOGLEVEL": cmd_setLogLevel
    }

# Removes invalid charaters and lowercase ISY Node address
def getValidNodeAddress(s):

    # remove <>`~!@#$%^&*(){}[]?/\;:"' characters
    addr = re.sub(r"[<>`~!@#$%^&*(){}[\]?/\\;:\"']+", "", s)

    return addr[-14:].lower()

# Removes invalid charaters for ISY Node description
def getValidNodeName(s):

    # remove <>`~!@#$%^&*(){}[]?/\;:"' characters from names
    return re.sub(r"[<>`~!@#$%^&*(){}[\]?/\\;:\"']+", "", s)

# Convert possibly empty string to int
def makeInt(s):

    return int(s) if s else 0

# Convert state string to state values for the ISY
def translateState(s):

    return int(s) if s else IX_DEV_ST_UNKNOWN

# Main function to establish Polyglot connection
if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface()
        polyglot.start()
        control = Controller(polyglot)
        control.runForever()
    except (KeyboardInterrupt, SystemExit):
        LOGGER.warning("Received interrupt or exit...")
        polyglot.stop()
    except Exception as err:
        LOGGER.error('Excption: {0}'.format(err), exc_info=True)
        sys.exit(0)