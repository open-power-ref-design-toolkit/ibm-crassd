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
import config
from config import *
import imp
import notificationlistener

def sigHandler(signum, frame):
    """
         Used to handle kill signals from the operating system
           
         @param signum: integer, the signal number received from the os
         @param frame; contextual frame
         @return: set global kill now to true and lead to termination
    """ 
    if (signum == signal.SIGTERM or signum == signal.SIGINT):
        print("Termination signal received.")
        global killNow
        killNow = True
    elif(signum == signal.SIGUSR1):
        print("Queue size: " + str(nodes2poll.qsize()))
    else:
        print("Signal received" + signum)
        
#setup the interrupt to handle SIGTERM, SIGINT
signal.signal(signal.SIGTERM, sigHandler)
signal.signal(signal.SIGINT, sigHandler)
signal.signal(signal.SIGUSR1, sigHandler)


def errorHandler(severity, message):
    """
         Used to handle creating entries in the system log for this service
           
         @param severity: the severity of the syslog entry to create
         @param message: string, the message to post in the syslog
    """
    print("Creating syslog entry")
    syslog.openlog(ident="IBMPowerHWMonitor", logoption=syslog.LOG_PID|syslog.LOG_NOWAIT)
    syslog.syslog(severity, message)    

  
def updateEventDictionary(eventsDict):
    newEventsDict = {}
    for key in eventsDict:
        commonEvent = {}
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
                commonEvent['timestamp'] = str(int(int(eventsDict[key]['timestamp'])/1000))
                commonEvent['ComponentInstance'] = str(eventsDict[key]['ComponentInstance'])
                newEventsDict[key] = commonEvent
            except KeyError:
                print (key +' not found in events dictionary')
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print ("exception: ", exc_type, fname, exc_tb.tb_lineno)
#                 sys.stdout.flush()
                
    return newEventsDict


def updateBMCLastReports():
    """
         update the bmc ini file to record last log reported
    """ 
    global killNow
    confParser = configparser.ConfigParser()
    if os.path.exists('/opt/ibm/ras/etc/bmclastreports.ini'):
        try: 
            confParser.read('/opt/ibm/ras/etc/bmclastreports.ini')
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print ("exception: ", exc_type, fname, exc_tb.tb_lineno)
    while True:
        if killNow: break
        #node contains {entity: entName, bmchostname: bmchostname, lastlogtime: timestamp, dupTimeIDList: [ID1, ID2]  
#         if not updateConfFile.empty(): 
        node = updateConfFile.get()
        

        if len(node['dupTimeIDList']) >= 1:
            tmpList = []
            for cerid in node['dupTimeIDList']:
                tmpList.append(str(cerid))
            node['dupTimeIDList'] = tmpList
        data2write = {'lastLogTime': str(node['lastLogTime']), 'dupTimeIDList': node['dupTimeIDList']}
        if node['entity']+'_bmcs' not in confParser:
            confParser[node['entity']+'_bmcs'] = {}
        confParser[node['entity']+'_bmcs'][node['bmchostname']] = str(data2write)
        with open('/opt/ibm/ras/etc/bmclastreports.ini', 'w') as configfile:
            confParser.write(configfile)
        
        updateConfFile.task_done()
        
   
def BMCEventProcessor():
    """
         processes alerts and is run in child threads
    """  
    eventsDict = {};
    global notifyList
    global killNow
    global networkErrorList
    updateNotifyTimes = False
    while True:
        nodeCommsLost = False
        if killNow: 
            break
        else:
            node = nodes2poll.get()
            name = threading.currentThread().getName()
            bmcHostname = node['bmcHostname']
            impactednode = node['xcatNodeName']
            username = node['username']
            password = node['password']
            try:
                print(name +": " + bmcHostname)
#                 sys.stdout.flush()
                if(node['accessType']=="openbmcRest"):
#                     proc = subprocess.Popen(['python', '/opt/ibm/ras/bin/openbmctool.py', '-H', bmcHostname, '-U', 'root', '-P', '0penBmc','-j','-t','/opt/ibm/ras/lib/policyTable.yml', 'sel', 'print'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
#                     eventList = str(proc.communicate()[0])
                    try:
                        eventBytes = subprocess.check_output(['python', '/opt/ibm/ras/bin/openbmctool.py', '-H', bmcHostname, '-U', username, '-P', password,'-j','-t','/opt/ibm/ras/lib/policyTable.json', 'sel', 'print'])
                        eventList = eventBytes.decode('utf-8')
                    except subprocess.CalledProcessError as e:
                        print(e.output)
                    
                    if eventList.find('{') != -1: #check for valid response
                        eventList = eventList[eventList.index('{'):]
                    else:
                        print('unable to get list of events from bmc')
                        print(eventList)
#                         sys.stdout.flush()
                        continue
                    eventsDict = json.loads(eventList)
                    eventsDict = updateEventDictionary(eventsDict)
                elif(node['accessType']=="ipmi"):
#                     proc= subprocess.Popen(['java', '-jar', '/opt/ibm/ras/lib/crassd.jar', bmcHostname, "ADMIN", 'ADMIN'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
#                     eventList = str(proc.communicate()[0])
                    eventList = subprocess.check_output(['java', '-jar', '/opt/ibm/ras/lib/crassd.jar', bmcHostname, username, password]).decode('utf-8')
                    if eventList.find('{') != -1: #check for valid response
                        eventList = eventList[eventList.index('{'):] #keyboard terminate causing substring not found here
                    else:
                        print('unable to get list of events from bmc')
                        print(eventList)
#                         sys.stdout.flush()
                        continue
                    eventsDict = json.loads(eventList)
                    print("processing alerts")
#                     sys.stdout.flush()
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
                                    #forward the network connection failure at 3 consecutive failures. 
                                    continue
                                
                            #only report new events
                            for key in notifyList:
#                                 print(bmcHostname +' notifying: ' + str(key))
                                updateNotifyTimes = False
                                with lock:
                                    receiveEntityStatus = notifyList[key]['receiveEntityDown']
                                    dupList = notifyList[key][bmcHostname]['dupTimeIDList']
                                    func = notifyList[key]['function']
                                    notifyList[key]['failedFirstTry'] = False
                                    lastlogtime = notifyList[key][bmcHostname]['lastLogTime']
                                if(eventsDict[event]['timestamp']>lastlogtime):
                                    repsuccess = func(eventsDict[event], impactednode, notifyList) 
#                                     if funcName in locals():
#                                         repsuccess = locals()[funcName](eventsDict[event], impactednode, notifyList)
#                                     elif funcName in globals():
#                                         repsuccess = globals()[funcName](eventsDict[event], impactednode, notifyList)
#                                     else:
#                                         errorHandler(syslog.LOG_ERR, "Unable to find function " +funcName)
#                                         killNow = True
#                                         break
                                    with lock:
                                        notifyList[key]['successfullyReported'] = repsuccess
#                                     print('Notify response:' + str(repsuccess))
                                    if repsuccess:
                                        with lock: 
                                            notifyList[key][bmcHostname]['lastLogTime'] = eventsDict[event]['timestamp']
                                            del notifyList[key][bmcHostname]['dupTimeIDList'][:]
                                            notifyList[key][bmcHostname]['dupTimeIDList'].append(eventsDict[event]['CerID'])
                                        updateNotifyTimes = True
                                    else:
                                        with lock:
                                            notifyList[key]['failedFirstTry'] = True
                                            receiveEntityStatus = notifyList[key]['receiveEntityDown']
                                        if(receiveEntityStatus== False):
                                            with lock:
                                                func = notifyList[key]['function']
                                            repsuccess = func(eventsDict[event], impactednode, notifyList)
                                            
#                                             with lock:
#                                                 funcName = str(notifyList[key]['function'])
# #                                             
#                                             if funcName in locals():
#                                                 repsuccess = locals()[funcName](eventsDict[event], impactednode, notifyList)
#                                             elif funcName in globals():
#                                                 repsuccess = globals()[funcName](eventsDict[event], impactednode, notifyList)
#                                             else:
#                                                 errorHandler(syslog.LOG_ERR, "Unable to find function " +funcName)
#                                                 killNow = True
#                                                 break
                                            with lock:
                                                notifyList[key]['successfullyReported'] = repsuccess 
                                            if(repsuccess == False):
#                                                 errorHandler(syslog.LOG_ERR, "Unable to forward HW event to "+str(key)+': ' + str(eventsDict[event]['CerID']) )
                                                break
                                            else:
                                                with lock: 
                                                    notifyList[key][bmcHostname]['lastLogTime'] = eventsDict[event]['timestamp']
                                                    del notifyList[key][bmcHostname]['dupTimeIDList'][:]
                                                    notifyList[key][bmcHostname]['dupTimeIDList'].append(eventsDict[event]['CerID'])
                                                    updateNotifyTimes = True
                                        else:
                                            break
                                elif(eventsDict[event]['timestamp'] == lastlogtime):
                                    with lock:
                                        notifyList[key]['failedFirstTry'] = False
                                        dupList = notifyList[key][bmcHostname]['dupTimeIDList']
                                    if(eventsDict[event]['CerID'] not in dupList):
                                        with lock:
                                            func = notifyList[key]['function']
                                        repsuccess = func(eventsDict[event], impactednode, notifyList)
#                                             funcName = str(notifyList[key]['function'])
#                                         if funcName in locals():
#                                             repsuccess= locals()[funcName](eventsDict[event], impactednode, notifyList)
#                                         elif funcName in globals():
#                                             repsuccess = globals()[funcName](eventsDict[event], impactednode, notifyList)
#                                         else:
#                                             errorHandler(syslog.LOG_ERR, "Unable to find function " +funcName)
#                                             killNow = True
#                                             break
                                        with lock:
                                            notifyList[key]['successfullyReported'] = repsuccess
                                        if repsuccess:
                                            with lock: 
                                                notifyList[key][bmcHostname]['dupTimeIDList'].append(eventsDict[event]['CerID'])
                                            updateNotifyTimes = True
                                        else:
                                            with lock:
                                                notifyList[key]['failedFirstTry'] = True
                                                receiveEntityStatus = notifyList[key]['receiveEntityDown']
                                            if(receiveEntityStatus == False):
                                                with lock:
                                                    func = notifyList[key]['function']
                                                repsuccess = func(eventsDict[event], impactednode, notifyList)
#                                                 with lock:
#                                                     funcName = str(notifyList[key]['function'])
#                                                 if funcName in locals():
#                                                     repsuccess = locals()[funcName](eventsDict[event], impactednode, notifyList)
#                                                 elif funcName in globals():
#                                                     repsuccess = globals()[funcName](eventsDict[event], impactednode, notifyList)
#                                                 else:
#                                                     errorHandler(syslog.LOG_ERR, "Unable to find function " +funcName)
#                                                     killNow = True
#                                                     break
                                                with lock:
                                                    notifyList[key]['successfullyReported'] = repsuccess
                                                if(repsuccess == False):
#                                                     errorHandler(syslog.LOG_ERR, "Unable to forward HW event to "+str(key)+': ' + str(eventsDict[event]['CerID']) )
                                                    break
                                                else:
                                                    with lock: 
                                                        notifyList[key][bmcHostname]['dupTimeIDList'].append(eventsDict[event]['CerID'])
                                                    updateNotifyTimes = True
                                            break
#                 reported = False 
                                if updateNotifyTimes:
                                    updateNotifyTimes = False
                                    #node contains {entity: entName, bmchostname: bmchostname, lastlogtime: timestamp, dupTimeIDList: [ID1, ID2]     
                                    updateNotifyTimesData = {'entity': key, 'bmchostname': bmcHostname, 'lastLogTime': notifyList[key][bmcHostname]['lastLogTime'],
                                                              'dupTimeIDList': notifyList[key][bmcHostname]['dupTimeIDList']}
                                    updateConfFile.put(updateNotifyTimesData)
                                 
                nodes2poll.task_done()
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print("exception: ", exc_type, fname, exc_tb.tb_lineno)
                print(e)
#                 sys.stdout.flush()
            eventsDict.clear()
            
            
def loadBMCLastReports():
    """
         Loads the previously reported alerts from a configuration file
           
         @return: modifies global list of monitored nodes with previously reported alerts
    """ 
    if os.path.exists('/opt/ibm/ras/etc/bmclastreports.ini'):
        confParser = configparser.ConfigParser()
        global notifyList
        try: 
            confParser.read('/opt/ibm/ras/etc/bmclastreports.ini')
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print ("exception: ", exc_type, fname, exc_tb.tb_lineno)
        try:
            for key in notifyList:
                bmcs = dict(confParser.items(str(key) + '_bmcs'))
                for node in mynodelist:
                    if node['bmcHostname'] in bmcs:
                        bmcString = str(bmcs[node['bmcHostname']]).replace("\'", "\"")
                        bmcs[node['bmcHostname']]= json.loads(bmcString)
                        notifyList[key][node['bmcHostname']]['lastLogTime'] = str(bmcs[node['bmcHostname']]['lastLogTime'])
                        notifyList[key][node['bmcHostname']]['dupTimeIDList'] = bmcs[node['bmcHostname']]['dupTimeIDList']
        except KeyError:
            errorHandler(syslog.LOG_ERR, "No section: bmcs in ini file. All bmc events will be forwarded to entities being notified. ")
        except configparser.NoSectionError:
            errorHandler(syslog.LOG_ERR, "No section: "+str(key) +"_bmcs in ini file. All bmc events will be forwarded to entities being notified. ")

def getPlugins():
    """
        gets a list of valid plugins from the plugin directory
       
       @return: a list containing valid files to import 
    """
    
    plugins = []
    plugindir = "plugins"
    mainmodule = "__init__"
    files = os.listdir(plugindir)
    for filename in files:
        fullpath = os.path.join(plugindir, filename)
        if os.path.isdir(fullpath):
            for f in os.listdir(fullpath):
                addFile = os.path.join(filename, f)
                files.append(addFile)
        if not os.path.isdir(fullpath) and ".py" in filename and not mainmodule in filename and not ".pyc" in filename:
            #is a potential module
            modname = os.path.basename(fullpath).split('.py')[0]
            pathonly = os.path.split(fullpath)[0]
            info = imp.find_module(modname ,[pathonly])
            if info not in plugins:
                plugins.append({"name":modname, "info":info})
        
    return plugins

def loadPlugins(plugin):
    """
        Loads the specified plugin
        @plugin: the absolute path and filename to the module to load
        @return: loaded module 
    """ 
    return imp.load_module(plugin["name"], *plugin["info"])

def createNodeList(confParser):
    """
        Gets the list of nodes and loads mynodeList dictionary
        @confParser: The configuration parser object with the nodes entity
        @return: The high level list of nodes
    """
    
    try:
        nodes = dict(confParser.items('nodes'))
        for key in nodes:
            mynodelist.append(json.loads(nodes[key]))
            if 'username' not in mynodelist[-1]:
                if mynodelist[-1]['accessType'] == "ipmi":
                    mynodelist[-1]['username'] = "ADMIN"
                    mynodelist[-1]['password'] = "ADMIN"
                elif mynodelist[-1]['accessType'] == 'openbmcRest':
                    mynodelist[-1]['username'] = "root"
                    mynodelist[-1]['password'] = "0penBmc"
            mynodelist[-1]['dupTimeIDList'] = []
            mynodelist[-1]['lastLogTime'] = 0
            mynodelist[-1]['pollFailedCount'] = 0
            for entity in notifyList:
                notifyList[entity][mynodelist[-1]['bmcHostname']] = {
                    'lastLogTime': mynodelist[-1]['lastLogTime'],
                    'dupTimeIDList': mynodelist[-1]['dupTimeIDList']}
       
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print("exception: ", exc_type, fname, exc_tb.tb_lineno)
        print(e)
        sys.exit()
    
def validatePluginNotifications(confParser):
    """
        Validates plugins loaded for each of the designated notifications. 
        Will remove reported to entities if their plugin's notify function isn't found
        @confParser: the configuration file parser with the data containing node info
    """
    #check for entities to notify that don't have associated plugin
    missingPlugins = []
    for entity in notifyList:
        if isinstance(notifyList[entity]['function'], str) or isinstance(notifyList[entity]['function'], unicode):
            errorHandler(syslog.LOG_WARNING,"Notify function not found " + notifyList[entity]['function'] +". This entity will not be notified of alerts.")
            missingPlugins.append(entity)
    
    #remove entities to notify that don't have the associated plugin
    for plugin in missingPlugins:
        del notifyList[plugin]
        
    
def setupNotifications():
    """
        Loads the information from the configuration file and setup notification to monitoring entities
        @return the configuration parser object   
    """ 
    #read the config file
    confParser = configparser.ConfigParser()
    global notifyList
    notifyList = {}
    try:
        if os.path.exists('/opt/ibm/ras/etc/ibm-crassd.config'):
            confParser.read('/opt/ibm/ras/etc/ibm-crassd.config')
            test = dict(confParser.items('notify'))
            for key in test:
                if test[key] == 'True':
                    notifyList[key] = {"function": test[key+'function'], 
                                        "receiveEntityDown":False,
                                        "failedFirstTry": False,
                                        "successfullyReported": True}
        else:
            errorHandler(syslog.LOG_CRIT, "Configuration file not found. Exiting.")
            sys.exit()
    except KeyError:
        errorHandler(syslog.LOG_ERR, "No section: notify in file ibmpowerhwmon.conf. Alerts will not be forwarded. Terminating")
        sys.exit() 
    
    #get the nodes to push alerts to
    createNodeList(confParser)
    
    for i in getPlugins():
        print("Loading Plugin " + i["name"])
        plugin = loadPlugins(i)
        for key in notifyList:
            if key in i["name"]:
                if hasattr(plugin, 'initialize'):
                    if not plugin.initialize():
                        errorHandler(syslog.LOG_CRIT, 'Plugin: ' + i['name'] + ' failed to initialize. Aborting now.')
                        sys.exit()
        for entity in notifyList:
            if isinstance(notifyList[entity]['function'], basestring):
                if hasattr(plugin, notifyList[entity]["function"]):
                    notifyList[entity]["function"] = getattr(plugin, notifyList[entity]["function"])
    return confParser
    
def configurePushNotifications():   
    """
        configures a websocket to listen for push notifications from openbmc. Spawns 1 thread per push notification. 
        updates the node list by adding information on the thread for each websocket 
    """ 
    for node in mynodelist:
        if node['accessType'] == 'openbmcRest':
            t = threading.Thread(target=notificationlistener.openSocket, args=[node['bmcHostname'], node['username'], node['password']])
            node['listener'] = t
            t.daemon = True
            t.start()  
def queryAllNodes():
    """
        Queries all nodes to get initial status upon starting up. 
    """ 
    for node in mynodelist:
        #load nodes that are using polling into the queue
        nodes2poll.put(node)
def initialize():
    """
        Initializes the application by loading the nodes to monitor, getting the plugins needed, and setting up
        the forwarding through the specified plugins. Spools up the threads that will process the bmc alerts
        when a queue entry is created. This also configures push notifications. 
    """ 
    global csmDown
    csmDown = False
    global killNow
    killNow = False

    #The following list indicates failure to communicate to the BMC and retrieve information
    global networkErrorList
    networkErrorList = ['FQPSPIN0000M','FQPSPIN0001M', 'FQPSPIN0002M','FQPSPIN0003M','FQPSPCR0020M', 'FQPSPSE0004M']
    
    #Setup Notifications for entities to push alerts to
    confParser = setupNotifications()
    
    #validate all of the needed plugins loaded
    validatePluginNotifications(confParser)
    #load last reported times from storage file to prevent duplicate entries
    loadBMCLastReports()
    
    #run LSF to verify systems to monitor
    #to be implemented later
    
    #Determine the maximum number of nodes
    maxThreads = 1
    try:
        maxThreads = int(dict(confParser.items('base_configuration'))['maxthreads'])
    except KeyError:
        errorHandler(syslog.LOG_ERR, "No section: base configuration in file ibmpowerhwmon.conf. Defaulting to one thread for polling") 
    
    
    #Time below in seconds
    minPollingInterval = 30.0
    numPasses = 1
    #Create the worker threads
    if(maxThreads >= len(mynodelist)):
        maxThreads = len(mynodelist)
    else:
        numPasses = math.ceil(len(mynodelist)/maxThreads)
    minPollingInterval = 15*numPasses
    for i in range(maxThreads):
        print("Creating thread " + str(i))

        t = threading.Thread(target=BMCEventProcessor)
        t.daemon = True
        t.start()   
      
    t = threading.Thread(target=updateBMCLastReports)
    t.daemon = True
    t.start()
    
    configurePushNotifications()
    queryAllNodes()
    #Setup polling interval
    pollNodes(minPollingInterval) 

def pollNodes(interval):
    """
         Used as timer for the polling interval. set to 20 seconds
           
         @return: Does not return a specific value but loads the global queue with nodes that get polled 
    """ 
    print ("polling the nodes")
    global killNow
    if not killNow:
        t = threading.Timer(interval, pollNodes, [interval])
        t.daemon = True
        t.start()
    
    
    for node in mynodelist:
        if node['accessType'] == 'ipmi':
            #load nodes that are using polling into the queue
            nodes2poll.put(node)
        elif node['accessType'] == 'openbmcRest':
            if 'listener' in node and not node['listener'].isAlive():
                t = threading.Thread(target=notificationlistener.openSocket, args=[node['bmcHostname'], node['username'], node['password']])
                node['listener'] = t
                t.daemon = True
                t.start()  
    
    #check for dead push notification
    
  
if __name__ == '__main__':
    """
         main thread for the application. 
    """   
    try:
#         nodes2poll = queue.Queue()
#         updateConfFile = queue.Queue()
#         mynodelist = []
#         missingEvents = {}
#         lock = threading.Lock()
        initialize()
#         global killNow
        
        print(os.getpid())
        while(True):
            time.sleep(1)
            if(killNow):
                break
        errorHandler(syslog.LOG_ERR, "The Power HW Monitoring service has been stopped")
        sys.exit()
    except KeyboardInterrupt:
        print ("Terminating")
        sys.exit()