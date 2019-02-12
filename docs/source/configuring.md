# Configuring ibm-crassd
## Manually Configuring Nodes
1.	Open the configuration file located at `/opt/ibm/ras/etc/ibm-crassd.config`. This location may change. 
2.	The `[nodes]` section is located near the top.
3.	Nodes must be added or removed sequentially. For example, node1, node2, node3. 
  a.	See the section on nodes to get an explanation of each of the fields comprising nodes. 
4.	Save and close the file. 
5.	Node changes will be picked up when the service is restarted.
## Node Entry information from the ibm-crassd configuration file (/opt/ibm/ras/etc/ibm-crassd.config) 
Node entries in the crassd configuration file contain several elements. The entire property set must also be encompassed with {}. Below is an example entry.
`node1 = {"bmcHostname": "my-9006-bmc.aus.stglabs.ibm.com", "xcatNodeName": "xcat2", "accessType":"ipmi"}`

Each property comes as a pair on the right hand side of the equals sign. The properties don’t have to be in a specific order. All property IDs and values must be encased in quotes. 
•	bmcHostname: This is the string that is either the BMC hostname or the BMC IP address.  
•	xcatNodeName: This is the hostname of the Host OS. This may also be the IP of the Host OS. 
•	accessType: This tells what the connection method is to the bmc. Currently accepted values are ipmi (for 9006, 5104 Machine Types) and openbmcRest for 8335-GTC and 8335-GTW systems. 
### Setting up the base configuration section
This section allows the user to specify some basic controls for the ibm-crassd service. 
The maxThreads variable is used to define the number of processing threads that are used to collect, parse and forward alerts to the various plugins, based on what is enabled. The current recommended setting for this variable is 40. 

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
