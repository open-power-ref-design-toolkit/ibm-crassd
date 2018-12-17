"""
 Copyright 2017 IBM Corporation

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""
import datetime
import json
import syslog
import config
try:
    import Queue as queue
except ImportError:
    import queue
import traceback
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
    errorString = ""
    
    #check if socket is active by receiving and checking for eof
    try:
        logSocket.settimeout(0.1)
        data = logSocket.recv(4096)
        if not data:
            connected = False
        else:
            connected = True
    except socket.timeout:
        connected = True
    except Exception as e:
        connected = False
        errorString = e
    
        
    # Try 3 times to open the socket connection
    if not connected:
        for x in range(0, 3): 
            try:
                logSocket.connect((host,port))
                connected = True
                break
            except socket.error as erString:
                errorString = erString
                continue
    if not connected:
        if not logstashDown:
            config.errorLogger(syslog.LOG_ERR, "Logstash connection failure: {}".format(errorString))
    return connected

def writeToSocket(logSocket, alert2Send):
    #while not config.killNow:
        sendFailed = False
        #alert2Send = logqueue.get()
        #data2send = json.dumps(alert2Send['logEntry'],sort_keys=False, indent=4, separators=(',', ': ')).encode()
#         eventTime =datetime.datetime.fromtimestamp(int(alert2Send['logEntry']['timestamp'])).strftime("%Y-%m-%d %H:%M:%S")
        data2send = json.dumps(alert2Send['logEntry'], indent=0, separators=(',', ':')).replace('\n','') +"\n"
        data2send = data2send.encode()
        try:
            logSocket.sendall(data2send)
        except socket.error:
            sendFailed = True
        except Exception as e:
            traceback.print_tb(e.__traceback__)
            print(e)
        if sendFailed:
            with config.lock:
                host = config.pluginConfigs['logstash']['host']
                port = int(config.pluginConfigs['logstash']['port'])
                alert2Send['entityAttr']['logstash']['failedFirstTry']= True
            if connectToSocket(logSocket, host, port, alert2Send['entityAttr']['logstash']['receiveEntityDown']):
                sendFailed = False
                try:
                    logSocket.sendall(data2send)
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
        if not sendFailed:
            config.errorLogger(syslog.LOG_INFO, "Sent to logstash: {analert}".format(analert = data2send))
        return not sendFailed
    #logSocket.close()

def initialize():
    config.pluginVars['logstash'] = {}
#     config.pluginVars['logstash']['logstashQueue'] = queue.Queue()
    try:
        host = config.pluginConfigs['logstash']['host']
        port = int(config.pluginConfigs['logstash']['port'])
    except KeyError:
        config.errorLogger(syslog.LOG_ERR, "Host and port configurations missing for logstash plugin. Defaulting to 127.0.0.1:10522")
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
    return writeToSocket(config.pluginVars['logstash']['logstashSocket'], queDict)
    
     