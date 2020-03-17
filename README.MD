# iAquaLink-polyglotv2
A NodeServer for Polyglot v2 that interfaces to the iAquaLink™ cloud service to allow the ISY 994i to control Jandy® AquaLink® pool controllers and accessories. See https://www.iaqualink.com for more information on iAquaLink™.

### Instructions for local Polyglot-V2 installation:

1. Install the iAquaLink nodeserver from the Polyglot Nodeserver Store.
2. Log into the Polyglot Dashboard (https://<Polyglot Server IP Address>:3000)
3. Add the iAquaLink nodeserver as a Local (Co-Resident with Polyglot) nodeserver type.
4. Modify the following Configuration Parameters:

Advanced Configuration:
```
    "shortPoll" = polling interval for iAquaLink cloud service in "active" polling mode - defaults to 15 seconds (better to go no more frequent than this).
    "longPoll" = polling interval for iAquaLink cloud service when not in "active" polling mode - defaults to 60 seconds.
```
Custom Configuration Parameters:
```
    "username" = username (email address) for logging into the iAquaLink service.
    "password" = password for logging into the iAquaLink service.
```
5. Once the "iAquaLink NodeServer" node appears in ISY994i Adminstative Console, click "Discover Devices" to load nodes for each of the system devices and aux relays on the pool controller(s) in your profile. THIS PROCESS MAY TAKE SEVERAL SECONDS depending on the number of systems you have and the activity on the iAqauLink service, so please be patient and wait 30 seconds or more before retrying. Also, please check the Polyglot Dashboard for messages regarding Discover Devices failure conditions.

### Notes:

1. The nodeserver relies on polling of the iAquaLink service and toggling of device states. Because of this, the nodeserver must first update the state before peforming any On, Off, etc. commands. Please be patient and provide time (up to shortPoll seconds) for the state change to be reflected before retrying your command.

For more information regarding this Polyglot Nodeserver, see https://forum.universal-devices.com/topic/28463-polyglot-bond-bridge-nodeserver/.
