# ibm-crassd
# IBM CRASSD Installation
## Prerequisites version < 0.8-10
-	Python 2.7 or greater
-	Java 1.7.0 or greater
-	python-configparser (found in EPEL)
-	python-websocket-client
-	python-requests if monitoring 8335-GTG, 8335-GTC, 8335-GTW
-	openbmctool if monitoring 8335-GTG, 8335-GTC, 8335-GTW
-	ipmitool
## Prerequisites for ibm-crassd 0.8-10 and above
This version switches to python 3 compatibility
- Python 3.4 or greater
-	Java 1.7.0 or greater
-	python-configparser (found in EPEL)
-	python34-websocket-client
-	python34-requests if monitoring 8335-GTG, 8335-GTC, 8335-GTW
-	openbmctool if monitoring 8335-GTG, 8335-GTC, 8335-GTW
-	ipmitool
-	pexpect
## Installation
### ESS
1.	From the ESS management node type `yum install /install/gss/otherpkgs/rhels7/ppc64le/gss/ibm-crassd-0.8-1.ppc64le.rpm`
### RHEL Based Systems
1.	Transfer the rpm to the management system or service node you wish to install this service on. 
2.	Type `yum install /path/to/rpm`, where /path/to/rpm is the full path to the rpm you just copied to the system. 
## Upgrading:
1.	Backup the ibm-crassd.config file found at `/opt/ibm/ras/etc/ibm-crassd.config`
2.	Backup the bmclastreports.ini file found at `/opt/ibm/ras/etc/bmclastreports.ini`
3.	Stop the service using `systemctl stop ibm-crassd`
4.	Install ibm-crassd using the instructions above.
5.	Restore the two backed up files to their original locations.
6.	Start the service using `systemctl start ibm-crassd`. 
## Configuration
### Manually Configuring Nodes
1.	Open the configuration file located at `/opt/ibm/ras/etc/ibm-crassd.config`
2.	The `[nodes]` section is located near the top.
3.	Nodes must be added or removed sequentially. For example, node1, node2, node3. 
  a.	See the section on nodes to get an explanation of each of the fields comprising nodes. 
4.	Save and close the file. 
5.	Node changes will be picked up when the service is restarted.
### Node Entry information from the ibm-crassd configuration file (/opt/ibm/ras/etc/ibm-crassd.config) 
Node entries in the crassd configuration file contain several elements. The entire property set must also be encompassed with {}. Below is an example entry.
`node1 = {"bmcHostname": "my-9006-bmc.aus.stglabs.ibm.com", "xcatNodeName": "xcat2", "accessType":"ipmi"}`

Each property comes as a pair on the right hand side of the equals sign. The properties don’t have to be in a specific order. All property IDs and values must be encased in quotes. 
•	bmcHostname: This is the string that is either the BMC hostname or the BMC IP address.  
•	xcatNodeName: This is the hostname of the Host OS. This may also be the IP of the Host OS. 
•	accessType: This tells what the connection method is to the bmc. Currently accepted values are ipmi (for 9006, 5104 Machine Types) and openbmcRest for 8335-GTC and 8335-GTW systems. 
### Setting up the base configuration section
This section allows the user to specify some basic controls for the ibm-crassd service. 
The maxThreads variable is used to define the number of processing threads that are used to collect, parse and forward alerts to the various plugins, based on what’s enabled. The current recommended setting for this variable is 40. 
## Configuration for integrating into ESS
1.	Open the configuration file in `/var/mmfs/mmsysmon/mmsysmonitor.conf`.
2.	Locate the `[general]` section of the file.
3.	Add entry: `powerhw_enabled = true`
4.	Save and close the file. 
5.	Open the configuration file located at `/opt/ibm/ras/etc/ibm-crassd.config`
6.	Locate the `[notify]` section
7.	Set `ESS=True`
8.	Set `CSM=False`
9.	Enable any other plugins by setting their name to True. Disable any plugins you do not wish to use by setting their value to False.
a.	For example `ESS=True`, `CSM=False`, `logstash=False`. 
10.	Save and close the file.
11.	Type `mmsysmoncontrol restart` to reload the mmhealth service and pick up the changes. 
12.	Start the service with `systemctl start ibm-crassd`. It is also recommended to enable the service so it starts automatically when the Host OS starts. This is done using the command `systemctl enable ibm-crassd`
## Configuration for integrating into CSM
1.	Ensure CSM services are running according to CSM documentation
•	csmrestd must be running on the same node as the ibm-crassd service.
2.	Open the configuration file located at `/opt/ibm/ras/etc/ibm-crassd.config`
3.	Locate the `[notify]` section
4.	Set `ESS=False`
5.	Set `CSM=True`
6.	Enable any other plugins by setting their name to True. Disable any plugins you do not wish to use by setting their value to False.
•	For example `ESS=False`, `CSM=True`, `logstash=True`. 
7.	Locate the `[csm]` section of the configuration file. 
•	Specify the IP address and Port for the csmrestd service. The defaults are specified and will work with most configurations.  
8.	Save and close the file. 
9.	Start the service with `systemctl start ibm-crassd`. It is also recommended to enable the service so it starts automatically when the Host OS starts. This is done using the command `systemctl enable ibm-crassd`

## Configuration for integrating with logstash
1.	Ensure logstash services are running according to logstash documentation
2.	Open the configuration file located at `/opt/ibm/ras/etc/ibm-crassd.config`
3.	Locate the `[notify]` section
4.	Set `logstash=True`
5.	Enable any other plugins by setting their name to True. Disable any plugins you do not wish to use by setting their value to False.
•	For example `ESS=False`, `CSM=True`, `logstash=True`. 
6.	Locate the [logstash] section of the configuration file. 
•	Specify the IP address and Port for the logstash service. The defaults are specified. 
7.	Save and close the file. 
8.	Start the service with `systemctl start ibm-crassd`. It is also recommended to enable the service so it starts automatically when the Host OS starts. This is done using the command `systemctl enable ibm-crassd`

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

