# iAquaLink-polyglotv2
A NodeServer for Polyglot v2 that interfaces to the iAquaLink™ cloud service to allow the ISY 994i to control Jandy® AquaLink® pool controllers and accessories. See https://www.iaqualink.com for more information on iAquaLink™.

### Instructions for local Polyglot-V2 installation:

From the Polyglot Dashboard:
1. Install the iAquaLink nodeserver from the Polyglot Nodeserver Store.
2. Add the iAquaLink nodeserver as a Local (Co-Resident with Polyglot) nodeserver type.
3. Modify the following Configuration Parameters:

    ##### Advanced Configuration:
    - key: shortPoll, value: polling interval for iAquaLink cloud service in "active" polling mode (defaults to 15 seconds - better to not go more frequent than this).
    - key: longPoll, value: polling interval for iAquaLink cloud service when not in "active" polling mode (defaults to 180 seconds).

    ##### Custom Configuration Parameters:
    - key: username, value: username (email address) for logging into the iAquaLink service (required).
    - key: password, value: password for logging into the iAquaLink service (required).
    - key: sessionTTL, value: number of seconds that the session ID is refreshed in order to avoid timeout (optional - defaults to 43200 (12 hours))

4. Start (Restart) the iAqualink nodeserver from the Polyglot Dashboard
5. Once the "iAquaLink NodeServer" node appears in ISY994i Adminisrative Console, click "Discover Devices" to load nodes for each of the system devices and aux relays in the pool controller(s) in your profile. THIS PROCESS MAY TAKE SEVERAL SECONDS depending on the number of systems you have and the activity on the iAqauLink service, so please be patient and wait 30 seconds or more before retrying. Also, please check the Polyglot Dashboard for messages regarding Discover Devices failure conditions.

### Notes:

1. The nodeserver relies on polling of the iAquaLink service and toggling of device states. Because of this, the nodeserver must first update the state before peforming any On, Off, etc. commands. Please be patient and provide time (up to shortPoll seconds) for the state change to be reflected before retrying your command.
2. If you change the setup on your AquaLink (temperature unit, type of devices assigned to the AUX relays, etc.), you must delete all the nodes EXCEPT the iAquaLink Nodeserver node from the Polyglot Dashboard (not the ISY), restart the nodeserver, and perform the "Discover Devices" procedure again.
3. After adding all the nodes from "Discover Devices," the node states in the ISY Admin Console will all display with default or "N/A" values. The intial values should be retrieved at the next polling of the iAqualink service. However, depending on timing, the initial state value messages for the new nodes may arrive before the Admin Console has added the nodes, in which case the values will be lost and subsequent polls will not update the values. In that case, to get the initial values for the node states, use the "Update States" for each Aqualink Controller node to retrieve the latest state values for that controller.

For more information regarding this Polyglot Nodeserver, see https://forum.universal-devices.com/topic/29262-polyglot-iaqualink-nodeserver/.
