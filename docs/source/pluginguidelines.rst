====================================
Guidelines for creating a new plugin
====================================

Mandatory functions
===================
1. initialize() function to test basic connection to the location for pushing alerts to
2. notify<Endpoint> function. This is called by ibm-crassd to push the alert to the endpoint

Data Format for the ibm-crassd structures
=========================================
Event
#########################################
The following are the common properties that appear on every event. Many of these properties can be customized in the openbmctool policy table. 

.. code-block:: JSON

    {
        "CerID": "string. EventID which, can be found in IBM Knowledge Center per MTM",
        "message": "string. Description of the problem",
        "logNum": "string. logPostion as a number",
        "severity": "string. Severity of the event. One of Critical, Warning, Info",
        "subSystem": "string. Description of the part of the system impacted",
        "eventType": "string. Description of the type of event",
        "serviceable": "string. Indicates if a human needs to take action on the log entry",
        "callHome": "string. Indicates if the alert will be automatically sent to support in an environment with the IBM CALL HOME service enabled",
        "compInstance": "integer. Indicates a slot or socket number for the specified component",
        "lengthyDescription": "string. A verbose description of the problem",
        "LogSource": "string. The source of the log entry",
        "RelatedEventIDs": "string. A dictionary containing IDs related to this one. Not currently used",
        "timestamp": "string. The timestamp for the log entry as a UNIX timestamp (Seconds since epoch)",
        "vmMigration": "string. Indicates if workload should be migrated from the system. Not currently used."
    }

Impacted Node
#########################################
The following information provides details about the node structure. The following detials provide information about the python dictionary used, along with the type. 

.. code-block:: JSON

    {
      "bmcHostname": "string. Hostname or IP of the BMC",
      "xcatNodeName": "string. Reference description for the node, commonly host side hostname",
      "accessType": "string. One of ipmi, openbmcRest, redfish. Redfish not currently implemented.",
      "username": "string. Username for the BMC",
      "password": "string. Password for the specified BMC username",
      "dupTimeIDList": "list of strings. List of IDs that occurred most recently with the same timestamp",
      "lastLogTime": "integer. Timestamp of the last log(s) entry. UNIX timestamp",
      "pollFailedCount": "integer. Count of the number of times a bmc poll has failed. Resets after a successful poll"
    }

entityAttr
#########################################
This contains a set of information for the endpoint that is being reported to. ibm-crassd tracks the status of endpoints where alerts are pushed to, and the plugin is required to update these attributes appropriately. 

.. code-block:: JSON

    {
      "function": "pointer. A pointer to the notify function",
      "receiveEntityDown": "Boolean indicator if the plugin is able to contact the receiving entity. For example, not network reachable.",
      "failedFirstTry": "Boolean. if the first attempt to send the alert has failed. The plugin should attempt at least twice.",
      "successfullyReported": "Boolean. True, if the alert was successfully reported to the endpoint. If successful, receiveEntityDown should be set to False, and also failedFirstTry should be set to False"
    }

Creating Configurable options
=========================================
1. Add options to the ibm-crassd.config file, creating a section for your plugin name. ex: ``[pluginName]``  
2. import the config module to your plugin.
3. Plugin variables will come in three pieces found in the following sections with detailed descriptions and informaiton about accessing them.
4. Configuration options should be added to the ibm-crassd.config file, or create your own config file in your plugin's directory and load the settings during plugin initialization.

Plugin Configuration Values from config file
##############################################
These settings are stored into a dictionary in the publicly available config variable. This is done to support the multi-threading approach with ibm-crassd's design. Accessing these is simple by using the following syntax.

``mySetting = config.pluginConfigs['pluginName']['mySetting']``

These settings should be validated in the plugin initialization section. Invalid settings for your plugin should halt ibm-crassd on startup. 

Plugin Policies for alerts
#########################################
This setting is stored into a dictionary for use by multiple threads. The policy is loaded from the file system one time and cached for future use. Policy updates require a restart of the ibm-crassd service. The policy table should be loaded during the initialization of the plugin. Failures should halt the ibm-crassd service.

``myPolicy = config.pluginConfigs['pluginName']['myPolicy']``

Storing plugin Variables for global use
#########################################
If variables for your plugin need to be stored so they are centralized for access across multiple threads, the following mechanism can be used. 

``myVar = config.pluginVars['pluginName']['myVariable']``

It is the responsibility of the plugin to use proper thread locks when setting this variable outside of the initialization. 

.. code-block:: python
   
    import config
    #some code processing an alert
    #=======================================================
    with config.lock:
      config.pluginVars['pluginName'][myVariable] = myValue

    #=======================================================
    #Continue with operations

Reporting Errors to the system journal
=========================================
If your plugin is experiencing issues or needs to write debug messages to the system journal a mechanism is provided. Keep in mind debug messages should use the syslog ``LOG_DEBUG`` severity, and will only appear in the journal if the ibm-crassd configuration has debug messages available.

To create a journal entry, a simple method is called with two variables. The first is the syslog severity, which uses the syslog library values such as ``LOG_INFO`` and a string describing the problem or statement being made. 

The following is an example of creating a log entry from a plugin:

.. code-block:: python

    import config
    # Missing configuration for a remote server
    config.errorLogger(syslog.LOG_ERR, "Unable to find configuration for the remote logstash server. Defaulting to 127.0.0.1:10522")


