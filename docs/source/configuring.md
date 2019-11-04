# Configuring ibm-crassd
## Manually Configuring Nodes
1.	Open the configuration file located at `/opt/ibm/ras/etc/ibm-crassd.config`. This location may change. 
2.	The `[nodes]` section is located near the top.
3.	Nodes must be added or removed sequentially. For example, node1, node2, node3. 
  a.	See the section on nodes to get an explanation of each of the fields comprising nodes. 
4.	Save and close the file. 
5.	Node changes will be picked up when the service is restarted.
## Node Entry information from the ibm-crassd configuration file (/opt/ibm/ras/etc/ibm-crassd.config) 
Node entries in the ibm-crassd configuration file contain several elements. The entire property set must also be encompassed with {}. Below is an example entry.
`node1 = {"bmcHostname": "my-9006-bmc.aus.stglabs.ibm.com", "xcatNodeName": "xcat2", "accessType":"ipmi"}`

Each property comes as a pair on the right hand side of the equals sign. The properties don’t have to be in a specific order. All property IDs and values must be encased in quotes. 
•	bmcHostname: This is the string that is either the BMC hostname or the BMC IP address.  
•	xcatNodeName: This is the hostname of the Host OS. This may also be the IP of the Host OS. 
•	accessType: This tells what the connection method is to the BMC. Currently accepted values are ipmi (for 9006, 5104 Machine Types) and openbmcRest for 8335-GTC and 8335-GTW systems. 
## Setting up the base configuration section
This section allows the user to specify some basic controls for the ibm-crassd service. 
- The maxThreads variable is used to define the number of processing threads that are used to collect, parse and forward BMC alerts to the various plugins, based on what is enabled. The current recommended setting for this variable is 40. 
- The enableTelemetry option can be set to **True** to turn on telemetry streaming, or **False** to disable telemetry streaming.
- The nodesPerGathererProcess option is used to set the number of BMCs assigned to a sub-process. This can allow performance to be finely tuned for the telemetry streaming service. The default setting is 10. 
- The enableDebugMsgs option can be set to True when trying to debug a difficult problem or to help find problems with initial setup. The default setting is False. 

## Configuration of the Tracker File Storage Location
Configuring where to put tracker files can be found under the section of [lastReports]. This directory is also used to specify where the configuration file for ibm-crassd is located. The default location is **/opt/ibm/ras/etc**
To support multiple tracker and configuration files in the same storage location (directory), it is imperative to name the tracker and configuration files with the format **<nodewithcrassd_hostname>.ibm-crassd.config**. The ibm-crassd service places highest priority when the hostname.ibm-crassd.config file name format is used.

## Configuration of Analysis Scripts for ibm-crassd
Deep analysis of alerts is sometimes wanted or desired. The ibm-crassd service supports this behavior by allowing the creation of analysis files, and then adding configuration options for them.
To create and run analysis scripts, a few things must be done. 
1. Create a python module, with the following name format analyze**alertID**.py.
2. Add a configuration option to ibm-crassd.config file under the analysis section using the following format **alertID**=**option**. 
3. Configure the setting to one of the following three options.
	- **clear** - This option, after a positive analysis return, will have ibm-crassd delete the alert from the BMC which surfaced it. 
	- **filter** - This option, will only cause ibm-crassd to filter the alert so it's not sent to the varying reporting plugins. It will leave the alert on the BMC. 
	- **disable** - This option will prevent the analysis script from being run, and the alert will be forwarded as normal. 
# Plugin Configuration
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



