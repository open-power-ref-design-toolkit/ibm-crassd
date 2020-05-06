#!/usr/bin/python3 -u
# 
#  Copyright 2017 IBM Corporation
# 
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
# 
#        http://www.apache.org/licenses/LICENSE-2.0
# 
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
# 

"""
    This module establishes websocket connections to all the managed bmcs then starts a socket based server.
    With the socket server, clients can subscribe to a stream of sensor readings using filters. Filters
    can be based on sensor name and sensor type. A client can also adjust the frequency to a maximum rate of
    once per second. 
    
    This module when establishing websocket connections, will assign a maximum of 50 nodes per subprocess. 
    Each of the subprocesses will collect the push notification, and process it into the sensor data dictionary
    structure. The socket server also establishes it's own subprocess so it can handle dealing with multiple
    clients. Each websocket subprocess will receive an average rate of 2.5 Mbps worth per 50 monitored nodes.
    
    The socket server will listen on all established network interfaces including the local host. This allows
    telemetry data to be streamed to a local service, or to a remote monitoring application. 
    
    In the event of a connection loss to a BMC this module will also work on establishing a new connection
    to the BMC and should only surface one connection loss message after 3 attempts of failing to reconnect. 
    This error message will be sent to the established plugins to forward to a configured log manager like ELK. 
"""
import websocket
import time
import sys
import ssl
import json
import requests
import threading
import multiprocessing
try:
    import queue
except ImportError:
    import Queue as queue
import traceback
import subprocess
import os
import socket
import struct
import config
import syslog
import signal
import select


def get_size(obj, seen=None):
    """Recursively finds size of objects"""
    size = sys.getsizeof(obj)
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    # Important mark as seen *before* entering recursion to gracefully handle
    # self-referential objects
    seen.add(obj_id)
    if isinstance(obj, dict):
        size += sum([get_size(v, seen) for v in obj.values()])
        size += sum([get_size(k, seen) for k in obj.keys()])
    elif hasattr(obj, '__dict__'):
        size += get_size(obj.__dict__, seen)
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
        size += sum([get_size(i, seen) for i in obj])
    return size

def sigHandler(signum, frame):
    """
         Used to handle kill signals from the operating system
           
         @param signum: integer, the signal number received from the os
         @param frame; contextual frame
         @return: set global kill now to true and lead to termination
    """ 
    if (signum == signal.SIGTERM or signum == signal.SIGINT):
        global killSig
        killSig.set()
    else:
        config.errorLogger(syslog.LOG_DEBUG, "Signal received: {sigNum}".format(sigNum=signum))

def getMemInfo(signum, frame):
    global pidList
    if (signum ==signal.SIGUSR1):
        lines = ''
        mainpid = os.getppid()
        with open('/proc/{apid}/status'.format(apid=mainpid), 'r') as f:
            lines = f.readlines()
        for line in lines:
            if 'VmSize' in line:
                memsize = int(line.split(' ')[-2])
            if 'VmRSS' in line:
                memrsize = int(line.split(' ')[-2])
                config.errorLogger(syslog.LOG_DEBUG, 'Parent PID: {apid}  VMUsage: {memsize} kB Resident Set Size: {memrsize} kB'.format(apid=mainpid, memsize=memsize, memrsize=memrsize))
                break
        for apid in pidList:
            with open('/proc/{apid}/status'.format(apid=apid), 'r') as f:
                lines = f.readlines()
            for line in lines:
                if 'VmSize' in line:
                    memsize = int(line.split(' ')[-2])
                if 'VmRSS' in line:
                    memrsize = int(line.split(' ')[-2])
                    config.errorLogger(syslog.LOG_DEBUG, 'PID: {apid}  Usage: {memsize} kB Resident Set Size: {memrsize} kB'.format(apid=apid, memsize=memsize, memrsize=memrsize))
                    break
                
def gathererDumpMem(signum, fname):
    global sensorData
    global gathererNodeList
    global sensorList
    global messageQueue
    global sendQueue
    if (signum ==signal.SIGUSR1):
        myPID = os.getpid()
        curtime = time.strftime("%Y-%m-%d %H:%M:%S")
        with open('/tmp/crassd-gatherer-{apid}-{curTime}.txt'.format(apid=myPID, curTime=curtime), 'w') as f:
            f.write('---------Sensor Data --------\n')
            f.write('Size: {memsize} B\n'.format(memsize = get_size(sensorData)))
            f.write('{data}\n\n'.format(data=json.dumps(sensorData)))
            f.write('--------gathererNodeList-------------------\n')
            f.write('Size: {memsize} B\n'.format(memsize =get_size(gathererNodeList)))
            f.write('{data}\n\n'.format(data=repr(gathererNodeList)))
            f.write('--------config.NodeList-------------------\n')
            f.write('Size: {memsize} B\n'.format(memsize =get_size(config.mynodelist)))
            f.write('{data}\n\n'.format(data=repr(config.mynodelist)))
            f.write('--------sensorList-------------------\n')
            f.write('Size: {memsize} B\n'.format(memsize =get_size(sensorList)))
            f.write('{data}\n\n'.format(data=repr(sensorList)))
            f.write('--------messageQueue-------------------\n')
            f.write('Queue length: {memsize} \n\n'.format(memsize =messageQueue.qsize()))
            f.write('--------sendQueue-------------------\n')
            f.write('Queue length: {memsize} \n'.format(memsize =sendQueue.qsize()))

def sockServerDumpMem(signum, fname):
    global sensorData
    global telemUpdateQueue
    if (signum ==signal.SIGUSR1):
        myPID = os.getpid()
        curtime = time.strftime("%Y-%m-%d %H:%M:%S")
        with open('/tmp/crassd-socketServer-{apid}-{curTime}.txt'.format(apid=myPID, curTime=curtime), 'w') as f:
            f.write('---------Sensor Data --------\n')
            f.write('Size: {memsize}\n'.format(memsize =get_size(sensorData)))
            f.write('{data}\n\n'.format(data=repr(sensorData)))
            f.write('--------config.NodeList-------------------\n')
            f.write('Size: {memsize}\n'.format(memsize =get_size(config.mynodelist)))
            f.write('{data}\n\n'.format(data=repr(config.mynodelist)))
            f.write('--------telemUpdateQueue-------------------\n')
            f.write('Queue length: {memsize}\n'.format(memsize =telemUpdateQueue.qsize()))
def killQueueChecker():
    global killNow
    global killQueue
    while True:
        killNow = killQueue.get()
        break

def connectionErrHandler(jsonFormat, errorStr, err):
    """
         Error handler various connection errors to bmcs
           
         @param jsonFormat: boolean, used to output in json format with an error code. 
         @param errorStr: string, used to color the text red or green
         @param err: string, the text from the exception 
    """ 
    if errorStr == "Timeout":
        if not jsonFormat:
            return("FQPSPIN0000M: Connection timed out. Ensure you have network connectivity to the bmc")
        else:
            conerror = {}
            conerror['CommonEventID'] = 'FQPSPIN0000M'
            conerror['sensor']="N/A"
            conerror['state']="N/A"
            conerror['additionalDetails'] = "N/A"
            conerror['Message']="Connection timed out. Ensure you have network connectivity to the BMC"
            conerror['LengthyDescription'] = "While trying to establish a connection with the specified BMC, the BMC failed to respond in adequate time. Verify the BMC is functioning properly, and the network connectivity to the BMC is stable."
            conerror['Serviceable']="Yes"
            conerror['CallHomeCandidate']= "No"
            conerror['Severity'] = "Critical"
            conerror['EventType'] = "Communication Failure/Timeout"
            conerror['VMMigrationFlag'] = "Yes"
            conerror["AffectedSubsystem"] = "Interconnect (Networking)"
            conerror["timestamp"] = str(int(time.time()))
            conerror["UserAction"] = "Verify network connectivity between the two systems and the bmc is functional."
            eventdict = {}
            eventdict['event0'] = conerror
            eventdict['numAlerts'] = '1'
            
            errorMessageStr = errorMessageStr = json.dumps(eventdict, sort_keys=True, indent=4, separators=(',', ': '), ensure_ascii=False)
            return(errorMessageStr)
    elif errorStr == "ConnectionError":
        if not jsonFormat:
            return("FQPSPIN0001M: " + str(err))
        else:
            conerror = {}
            conerror['CommonEventID'] = 'FQPSPIN0001M'
            conerror['sensor']="N/A"
            conerror['state']="N/A"
            conerror['additionalDetails'] = str(err)
            conerror['Message']="Connection Error. View additional details for more information"
            conerror['LengthyDescription'] = "A connection error to the specified BMC occurred and additional details are provided. Review these details to resolve the issue."
            conerror['Serviceable']="Yes"
            conerror['CallHomeCandidate']= "No"
            conerror['Severity'] = "Critical"
            conerror['EventType'] = "Communication Failure/Timeout"
            conerror['VMMigrationFlag'] = "Yes"
            conerror["AffectedSubsystem"] = "Interconnect (Networking)"
            conerror["timestamp"] = str(int(time.time()))
            conerror["UserAction"] = "Correct the issue highlighted in additional details and try again"
            eventdict = {}
            eventdict['event0'] = conerror
            eventdict['numAlerts'] = '1'
            
            errorMessageStr = json.dumps(eventdict, sort_keys=True, indent=4, separators=(',', ': '), ensure_ascii=False)
            return(errorMessageStr)
    elif errorStr == "LoginFailed":
        if not jsonFormat:
            return("FQPSPSE0067F: " + str(err))
        else:
            conerror = {}
            conerror['CommonEventID'] = 'FQPSPSE0067F'
            conerror['sensor']="N/A"
            conerror['state']="N/A"
            conerror['additionalDetails'] = str(err)
            conerror['Message']="Unable to login to the BMC. Ensure the credentials provided are correct."
            conerror['LengthyDescription'] = "A failure response was received from the BMC, indicating the login was not successful"
            conerror['Serviceable']="No"
            conerror['CallHomeCandidate']= "No"
            conerror['Severity'] = "Warning"
            conerror['EventType'] = "Administrative"
            conerror['VMMigrationFlag'] = "Yes"
            conerror["AffectedSubsystem"] = "Systems Management - Security"
            conerror["timestamp"] = str(int(time.time()))
            conerror["UserAction"] = "Correct the issue highlighted in additional details and try again"
            eventdict = {}
            eventdict['event0'] = conerror
            eventdict['numAlerts'] = '1'
            
            errorMessageStr = json.dumps(eventdict, sort_keys=True, indent=4, separators=(',', ': '), ensure_ascii=False)
            return(errorMessageStr)
    else:
        return("Unknown Error: "+ str(err))


def login(host, username, pw,jsonFormat):
    """
         Logs into the BMC and creates a session
           
         @param host: string, the hostname or IP address of the bmc to log into
         @param username: The user name for the bmc to log into
         @param pw: The password for the BMC to log into
         @param jsonFormat: boolean, flag that will only allow relevant data from user command to be display. This function becomes silent when set to true. 
         @return: Session object
    """
    if(jsonFormat==False):
        config.errorLogger(syslog.LOG_DEBUG, "Attempting login to: {bmc}".format(bmc=host))
    httpHeader = {'Content-Type':'application/json'}
    mysess = requests.session()
    try:
        r = mysess.post('https://'+host+'/login', headers=httpHeader, json = {"data": [username, pw]}, verify=False, timeout=30)
        loginMessage = r.json()
        if (loginMessage['status'] != "ok"):
            return (connectionErrHandler(jsonFormat, "LoginFailed", "Login Failed: {descript}, {statusCode}".format(descript=loginMessage['data']['description'], statusCode=loginMessage['message'])))
        return mysess
    except(requests.exceptions.Timeout):
        return (connectionErrHandler(jsonFormat, "Timeout", None))
    except(requests.exceptions.ConnectionError) as err:
        return (connectionErrHandler(jsonFormat, "ConnectionError", err))
    except json.decoder.JSONDecodeError as e:
        config.errorLogger(syslog.LOG_CRIT, "Failed parse login response from BMC: {bmc}".format(bmc=host))
        return None
    except Exception as e:
        config.errorLogger(syslog.LOG_CRIT, "Failed to login to the BMC: {bmc}".format(bmc=host))
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
        traceback.print_tb(e.__traceback__)
        return None

def logout(host, username, pw, session, jsonFormat):
    """
         Logs out of the bmc and terminates the session

         @param host: string, the hostname or IP address of the bmc to log out of
         @param username: The user name for the bmc to log out of
         @param pw: The password for the BMC to log out of
         @param session: the active session to use
         @param jsonFormat: boolean, flag that will only allow relevant data from user command to be display. This function becomes silent when set to true.
    """
    global logoutAPItime
    jsonHeader = {'Content-Type' : 'application/json'}
    try:
        r = session.post('https://'+host+'/logout', headers=jsonHeader,json = {"data": [username, pw]}, verify=False, timeout=60)
    except(requests.exceptions.Timeout):
        config.errorLogger(syslog.LOG_CRIT,connectionErrHandler(jsonFormat, "Timeout", None))
    if(jsonFormat==False):
        if r.status_code == 200:
            config.errorLogger(syslog.LOG_DEBUG,'User {usr} has been logged out from {bmc}'.format(usr=username, bmc=host))

def getNodePowerState(host, session, xcatNodeName, node):
    httpHeader = {'Content-Type':'application/json'}
    url="https://"+host+"/xyz/openbmc_project/state/chassis0/attr/CurrentPowerState"
    validResponse = True
    try:
        res = session.get(url, headers=httpHeader, verify=False, timeout=30)
    except(requests.exceptions.Timeout):
        return(connectionErrHandler(True, "Timeout", None))
    try:
        chassisPowerState = res.json()['data']
    except json.decoder.JSONDecodeError as e:
        config.errorLogger(syslog.LOG_CRIT, "Failed to parse chassis power state response from BMC: {bmc}".format(bmc=host))
        validResponse = False
    except KeyError as e:
        config.errorLogger(syslog.LOG_CRIT, "Invalid chassis power state response from BMC: {bmc}".format(bmc=host))
        validResponse = False
    if res.status_code != 200:
        validResponse = False
        config.errorLogger(syslog.LOG_ERR, "BMC Error Response received when querying chassis power state. ")
        if 'description' in chassisPowerState:
            config.errorLogger(syslog.LOG_ERR, "BMC Error Description: {errDescr}".format(errDescr=chassisPowerState['description']))
    if validResponse:
        node['NodeState'] = 'Powered {state}'.format(state = chassisPowerState.split('.')[-1])
        node['LastUpdateReceived'] = int(time.time())

def initSensors(host, session, xcatNodeName, node):
    '''
        Gets initial values for sensors
    '''
    global sensorList
    global sensorData
    httpHeader = {'Content-Type':'application/json'}
    url="https://"+host+"/xyz/openbmc_project/sensors/enumerate"
    try:
        res = session.get(url, headers=httpHeader, verify=False, timeout=30)
    except(requests.exceptions.Timeout):
        return(connectionErrHandler(True, "Timeout", None))
    validResponse = True
    try:
        sensors = res.json()["data"]
    except json.decoder.JSONDecodeError as e:
        config.errorLogger(syslog.LOG_CRIT, "Failed to parse sensor readings response from BMC: {bmc}".format(bmc=host))
        validResponse = False
    except KeyError as e:
        config.errorLogger(syslog.LOG_CRIT, "Invalid sensor readings response from BMC: {bmc}".format(bmc=host))
        validResponse = False
    if res.status_code != 200:
        validResponse = False
        config.errorLogger(syslog.LOG_ERR, "BMC Error Response received when querying sensor values. ")
        if 'description' in sensors:
            config.errorLogger(syslog.LOG_ERR, "BMC Error Description: {errDescr}".format(errDescr=sensors['description']))
        if 'exception' in sensors:
            config.errorLogger(syslog.LOG_DEBUG, "BMC Exception: {bmcException}".format(bmcException=sensors['exception']))
    
    if validResponse:
        try:
            # Do not update the global sensor list. This can vary between nodes, use the node['SensorList']
            senslist = node['SensorList']
            update = False
            for key in sensors:
                if 'PowerSupplyRedundancy' in key:
                    continue
                if key not in senslist:
                    senslist.append(key)
                    update = True

                keyparts = key.split('/')
                sensorType = keyparts[-2]
                sensorname = keyparts[-1]
                if 'inventory' in sensorname:
                    continue
                if 'chassis' in sensorname:
                    continue
                for sname in senslist:
                    if sensorname in sname:
                        sensorData[xcatNodeName][sensorname] = {}
                if('Scale' in sensors[key]): 
                        scale = 10 ** sensors[key]['Scale'] 
                else: 
                    scale = 1
                typeUnitDict = {'temperature': 'DegreesC', 
                                 'power': 'Watts',
                                 'fan_tach': 'RPMS',
                                 'voltage': 'Volts',
                                 'current': 'Amperes'}
                for sname in senslist:
                    if sensorname in sname:
                        sensorData[xcatNodeName][sensorname]['scale'] = scale
                        sensorData[xcatNodeName][sensorname]['value'] =sensors[key]['Value']
                        sensorData[xcatNodeName][sensorname]['type'] = (sensorType, sensors[key]['Unit'].split('.')[-1])
                for key in senslist:
                    if key not in sensors:
                        sensName = key.split('/')[-1]
                        sensorData[xcatNodeName][sensName] = {}
                        sensorData[xcatNodeName][sensorname]['scale'] = None
                        sensorData[xcatNodeName][sensorname]['type'] = None
                        sensorData[xcatNodeName][sensName]['value'] = None
            if update:
                node['SensorList'] = senslist
                node['LastUpdateReceived'] = int(time.time())
        except Exception as e:
            config.errorLogger(syslog.LOG_ERR, 'Error Processing response from BMC for sensor list')
            config.errorLogger(syslog.LOG_DEBUG, "BMC message was: {msg}".format(msg=sensors))
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
            traceback.print_tb(e.__traceback__)
            return
        for key in sensorList:
            if "logging" in key:
                continue
            if 'state/chassis0' in key:
                continue
            if 'control/occ' in key:
                continue
            keyparts = key.split('/')
            stype = keyparts[-2]
            sname = keyparts[-1]
            if sname not in sensorData[xcatNodeName]:
                sensorData[xcatNodeName][sname] = {}
                sensorData[xcatNodeName][sname]['value'] = None
                sensorData[xcatNodeName][sname]['type'] = (stype, typeUnitDict[stype])
                if 'fan_tach' in stype:
                    sensorData[xcatNodeName][sname]['scale'] = 1
                elif 'power' in stype:
                    sensorData[xcatNodeName][sname]['scale'] = 10 ** -6
                else:
                    sensorData[xcatNodeName][sname]['scale'] = 10 ** -3
    
def processMessages():
    global killSig
    global sensorData
    ##node properties {nodeName:{'LastUpdateReceived':'UNIXTimestamp','NodeState':'Powered On/Off', 'Connected': True | False,'SensorList':,['list','of','sensor','paths']}
    while True:
        if killSig.is_set():
            break
        text = messageQueue.get()
        try:
            updateTime = False
            message = json.loads(text['msg'])
            if 'logging' in message['path']:
                updateTime = True
                config.errorLogger(syslog.LOG_DEBUG, "Event notification received for {bmc}.".format(bmc=text['node']['bmcHostname']))
            elif 'sensors' in message["path"]:
                updateTime = True
                sensorName = message["path"].split('/')[-1]
                if 'Value' in message['properties']:
                    sensorData[text['node']['xcatNodeName']][sensorName]['value'] = message['properties']['Value']
                    if 'type' not in sensorData[text['node']['xcatNodeName']][sensorName]:
                        sensorData[text['node']['xcatNodeName']][sensorName]['type'] = None
                        sensorData[text['node']['xcatNodeName']][sensorName]['scale'] = None
                        wspm = text['node']['websocket']
                        wspm.close()
                        text['node']['Connected'] = False
#                 config.errorLogger(syslog.LOG_DEBUG, "Updated sensor readings for {bmc}.".format(bmc=text['node']['bmcHostname']))
            elif 'control' in message['path']:
                updateTime = True
                wspm = text['node']['websocket']
                wspm.close()
                text['node']['Connected'] = False
                config.errorLogger(syslog.LOG_DEBUG, "OCC state changed for {node}.".format(node=text['node']['xcatNodeName']))
            elif 'state' in message['path']:
                updateTime = True
                if 'CurrentPowerState' in message['properties']:
                    wspm = text['node']['websocket']
                    wspm.close()
                    text['node']['Connected'] = False
                    config.errorLogger(syslog.LOG_INFO,'Power state change detected for node {node}. Received state: {msgrcvd}'.format(node=text['node']['xcatNodeName'],msgrcvd=' '.join(message['properties']['CurrentPowerState'].split('.')[-2:])))
                    if 'PowerState.On' in message['properties']['CurrentPowerState']:
                        text['node']['NodeState'] = "Powered On"
                    else:
                        text['node']['NodeState'] = "Powered Off"
                    config.errorLogger(syslog.LOG_DEBUG, "Power state changed for node {node}.".format(node=text['node']['xcatNodeName']))
                else:
                    pass
            else:
                sendQueue.put(text['node'])
            if updateTime:
                text['node']['LastUpdateReceived'] = int(time.time())
        except Exception as e:
            config.errorLogger(syslog.LOG_WARNING, "Error encountered processing BMC message from {bmc}".format(bmc=text['node']['bmcHostname']))
            config.errorLogger(syslog.LOG_DEBUG, "BMC message was: {msg}".format(msg=text['msg']))
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
            traceback.print_tb(e.__traceback__)
            
        messageQueue.task_done()

def getNode(bmcURL):
    thisNode = {}
    for anode in config.mynodelist:
        if anode['bmcHostname'] in bmcURL:
            thisNode = anode
            break
#         if 'telemlistener' in anode and anode['telemlistener'] is not None:
#             if anode['telemlistener'].getName() == threading.currentThread().getName():
#                 thisNode = anode
#                 break
    return thisNode
            
def on_message(ws, message):
    thisNode = getNode(ws.url)
    thisNode['down'] = False
    messageQueue.put({'node': thisNode,'msg':message})
#     config.errorLogger(syslog.LOG_DEBUG, "Got Sensor reading from {bmc}".format(bmc=thisNode['bmcHostname']))

def on_error(ws, error):
    thisNode = getNode(ws.url)
    if len(thisNode) >0:
        if thisNode['websocket'] == ws:
            thisNode['telemlistener'] = None
        config.errorLogger(syslog.LOG_DEBUG, "Websocket error for {bmc}, details: {err}".format(bmc=thisNode['bmcHostname'], err=error))
        thisNode['LastUpdateReceived'] = int(time.time())
        thisNode['Connected'] = False
        try:
            logout(thisNode['bmcHostname'],thisNode['username'], thisNode['password'], thisNode['session'], True)
        except Exception as e:
            config.errorLogger(syslog.LOG_DEBUG, "Failed to log out of the bmc {bmc} after a websocket error.".format(bmc=thisNode['bmcHostname']))

def on_close(ws):
    thisNode = getNode(ws.url)
    if len(thisNode) >0:
        if thisNode['websocket'] == ws:
            thisNode['telemlistener'] = None
        config.errorLogger(syslog.LOG_DEBUG, "Websocket closed for {bmc}".format(bmc=thisNode['bmcHostname']))
        thisNode['LastUpdateReceived'] = int(time.time())
        thisNode['Connected'] = False
        try:
            logout(thisNode['bmcHostname'],thisNode['username'], thisNode['password'], thisNode['session'], True)
        except Exception as e:
            config.errorLogger(syslog.LOG_DEBUG, "Failed to log out of the bmc {bmc} after closing the websocket.".format(bmc=thisNode['bmcHostname']))
    
def on_open(ws):
    #open the websocket and subscribe to the sensors
    thisNode = getNode(ws.url)
    global sensorList
    nodeSensors = thisNode['SensorList'] 
    subList = nodeSensors + sensorList
    data = {"paths": subList, "interfaces": ["xyz.openbmc_project.Sensor.Value","xyz.openbmc_project.Logging.Entry",'org.open_power.OCC.Status', 'xyz.openbmc_project.State.Chassis']}
    ws.send(json.dumps(data))
    sendQueue.put(thisNode)
    config.errorLogger(syslog.LOG_DEBUG, "Websocket opened for {bmc}".format(bmc=thisNode['bmcHostname']))
    thisNode['connecting'] = False
    thisNode['Connected'] = True
    thisNode['LastUpdateReceived'] = int(time.time())
    thisNode['retryCount'] = 0


def createWebsocket(sescookie, bmcIP, node):
    cookieStr = ""
    for key in sescookie:
        if cookieStr != "":
            cookieStr = cookieStr + ";"
        cookieStr = cookieStr + key +"=" + sescookie[key]
    ws = websocket.WebSocketApp("wss://{bmc}/subscribe".format(bmc=bmcIP),
                              on_message = on_message,
                              on_error = on_error,
                              on_close = on_close,
                              cookie = cookieStr)
    node['websocket'] = ws
    ws.on_open = on_open
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

def setDefaultBMCCredentials(node):
    if config.mynodelist[-1]['accessType'] == "ipmi":
        node ['username'] = "ADMIN"
        node['password'] = "ADMIN"
    elif config.mynodelist[-1]['accessType'] == 'openbmcRest':
        node['username'] = "root"
        node['password'] = "0penBmc"

def openWebSocketsThreads(node): 
    global sensorData
    bmcIP = node['bmcHostname']
    systemName = node['xcatNodeName']
    node['connecting'] = True
    mysession = login(bmcIP,node['username'], node['password'], True)
    node['session'] = mysession
    if isinstance(mysession, requests.sessions.Session):
        node['down'] = False
        try:
            node['LastUpdateReceived'] = int(time.time())
            sescookie= mysession.cookies.get_dict()
            for i in range(3):
                getNodePowerState(bmcIP, mysession,systemName, node)
#                 print('Power State Updated')
                initSensors(bmcIP, mysession, systemName, node)
#                 print('Sensors Initialized')
                if len(sensorData[systemName])>0:
#                     print(sensorData[systemName])
                    break
            if len(sensorData[systemName])>0:
                node['retryCount'] = 0
                createWebsocket(sescookie, bmcIP, node)
                
            else:
                logout(bmcIP, node['username'], node['password'],mysession, True)
                raise ValueError("Failed to get initial sensor readings")
            
        except ValueError as e:
            node['telemlistener'] = None
            node['connecting'] = False
            config.errorLogger(syslog.LOG_CRIT, "Failed to initialize sensors with BMC: {bmc} three times. The BMC session is now terminated.".format(bmc=bmcIP))
        except Exception as e:
            node['telemlistener'] = None
            node['connecting'] = False
            config.errorLogger(syslog.LOG_CRIT, "Failed to open the websocket with BMC: {bmc}".format(bmc=bmcIP))
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
            traceback.print_tb(e.__traceback__)
    else:
        node['down'] = True
        node['telemlistener'] = None
        node['connecting'] = False
        if mysession is not None:
            config.errorLogger(syslog.LOG_CRIT, "Failed to login to BMC: {bmc} {uid} {pwd}".format(bmc=bmcIP, uid=node['username'], pwd=node['password']))
            config.errorLogger(syslog.LOG_ERR, "{err}".format(err=mysession))

def nullAllNodeSensReadings(node):
    global sensorData
    if node['xcatNodeName'] in sensorData:
        for sensor in sensorData[node['xcatNodeName']]:
            sensorData[node['xcatNodeName']][sensor]['value'] = None

def startMonitoringProcess(nodeList, mngedNodeList):
    #There's one monitoring process per 50 nodes
    global lock
    global killSig
    signal.signal(signal.SIGUSR1, gathererDumpMem)
    global gathererNodeList
    gathererNodeList = nodeList
    global sensorData
    for node in nodeList:
        if node['accessType'] == 'openbmcRest':
            node['LastUpdateReceived'] = int(time.time())
            node['nextConnAttempt'] = int(time.time())+90 #add 90s before first retry attempt to allow all of the subprocesses and threads to start
            node['retryCount'] = 0
            node['down'] = False
            node['Connected'] = False
            node['connecting']= True
            node['NodeState'] = False
            node['SensorList']= []
            sensorData[node['xcatNodeName']] = {}
            ws = threading.Thread(target = openWebSocketsThreads, args=[node])
            ws.daemon = True
            node['telemlistener'] = ws
            ws.start() 
    pm = threading.Thread(target = processMessages)
    pm.daemon = True
    pm.start()
#     time.sleep(90)
    
    while True:
        if killSig.is_set():
            config.errorLogger(syslog.LOG_DEBUG, "Killing gatherer process pid {mpid}".format(mpid=os.getpid()))
            break
        if not sendQueue.empty():
            pollNode = sendQueue.get()
            if 'xcatNodeName' not in pollNode:
                continue
            else:
                mngedNodeList.append(nodeReferenceDict[pollNode['xcatNodeName']])
            sendQueue.task_done()
        curTime = time.time()
        for node in nodeList:
            if node['telemlistener'] is not None:
                if not node['telemlistener'].is_alive():
                    node['telemlistener'] = None
            msgtimer = curTime - node['LastUpdateReceived']
            if node['accessType'] == 'openbmcRest':
                if not pm.isAlive():
                    try:
                        pm = threading.Thread(target = processMessages)
                        pm.daemon = True
                        pm.start()
                    except Exception as e:
                        config.errorLogger(syslog.LOG_ERR, "Failed to restart the thread for processing BMC telemetry notifications. ")
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
                        traceback.print_tb(e.__traceback__)
                if node['telemlistener'] is None and curTime>= node['nextConnAttempt'] and not node['connecting']:
                    try:
                        if node['retryCount'] <3:
                            node['Connected'] = False
                            ws = threading.Thread(target = openWebSocketsThreads, args=[node])
                            ws.daemon = True
                            node['telemlistener'] = ws
                            node['retryCount'] += 1
                            # throttle reconnection attempts to once every 30s
                            node['nextConnAttempt'] = int(curTime) + 30 
                            ws.start() 
                            config.errorLogger(syslog.LOG_ERR, "No thread found for monitoring {bmc} telemetry data. A new thread has been started.".format(bmc=node['bmcHostname']))
                        elif node['retryCount'] >=3:
                            if not node['down']:
                                config.errorLogger(syslog.LOG_CRIT, "ibm-crassd has failed to reconnect to BMC, {bmc}, more than three times.".format(bmc=node['bmcHostname']))
                                node['down'] = True
                            node['retryCount'] = 0
                    except Exception as e:
                        config.errorLogger(syslog.LOG_ERR, "Error trying to restart a thread for monitoring bmc telemetry data.")
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
                        traceback.print_tb(e.__traceback__)
                elif msgtimer > 90 and node['Connected'] and not node['connecting']:
                    try:
                        config.errorLogger(syslog.LOG_DEBUG, "No new messages received from BMC for 90 seconds. Restarting listener.")
                        node['Connected'] = False
                        node['connecting'] = True
                        nullAllNodeSensReadings(node)
                        if node['retryCount'] <=3:
                            oldws = node['websocket']
                            oldws.close()
                            ws = threading.Thread(target = openWebSocketsThreads, args=[node])
                            ws.daemon = True
                            node['telemlistener'] = ws
                            ws.start() 
                            node['retryCount'] +=1
                        if node['retryCount'] >3 and msgtimer>=300:
                            if not node['down']:
                                config.errorLogger(syslog.LOG_CRIT, "ibm-crassd has failed to reconnect to BMC, {bmc}, more than three times.".format(bmc=node['bmcHostname']))
                                node['down'] = True
                            node['retryCount'] = 0
                    except Exception as e:
                        if not node['down']:
                            config.errorLogger(syslog.LOG_CRIT, "The BMC, {bmc}, stopped sending telemetry data and ibm-crassd failed to reconnect to it.".format(bmc=node['bmcHostname']))
                            node['down'] = True
                else:
                    pass
                sensorData[node['xcatNodeName']]['LastUpdateReceived'] = node['LastUpdateReceived']
                sensorData[node['xcatNodeName']]['Connected'] = node['Connected']
                sensorData[node['xcatNodeName']]['NodeState'] = node['NodeState']
        time.sleep(0.9)
        telemUpdateQueue.put(sensorData)

def telemReceive():
    global killSig
    global sensorData
    while True:
        if killSig.is_set():
            break
        try:
            newData = telemUpdateQueue.get()
            sensorData.update(newData)
        except Exception as e:
            config.errorLogger(syslog.LOG_DEBUG, "Error updating sensor data with new readings.")
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
            traceback.print_tb(e.__traceback__)

def init(mngedNodeList):
    websocket.enableTrace(False)
    global gathererProcs
    global pidList
    nodespercore = config.nodespercore
    if len(config.mynodelist)%nodespercore > 0:
        oddNum = 1
    else:   
        oddNum = 0
    nodeConcurrentProcs = int(len(config.mynodelist)/nodespercore) + oddNum
    for num in range(nodeConcurrentProcs):
        startNum = num*nodespercore
        monitorNodeList = []
        if oddNum == 1 and num == nodeConcurrentProcs:
            monitorNodeList = config.mynodelist[startNum:-1]
        else:
            monitorNodeList = config.mynodelist[startNum:((num+1)*nodespercore)]
        gathererProc = multiprocessing.Process(target=startMonitoringProcess, args=[monitorNodeList, mngedNodeList])
        gathererProc.daemon = True
        gathererProc.start()
        pidList.append(gathererProc.pid)
        config.errorLogger(syslog.LOG_DEBUG, "Gatherer process {gpid} has been started.".format(gpid=gathererProc.pid))
        gathererProcs.append(gathererProc)
               
def recvall(sock, n):
    #helper function to receive n bytes or return None if EOF is hit
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data
     
def process_data(filterData, addr):
    """
        Processes the filter data received from a client. In the case of errors, defaults are used. 
        For invalid names and types, they are removed from the list. The full path of the sensor name must be included.
        
        @param filterData: The raw data received from the client. Must be in a JSON formatted string.
        @param addr: The address of the client as a string.
    """    
    try:
        filterDict = json.loads(filterData.decode())
        if 'frequency' in filterDict:
            if not isinstance(filterDict['frequency'], int):
                try:
                    filterDict['frequency'] = int(filterDict['frequency'])
                except Exception as e:
                    config.errorLogger(syslog.LOG_ERR, "{value} is not a valid frequency".format(value=filterDict['frequency']))
                    filterDict['frequency'] = 1
        if 'sensornames' in filterDict:
            if not isinstance(filterDict['sensornames'], list):
                config.errorLogger(syslog.LOG_ERR, "{value} is not a valid list of names".format(value=filterDict['sensornames']))
                filterDict.pop('sensornames', None)
            else:
                fullpathnames = []
                for sname in filterDict['sensornames']:
                    found = False
                    for fullSensName in sensorList:
                        if sname in fullSensName:
                            found = True
                            fullpathnames.append(fullSensName)
                            break
                    if not found:
                        config.errorLogger(syslog.LOG_ERR, "{value} is not a valid sensor name".format(value=sname))
                filterDict['sensornames'] = fullpathnames
                if len(filterDict['sensornames'])<= 0:
                    filterDict.pop('sensornames', None)
        if 'sensortypes' in filterDict:
            if not isinstance(filterDict['sensortypes'], list):
                config.errorLogger(syslog.LOG_ERR, "{value} is not a valid list of types".format(value=filterDict['sensortypes']))
                filterDict.pop('sensornames', None)
            else:
                validSensorTypes = ['current', 'power', 'voltage', 'temperature', 'fan_tach']
                for stype in filterDict['sensortypes']:
                    if stype not in validSensorTypes:
                        config.errorLogger(syslog.LOG_ERR, "{value} is not a valid sensor type".format(value=stype))
                        filterDict['sensortypes'].remove(stype)
                if len(filterDict['sensortypes'])<= 0:
                    filterDict.pop('sensortypes', None)
        return filterDict
    except Exception as e:
        config.errorLogger(syslog.LOG_CRIT, "Unable to process message from client {addr}. Error details: {err}".format(addr=addr, err=e))

def getFilteredData(filterInfo, sensorData):
    """
        Returns a dictionary containing the filtered sensors. 
        @param filterInfo: Dictionary containing the filters
        @return: Dictionary containing only the subscribed to sensors
    """
#     global sensorData
    filteredDict = {}
    #sensor names have the highest priority for filters
    try:
        if "sensornames" in filterInfo:
            for node in sensorData:
                if 'Time_Sent' in node: continue
                filteredDict[node] = {}
                for sname in filterInfo['sensornames']:
                    filteredDict[node][sname.split('/')[-1]] = sensorData[node][sname.split('/')[-1]]
                filteredDict[node]['LastUpdateReceived'] = sensorData[node]['LastUpdateReceived']
                filteredDict[node]['NodeState'] = sensorData[node]['NodeState']
                filteredDict[node]['Connected'] = sensorData[node]['Connected']
            return filteredDict
        elif 'sensortypes' in filterInfo:
            for node in sensorData:
                if 'Time_Sent' in node: continue
                filteredDict[node] = {}
                for sname in sensorData[node]:
                    if 'LastUpdateReceived' in sname: continue
                    elif 'NodeState' in sname: continue
                    elif 'Connected' in sname: continue
                    elif sensorData[node][sname]['type'] is None:
                        filteredDict[node][sname] = sensorData[node][sname]
                    elif sensorData[node][sname]['type'][0] in filterInfo['sensortypes']:
                        filteredDict[node][sname] = sensorData[node][sname]
                    else:
                        pass
                filteredDict[node]['LastUpdateReceived'] = sensorData[node]['LastUpdateReceived']
                filteredDict[node]['NodeState'] = sensorData[node]['NodeState']
                filteredDict[node]['Connected'] = sensorData[node]['Connected']
            return filteredDict
        else:
            return sensorData
    except Exception as e:
        config.errorLogger(syslog.LOG_DEBUG, "Failed to filter the sensors, returned all of them.")
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
        traceback.print_tb(e.__traceback__)
    return sensorData

def on_new_client(clientsocket, addr):
    """
         Run in a thread,under a subprocess, sends telemetry data to a subscribed client
           
         @param clientsocket: the socket opened with the subscriber
         @param addr: The address of the subscriber
    """ 
    global killSig
    global sensorData
    last_run = next_run = now = get_millis()
    clientSubRate = update_every
    clientsocket.settimeout(0.1)
    count = 0
    config.errorLogger(syslog.LOG_INFO, "Telemetry streaming connected to {address}".format(address= addr))

    filterInfo = {}
    while True:
        if killSig.is_set():
            break

        if next_run <= now:
            count += 1
            while next_run <=now:
                next_run += clientSubRate
            dt = now - last_run
            last_run = now
            
            if count == 1:
                dt = 0
            filteredSensors = getFilteredData(filterInfo, sensorData)
            filteredSensors['Time_Sent'] = int(time.time())
            data2send = (json.dumps(filteredSensors, indent=0, separators=(',', ':')).replace('\n','') +"\n").encode()
#             data2send = (json.dumps(sensorData, indent=0, separators=(',', ':')).replace('\n','') +"\n").encode()
            msg = struct.pack('>I', len(data2send)) + data2send
            clientsocket.sendall(msg) 
        time.sleep(0.3) #wait 1/3 of a second and check for new
        now = get_millis()   
        
        try:
            raw_msglen = recvall(clientsocket, 4)
            if not raw_msglen:
                break
            msglen = struct.unpack('>I', raw_msglen)[0]
            data = recvall(clientsocket, msglen)
            if not data:
                break
            else:
                filterInfo = process_data(data, addr)
                if 'frequency' in filterInfo:
                    clientSubRate = filterInfo['frequency'] * 1000
        except socket.timeout:
            pass
        except Exception as e:
            config.errorLogger(syslog.LOG_ERR, "Error processing message filters from client at: {caddress}.".format(caddress=addr))
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
            traceback.print_tb(e.__traceback__)

        
    for item in clientList:
        if addr == item:
            clientList.remove(item)
    clientsocket.close()
    config.errorLogger(syslog.LOG_INFO, "Telemetry streaming disconnected from {address}".format(address= addr))

    
def socket_server(servsocket):
    signal.signal(signal.SIGUSR1, sockServerDumpMem)
    global pidList
    global serverhostname
    global killSig
    global sensorData
    global syncTime
    syncTime = int(time.time())
    for node in config.mynodelist:
        sensorData[node['xcatNodeName']] = {}
        sensorData[node['xcatNodeName']]['LastUpdateReceived'] = None
        sensorData[node['xcatNodeName']]['Connected'] = None
        sensorData[node['xcatNodeName']]['NodeState'] = None
    dataUpdaterThread = threading.Thread(target=telemReceive)
    dataUpdaterThread.daemon = True
    dataUpdaterThread.start()
    
#     killQueueThread = threading.Thread(target=killQueueChecker)
#     killQueueThread.daemon = True
#     killQueueThread.start()
    
    servsocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servsocket.bind((serverhostname,config.telemPort))
    servsocket.listen(15)
    read_list = [servsocket]
    while True:
        if killSig.is_set():
            config.errorLogger(syslog.LOG_DEBUG, "Socket Server terminating")
            break
        try:
            if not dataUpdaterThread.isAlive():
                dataUpdaterThread = threading.Thread(target=telemReceive)
                dataUpdaterThread.daemon = True
                dataUpdaterThread.start()
                config.errorLogger(syslog.LOG_DEBUG, "Restarted the data consolidation thread")
            readable, writeable, errored = select.select(read_list, [], [], 5)
            for s in readable:
                if s is servsocket:
                    c, addr = servsocket.accept()
                    t = threading.Thread(target=on_new_client, args =[c,addr])
                    t.daemon = True
                    t.start()
                else:
                    data = s.recv(1024)
                    if data:
                        pass
                    else:
                        s.close()
                        read_list.remove(s)
            if ((int(time.time())-syncTime) >= 600):
                # syncronize the connection status for each node
                for node in config.mynodelist:
                    config.nodeProperties[node['xcatNodeName']]['LastUpdateReceived'] = sensorData[node['xcatNodeName']]['LastUpdateReceived']
                    config.nodeProperties[node['xcatNodeName']]['Connected'] = sensorData[node['xcatNodeName']]['Connected']
                    config.nodeProperties[node['xcatNodeName']]['NodeState'] = sensorData[node['xcatNodeName']]['NodeState']
        except Exception as e:
            config.errorLogger(syslog.LOG_ERR, "Failed to open a telemetry server connection with a client.")
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
            traceback.print_tb(e.__traceback__)
            
    servsocket.close()

def watchdogThread():
    global gathererProcs
    global killSig
    while True:
        if config.killNow:
            break
        if killSig.is_set():
            break
        for i in range(len(gathererProcs)):
            gproc = gathererProcs[i]
            gprocpid = gproc.pid
            if not gproc.is_alive():
                config.errorLogger(syslog.LOG_DEBUG, "Gatherer subprocess for system set {num} not running. Triggering Restart.".format(num=i))
                restartGathererProcess(i)
        sockprocID = sockServProcess.pid
        if not sockServProcess.is_alive():
            restartSockServ.set()
            config.errorLogger(syslog.LOG_DEBUG, "Socket server detected as not running. Triggering Restart. ")
        time.sleep(5)
            
def restartGathererProcess(nodeSet): 
    """
        Restarts a telem gathering subprocess
        @param nodeset: This contains an index value for the gathererProcs list
    """
    
    global gathererProcs
    global mngedNodeList
    global pidList
    nodespercore = config.nodespercore
    if len(config.mynodelist)%nodespercore > 0:
        oddNum = 1
    else:   
        oddNum = 0
    nodeConcurrentProcs = int(len(config.mynodelist)/nodespercore) + oddNum
    startNum = nodeSet*nodespercore
    monitorNodeList = []
    if oddNum == 1 and nodeSet == nodeConcurrentProcs:
        monitorNodeList = config.mynodelist[startNum:-1]
    else:
        monitorNodeList = config.mynodelist[startNum:((nodeSet+1)*nodespercore)]
    gathererProc = multiprocessing.Process(target=startMonitoringProcess, args=[monitorNodeList, mngedNodeList])
    gathererProc.daemon = True
    gathererProc.start()
    #pidList[0] is for the socket server, gaterer proc pids begin after that. 
    pidList[nodeSet+1] = gathererProc.pid
    gathererProcs[nodeSet] = gathererProc
    config.errorLogger(syslog.LOG_DEBUG, "Gatherer subprocess for system set {num} has been restarted with pid {gpid}".format(num=nodeSet, gpid=gathererProc.pid))


def memWatchdog():
    global pidList
    config.errorLogger(syslog.LOG_DEBUG,'Memory Watchdog PID: {apid}'.format(apid=os.getpid()))
    signal.signal(signal.SIGUSR1, getMemInfo)
    time.sleep(90)
    crassdpids = pidList
    memUsageList = []
    counter = 0
    lines = ''
    lastCheck = int(time.time())
    for subpid in crassdpids:
        with open('/proc/{apid}/status'.format(apid=subpid), 'r') as f:
            lines = f.readlines()
        for line in lines:
            if 'VmSize' in line:
                memUsageList.append(int(line.split(' ')[-2]))
                counter += 1
    pids2dumpMemContents = []
    while True:
        if killSig.is_set():
            break
        if (int(time.time()) - lastCheck) > 60:
            counter = 0
            lastCheck = int(time.time())
            crassdpids = pidList
            for subpid in crassdpids:
                try:
                    with open('/proc/{apid}/status'.format(apid=subpid), 'r') as f:
                        lines = f.readlines()
                    for line in lines:
                        if 'VmSize' in line:
                            tempMemSize = int(line.split(' ')[-2])
                            if tempMemSize > 1.2 *memUsageList[counter]:
                                pids2dumpMemContents.append(subpid)
                            counter += 1
                except Exception as e:
                    config.errorLogger(syslog.LOG_DEBUG, 'Error in memWatchdog process.')
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
                    traceback.print_tb(e.__traceback__)
            if len(pids2dumpMemContents)>0:
                fileList = os.listdir('/tmp')
                for i in range(len(pids2dumpMemContents)):
                    for fileName in fileList:
                        if pids2dumpMemContents[i] in fileName:
                            pids2dumpMemContents.pop(i)
                            
                if len(pids2dumpMemContents)> 0:
                    for apid in pids2dumpMemContents:
                        os.kill(apid, signal.SIGUSR1)
                
                with open('/tmp/crassd-{mpid}-{curTime}', 'w') as f:
                    pass
        time.sleep(1)
def main():
    global telemUpdateQueue 
    telemUpdateQueue= multiprocessing.Queue()
    global killSig
    killSig = multiprocessing.Event()
    global restartSockServ
    restartSockServ = multiprocessing.Event()
    global messageQueue
    messageQueue = queue.Queue()
    global clientList
    clientList = []
    global outputData
    outputData = {}
    global sensorData
    sensorData = {}
    global sensorList
    sensorList = [
                    "/xyz/openbmc_project/logging", 
                    "/xyz/openbmc_project/state/chassis0",
                    '/org/open_power/control/occ0',
                    '/org/open_power/control/occ1'
                  ]
    requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
    global wsClosed
    wsClosed = False
    global pmClosed
    pmClosed = False
    global lock
    lock = threading.Lock()
    global get_millis
    get_millis = lambda: int(round(time.time() * 1000))
    global sendQueue
    sendQueue = queue.Queue()
    nodeListManager = multiprocessing.Manager()
    global mngedNodeList
    mngedNodeList = nodeListManager.list()
    ##nodeProperteties {nodeName:{'LastUpdateReceived':'UNIXTimestamp','NodeState':'Powered On/Off': 'Connected':True|False,'SensorList':,['list','of','sensor','paths']}
    global serversocket
    serversocket = socket.socket()
    global serverhostname
    serverhostname = ''
    global port
    port = config.telemPort
    global update_every
    update_every = 1
    update_every = update_every*1000
    global killNow
    killNow = config.killNow
    global gathererProcs
    gathererProcs = []
    global nodeReferenceDict
    nodeReferenceDict = {}
    global pidList 
    pidList = nodeListManager.list()
    for node in config.mynodelist:
        nodeReferenceDict[node['xcatNodeName']] = node.copy()
    pidList.append(None)
    init(mngedNodeList)
    
    global sockServProcess
    sockServProcess = multiprocessing.Process(target=socket_server, args=[serversocket])
    sockServProcess.daemon = True
    sockServProcess.start()
    pidList[0] = sockServProcess.pid
    config.errorLogger(syslog.LOG_DEBUG, "Telmetry socket listener child pid: {apid}".format(apid=sockServProcess.pid))
    wd = threading.Thread(target=watchdogThread, args=[])
    wd.daemon = True
    wd.start()
    
    memWatchdogProc = multiprocessing.Process(target=memWatchdog, args=[])
    memWatchdogProc.daemon = True
    memWatchdogProc.start()
    config.errorLogger(syslog.LOG_INFO, 'Started Telemetry Streaming')
    
    while not config.killNow:
        time.sleep(0.5)
        try:
            #mngedNodeList is used to hold nodes that need to be polled for new alerts (No push notifications)
            if isinstance(mngedNodeList, str): break
            while len(mngedNodeList)>0:
#                 node = config.alertMessageQueue.get()
                node = mngedNodeList.pop(0)
                config.nodes2poll.put(node)
#                 config.alertMessageQueue.task_done()
            if restartSockServ.is_set():
                sockServProcess = multiprocessing.Process(target=socket_server, args=[serversocket])
                sockServProcess.daemon = True
                sockServProcess.start()
                pidList[0] = sockServProcess.pid
                restartSockServ.unset()
                config.errorLogger(syslog.LOG_DEBUG, "Socket Server process has been restarted with pid {apid}.".format(apid=sockServProcess.pid))
        except Exception as e:
            config.errorLogger(syslog.LOG_ERR, "Error processing an alert message.")
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
            traceback.print_tb(e.__traceback__)
    
    config.errorLogger(syslog.LOG_DEBUG, "Killing the telemetry server subprocesses.")
    
    killSig.set()
    memWatchdogProc.terminate()
    for aproc in gathererProcs:
        aproc.join()
#         killQueue.put(True)
    config.errorLogger(syslog.LOG_DEBUG, "Gatherer subprocesses killed")
    config.errorLogger(syslog.LOG_DEBUG, "Waiting on the socket server")
    sockServProcess.join()
    config.errorLogger(syslog.LOG_DEBUG, "Telemetry server socket server stopped.")

    
    config.errorLogger(syslog.LOG_DEBUG, "Telemetry Server stopped.")
    
    
if __name__ == "__main__":
    main()