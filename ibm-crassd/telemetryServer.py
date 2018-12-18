#!/usr/bin/python3 -u
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
import datetime
import subprocess
import os
import socket
import struct
import config
import syslog
import signal
import select

def sigHandler(signum, frame):
    """
         Used to handle kill signals from the operating system
           
         @param signum: integer, the signal number received from the os
         @param frame; contextual frame
         @return: set global kill now to true and lead to termination
    """ 
    if (signum == signal.SIGTERM or signum == signal.SIGINT):
        global killNow
        killNow = True
    else:
        print("Signal received" + signum)

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
        print("Attempting login...")
    httpHeader = {'Content-Type':'application/json'}
    mysess = requests.session()
    try:
        #seeing a hang here
        r = mysess.post('https://'+host+'/login', headers=httpHeader, json = {"data": [username, pw]}, verify=False, timeout=30)
        loginMessage = json.loads(r.text)
        if (loginMessage['status'] != "ok"):
            print(loginMessage["data"]["description"].encode('utf-8')) 
            sys.exit(1)
#         if(sys.version_info < (3,0)):
#             urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
#         if sys.version_info >= (3,0):
#             requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
        return mysess
    except(requests.exceptions.Timeout):
        return (connectionErrHandler(jsonFormat, "Timeout", None))
    except(requests.exceptions.ConnectionError) as err:
        return (connectionErrHandler(jsonFormat, "ConnectionError", err))


def initSensors(host, username, password, session, xcatNodeName):
    '''
        Gets initial values for sensors
    '''
    httpHeader = {'Content-Type':'application/json'}
    url="https://"+host+"/xyz/openbmc_project/sensors/enumerate"
    try:
        res = session.get(url, headers=httpHeader, verify=False, timeout=30)
    except(requests.exceptions.Timeout):
        return(connectionErrHandler(True, "Timeout", None))
    
    curtime = time.time()
    sensors = json.loads(res.text)["data"]
    sensorData[xcatNodeName] = {}
    for key in sensors:
        if 'PowerSupplyRedundancy' in key:
            continue
        keyparts = key.split('/')
        sensorType = keyparts[-2]
        sensorname = keyparts[-1]
        for sname in sensorList:
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
        for sname in sensorList:
            if sensorname in sname:
                sensorData[xcatNodeName][sensorname]['scale'] = scale
                sensorData[xcatNodeName][sensorname]['value'] =sensors[key]['Value']
#                 sensorData[host]['units'] = sensors[key]['Unit'].split('.')[-1]
                sensorData[xcatNodeName][sensorname]['type'] = (sensorType, sensors[key]['Unit'].split('.')[-1])
    
    for key in sensorList:
        keyparts = key.split('/')
        stype = keyparts[-2]
        sname = keyparts[-1]
        if sname not in sensorData[xcatNodeName]:
            sensorData[xcatNodeName][sname] = {}
            sensorData[xcatNodeName][sname]['value'] = 0
            sensorData[xcatNodeName][sname]['time'] = datetime.datetime.fromtimestamp(curtime).strftime("%Y-%m-%d %H:%M:%S")
            sensorData[xcatNodeName][sname]['type'] = (stype, typeUnitDict[stype])
            if 'fan_tach' in stype:
                sensorData[xcatNodeName][sname]['scale'] = 1
            elif 'power' in stype:
                sensorData[xcatNodeName][sname]['scale'] = 10 ** -6
            else:
                sensorData[xcatNodeName][sname]['scale'] = 10 ** -3
    
def processMessages():
    global killNow
    while True:
        if killNow:
            break
        text = messageQueue.get()
#         print("Processing Message")
        try:
            message = json.loads(text['msg'])
            sensorName = message["path"].split('/')[-1]
#             currentValue = sensorData[text['node']['bmcHostname']][sensorName]['value']
#             newValue = message['properties']['Value']
#             if newValue > currentValue:
            with lock:
                sensorData[text['node']['xcatNodeName']][sensorName]['value'] = message['properties']['Value']
        except Exception as e:
            pass
        messageQueue.task_done()

def getNode():
    thisNode = {}
    for anode in config.mynodelist:
        if 'telemlistener' in anode and anode['telemlistener'] is not None:
            if anode['telemlistener'].getName() == threading.currentThread().getName():
                thisNode = anode
                break
    return thisNode
            
def on_message(ws, message):
    thisNode = getNode()
    thisNode['activeTimer'] = time.time()
    thisNode['down'] = False
#     print("New Message")
    messageQueue.put({'node': thisNode,'msg':message})

def on_error(ws, error):
    thisNode = getNode()
    if thisNode['websocket'] == ws:
        thisNode['telemlistener'] = None
    

def on_close(ws):
    thisNode = getNode()
    if thisNode['websocket'] == ws:
        thisNode['telemlistener'] = None

def on_open(ws):
    #open the websocket and subscribe to the sensors
    data = {"paths": sensorList, "interfaces": ["xyz.openbmc_project.Sensor.Value"]}
    ws.send(json.dumps(data))

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
    wsClosed = False
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

def setDefaultBMCCredentials(node):
    if config.mynodelist[-1]['accessType'] == "ipmi":
        node ['username'] = "ADMIN"
        node['password'] = "ADMIN"
    elif config.mynodelist[-1]['accessType'] == 'openbmcRest':
        node['username'] = "root"
        node['password'] = "0penBmc"

def buildNodeList():
    """
        Attempts to autoConfigure the nodes to monitor
    """
    hostname = subprocess.check_output('hostname').decode('utf-8').strip()
    if ('.' in hostname):
        hostname = hostname.split('.')[0]
    nodeOutput= subprocess.check_output(['python3', '/opt/ibm/ras/bin/buildNodeList.py', '-j']).decode('utf-8')
    nodes2monitor = {}
    
    if 'Error' not in nodeOutput:
        xcatNodes = json.loads(nodeOutput)
        if hostname in xcatNodes:
            nodes2monitor = xcatNodes[hostname]
        else:
            print("Failed getting node list from xcat. Hostname not found in returned nodes.")
            sys.exit(1)
        try:
            for node in nodes2monitor:
                config.mynodelist.append({'xcatNodeName': nodes2monitor[node]['xcatNodeName'], 
                                   'bmcHostname': nodes2monitor[node]['bmcHostname'],
                                   'accessType': nodes2monitor[node]['accessType'],
                                   'pollFailedCount': 0,
                                   'lastLogTime': '0',
                                   'dupTimeIDList': []})
                
                setDefaultBMCCredentials(config.mynodelist[-1])
            if len(config.mynodelist)<1:
                print("Failed getting node list from xcat. No nodes returned")
                sys.exit(1)
        except Exception as e:
            #Log the exception and terminate
            exc_type, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print( "Exception: {type}, {frame}, {line}, {details}".format(
                type=exc_type, frame=fname, line=exc_tb.tb_lineno, details=e))
            print( "Unable to configure nodes automatically.")
            sys.exit(1)
    
    else:
        print("Failed getting node list from xcat. An Error occurred.")
        sys.exit(1)


def openWebSocketsThreads(node):            
    bmcIP = node['bmcHostname']
    systemName = node['xcatNodeName']
    mysession = login(bmcIP,"root", "0penBmc", True)
    node['activeTimer'] = time.time()
    node['retryCount'] = 0
    sescookie= mysession.cookies.get_dict()
    initSensors(bmcIP, 'root', '0penBmc', mysession, systemName)
    createWebsocket(sescookie, bmcIP, node)

def startMonitoringProcess(nodeList):
    killQueueThread = threading.Thread(target=killQueueChecker)
    killQueueThread.daemon = True
    killQueueThread.start()
    global activeThreads
    global lock
    for node in nodeList:
        if node['accessType'] == 'openbmcRest':
            node['activeTimer'] = time.time()
            node['retryCount'] = 0
            node['down'] = False
            ws = threading.Thread(target = openWebSocketsThreads, args=[node])
            ws.daemon = True
            ws.start() 
            node['telemlistener'] = ws
    pm = threading.Thread(target = processMessages)
    pm.daemon = True
    pm.start()
    activeThreads.append(ws)
    activeThreads.append(pm)
    time.sleep(60)
    global lock
    global killNow
    while True:
        if killNow:
            break
        for node in nodeList:
            msgtimer = time.time() - node['activeTimer']
            if node['accessType'] == 'openbmcRest':
                if node['telemlistener'] is None:
                    try:
                        ws = threading.Thread(target = openWebSocketsThreads, args=[node])
                        ws.daemon = True
                        ws.start() 
                        node['telemlistener'] = ws
                    except Exception as e:
                        pass
                elif msgtimer > 60:
                    try:
                        if node['retryCount'] <=3:
                            oldws = node['websocket']
                            oldws.close()
                            ws = threading.Thread(target = openWebSocketsThreads, args=[node])
                            ws.daemon = True
                            ws.start() 
                            node['telemlistener'] = ws
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
        time.sleep(0.9)
        telemUpdateQueue.put(sensorData)

def telemReceive():
    global killNow
    global sensorData
    while True:
        if killNow:
            break
        try:
            newData = telemUpdateQueue.get()
            sensorData.update(newData)
        except:
            pass

def init():
    websocket.enableTrace(False)
    global gathererProcs
    if len(config.mynodelist)%50 > 0:
        oddNum = 1
    else:
        oddNum = 0
    nodeConcurrentProcs = int(len(config.mynodelist)/50) + oddNum
    for num in range(nodeConcurrentProcs):
        startNum = num*50
        monitorNodeList = []
        if oddNum == 1 and num == nodeConcurrentProcs:
            monitorNodeList = config.mynodelist[startNum:-1]
        else:
            monitorNodeList = config.mynodelist[startNum:((num+1)*50)-1]
        gathererProc = multiprocessing.Process(target=startMonitoringProcess, args=[monitorNodeList])
        gathererProc.daemon = True
        gathererProc.start()
        gathererProcs.append(gathererProc)
        
    
           
def recvall(sock, n):
    #helperfunction to receive n bytes or return None if EOF is hit
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
    if "sensornames" in filterInfo:
        for node in sensorData:
            filteredDict[node] = {}
            for sname in filterInfo['sensornames']:
                filteredDict[node][sname.split('/')[-1]] = sensorData[node][sname.split('/')[-1]]
        return filteredDict
    elif 'sensortypes' in filterInfo:
        for node in sensorData:
            filteredDict[node] = {}
            for sname in sensorData[node]:
                if sensorData[node][sname]['type'][0] in filterInfo['sensortypes']:
                    filteredDict[node][sname] = sensorData[node][sname]
        return filteredDict
    else:
        return sensorData
    
    
def on_new_client(clientsocket, addr):
    """
         Run in a thread, sends telemetry data to a subscribed client
           
         @param clientsocket: the socket opened with the subscriber
         @param addr: The address of the subscriber
    """ 
    last_run = next_run = now = get_millis()
    clientSubRate = update_every
    clientsocket.settimeout(0.1)
    count = 0
    config.errorLogger(syslog.LOG_INFO, "Telemetry streaming connected to {address}".format(address= addr))
    global killNow
    filterInfo = {}
    while True:
        if killNow:
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
            print(e)

        
    for item in clientList:
        if addr == item:
            clientList.remove(item)
    clientsocket.close()

    
def socket_server(servsocket):
    global serverhostname
    dataUpdaterThread = threading.Thread(target=telemReceive)
    dataUpdaterThread.daemon = True
    dataUpdaterThread.start()
    
    killQueueThread = threading.Thread(target=killQueueChecker)
    killQueueThread.daemon = True
    killQueueThread.start()
    
    servsocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servsocket.bind((serverhostname,config.telemPort))
    servsocket.listen(15)
    read_list = [servsocket]
    global killNow
    while True:
        if killNow:
            break
        try:
            readable, writeable, errored = select.select(read_list, [], [], 30)
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
        except Exception as e:
            pass
    servsocket.close()

def main():
    global telemUpdateQueue 
    telemUpdateQueue= multiprocessing.Queue()
    global killQueue
    killQueue = multiprocessing.Queue()
    global messageQueue
    messageQueue = queue.Queue()
    global clientList
    clientList = []
    global outputData
    outputData = {}
    global sensorData
    sensorData = {}
    global sensorList
    sensorList = ["/xyz/openbmc_project/sensors/current/ps0_output_current",
                    "/xyz/openbmc_project/sensors/current/ps1_output_current",
                    "/xyz/openbmc_project/sensors/fan_tach/fan0_0",
                    "/xyz/openbmc_project/sensors/fan_tach/fan0_1",
                    "/xyz/openbmc_project/sensors/fan_tach/fan1_0",
                    "/xyz/openbmc_project/sensors/fan_tach/fan1_1",
                    "/xyz/openbmc_project/sensors/fan_tach/fan2_0",
                    "/xyz/openbmc_project/sensors/fan_tach/fan2_1",
                    "/xyz/openbmc_project/sensors/fan_tach/fan3_0",
                    "/xyz/openbmc_project/sensors/fan_tach/fan3_1",
                    "/xyz/openbmc_project/sensors/power/fan_disk_power",
                    "/xyz/openbmc_project/sensors/power/io_power",
                    "/xyz/openbmc_project/sensors/power/p0_gpu0_power",
                    "/xyz/openbmc_project/sensors/power/p0_gpu1_power",
                    "/xyz/openbmc_project/sensors/power/p0_gpu2_power",
                    "/xyz/openbmc_project/sensors/power/p0_io_power",
                    "/xyz/openbmc_project/sensors/power/p0_mem_power",
                    "/xyz/openbmc_project/sensors/power/p0_power",
                    "/xyz/openbmc_project/sensors/power/p1_gpu0_power",
                    "/xyz/openbmc_project/sensors/power/p1_gpu1_power",
                    "/xyz/openbmc_project/sensors/power/p1_gpu2_power",
                    "/xyz/openbmc_project/sensors/power/p1_io_power",
                    "/xyz/openbmc_project/sensors/power/p1_mem_power",
                    "/xyz/openbmc_project/sensors/power/p1_power",
                    "/xyz/openbmc_project/sensors/power/ps0_input_power",
                    "/xyz/openbmc_project/sensors/power/ps1_input_power",
                    "/xyz/openbmc_project/sensors/power/total_power",
                    "/xyz/openbmc_project/sensors/temperature/ambient",
                    "/xyz/openbmc_project/sensors/temperature/dimm0_temp",
                    "/xyz/openbmc_project/sensors/temperature/dimm1_temp",
                    "/xyz/openbmc_project/sensors/temperature/dimm10_temp",
                    "/xyz/openbmc_project/sensors/temperature/dimm11_temp",
                    "/xyz/openbmc_project/sensors/temperature/dimm12_temp",
                    "/xyz/openbmc_project/sensors/temperature/dimm13_temp",
                    "/xyz/openbmc_project/sensors/temperature/dimm14_temp",
                    "/xyz/openbmc_project/sensors/temperature/dimm15_temp",
                    "/xyz/openbmc_project/sensors/temperature/dimm2_temp",
                    "/xyz/openbmc_project/sensors/temperature/dimm3_temp",
                    "/xyz/openbmc_project/sensors/temperature/dimm4_temp",
                    "/xyz/openbmc_project/sensors/temperature/dimm5_temp",
                    "/xyz/openbmc_project/sensors/temperature/dimm6_temp",
                    "/xyz/openbmc_project/sensors/temperature/dimm7_temp",
                    "/xyz/openbmc_project/sensors/temperature/dimm8_temp",
                    "/xyz/openbmc_project/sensors/temperature/dimm9_temp",
                    "/xyz/openbmc_project/sensors/temperature/gpu0_core_temp",
                    "/xyz/openbmc_project/sensors/temperature/gpu0_mem_temp",
                    "/xyz/openbmc_project/sensors/temperature/gpu1_core_temp",
                    "/xyz/openbmc_project/sensors/temperature/gpu1_mem_temp",
                    "/xyz/openbmc_project/sensors/temperature/gpu2_core_temp",
                    "/xyz/openbmc_project/sensors/temperature/gpu2_mem_temp",
                    "/xyz/openbmc_project/sensors/temperature/gpu3_core_temp",
                    "/xyz/openbmc_project/sensors/temperature/gpu3_mem_temp",
                    "/xyz/openbmc_project/sensors/temperature/gpu4_core_temp",
                    "/xyz/openbmc_project/sensors/temperature/gpu4_mem_temp",
                    "/xyz/openbmc_project/sensors/temperature/gpu5_core_temp",
                    "/xyz/openbmc_project/sensors/temperature/gpu5_mem_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core0_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core1_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core10_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core11_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core12_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core13_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core14_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core15_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core18_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core19_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core2_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core20_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core21_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core22_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core23_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core3_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core4_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core5_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core6_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core7_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core8_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_core9_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_vcs_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_vdd_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_vddr_temp",
                    "/xyz/openbmc_project/sensors/temperature/p0_vdn_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core0_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core1_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core10_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core11_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core12_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core13_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core14_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core16_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core17_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core18_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core19_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core2_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core20_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core22_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core23_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core3_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core4_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core5_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core6_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core7_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core8_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_core9_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_vcs_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_vdd_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_vddr_temp",
                    "/xyz/openbmc_project/sensors/temperature/p1_vdn_temp",
                    "/xyz/openbmc_project/sensors/temperature/pcie",
                    "/xyz/openbmc_project/sensors/voltage/ps0_input_voltage",
                    "/xyz/openbmc_project/sensors/voltage/ps0_output_voltage",
                    "/xyz/openbmc_project/sensors/voltage/ps1_input_voltage",
                    "/xyz/openbmc_project/sensors/voltage/ps1_output_voltage"
                  ]
    requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
    global wsClosed
    wsClosed = False
    global pmClosed
    pmClosed = False
    global lock
    lock = threading.Lock()
    global activeThreads
    activeThreads = []
    global get_millis
    get_millis = lambda: int(round(time.time() * 1000))
    global sendQueue
    sendQueue = queue.Queue()
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
    init()
    config.errorLogger(syslog.LOG_INFO, 'Starting Telemetry Streaming')
    sockServProcess = multiprocessing.Process(target=socket_server, args=[serversocket])
    sockServProcess.start()
    while not config.killNow:
        time.sleep(1)
    for i in range(1+len(gathererProcs)):
        killQueue.put(True)
    sockServProcess.terminate()
    for aproc in gathererProcs:
        aproc.terminate()
    
if __name__ == "__main__":
    main()
    