#!/usr/bin/python
'''
#================================================================================
#
#    ibmpowerhwmon.py
#
#    Copyright IBM Corporation 2015-2017. All Rights Reserved
#
#    This program is licensed under the terms of the Eclipse Public License
#    v1.0 as published by the Eclipse Foundation and available at
#    http://www.eclipse.org/legal/epl-v10.html
#
#    U.S. Government Users Restricted Rights:  Use, duplication or disclosure
#    restricted by GSA ADP Schedule Contract with IBM Corp.
#
#================================================================================
'''
import signal, os, sys
import requests
import syslog
import time, datetime
import threading
try: 
    import configparser
except ImportError:
    import ConfigParser as configparser
try:
    import Queue as queue
except ImportError:
    import queue
import subprocess
import json
import math

"""
     Used to handle kill signals from the operating system
       
     @param signum: integer, the signal number received from the os
     @param frame; contextual frame
     @return: set global kill now to true and lead to termination
""" 
def sigHandler(signum, frame):
    if (signum == signal.SIGTERM or signum == signal.SIGINT):
        print("Termination signal received.")
        global killNow
        killNow = True
    else:
        print("Signal received" + signum)
        
#setup the interrupt to handle SIGTERM, SIGINT
signal.signal(signal.SIGTERM, sigHandler)
signal.signal(signal.SIGINT, sigHandler)

"""
     Used to handle kill signals from the operating system
       
     @param severity: the severity of the syslog entry to create
     @param message: string, the message to post in the syslog
"""
def errorHandler(severity, message):
    print("Creating syslog entry")
    syslog.openlog(ident="IBMPowerHWMonitor", logoption=syslog.LOG_PID|syslog.LOG_NOWAIT)
    syslog.syslog(severity, message)    

"""
     sends alert to mmhealth
       
     @param cerEvent: dict, the cerEvent to send
     @param impactedNode; the node that had the alert
     @param entityAttr: dictionary, contains the list of known attributes for the entity to report to
"""    
def notifymmhealth(cerEvent, impactedNode, entityAttr):
    mmHealthDown = entityAttr['mmhealth']['receiveEntityDown']
    eventsToReportList = ["FQPSPPW0006M","FQPSPPW0019I","FQPSPPW0007M","FQPSPPW0016I","FQPSPPW0008M","FQPSPPW0020I",
                          "FQPSPPW0009M","FQPSPPW0017I","FQPSPPW0010M","FQPSPPW0021I","FQPSPPW0011M","FQPSPPW0018M"]
    eventsToReportList.sort()
    if os.path.exists('/usr/lpp/mmfs/bin/mmsysmonc'):
        if(cerEvent['CerID'] in eventsToReportList):
            proc = subprocess.Popen(['/usr/lpp/mmfs/bin/mmsysmonc', 'event', 'powerhw', cerEvent['CerID'], cerEvent['compInstance'], impactedNode], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            result = proc.communicate()[0]
            
            if mmHealthDown:
                with lock:
                    entityAttr['mmhealth']['receiveEntityDown'] = False
                
            if "Event "+ cerEvent['CerID'] + " raised" in result:
                return True
            else: 
                return False
        else:
            return True
    else:
        errorHandler(syslog.LOG_CRIT, "Unable to find mmsysmonc. Ensure the utility is installed properly and part of the PATH")
        if not mmHealthDown:
            with lock:
                entityAttr['mmhealth']['receiveEntityDown'] = True
    
    return False

"""
     sends alert to CSM
       
     @param cerEvent: dict, the cerEvent to send
     @param impactedNode; the node that had the alert
     @param entityAttr: dictionary, contains the list of known attributes for the entity to report to
     @return: True if notification was successful, false if it was unable to send the alert
"""
def notifyCSM(cerEvent, impactedNode, entityAttr):
    httpHeader = {'Content-Type':'application/json'}
    failedFirstFlag = entityAttr['csm']['failedFirstTry']
    csmDown = entityAttr['csm']['receiveEntityDown']
    if(cerEvent['serviceable'] == 'No'):
        return True
    if(failedFirstFlag == False):
        msgID = "bmc." + "".join(cerEvent['eventType'].split()) + "." + cerEvent['CerID']
        eventEntry = {'msg_id': msgID, 'location_name':impactedNode, 'time_stamp':datetime.datetime.fromtimestamp(int(cerEvent['timestamp'])).strftime("%Y-%m-%d %H:%M:%S"),
                      "raw_data": "serviceable:"+ cerEvent['serviceable'] + " || subsystem: "+ cerEvent['subSystem'] }
    else:
        msgID = "bmc.Firmware/SoftwareFailure.FQPSPEM0003G"
        eventEntry = {'msg_id': msgID, 'location_name':impactedNode, 'time_stamp':time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                      "raw_data":(cerEvent['CerID'] + "|| "+cerEvent['message']+"|| serviceable:"+ cerEvent['serviceable']+ "|| severity: "+ 
                                  cerEvent['severity'])}
    if("additionalDetails" in cerEvent):
        eventEntry['raw_data'] = eventEntry['raw_data'] + cerEvent['sensor'] + " || " + cerEvent['state'] + " || " + cerEvent['additionalDetails']
    try:
        r = requests.post('http://127.0.0.1:5555/csmi/V1.0/ras/event/create', headers=httpHeader, data=json.dumps(eventEntry), timeout=30)
        if (r.status_code != 200):
#             if csmDown == False:
#                 errorHandler(syslog.LOG_ERR, "Unable to forward HW event to CSM: "+ msgID )
#                 csmDown = True;
#             print(r.raise_for_status()) 
            with lock:
                entityAttr['csm']['receiveEntityDown'] = False
            return False
        else:
            print("Successfully reported to CSM: " + msgID)
            if csmDown == True:
                with lock:
                    entityAttr['csm']['receiveEntityDown']=False
            return True
    except(requests.exceptions.Timeout):
        if csmDown == False:
            errorHandler(syslog.LOG_ERR, "Connection Timed out connecting to csmrestd system service. Ensure the service is running")
            with lock:
                entityAttr['csm']['receiveEntityDown'] = True;
        return False
    except(requests.exceptions.ConnectionError) as err:
        if csmDown == False:
            errorHandler(syslog.LOG_ERR, "Encountered an error connecting to csmrestd system service. Ensure the service is running. Error: " + str(err))
            with lock:
                entityAttr['csm']['receiveEntityDown'] = True;
        return False   


def updateEventDictionary(eventsDict):
    newEventsDict = {}
    commonEvent = {}
    for key in eventsDict:
        if("numAlerts" in key):
            newEventsDict[key] = eventsDict[key]
        elif(type(eventsDict[key]) is not dict):
            newEventsDict[key] = eventsDict[key]
        elif("error" in eventsDict[key]):
            newEventsDict[key] = eventsDict[key]
        else:
            try:
                commonEvent['CerID'] = eventsDict[key]['CommonEventID']
                commonEvent['message'] = eventsDict[key]['Message']
                commonEvent['lengthyDescription'] = eventsDict[key]['LengthyDescription']
                commonEvent['serviceable'] = eventsDict[key]['Serviceable']
                commonEvent['callHome'] = eventsDict[key]['CallHomeCandidate']
                commonEvent['severity'] = eventsDict[key]['Severity']
                commonEvent['eventType'] = eventsDict[key]['EventType']
                commonEvent['vmMigration'] = eventsDict[key]['VMMigrationFlag']
                commonEvent['subSystem'] = eventsDict[key]['AffectedSubsystem']
                commonEvent['userAction'] = eventsDict[key]['UserAction']
                commonEvent['timestamp'] = str(int(eventsDict[key]['timestamp'])/1000)
                newEventsDict[key] = commonEvent
            except KeyError:
                print (eventsDict[key])
                print (KeyError)
                
    return newEventsDict

"""
     processes alerts and is run in child threads
"""     
def BMCEventProcessor():
    eventsDict = {};
    global notifyList
    global killNow
    global networkErrorList
    while True:
        nodeCommsLost = False
        if killNow: 
            break
        else:
            node = nodes2poll.get()
            name = threading.currentThread().getName()
            bmcHostname = node['bmcHostname']
            impactednode = node['xcatNodeName']
            try:
                print(name +": " + bmcHostname)
                if(node['accessType']=="openbmcRest"):
                    proc = subprocess.Popen(['python', '/opt/ibm/ras/bin/openbmctool.py', '-H', bmcHostname, '-U', 'root', '-P', '0penBmc','-j','-t','/opt/ibm/ras/lib/policyTable.yml', 'sel', 'print'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    eventList = proc.communicate()[0]
                    if eventList.find('{') != -1: #check for valid response
                        eventList = eventList[eventList.index('{'):]
                    else:
                        print('unable to get list of events from bmc')
                        print(eventList)
                        continue
                    eventsDict = json.loads(eventList)
                    eventsDict = updateEventDictionary(eventsDict)
                elif(node['accessType']=="ipmi"):
                    proc= subprocess.Popen(['java', '-jar', '/opt/ibm/ras/lib/crassd.jar', bmcHostname, "ADMIN", 'ADMIN'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    eventList = proc.communicate()[0]
                    if eventList.find('{') != -1: #check for valid response
                        eventList = eventList[eventList.index('{'):] #keyboard terminate causing substring not found here
                    else:
                        print('unable to get list of events from bmc')
                        print(eventList)
                        continue
                    eventsDict = json.loads(eventList)
                    print("processing alerts")
                else:
                    #use redfish
                    print("redfish not supported")
                    continue
                
                
                #process the alerts
                if (eventsDict['numAlerts'] == 0):
                    #node poll was successful
                    node['pollFailedCount'] = 0
                    continue
                else:
                    for i in range(0, len(eventsDict)-1):
                        if(killNow):
                            break
                        event = "event" +str(i)
                        
                        if "error" in eventsDict[event]:
                            node['pollFailedCount'] = 0
                            begIndex = eventsDict[event]['error'].rfind(":") + 2
                            missingKey = eventsDict[event]['error'][begIndex:]
                            if(missingKey not in missingEvents.keys()):
                                with lock: 
                                    missingEvents[missingKey] = True
                                errorHandler(syslog.LOG_ERR, "Event not found in lookup table: " + missingKey)
                        else:
                            #check for failure to poll the bmc
                            if(eventsDict[event]['CerID'] in networkErrorList):
                                if (nodeCommsLost == False):
                                    nodeCommsLost = True
                                    node['pollFailedCount'] += 1
                                if(node['pollFailedCount'] != 2):
                                    continue
                                
                            #only report new events
                            for key in notifyList:
                                funcName = str(notifyList[key]['function'])
                                if(eventsDict[event]['timestamp']>notifyList[key][bmcHostname]['lastLogTime']):
                                    if funcName in locals():
                                        notifyList[key]['successfullyReported'] = locals()[funcName](eventsDict[event], impactednode, notifyList)
                                    elif funcName in globals():
                                        notifyList[key]['successfullyReported'] = globals()[funcName](eventsDict[event], impactednode, notifyList)
                                    else:
                                        errorHandler(syslog.LOG_ERR, "Unable to find function " +funcName)
                                        killNow = True
                                        break
                                    if notifyList[key]['successfullyReported']:
                                        with lock: 
                                            notifyList[key][bmcHostname]['lastLogTime'] = eventsDict[event]['timestamp']
                                            del notifyList[key][bmcHostname]['dupTimeIDList'][:]
                                            notifyList[key][bmcHostname]['dupTimeIDList'].append(eventsDict[event]['CerID'])
                                    else:
                                        if(notifyList[key]['receiveEntityDown'] == False):
                                            with lock:
                                                if funcName in locals():
                                                    notifyList[key]['successfullyReported'] = locals()[funcName](eventsDict[event], impactednode, True)
                                                elif funcName in globals():
                                                    notifyList[key]['successfullyReported'] = globals()[funcName](eventsDict[event], impactednode, True)
                                                else:
                                                    errorHandler(syslog.LOG_ERR, "Unable to find function " +funcName)
                                                    killNow = True
                                                    break
                                            if(notifyList[key]['successfullyReported'] == False):
                                                errorHandler(syslog.LOG_ERR, "Unable to forward HW event to "+key+': ' + event['CerID'] )
                                                break
                                            else:
                                                with lock: 
                                                    notifyList[key][bmcHostname]['lastLogTime'] = eventsDict[event]['timestamp']
                                                    del notifyList[key][bmcHostname]['dupTimeIDList'][:]
                                                    notifyList[key][bmcHostname]['dupTimeIDList'].append(eventsDict[event]['CerID'])
                                        else:
                                            break
                                elif(eventsDict[event]['timestamp'] == notifyList[key][bmcHostname]['lastLogTime']):
                                    if(eventsDict[event]['CerID'] not in notifyList[key][bmcHostname]['dupTimeIDList']):
                                        with lock:
                                            if funcName in locals():
                                                notifyList[key]['successfullyReported'] = locals()[notifyList[key]['function']](eventsDict[event], impactednode, False)
                                            elif funcName in globals():
                                                notifyList[key]['successfullyReported'] = globals()[notifyList[key]['function']](eventsDict[event], impactednode, False)
                                            else:
                                                errorHandler(syslog.LOG_ERR, "Unable to find function " +funcName)
                                                killNow = True
                                                break

                                        if notifyList[key]['successfullyReported']:
                                            with lock: 
                                                notifyList[key][bmcHostname]['dupTimeIDList'].append(eventsDict[event]['CerID'])
                                        else:
                                            if(notifyList[key]['receiveEntityDown'] == False):
                                                with lock:
                                                    if funcName in locals():
                                                        notifyList[key]['successfullyReported'] = locals()[notifyList[key]['function']](eventsDict[event], impactednode, True)
                                                    elif funcName in globals():
                                                        notifyList[key]['successfullyReported'] = globals()[notifyList[key]['function']](eventsDict[event], impactednode, True)
                                                    else:
                                                        errorHandler(syslog.LOG_ERR, "Unable to find function " +funcName)
                                                        killNow = True
                                                        break
                                                
                                                if(notifyList[key]['successfullyReported'] == False):
                                                    errorHandler(syslog.LOG_ERR, "Unable to forward HW event to "+key+': ' + event['CerID'] )
                                                    break
                                                else:
                                                    with lock: 
                                                        notifyList[key][bmcHostname]['dupTimeIDList'].append(eventsDict[event]['CerID'])
                                            break
#                 reported = False               
                nodes2poll.task_done()
            except Exception as e:
                tb = sys.exc_info()
                print(str(e) + "line: ")
                print(tb)
            eventsDict.clear()

"""
     Loads the information from the configuration file and initializes the daemon for main operation
       
     @return: modifies global list of nodes, and loads the list with nodes the daemon is responsible for. 
""" 
def initialize():
    global csmDown
    csmDown = False
    global killNow
    killNow = False

    #The following list indicates failure to communicate to the BMC and retrieve information
    global networkErrorList
    networkErrorList = ['FQPSPIN0000M','FQPSPIN0001M', 'FQPSPIN0002M','FQPSPIN0003M','FQPSPCR0020M', 'FQPSPSE0004M']
    #read the config file
    confParser = configparser.ConfigParser()
    #Setup Notifications
    global notifyList
    notifyList = {}
    try:
        confParser.read('/opt/ibm/ras/etc/ibmpowerhwmon.config')
        test = dict(confParser.items('notify'))
        for key in test:
            if test[key] == 'True':
                notifyList[key] = {"function": test[key+'function'], 
                                    "receiveEntityDown":False,
                                    "failedFirstTry": False,
                                    "successfullyReported": True}
    except KeyError:
        errorHandler(syslog.LOG_ERR, "No section: notify in file ibmpowerhwmon.conf. All alerts will be reported to the system log") 

    try:
        
        nodes = dict(confParser.items('nodes'))
        for key in nodes:
            mynodelist.append(json.loads(nodes[key]))
            mynodelist[-1]['dupTimeIDList'] = list(mynodelist[-1]['dupTimeIDList'])
            mynodelist[-1]['pollFailedCount'] = 0
            for entity in notifyList:
                notifyList[entity][mynodelist[-1]['bmcHostname']] = {
                    'lastLogTime': mynodelist[-1]['lastLogTime'],
                    'dupTimeIDList': mynodelist[-1]['dupTimeIDList']}
    except Exception as e:
        print(e)
    
    #run LSF to verify systems to monitor
    #to be implemented later
    
    #Determine the maximum number of nodes
    maxThreads = 1
    try:
        maxThreads = int(dict(confParser.items('base configuration'))['maxthreads'])
    except KeyError:
        errorHandler(syslog.LOG_ERR, "No section: base configuration in file ibmpowerhwmon.conf. Defaulting to one thread for polling") 
    
    
    #Time below in seconds
    minPollingInterval = 30.0
    numPasses = 1
    #Create the worker threads
    if(maxThreads >= len(nodes)):
        maxThreads = len(nodes)
    else:
        numPasses = math.ceil(len(nodes)/maxThreads)
    minPollingInterval = 15*numPasses
    for i in range(maxThreads):
        print("Creating thread " + str(i))
        t = threading.Thread(target=BMCEventProcessor)
        t.daemon = True
        t.start()   
    
    
    #Setup polling interval
    pollNodes(minPollingInterval) 
"""
     Used as timer for the polling interval. set to 20 seconds
       
     @return: Does not return a specific value but loads the global queue with nodes that get polled 
""" 
def pollNodes(interval):
    print ("polling the nodes")
    global killNow
    if not killNow:
        t = threading.Timer(interval, pollNodes, [interval])
        t.daemon = True
        t.start()
    
    
    for i in range (len(mynodelist)):
        nodes2poll.put(mynodelist[i])
    
    
"""
     main thread for the applications. Runs a single thread to process node alerts. 
"""     
if __name__ == '__main__':
    try:
        nodes2poll = queue.Queue()
        mynodelist = []
        missingEvents = {}
        lock = threading.Lock()
        initialize()
        global killNow
#         nodes2poll.join()
        
        print(os.getpid())
        while(True):
#             time.sleep(10)
#             if(nodes2poll.empty() == False):
#                 BMCEventProcessor()
            if(killNow):
                break
        errorHandler(syslog.LOG_ERR, "The Power HW Monitoring service has been stopped")
        sys.exit()
    except KeyboardInterrupt:
        print ("Terminating")
        sys.exit()