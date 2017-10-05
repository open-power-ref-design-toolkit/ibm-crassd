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
import time
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
     processes an alert from the openbmc
       
     @param openBMCEvent: dict, contains the event and all of it's properties
"""      
def OpenBMCEventHandler(openBMCEvent):
    return
"""
     sends alert to CSM
       
     @param cerEvent: dict, the cerEvent to send
     @param impactedNode; the node that had the alert
     @param failedFirstFlag: boolean, if true, report the alert using the generic entry
     @return: True if notification was successful, false if it was unable to send the alert
"""
def notifyCSM(cerEvent, impactedNode, failedFirstFlag):
    httpHeader = {'Content-Type':'application/json'}
    if(failedFirstFlag == False):
        msgID = "bmc." + "".join(cerEvent['eventType'].split()) + "." + cerEvent['CerID']
        eventEntry = {'msg_id': msgID, 'location_name':impactedNode, 'time_stamp':time.ctime(int(cerEvent['timestamp']))}
    else:
        msgID = "bmc.Firmware/SoftwareFailure.FQPSPEM0003G"
        eventEntry = {'msg_id': msgID, 'location_name':impactedNode, 'time_stamp':time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                      "raw_data":(cerEvent['CerID'] + "|| "+cerEvent['message']+"|| serviceable:"+ cerEvent['serviceable']+ "|| severity: "+ 
                                  cerEvent['severity'])}
    global csmDown
    try:
        r = requests.post('http://127.0.0.1:5555/csmi/V1.0/ras/event/create', headers=httpHeader, data=json.dumps(eventEntry), timeout=30)
        if (r.status_code != 200):
#             if csmDown == False:
#                 errorHandler(syslog.LOG_ERR, "Unable to forward HW event to CSM: "+ msgID )
#                 csmDown = True;
#             print(r.raise_for_status()) 
            csmDown = False
            return False
        else:
            print("Successfully reported to CSM: " + msgID)
            if csmDown == True:
                csmDown=False
            return True
    except(requests.exceptions.Timeout):
        if csmDown == False:
            errorHandler(syslog.LOG_ERR, "Connection Timed out connecting to csmrestd system service. Ensure the service is running")
            csmDown = True;
        return False
    except(requests.exceptions.ConnectionError) as err:
        if csmDown == False:
            errorHandler(syslog.LOG_ERR, "Encountered an error connecting to csmrestd system service. Ensure the service is running. Error: " + str(err))
            csmDown = True;
        return False   


"""
     processes alerts and is run in child threads
"""     
def BMCEventProcessor():
    eventsDict = {};
    global csmDown
    global killNow;
    while True:
        if killNow: 
            break
        else:
            node = nodes2poll.get()
            name = threading.currentThread().getName()
            bmcHostname = node['bmcHostname']
            try:
                print(name +": " + bmcHostname)
                if(node['accessType']=="openbmcRest"):
                    proc = subprocess.Popen(['python', 'openbmctool.py', '-H', bmcHostname, '-U', 'root', '-P', '0penBmc','-j', 'sel', 'list'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    eventList = proc.communicate()[0]
                    eventList = eventList[eventList.index('{'):]
                    eventsDict = json.loads(eventList)
                elif(node['accessType']=="ipmi"):
                    proc= subprocess.Popen(['java', '-jar', '/opt/ibm/ras/lib/crassd.jar', bmcHostname, "ADMIN", 'ADMIN'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    eventList = proc.communicate()[0]
                    eventList = eventList[eventList.index('{'):] #keyboard terminate causing substring not found here
                    eventsDict = json.loads(eventList)
                    print("processing alerts")
                else:
                    #use redfish
                    time.sleep(1)
                
                for i in range(0, len(eventsDict)-1):
                    event = "event" +str(i)
                    if "error" in eventsDict[event]:
                        begIndex = eventsDict[event]['error'].rfind(":") + 2
                        missingKey = eventsDict[event]['error'][begIndex:]
                        if(missingKey not in missingEvents.keys()):
                            with lock: 
                                missingEvents[missingKey] = True
                            errorHandler(syslog.LOG_ERR, "Event not found in lookup table: " + missingKey)
                    else:
                        #only report new events
                        if(eventsDict[event]['timestamp']>node['lastLogTime']):
                            reported = notifyCSM(eventsDict[event], bmcHostname, False)
                            if reported:
                                with lock: 
                                    node['lastLogTime'] = eventsDict[event]['timestamp']
                                    del node['dupTimeIDList'][:]
                            else:
                                if(csmDown == False):
                                    reported = notifyCSM(eventsDict[event], bmcHostname)
                                    if(reported == False):
                                        errorHandler(syslog.LOG_ERR, "Unable to forward HW event to CSM: "+ event['CerID'] )
                                        break
                                else:
                                    break
                        if(eventsDict[event]['timestamp']== node['lastLogTime']):
                            if(eventsDict[event]['CerID'] not in node['dupTimeIDList']):
                                reported = notifyCSM(eventsDict[event], bmcHostname)
                                if reported:
                                    with lock: 
                                        node['dupTimeIDList'].append(eventsDict[event]['timestamp'])
                                else:
                                    break
                reported = False               
                nodes2poll.task_done()
            except Exception as e:
                print(str(e))
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
    #read the config file
    confParser = configparser.ConfigParser()
    try:
        confParser.read('/opt/ibm/ras/etc/ibmpowerhwmon.config')
        nodes = dict(confParser.items('nodes'))
        for key in nodes:
            mynodelist.append(json.loads(nodes[key]))
    except Exception as e:
        print(e)
    
    #run LSF to verify systems to monitor
    
    
    #Create the worker threads
#     for i in range(3):
#         print("Creating thread " + str(i))
#         t = threading.Thread(target=BMCEventProcessor)
#         t.daemon = True
#         t.start()
#     errorHandler(syslog.LOG_INFO, "has been successfully started.")    
    #Setup polling interval
    pollNodes() 
"""
     Used as timer for the polling interval. set to 20 seconds
       
     @return: Does not return a specific value but loads the global queue with nodes that get polled 
""" 
def pollNodes():
    print ("polling the nodes")
    global killNow
    if not killNow:
        t = threading.Timer(20.0, pollNodes)
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
            if(nodes2poll.empty() == False):
                BMCEventProcessor()
            if(killNow):
                break
        errorHandler(syslog.LOG_ERR, "The Power HW Monitoring service has been stopped")
        sys.exit()
    except KeyboardInterrupt:
        print ("Terminating")
        sys.exit()