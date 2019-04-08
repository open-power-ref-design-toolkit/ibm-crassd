
def initialize():
    """
        Steps that you need to do for setup. see example with configuring ports below
    """
    config.pluginVars['pluginName'] = {}
    try:
        host = config.pluginConfigs['pluginName']['host']
        port = int(config.pluginConfigs['pluginName']['port'])
    except KeyError:
        config.errorLogger(syslog.LOG_ERR, "Host and port configurations missing for pluginName plugin. Defaulting to 127.0.0.1:10522")
        host="127.0.0.1"
        port=10522
    
    config.pluginVars['pluginName']['mySocket'] = socket.socket()
    if not connectToSocket(config.pluginVars['pluginName']['mySocket'], host, port, False):
	#returning false will cause the plugin to not load and stop the ibm-crassd service from starting
        return False

    #returning true indicates initialization was successful
    return True
   

def notifyPluginName(cerEvent, impactedNode, entityAttr):
    """
         parses log entry from ibmcrassd and sends it to PluginName
           
         @param cerEvent: dict, the cerEvent (logEntry) to send
         @param impactedNode: the node that had the alert dictionary
         @param entityAttr: dictionary, contains the list of known attributes for the entity to report to
         @return: True if notification was successful, false if it was unable to send the alert
    """
    
    newAlert = {'type':'ibm-crasssd-bmc-alerts', 'source': impactedNode, 
                'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'data': cerEvent
             }
    queDict = {}
    queDict['entityAttr'] = entityAttr
    queDict['logEntry'] = newAlert
    return writeToSocket(config.pluginVars['pluginName']['mySocket'], queDict)
    
     
