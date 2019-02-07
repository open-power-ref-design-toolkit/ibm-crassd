# Checking health of the ibm-crassd service
## Controlling the ibm-crassd service with system controls
The following commands can all be run from the command line with the system that has the IBM crassd service installed. 
### Verify the service is running
`systemctl status ibm-crassd`
### Starting the service
`systemctl start ibm-crassd`
### Stopping the service
`systemctl stop ibm-crassd`
### Enabling the service so it starts automatically on subsequent boots
`systemctl enable ibm-crassd`

### Checking the system logs for problems
The journalctl command is the best way to check for alerts within the Linux Journal. The ibm-crassd service will create entries for problems it encounters and can be useful for debugging setup problems. The following command can be used to find all journal entries. 
`journalctl -u ibm-crassd`

### Checking for forwarded BMC alerts in CSM
To check the power status of the nodes in csm the following command can be used:
`/opt/ibm/csm/bin/csm_ras_event_query -m "bmc.%" -b "2018-07-25 14:00:00.000000" -l "sn01"`
The above command specifies several things, the first option being the message. Here, we use “bmc.%” to get all alerts sourced from the bmc. These are the only types of alerts forwarded by ibm-crassd. The next option -b is used to specify all alerts from a time forward and can be omitted if needed. The example provided displays all alerts since 2:00 PM on July 25, 2018. The last option is used to specify a location. This is optional as well and can be used to specify a specific node. This is listed as xcatNodeName in the configuration file. 

### Checking for forwarded BMC alerts in ESS
To check the power status of the nodes in ESS the following command can be used:
`mmhealth node show POWERHW`
To see more specifics of that output
`mmhealth node show POWERHW -v`
## Viewing system log information about the crassd service
The ibm-crassd service will report alerts into the Linux system logs. These can be viewed with the following command: `journalctl -u ibm-crassd`


