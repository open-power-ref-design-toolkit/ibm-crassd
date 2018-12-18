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
import signal, os, sys
import requests
import syslog
import time, datetime
import threading
import configparser
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
import socket
import telemetryServer

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
        config.killNow = True
    elif(signum == signal.SIGUSR1):
        errorLogger(syslog.LOG_INFO,"Queue size: " + str(nodes2poll.qsize()))
    else:
        print("Signal received" + signum)


def updateTimesforLastReports(signum, frame):
    """
        Updates BMC last reports file to current time
    """
    filename = config.updateNodeTimesfile
    if os.path.exists(filename):
        Updatesconfparser = configparser.ConfigParser()
        parsedFiles = Updatesconfparser.read(filename)
        updatedNodes =[]
        if filename in parsedFiles:
            try:
                for section in Updatesconfparser.sections(): 
                    nodes = dict(Updatesconfparser.items(section))
                    for node in config.mynodelist:
                        for markedNode in Updatesconfparser[section]:
                            if node['xcatNodeName'] == str(markedNode):
                                bmcHostname = node['bmcHostname']
                                impactednode = node['xcatNodeName']
                                updateNotifyTimesData = {'entity': section, 'bmchostname': node['bmcHostname'], 'lastLogTime': nodes[markedNode],
                                                         'dupTimeIDList': []}
                                updateConfFile.put(updateNotifyTimesData)
                                updatedNodes.append(markedNode)
                                with lock: 
                                    notifyList[section][bmcHostname]['lastLogTime'] = nodes[markedNode]
                                    del notifyList[section][bmcHostname]['dupTimeIDList'][:]
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print("exception: ", exc_type, fname, exc_tb.tb_lineno)
                print(e)
            try:
                os.remove(config.updateNodeTimesfile)
                for section in Updatesconfparser.sections():
                    errorLogger(syslog.LOG_INFO, "Updated {entity} BMC reporting times for: {bmcList}".format(bmcList=", ".join(updatedNodes), entity=section))
            except Exception as e:
                errorLogger(syslog.LOG_ERR, 'Unable to delete file {filename}'.format(filename=config.updateNodeTimesfile))
        else:
            errorLogger(syslog.LOG_ERR, "Unable to parse updateNodes.ini file.")
        

        
        
def errorLogger(severity, message):
    """
         Used to handle creating entries in the system log for this service
           
         @param severity: the severity of the syslog entry to create
         @param message: string, the message to post in the syslog
    """
    syslog.openlog(ident="ibm-crassd", logoption=syslog.LOG_PID|syslog.LOG_NOWAIT)
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
            keyTranslator = {'CommonEventID': 'CerID', 'Message': 'message', 'LengthyDescription': 'lengthyDescription',
                             'Serviceable':'serviceable', 'CallHomeCandidate': 'callHome', 'Severity': 'severity',
                             'EventType': 'eventType', 'VMMigrationFlag':'vmMigration', 'AffectedSubsystem': 'subSystem', 
                             'UserAction':'userAction', 'ComponentInstance': 'compInstance'}
            try:
                for eventProperty in eventsDict[key]:
                    if eventProperty in keyTranslator:
                        commonEvent[keyTranslator[eventProperty]] = eventsDict[key][eventProperty]
                    elif eventProperty == 'timestamp':
                        commonEvent[eventProperty] = str(int(int(eventsDict[key]['timestamp'])/1000))
                    else:
                        commonEvent[eventProperty] = eventsDict[key][eventProperty]
                newEventsDict[key] = commonEvent
            except KeyError:
                print (key +' not found in events dictionary')
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print ("exception: ", exc_type, fname, exc_tb.tb_lineno)
#                 sys.stdout.flush()
                
    return newEventsDict

def statistics2Write():
    """
        Builds the statistics dictionary of data to write
    """
    statistics = {}
    for analyzedID in config.analyzeIDcount:
        statistics['suppressed_'+ analyzedID] = config.analyzeIDcount[analyzedID]
    return statistics

def updateBMCLastReports():
    """
         update the bmc ini file to record last log reported
    """
    global killNow
    confParser = configparser.ConfigParser()
    if os.path.exists(config.bmclastreports):
        try:
            confParser.read(config.bmclastreports)
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print ("exception: ", exc_type, fname, exc_tb.tb_lineno)
    while True:
        if killNow: break
        #node contains {entity: entName, bmchostname: bmchostname, lastlogtime: timestamp, dupTimeIDList: [ID1, ID2]
        node = updateConfFile.get()

        if len(node['dupTimeIDList']) >= 1:
            tmpList = []
            for cerid in node['dupTimeIDList']:
                tmpList.append(str(cerid))
            node['dupTimeIDList'] = tmpList
        data2write = {'lastLogTime': str(node['lastLogTime']), 'dupTimeIDList': node['dupTimeIDList'], 'hrTime': datetime.datetime.fromtimestamp(int(node['lastLogTime'])).strftime("%Y-%m-%d %H:%M:%S")}
        statistics = statistics2Write()
        if len(statistics)>0:
            confParser['statistics'] = statistics
        try:
            if node['entity']+'_bmcs' not in confParser:
                confParser[node['entity']+'_bmcs'] = {}
            confParser[node['entity']+'_bmcs'][node['bmchostname']] = str(data2write)
            with open(config.bmclastreports, 'w') as configfile:
                confParser.write(configfile)
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print("exception: ", exc_type, fname, exc_tb.tb_lineno)
            traceback.print_tb(e.__traceback__)
            print(e)
            continue

        updateConfFile.task_done()



def getBMCAlerts(node):
    """
        Gets alerts from the node's BMC and puts them into a dictionary with a common format
        
        @param node: A dictionary containing properties about a node
        @return: dictionary with common format containing alerts
    """        
    eventList=""
    eventsDict = {}
    name = threading.currentThread().getName()
    bmcHostname = node['bmcHostname']
    impactednode = node['xcatNodeName']
    username = node['username']
    password = node['password']
    try:
        #get the alerts from the bmc and place in a common format
        if(node['accessType']=="openbmcRest"):
            #use openbmctool for openbmc rest interface
            try:
                eventBytes = subprocess.check_output([config.pyString, '/opt/ibm/ras/bin/openbmctool.py', '-H', bmcHostname, '-U', username, '-P', password,'-j','-t','/opt/ibm/ras/lib/policyTable.json', 'sel', 'print'])
                eventList = eventBytes.decode('utf-8')
            except subprocess.CalledProcessError as e:
                if e.returncode == 1:
                    eventList = e.output.decode('utf-8')
                else:
                    errorLogger(syslog.LOG_ERR, "An unknown error has occurred when retrieving bmc alerts from {hostname}. Error Details: {msg}".format(hostname=impactednode, msg=e.message))
                    eventList = {'numAlerts': 0, 'failedPoll': True}
            if not isString(eventList):
                eventList = eventList.decode('utf-8')
            if eventList.find('{') != -1: #check for valid response
                eventList = eventList[eventList.index('{'):]
                eventsDict = json.loads(eventList)
            else:
                errorLogger(syslog.LOG_ERR, "An invalid response was received from bmc when requesting alerts for {hostname}".format(hostname=impactednode))
                eventsDict = {'numAlerts': 0, 'failedPoll': True}
            eventsDict = updateEventDictionary(eventsDict)
        elif(node['accessType']=="ipmi"):
            #use java sel parser and ipmitool to get alerts from ipmi node
            eventList = subprocess.check_output(['java', '-jar', '/opt/ibm/ras/lib/crassd.jar', bmcHostname, username, password]).decode('utf-8')
            if eventList.find('{') != -1: #check for valid response
                eventList = eventList[eventList.index('{'):] #keyboard terminate causing substring not found here
                eventsDict = json.loads(eventList)
            else:
                errorLogger(syslog.LOG_ERR, "An invalid response was received when retrieving bmc alerts from {hostname}. Response Details: {msg}".format(hostname=impactednode, msg=eventList))
                eventsDict = {'numAlerts': 0, 'failedPoll': True}
        else:
            #use redfish
            errorLogger(syslog.LOG_ERR, "redfish not supported")
            eventList = {'numAlerts': 0, 'failedPoll': True}
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print("exception: ", exc_type, fname, exc_tb.tb_lineno)
        print(e)
        traceback.print_tb(e.__traceback__)
        eventsDict = {'numAlerts': 0, 'failedPoll': True}
    
    return eventsDict

def resetFailedNotify(bmcHostname):
    """
       Resets the failed to notify counter for this round of polled events for the specified BMC
       
       @param bmcHostname: The identifier used for the BMC
    """
    for key in notifyList:
        with lock:
            notifyList[key][bmcHostname]['pollNotifyFailed'] = 0

def updateTrackingTimes(event, notifyEntity, bmcHostname):    
    """
        Updates the tracking for last reported BMC alert
    """
    with lock:
        lastlogtime = notifyEntity[bmcHostname]['lastLogTime']
    if event['timestamp'] > lastlogtime:
        with lock: 
            notifyEntity[bmcHostname]['lastLogTime'] = event['timestamp']
            del notifyEntity[bmcHostname]['dupTimeIDList'][:]
            notifyEntity[bmcHostname]['dupTimeIDList'].append(event['CerID'])
    elif event['timestamp'] == lastlogtime:
        with lock:
            notifyEntity[bmcHostname]['dupTimeIDList'].append(event['CerID'])
        
def analyzeit(event, username, bmcHostname, password, accessType):
    """
        Checks to see if analysis needs run and runs it for the provided event. 
        Returns True if the event is valid to report upstream, otherwise returns false.
    """
    analysisPassed = True
    pyVersion = config.pyString
    if(event['CerID'] in config.analyzeIDList and accessType == 'openbmcRest'):
        script2call = 'analyze{id}.py'.format(id=event['CerID'])
        if 'FQPSPW0034M' in script2call:
            pyVersion = 'python'
        command = [pyVersion, script2call, '-c', '-U', username, '-H', bmcHostname, '-P', password, '-n', event['logNum']]
        if 'clear' in config.analysisOptions[event['CerID']]:
            command.append('-a')
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        result, err = proc.communicate()
        if 'false' in result.decode('utf-8').lower():
            analysisPassed = False
            with lock: 
                config.analyzeIDcount[event['CerID']] +=1
    return analysisPassed
       
def processAlert(event, bmcHostname, impactednode, username, password, accessType):   
    """
        Processes the given alert and notifies the correct entity. If unable to report, increments pollNotifyFailed
        for the notify entity. 
       
       @param event: Dictionary containing all the alert properties
       @return: True if the notifyTimes need updated, False otherwise
    """
    updateTimes = False
    analysisPassed = None
    for key in notifyList:
        updateNotifyTimes = False
        
        with lock:
            receiveEntityStatus = notifyList[key]['receiveEntityDown']
            dupList = notifyList[key][bmcHostname]['dupTimeIDList']
            func = notifyList[key]['function']
            notifyList[key]['failedFirstTry'] = False
            lastlogtime = notifyList[key][bmcHostname]['lastLogTime']
            failedThisPoll = notifyList[key][bmcHostname]['pollNotifyFailed']
        newAlert = (event['timestamp']>lastlogtime or 
                    (event['timestamp']==lastlogtime and event['CerID'] not in dupList) and
                    failedThisPoll==0)
        if(newAlert):
            #only report new alerts
            if analysisPassed is None:
                #run any available analysis scripts
                analysisPassed = analyzeit(event, username, bmcHostname, password, accessType)
            if analysisPassed:
                #process the valid alert
                repsuccess = func(event, impactednode, notifyList) 
                with lock:
                    notifyList[key]['successfullyReported'] = repsuccess
                if repsuccess:
                    updateTrackingTimes(event, notifyList[key], bmcHostname)
                    updateNotifyTimes = True
                else:
                    with lock:
                        notifyList[key]['failedFirstTry'] = True
                        receiveEntityStatus = notifyList[key]['receiveEntityDown']
                    if(receiveEntityStatus== False):
                        with lock:
                            func = notifyList[key]['function']
                        repsuccess = func(event, impactednode, notifyList)
                        
                        with lock:
                            notifyList[key]['successfullyReported'] = repsuccess 
                        if(repsuccess):
                            updateTrackingTimes(event, notifyList[key], bmcHostname)
                            updateNotifyTimes = True
                        else:
                            with lock:
                                notifyList[key][bmcHostname]['pollNotifyFailed'] += 1
                    else:
                        with lock:
                            notifyList[key][bmcHostname]['pollNotifyFailed'] += 1
            else:
                #analysis found a false alert, filter it
                updateTrackingTimes(event, notifyList[key], bmcHostname)
                updateNotifyTimes = True
                errorLogger(syslog.LOG_INFO, "Filtered alert {id} on {thenode}".format(id=event['CerID'], thenode=impactednode))
            if updateNotifyTimes:
                #node contains {entity: entName, bmchostname: bmchostname, lastlogtime: timestamp, dupTimeIDList: [ID1, ID2]     
                updateNotifyTimesData = {'entity': key, 'bmchostname': bmcHostname, 'lastLogTime': notifyList[key][bmcHostname]['lastLogTime'],
                                          'dupTimeIDList': notifyList[key][bmcHostname]['dupTimeIDList']}
                updateConfFile.put(updateNotifyTimesData)

 
def BMCEventProcessor():
    """
         processes alerts and is run in child threads
    """  
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
            eventList = {}
            bmcEvent = {}
            name = threading.currentThread().getName()
            bmcHostname = node['bmcHostname']
            impactednode = node['xcatNodeName']
            username = node['username']
            password = node['password']
            resetFailedNotify(bmcHostname)
            try:
                print(name +": " + bmcHostname)
                #get the alerts from the bmc and place in a common format
                eventsDict = getBMCAlerts(node)
                
                #process the alerts
                if (eventsDict['numAlerts'] == 0):
                    #node poll was successful and no alerts to process
                    node['pollFailedCount'] = 0
                    continue
                elif('failedPoll' in eventsDict):
                    node['pollFailedCount'] += 1
                    if(node['pollFailedCount'] != 2):
                        #create a log entry for failing to process sel entries
                        errorLogger(syslog.LOG_ERR, "Failed to process BMC alerts for {host} three or more times".format(host=impactednode))
                        continue
                else:
                    #process the received alerts
                    for i in range(len(eventsDict)-1):
                        if(killNow):
                            break
                        event = "event" +str(i)
                        bmcEvent = eventsDict[event]
                        if "error" in eventsDict[event]:
                            node['pollFailedCount'] = 0
                            begIndex = eventsDict[event]['error'].rfind(":") + 2
                            missingKey = eventsDict[event]['error'][begIndex:]
                            if(missingKey not in missingEvents.keys()):
                                with lock: 
                                    missingEvents[missingKey] = True
                                errorLogger(syslog.LOG_ERR, "Event not found in lookup table for node {node}: {alert}".format(alert=missingKey, node=impactednode))
                        else:
                            #check for failure to poll the bmc
                            if(eventsDict[event]['CerID'] in networkErrorList):
                                if (nodeCommsLost == False):
                                    nodeCommsLost = True
                                    node['pollFailedCount'] += 1
                                if(node['pollFailedCount'] != 2):
                                    #forward the network connection failure at 3 consecutive failures. 
                                    continue

                            #process the alerts
                            processAlert(eventsDict[event], bmcHostname, impactednode, username, password, node['accessType'])                                   
                nodes2poll.task_done()
            except Exception as e:
                print
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print("exception: ", exc_type, fname, exc_tb.tb_lineno)
                print(e)
            eventsDict.clear()
            
            
def loadBMCLastReports():
    """
         Loads the previously reported alerts from a configuration file
           
         @return: modifies global list of monitored nodes with previously reported alerts
    """ 
    if os.path.exists(config.bmclastreports):
        confParser = configparser.ConfigParser()
        global notifyList
        try: 
            confParser.read(config.bmclastreports)
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
            if 'statistics' in confParser:
                for key in dict(confParser['statistics']):
                    id = key.split('suppressed_')[1].upper()
                    config.analyzeIDcount[id] = int(confParser['statistics'][key])
        except KeyError:
            errorLogger(syslog.LOG_ERR, "No section: bmcs in ini file. All bmc events will be forwarded to entities being notified. ")
        except configparser.NoSectionError:
            errorLogger(syslog.LOG_ERR, "No section: "+str(key) +"_bmcs in ini file. All bmc events will be forwarded to entities being notified. ")

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
    needWebsocket = False
    try:
        nodes = dict(confParser.items('nodes'))
        for key in nodes:
            mynodelist.append(json.loads(nodes[key].replace("'",'"')))
            if 'username' not in mynodelist[-1]:
                if mynodelist[-1]['accessType'] == "ipmi":
                    mynodelist[-1]['username'] = "ADMIN"
                    mynodelist[-1]['password'] = "ADMIN"
                elif mynodelist[-1]['accessType'] == 'openbmcRest':
                    mynodelist[-1]['username'] = "root"
                    mynodelist[-1]['password'] = "0penBmc"
            if mynodelist[-1]['accessType'] == 'openbmcRest':
                needWebsocket = True
            mynodelist[-1]['dupTimeIDList'] = []
            mynodelist[-1]['lastLogTime'] = '0'
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
        errorLogger(syslog.LOG_CRIT, "Unable to read node list from configuration file")
        sys.exit()
    
    #load optional module for monitoring openbmc systems
    if needWebsocket:
        global notificationlistener
        import notificationlistener
    
def isString(var):
    if sys.version_info < (3,0):
        return isinstance(var, basestring)
    else:
        return isinstance(var, str)
    
def validatePluginNotifications(confParser):
    """
        Validates plugins loaded for each of the designated notifications. 
        Will remove reported to entities if their plugin's notify function isn't found
        @confParser: the configuration file parser with the data containing node info
    """
    #check for entities to notify that don't have associated plugin
    missingPlugins = []
    for entity in notifyList:
        if isString(notifyList[entity]['function']):
            errorLogger(syslog.LOG_WARNING,"Notify function not found " + notifyList[entity]['function'] +". This entity will not be notified of alerts.")
            missingPlugins.append(entity)
    
    #remove entities to notify that don't have the associated plugin
    for plugin in missingPlugins:
        del notifyList[plugin]

def getConfigPaths(forceHostname=False):
    '''
        Determines the right pathname to use for the config file and
        for the bmc last reports file. 
    '''
    
    hostname = socket.gethostname().split('.')[0]
    path = os.sep.join(config.configFileName.split('/')[:-1])
    dynamicConfigFile = path + os.sep + hostname + '.' + config.configFileName.split('/')[-1]
    useHostname = False
    if forceHostname:
        useHostname = True
    if os.path.exists(dynamicConfigFile):
        if hostname not in config.configFileName:
            config.configFileName = dynamicConfigFile
            useHostname=True
        
    confParser = configparser.ConfigParser()
    confParser.read(config.configFileName)
    basePath = config.bmclastreports
    if 'lastReports' in confParser:
        basePath = confParser['lastReports']['fileLoc']
    if useHostname:
        config.bmclastreports = basePath + os.sep + hostname + '.bmclastreports.ini'
    else:
        config.bmclastreports = basePath + os.sep + 'bmclastreports.ini'
    
def setupNotifications():
    """
        Loads the information from the configuration file and setup notification to monitoring entities
        @return the configuration parser object   
    """ 
    #read the config file
    confParser = configparser.ConfigParser()
    getConfigPaths()
    try:
        #check for dynamic config file
        if os.path.exists(config.configFileName):
            confParser.read(config.configFileName)
            test = dict(confParser.items('notify'))
            for key in test:
                if test[key] == 'True':
                    notifyList[key] = {"function": test[key+'function'], 
                                        "receiveEntityDown":False,
                                        "failedFirstTry": False,
                                        "successfullyReported": True}
                    if confParser.has_section(key):
                        pluginConfSettings = {key: dict(confParser.items(key))}
                        config.pluginConfigs.update(pluginConfSettings)
        else:
            errorLogger(syslog.LOG_CRIT, "Configuration file not found. Exiting.")
            sys.exit()
    except KeyError:
        errorLogger(syslog.LOG_ERR, "No section: notify in file ibm-crassd.config. Alerts will not be forwarded. Terminating")
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
                        errorLogger(syslog.LOG_CRIT, 'Plugin: ' + i['name'] + ' failed to initialize. Aborting now.')
                        sys.exit()
        for entity in notifyList:
            if isString(notifyList[entity]['function']):
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
        #loads all nodes into the queue for retrieving the current state of the nodes
        nodes2poll.put(node)
        
def getMinimumPollingInterval(numWorkerThreads):
    """
        determines the number of passes that have to be made to process all nodes. Passes are only used for 
        polling a node. Absolute minimum polling interval is 30 seconds.  
    
        @return: Integer value representing the number of seconds between polling
    """
    #count number of nodes being polled, omit ones using push notifications
    count = 0
    for node in mynodelist:
        if node['accessType'] == 'ipmi':
            count += 1
    if count == 0: 
        count=1       
    numpasses = math.ceil(float(count)/numWorkerThreads)       
    #Time below in seconds
    minPollingInterval = 25*numpasses
    
    return minPollingInterval

def setDefaultBMCCredentials(node):
    if mynodelist[-1]['accessType'] == "ipmi":
        node ['username'] = "ADMIN"
        node['password'] = "ADMIN"
    elif mynodelist[-1]['accessType'] == 'openbmcRest':
        node['username'] = "root"
        node['password'] = "0penBmc"
        
def updateConfigFileNodes(confParser, nodes2monitor):
    """
        Writes changes to the configuration file for the nodes to monitor. 
        Only used during auto configuration
    """
    count = 1
    nodeDict = {}
    for node in nodes2monitor:
        nodeDict['node{num}'.format(num=count)] = {
            'bmcHostname': nodes2monitor[node]['bmcHostname'],
            'xcatNodeName': nodes2monitor[node]['xcatNodeName'],
            'accessType': nodes2monitor[node]['accessType']}
        count += 1
    confParser['nodes'] = nodeDict
    with open(config.configFileName, 'w') as configfile:
        confParser.write(configfile)

def autoConfigureNodes(confParser):
    """
        Attempts to autoConfigure the nodes to monitor
    """
    hostname = subprocess.check_output('hostname').decode('utf-8').strip()
    if ('.' in hostname):
        hostname = hostname.split('.')[0]
    nodeOutput= subprocess.check_output([config.pyString, 'buildNodeList.py', '-j']).decode('utf-8')
    nodes2monitor = {}
    dynamicConfigFile = config.configFileName
    if hostname not in config.configFileName:
        path = os.sep.join(config.configFileName.split('/')[:-1])
        dynamicConfigFile = path + os.sep + hostname + '.' + config.configFileName.split('/')[-1]
        config.configFileName= dynamicConfigFile

    needWebsocket = False
    if 'Error' not in nodeOutput:
        xcatNodes = json.loads(nodeOutput)
        if hostname in xcatNodes:
            nodes2monitor = xcatNodes[hostname]
        else:
            errorLogger(syslog.LOG_CRIT, "Unable to auto-configure ibm-crassd. Please ensure nodes are configured in the configuration file at /opt/ibm/ras/etc/ibm-crassd.config")
            killNow = True
            sys.exit(1)
        try:
            for node in nodes2monitor:
                mynodelist.append({'xcatNodeName': nodes2monitor[node]['xcatNodeName'], 
                                   'bmcHostname': nodes2monitor[node]['bmcHostname'],
                                   'accessType': nodes2monitor[node]['accessType'],
                                   'pollFailedCount': 0,
                                   'lastLogTime': '0',
                                   'dupTimeIDList': []})
                
                setDefaultBMCCredentials(mynodelist[-1])
                if mynodelist[-1]['accessType'] == 'openbmcRest':
                    needWebsocket = True
                for entity in notifyList:
                    notifyList[entity][mynodelist[-1]['bmcHostname']] = {
                    'lastLogTime': mynodelist[-1]['lastLogTime'],
                    'dupTimeIDList': mynodelist[-1]['dupTimeIDList']}
            if len(mynodelist)<1:
                errorLogger(syslog.LOG_CRIT, "Unable to auto-configure ibm-crassd. Please ensure nodes are configured in the configuration file at /opt/ibm/ras/etc/ibm-crassd.config")
                killNow = True
                sys.exit(1)
        except Exception as e:
            #Log the exception and terminate
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            errorLogger(syslog.LOG_ERR, "Exception: {type}, {frame}, {line}, {details}".format(
                type=exc_type, frame=fname, line=exc_tb.tb_lineno, details=e))
            errorLogger(syslog.LOG_CRIT, "Unable to configure nodes automatically.")
            sys.exit(1)
    
        #load optional module for monitoring openbmc systems
        if needWebsocket:
            global notificationlistener
            import notificationlistener
        updateConfigFileNodes(confParser, nodes2monitor)
        getConfigPaths(True)
    else:
        errorLogger(syslog.LOG_CRIT, "Unable to auto-configure ibm-crassd. Please ensure nodes are configured in the configuration file at /opt/ibm/ras/etc/ibm-crassd.config")
        killNow = True
        sys.exit(1)

def getIDstoAnalyze(confParser):
    directory = os.getcwd() + os.sep
    filelist = [afile for afile in os.listdir(directory) if os.path.isfile(''.join([directory, afile]))]
    try:
        if 'analysis' in confParser:
            for id in confParser['analysis']:
                upperID = id.upper()
                if 'clear' in confParser['analysis'][id]:
                    config.analysisOptions[upperID] = 'clear'
                elif 'filter' in confParser['analysis'][id]:
                    config.analysisOptions[upperID] = 'filter'
                if id not in config.analyzeIDList:
                    with lock:
                        config.analyzeIDList.append(upperID)
                        config.analyzeIDcount[upperID] = 0
            for id in config.analyzeIDList:
                tempfilename = 'analyze{id}.py'.format(id=upperID)
                if tempfilename not in filelist:
                    errorLogger(syslog.LOG_CRIT, "Unable to find analysis script {scriptName}. Continuing to run without it.".format(scriptName=tempfilename))
                    with lock:
                        config.analyzeIDList.remove(upperID)
                        config.analyzeIDcount.pop(upperID, None)
            return
    except Exception as e:
        errorLogger(syslog.LOG_CRIT, "Unable to read the analysis section of the ibm-crassd configuration file. Attempting to run with the installed analysis scripts in filter mode.")

    for f in filelist:
        if 'analyze' in f:
            id = f.split('analyze')[1].split('.')[0]
            if id not in config.analyzeIDList:
                with lock:
                    config.analyzeIDList.append(id)
                    config.analyzeIDcount[id] = 0
                    config.analysisOptions[id] = 'filter'

def updateMaxThreads(confParser):
    """
        Called after an autoconfigure to set the maxThreads variable dynamically to ensure best performance
    """
    nodeCount = len(mynodelist)
    maxThreads = 1
    if nodeCount > 40:
        maxThreads = 40
    else:
        maxThreads = nodeCount
    confParser['base_configuration']['maxThreads'] = str(maxThreads)
    
    with open(config.configFileName, 'w') as configfile:
        confParser.write(configfile)
    
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
    networkErrorList = config.networkErrorList
    
    #Setup Notifications for entities to push alerts to
    confParser = setupNotifications()
    

    
    #validate all of the needed plugins loaded
    validatePluginNotifications(confParser)
    errorLogger(syslog.LOG_INFO, "Node Count: {count}".format(count=len(mynodelist)))
    #check the node count to see if nodes were specified
    if len(mynodelist)<1:
        #The node list seems short, attempt to scan for nodes that report to this service node
        autoConfigureNodes(confParser)
        updateMaxThreads(confParser)

    #Check for analysis scripts
    getIDstoAnalyze(confParser)
    #load last reported times from storage file to prevent duplicate entries
    loadBMCLastReports()

    
    #Determine the maximum number of nodes
    maxThreads = 1
    try:
        maxThreads = int(confParser['base_configuration']['maxThreads'])
    except KeyError:
        errorLogger(syslog.LOG_ERR, "No section: base configuration in file ibm-crassd.config. Defaulting to one thread for polling") 
        
    
    if(maxThreads >= len(mynodelist)):
        maxThreads = len(mynodelist)

    if(maxThreads<1): maxThreads=1
    minPollingInterval = getMinimumPollingInterval(maxThreads)
    #Create the worker threads
    
    for i in range(maxThreads):
        print("Creating thread " + str(i))

        t = threading.Thread(target=BMCEventProcessor)
        t.daemon = True
        t.start()   
      
    t = threading.Thread(target=updateBMCLastReports)
    t.daemon = True
    t.start()
    
    configurePushNotifications()
    
    #start TelemetryServer if enabled
    if 'enableTelemetry' in confParser['base_configuration']:
        enableTelem = confParser['base_configuration']['enableTelemetry']
        if confParser['base_configuration']['enableTelemetry'] == 'True':
            if 'telemetryPort' in confParser['base_configuration']:
                config.telemPort = int(confParser['base_configuration']['telemetryPort'])
            telemThread = threading.Thread(target=telemetryServer.main)
            telemThread.daemon = True  
            telemThread.start()
    
    queryAllNodes()
    #Setup polling interval
    pollNodes(minPollingInterval) 

def pollNodes(interval):
    """
         Used as timer for the polling interval. set to 25 second minimum
           
         @return: Does not return a specific value but loads the global queue with nodes that get polled 
    """ 
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
    #setup the interrupt to handle SIGTERM, SIGINT
    signal.signal(signal.SIGTERM, sigHandler)
    signal.signal(signal.SIGINT, sigHandler)
    signal.signal(signal.SIGUSR1, sigHandler)
    signal.signal(signal.SIGUSR2, updateTimesforLastReports)
    try:
        initialize()
        print(os.getpid())
        while(True):
            time.sleep(1)
            if(killNow):
                break
        errorLogger(syslog.LOG_ERR, "The Power HW Monitoring service has been stopped")
        sys.exit()
    except KeyboardInterrupt:
        print ("Terminating")
        sys.exit()