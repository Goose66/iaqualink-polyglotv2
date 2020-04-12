## iAquaLink NodeServer Configuration
##### Advanced Configuration:
- key: shortPoll, value: polling interval for iAquaLink cloud service in "active" polling mode (defaults to 15 seconds - better to not go more frequent than this).
- key: longPoll, value: polling interval for iAquaLink cloud service when not in "active" polling mode (defaults to 180 seconds).

##### Custom Configuration Parameters:
- key: username, value: username (email address) for logging into the iAquaLink service (required).
- key: password, value: password for logging into the iAquaLink service (required).
- key: sessionTTL, value: number of seconds that the session ID is refreshed in order to avoid timeout (optional - defaults to 43200 (12 hours))

Once the "iAquaLink Nodeserver" node appears in The ISY Administrative Console and shows as Online, press the "Discover Devices" button to load the systems and devices configured in your iAquaLink profile.