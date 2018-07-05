import datetime
import json
import syslog
import config
import threading
try:
    import Queue as queue
except ImportError:
    import queue

import socket

def connectToSocket(logSocket, host, port, logstashDown):
    """
        Opens a connection to the logstash instance.
        @param logSocket: the socket object to use
        @param host: IP or hostname to connect to
        @param port: port number for logstash service
        @param logstashDown: boolean, True is logstash is down, preventing log flooding of error messages on reconnect
        
        @return: Connection status after attempting to connect. True when successful. 
    """
    connected = False
    # Try 3 times to open the socket connection
    for x in range(0, 3): 
        try:
            logSocket.connect((host,port))
            connected = True
            break
        except socket.error as erString:
            continue
    if not connected:
        if not logstashDown:
            config.errorHandler(syslog.LOG_ERR, "Logstash connection failure: {}".format(erString))
    return connected

def writeToSocket(logSocket, alert2Send):
    #while not config.killNow:
        sendFailed = False
        #alert2Send = logqueue.get()
        try:
            logSocket.sendall(json.dumps(alert2Send['logEntry'],sort_keys=False, indent=4, separators=(',', ': ')))
        except socket.error:
            sendFailed = True
        if sendFailed:
            with config.lock:
                host = config.pluginConfigs['logstash']['host']
                port = int(config.pluginConfigs['logstash']['port'])
                alert2Send['entityAttr']['logstash']['failedFirstTry']= True
            if connectToSocket(logSocket, host, port, alert2Send['entityAttr']['logstash']['receiveEntityDown']):
                sendFailed = False
                try:
                    logSocket.sendall(json.dumps(alert2Send['logEntry'],sort_keys=False, indent=4, separators=(',', ': ')))
                    sendFailed = False
                except socket.error:
                    sendFailed = True
                with config.lock:
                    alert2Send['entityAttr']['logstash']['failedFirstTry']= False
                    alert2Send['entityAttr']['logstash']['receiveEntityDown']= True
            else:
                sendFailed = True
                with config.lock:
                    alert2Send['entityAttr']['logstash']['failedFirstTry']= False
                    alert2Send['entityAttr']['logstash']['receiveEntityDown']= True
        return not sendFailed
    #logSocket.close()

def initialize():
    config.pluginVars['logstash'] = {}
#     config.pluginVars['logstash']['logstashQueue'] = queue.Queue()
    try:
        host = config.pluginConfigs['logstash']['host']
        port = int(config.pluginConfigs['logstash']['port'])
    except KeyError:
        config.errorHandler(syslog.LOG_ERR, "Host and port configurations missing for logstash plugin. Defaulting to 127.0.0.1:10522")
        host="127.0.0.1"
        port=10522
    
    config.pluginVars['logstash']['logstashSocket'] = socket.socket()
    if not connectToSocket(config.pluginVars['logstash']['logstashSocket'], host, port, False):
        return False
#     t = threading.Thread(target=writeToSocket, args=(config.pluginVars['logstash']['logstashSocket'],
#                                                      config.pluginVars['logstash']['logstashQueue']))
#     t.daemon = True
#     t.start()
    return True
   

def notifyLogstash(cerEvent, impactedNode, entityAttr):
    """
         sends alert to logstash
           
         @param cerEvent: dict, the cerEvent to send
         @param impactedNode: the node that had the alert
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
#     config.pluginVars['logstash']['logstashQueue'].put(queDict)
    return writeToSocket(config.pluginVars['logstash']['logstashSocket'], queDict)
    
     