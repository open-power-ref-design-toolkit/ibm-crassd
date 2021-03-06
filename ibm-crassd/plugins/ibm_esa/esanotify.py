"""
 Copyright 2017, 2020 IBM Corporation

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
import requests
import json
import syslog
import config
from config import *
try:
    import Queue as queue
except ImportError:
    import queue
import traceback
import socket
import multiprocessing
import openbmctool
import subprocess
import sys
import os, shutil
import time
import threading
import datetime
from apscheduler.schedulers.background  import BackgroundScheduler
from apscheduler.events import *
import smtplib
from smtplib import SMTPException

def checkESAConnection(esaIP, esaPort):
    """
        Establish a connection with the ESA application
        if successful return true, otherwise return false
        will generate journal entries with connection problems. 
        @param esaIP: The network address for the ESA application
        @param esaPort: The network port for the ESA application
    """
    config.pluginVars['esa']['session'] = requests.session()
    esasess= config.pluginVars['esa']['session']
    baseurl = 'https://{esaip}:{esaport}/rest/v1/'.format(esaip=esaIP, esaport=esaPort)
    resp = esasess.get(baseurl, verify=False)
    if resp.status_code == 200:
        jsonData = resp.json()
        if 'accepting requests' in jsonData['items']['details']:
            config.pluginVars['esa']['baseurl'] = baseurl
            return True
        else:
            config.errorLogger(syslog.LOG_ERR, 'ESA is alive but not ready to receive alerts. Status: {stat} Details: {err}'.format(stat= jsonData['items']['config-status'],err=jsonData['items']['details']))
    else:
        config.errorLogger(syslog.LOG_ERR, 'Unable to connect to ESA. {Code}: {desc}'.format(Code=requests.status_codes._codes[resp.status_code][0]))
    
    return False

def registerCRASSD(esaIP, esaPort):
    """
        Establish a session with the ESA application and register the ibm-crassd application
        This populates a plugin global variable with the ESA id for the service
        Otherwise, it sets that variable to NoneType
        @param esaIP: The network address for the ESA application
        @param esaPort: The network port for the ESA application
    """
    #Attempt to create record for ibm-crassd
    #The order of the data is important in the JSON structure
    esasess = config.pluginVars['esa']['session']
    crassdData = {
        'hostname': 'ibm-crassd-{thissys}'.format(thissys=config.hostname),
        'app.owner': 'CRASSD',
        'product.software':[
            {
                'version': config.crassd_version,
                'GUID':str(config.crassd_uuid),
                'CompID': 'ESA-Plugin',
                'ProductID': 'ibm-crassd',
                'Division': 'RAS',
                'description': 'A HW monitoring service for Power systems',
                'vendor': 'IBM'
            }
        ],
        'EndpointType': 'ServiceMonitor'
       }
    encodedJSONData = json.dumps(crassdData)
    url = config.pluginVars['esa']['baseurl']+'endpoint/'
    resp = esasess.post(url, headers=config.pluginVars['esa']['esa_header'], data=encodedJSONData, verify=False)
 # sample data   {'status': {'code': 201, 'message': 'Warning. An existing system record was updated as a result.'}, 'system.id': '528f69400d4a7774325a15523d79e8f1'}
    if resp.status_code == 200:
        respContent = resp.json()
        if respContent['status']['code'] in [200, 201]:
            config.pluginVars['esa']['crassdID'] = respContent['system.id']
        else: 
            config.errorLogger(syslog.LOG_ERR, "ESA registration of ibm-crassd failed. ESA Status code: {scode}; Message {msg}".format(scode=respContent['status']['code'], msg=respContent['status']['message']))
            config.pluginVars['esa']['crassdID'] = None
    else:
        config.errorLogger(syslog.LOG_ERR, "Failed to register ibm-crassd with the ESA application. Status code: {scode}; Message {msg}")
        config.pluginVars['esa']['crassdID'] = None


def getOBMCEndpointInfo(hostIP, nodeIP, nodeUser, nodePass):
    '''
        Collects System information from the OpenBMC codestack so the node
        can be registered with ESA. Includes MTM and serial number.
        @param hostIP: The IP address or hostname for the Host OS
        @param nodeIP: The address of the bmc
        @param nodeUser: The username for the BMC
        @param nodePass: The password for the BMC
        @return: NoneType if collection failed, 
                 Dictionary with node info if successful
    '''
    bmcsession = openbmctool.login(nodeIP, nodeUser, nodePass, True, False)
    nodeInfo = None
    if isinstance(bmcsession, str):
        config.errorLogger(syslog.LOG_ERR, "ESA Plugin Failed to login to the bmc: {bmc}".format(bmc=nodeIP))
    else:
        url="https://"+nodeIP+"/xyz/openbmc_project/inventory/system"
        try:
            res = bmcsession.get(url, headers=openbmctool.jsonHeader, verify=False, timeout=60)
            if 'data' in res.json():
                nodeInfo = res.json()['data']
                nodeInfo['hostname'] = hostIP
                nodeInfo['FirmwareInfo'] = ''
        except(requests.exceptions.Timeout):
            config.errorLogger(syslog.LOG_ERR, "ESA Plugin Failed to get system MTMS: {bmc}. Timed out waiting for the BMC".format(bmc=nodeIP))
            return None
        except Exception as e:
            config.errorLogger(syslog.LOG_ERR, "Failed to collect firmware info: {bmc}".format(bmc=nodeIP))
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
            traceback.print_tb(e.__traceback__)
            return None
        
        url="https://"+nodeIP+"/xyz/openbmc_project/software/functional"
        try:
            res = bmcsession.get(url, headers=openbmctool.jsonHeader, verify=False, timeout=60)
            info = res.json()
            if 'endpoints' in info['data']:
                for swID in info['data']['endpoints']:
                    url="https://"+nodeIP+swID
                    swres = bmcsession.get(url, headers=openbmctool.jsonHeader, verify=False, timeout=60)
                    swData = swres.json()['data']
                    if 'BMC' in swData['Purpose']:
                        nodeInfo['FirmwareInfo'] = nodeInfo['FirmwareInfo'] + "BMC: {version}\n".format(version=swData['Version'])
                    else:
                        nodeInfo['FirmwareInfo'] = nodeInfo['FirmwareInfo'] + "Host: {version}\n".format(version=swData['Version'])
        except(requests.exceptions.Timeout):
            config.errorLogger(syslog.LOG_ERR, "ESA Plugin Failed to get system MTMS: {bmc}".format(bmc=nodeIP))
            return None
        except Exception as e:
            config.errorLogger(syslog.LOG_ERR, "Failed to collect firmware info: {bmc}".format(bmc=nodeIP))
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
            traceback.print_tb(e.__traceback__)
            return None
        return nodeInfo        


def getIPMIEndpointInfo(hostIP, nodeIP, nodeUser, nodePass):
    '''
        Collects information from an IPMI based system
        @param hostIP: The IP address or hostname for the Host OS
        @param nodeIP: The address of the bmc
        @param nodeUser: The username for the BMC
        @param nodePass: The password for the BMC
        @return: NoneType if collection failed, 
                 Dictionary with node info if successful
    '''
    nodeInfo = None
    try:
        chassisInfo = subprocess.check_output(['/usr/bin/ipmitool', 
                                               '-I', 'lanplus',
                                               '-H', nodeIP, 
                                               '-U', nodeUser, 
                                               '-P', nodePass, 
                                               'fru', 'print', '0'
                                              ], stderr=subprocess.STDOUT).decode('utf-8')
        nodeInfo = {}
        for line in chassisInfo.split("\n"):
            #AssetTag
            if 'Product Asset Tag' in line:
                nodeInfo['AssetTag'] = line.split(':')[1].strip()
            #BuildDate
            elif 'Board Mfg Date' in line:
                nodeInfo['BuildDate'] = ':'.join(line.split(':')[1:]).strip()
            #Manufacturer
            elif 'Product Manufacturer' in line:
                nodeInfo['Manufacturer'] = line.split(':')[1].strip()
            #Model
            elif 'Chassis Part Number' in line:
                nodeInfo['Model'] = line.split(':')[1].strip()
            #PartNumber
            elif 'Product Part Number' in line:
                nodeInfo['PartNumber'] = line.split(':')[1].strip()
            #SerialNumber
            elif 'Chassis Serial' in line:
                nodeInfo['SerialNumber'] = line.split(':')[1].strip()
            else:
                continue
    except subprocess.CalledProcessError as e:
        errorContent = e.output.decode('utf-8')
        if 'Address lookup' in errorContent:
            config.errorLogger(syslog.LOG_ERR, "Failed to connect to the BMC for {node}. Ensure the specified address is correct.".format(node=hostIP))
        else:
            config.errorLogger(syslog.LOG_ERR, "Failed to collect chassis information from the BMC for {node}.".format(node=nodeIP))
            config.errorLogger(syslog.LOG_DEBUG, errorContent)
        return None
    except Exception as e:
        config.errorLogger(syslog.LOG_ERR, "Failed to collect chassis information from the BMC for {node}.".format(node=nodeIP))
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
        traceback.print_tb(e.__traceback__)
        return None
    
    nodeInfo['hostname'] = hostIP
    firmwareString = ''
    #collect host firmware info
    try:
        chassisInfo = subprocess.check_output(['/usr/bin/ipmitool', 
                                               '-I', 'lanplus',
                                               '-H', nodeIP, 
                                               '-U', nodeUser, 
                                               '-P', nodePass, 
                                               'fru', 'print', '47'
                                              ], stderr=subprocess.STDOUT).decode('utf-8')
        for line in chassisInfo.split("\n"):
            if 'Product Version' in line:
                firmwareInfo  = "Host: {version}\n".format(version=line.split(':')[1].strip())
                break
            else:
                continue
    except subprocess.CalledProcessError as e:
        errorContent = e.output.decode('utf-8')
        if 'Address lookup' in errorContent:
            config.errorLogger(syslog.LOG_ERR, "Failed to connect to the BMC for {node}. Ensure the specified address is correct.".format(node=hostIP))
        else:
            config.errorLogger(syslog.LOG_ERR, "Failed to collect chassis information from the BMC for {node}.".format(node=nodeIP))
            config.errorLogger(syslog.LOG_DEBUG, errorContent)
        return None
    except Exception as e:
        config.errorLogger(syslog.LOG_ERR, "Failed to collect chassis information from the BMC for {node}.".format(node=nodeIP))
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
        traceback.print_tb(e.__traceback__)
        return None

    # collect bmc firmware info
    try:
        chassisInfo = subprocess.check_output(['/usr/bin/ipmitool', 
                                               '-I', 'lanplus',
                                               '-H', nodeIP, 
                                               '-U', nodeUser, 
                                               '-P', nodePass, 
                                               'mc', 'info'
                                              ], stderr=subprocess.STDOUT).decode('utf-8')
        for line in chassisInfo.split("\n"):
            if 'Firmware Revision' in line:
                firmwareInfo  = firmwareInfo + "BMC: {version}\n".format(version= line.split(':')[1].strip())
                break
            else:
                continue
    except subprocess.CalledProcessError as e:
        errorContent = e.output.decode('utf-8')
        if 'Address lookup' in errorContent:
            config.errorLogger(syslog.LOG_ERR, "Failed to connect to the BMC for {node}. Ensure the specified address is correct.".format(node=hostIP))
        else:
            config.errorLogger(syslog.LOG_ERR, "Failed to collect chassis information from the BMC for {node}.".format(node=nodeIP))
            config.errorLogger(syslog.LOG_DEBUG, errorContent)
        return None
    except Exception as e:
        config.errorLogger(syslog.LOG_ERR, "Failed to collect chassis information from the BMC for {node}.".format(node=nodeIP))
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
        traceback.print_tb(e.__traceback__)
        return None

    nodeInfo['FirmwareInfo']= firmwareInfo
    return nodeInfo


def registerHWEndpoint(esaIP, esaPort, endpointInfo):
    """
        Establish a session with the ESA application and register a system
        @param esaIP: The IP address or hostname for the esa application
        @param esaPort: The network port number for the esa service
        @param endpointInfo: dictionary containing information about the system to register
        @return: NoneType if registration failed, otherwise a string containing the esaID for the system
    """
    #Attempt to create record for a managed system
    #The order of the data is important in the JSON structure
    descript = 'Power 9 System with OpenBMC'
    esasess = config.pluginVars['esa']['session']
#    {'AssetTag': 'PRI[Ve87-f34*2841853&&1582154252000]PRI', 'BuildDate': '',
#      'Cached': False, 'FieldReplaceable': False, 'Manufacturer': '', 
#      'Model': '8335-GTC        ', 'PartNumber': '', 'Present': True, 'PrettyName': '', 'SerialNumber': '131886a         '}
    try:
        sysData = {
                'hostname': endpointInfo['hostname'],
                'app.owner': 'CRASSD',
                'product.hardware':[
                    {
                        'vendor': 'IBM',
                        'description': endpointInfo['PrettyName'],
                        'Model': endpointInfo['Model'].split('-')[1].strip(),
                        'MachineType': endpointInfo['Model'].split('-')[0].strip(), 
                        'SerialNumber': endpointInfo['SerialNumber'].strip(),
                        'info.about': 'basic'
                    }
                ],
                'related-endpoints':[
                    {
                        'related-by': 'managedBy',
                        'system.id': config.pluginVars['esa']['crassdID']
                    }
                ],
                'firmware.info':"BMC: ibm-v2.3-476-g2d622cb-r33-coral-cfm-0-gb2c03c9 \n HOST: IBM-witherspoon-OP9_v2.0.14_1.2",
                'EndpointType': 'ServiceProcessor'
               }
        encodedJSONData = json.dumps(sysData)

        resp3 = requests.Session().post(config.pluginVars['esa']['baseurl']+'endpoint/', headers=config.pluginVars['esa']['esa_header'], data=encodedJSONData, verify=False)
        if resp3.status_code == 200:
            content = resp3.json()
            if content['status']['code'] == 200 or content['status']['code'] == 201:
                return content['system.id']
            else:
                config.errorLogger(syslog.LOG_ERR, 'An error occurred trying to register the endpoint.')
                config.errorLogger(syslog.LOG_ERR, 'ESA Application Response: {errorInfo}'.format(errorInfo=content['status']['message']))
                return None
        else:
            config.errorLogger(syslog.LOG_ERR, 'An error occurred when reaching the ESA application REST API')
            config.errorLogger(syslog.LOG_ERR, 'Error Code {errcode}: {desc}'.format(errcode=resp.status_code, desc=requests.status_codes._codes[resp3.status_code][0]))
            return None
    except Exception as e:
        config.errorLogger(syslog.LOG_ERR, "Failed to register {node} with the ESA application.".format(node=endpointInfo['hostname']))
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
        traceback.print_tb(e.__traceback__)
        return None


def nodeInfoCollection(anode):
    '''
        Takes in the parameters of a node and calles the corresponding collection function
        @param anode: dict containing information about the node
        @return: a dictionary with the node and updated properties
    '''
    node = anode.copy()
    if node['accessType'] == 'ipmi':
        nodeInfo = getIPMIEndpointInfo(node['xcatNodeName'], node['bmcHostname'], node['username'], node['password'])
        if nodeInfo is None:
            node['esaRegistered'] = False
            return node
        else:
            nodeInfo['PrettyName'] = nodeInfo['hostname']
    elif node['accessType'] == 'openbmcRest':
        nodeInfo = getOBMCEndpointInfo(node['xcatNodeName'], node['bmcHostname'], node['username'], node['password'])
        if nodeInfo is None:
            node['esaRegistered'] = False
            return node
    else:
        print('Unsupported BMC access type')
        node['esaRegistered'] = False
        return node

    try: 
        #Remove the ending dots
        nodeInfo['Model']=nodeInfo['Model'].replace('.','')
        nodeInfo['SerialNumber']=nodeInfo['SerialNumber'].replace('.','')
    except Exception as e:
        config.errorLogger(syslog.LOG_ERR, "ESA Plugin Failed to get system MTMS: {bmc}".format(bmc=node['bmcHostname']))
        node['esaRegistered'] = False
        return node
        
    nodeid = registerHWEndpoint(config.pluginVars['esa']['esa_ip'],config.pluginVars['esa']['esa_port'], nodeInfo)
    node['MTM'] = nodeInfo['Model'].strip()
    node['Serial'] = nodeInfo['SerialNumber'].strip()
    if nodeid is not None:
        node['esaRegistered'] = True
        config.errorLogger(syslog.LOG_ERR, "Node is Registered in ESA succesfully:{bmc}".format(bmc=node['bmcHostname']))
        node['esaID'] = nodeid
    else:
        node['esaRegistered'] = False
    return node


def esaHeartbeat():
    '''
        Performs the heart beat for the nodes
        @return: True if heart beat was able to be sent, False if heart beat sending failed
    '''
    
    # Base structure for the heartbeat
    # {"app.owner": "string","endpoints": [{"system.id": "string"}]}
    
    #generate the list of endpoints for the packet
    esasess = config.pluginVars['esa']['session']
    endpointList = [{'system.id': config.pluginVars['esa']['crassdID']}]
    
 
    for node in config.mynodelist:
        if 'Connected' in config.nodeProperties[node['xcatNodeName']]:
            connected = config.nodeProperties[node['xcatNodeName']]['Connected']
        else :
            connected = None
        if 'LastUpdateReceived' in config.nodeProperties[node['xcatNodeName']]:
             lastUpdateTime = config.nodeProperties[node['xcatNodeName']]['LastUpdateReceived']
        else :
             lastUpdateTime = None
       
        if connected is None or lastUpdateTime is None: continue
        if not config.nodeProperties[node['xcatNodeName']]['esaRegistered']:
            #The node has never been registered with esa
            try:
                newNode = nodeInfoCollection(node)                
                if newNode['esaRegistered'] :
                    config.updateManagedDict(config.nodeProperties[node['xcatNodeName']], newNode)  
                    endpointList.append({'system.id': config.nodeProperties[node['xcatNodeName']]['esaID']})
                else:
                    continue
            except Exception as e:
                config.errorLogger(syslog.LOG_ERR, "Failed to register {node} with the ESA application.".format(node=endpointInfo['hostname']))
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
                traceback.print_tb(e.__traceback__)
                continue
        if config.nodeProperties[node['xcatNodeName']]['Connected']:
            #ibm-crassd has an active connection with the system
            endpointList.append({'system.id': config.nodeProperties[node['xcatNodeName']]['esaID']})
        elif (not connected and ((int(time.time())-lastUpdateTime) < 86000)):
            #System has been disconnected less than 24 hours
            endpointList.append({'system.id': config.nodeProperties[node['xcatNodeName']]['esaID']})
        else:
            #system has been disconnected for more than 24 hours
            config.errorLogger(syslog.LOG_INFO, 'Node {nodename} has been disconnected more than 24 hours. No heartbeat was sent to ESA for it.'.format(nodename=node['xcatNodeName']))
            continue

    heartbeatPacket = {
        "endpoints": endpointList
    }
    
    encodedJSONData = json.dumps(heartbeatPacket)   
    try:
        resp3 = esasess.post(config.pluginVars['esa']['baseurl'] + 'data/hb', headers=config.pluginVars['esa']['esa_header'], data=encodedJSONData, verify=False)
        if resp3.status_code == 200:
            content = resp3.json()
            if content['status']['code'] == 200:
                return True
            else:
                config.errorLogger(syslog.LOG_ERR, 'An error occurred trying to send a heartbeat to the ESA application')
                config.errorLogger(syslog.LOG_ERR, 'ESA Application Response: {errorInfo}'.format(errorInfo=content['status']['message']))
                return False
        else:
            config.errorLogger(syslog.LOG_ERR, 'An error occurred when reaching the ESA application REST API')
            config.errorLogger(syslog.LOG_ERR, 'Error Code {errcode}: {desc}'.format(errcode=resp.status_code, desc=requests.status_codes._codes[resp3.status_code][0]))
            return False
    except Exception as e:
        config.errorLogger(syslog.LOG_ERR, "Failed to send the heartbeat to ESA".format(node=endpointInfo['hostname']))
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
        traceback.print_tb(e.__traceback__)
        return False


def monitorThread():
    '''
        This is run as a thread used to ensure the subprocess continues to run. 
        It is also intended to ensure a graceful shutdown. 
    '''
    while not config.killNow:
        time.sleep(0.5)
        if not config.pluginVars['esa']['monitoringProcess'].is_alive():
            #primary subprocess has died. Restart it. 
            monitorProcess = multiprocessing.Process(target=primaryMonitoringProcess(), args=[])
            monitorProcess.daemon = True
            monitorProcess.start()
            config.pluginVars['esa']['monitoringProcess'] = monitorProcess
    config.pluginVars['esa']['killSig'].set()
    
    #wait for the subprocess to terminate before exiting the thread
    config.pluginVars['esa']['monitoringProcess'].join()
    


def sendEventToESA(node, event):
    '''
        This function sends a call home event to ESA for a node
        This will update the nodeProperties dictionary for the specified node,
        with the active events. 
        EV001
        @param node: The node which the event is for
        @param event: The event to call home
        @return: True if successful, false if unable to send
    '''
    esasess = config.pluginVars['esa']['session']

    severityMap = {"Critical":"1", "Warning":"2", "Information":"3"}
    mtm = config.nodeProperties[node]['MTM'].split('-')
    '''
    failingUnit = {
        "Model": mtm[1],
        "MachineType": mtm[0],
        "SerialNumber": config.nodeProperties[node]['Serial']
    }
    '''
    origTimeStamp = time.asctime(time.localtime(int(event['timestamp'])))

    eventPacket = {
        "system.id": config.nodeProperties[node]['esaID'],
        "error.code": event['CerID'],
        "resource.name": node,
        "event.original.timestamp": event['timestamp'],
        "event.serviceability": "callhome",
        "event.client.id": "CRASSD",
        "severity": severityMap.get(event['severity']),
        "event-description": event['message'],
        "event-details": event['lengthyDescription']
        #"failingunit": failingUnit
    }

    encodedJSONData = json.dumps(eventPacket)
    try:
        resp3 = esasess.post(config.pluginVars['esa']['baseurl'] + 'event', headers=config.pluginVars['esa']['esa_header'], data=encodedJSONData, verify=False)
        if resp3.status_code == 200:
            content = resp3.json()
            if content['status']['code'] == 200:
                return content['event']['event.id']
            else:
                config.errorLogger(syslog.LOG_ERR, 'An error occurred trying to send a event to the ESA application')
                config.errorLogger(syslog.LOG_ERR, 'ESA Application Response: {errorInfo}'.format(errorInfo=content['status']['message']))
                return None
        else:
            config.errorLogger(syslog.LOG_ERR, 'An error occurred when reaching the ESA application REST API')
            config.errorLogger(syslog.LOG_ERR, 'Error Code {errcode}: {desc}'.format(errcode=resp.status_code, desc=requests.status_codes._codes[resp3.status_code][0]))
            return None
    except Exception as e:
        config.errorLogger(syslog.LOG_ERR, "Failed to send the event to ESA".format(node=endpointInfo['hostname']))
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
        traceback.print_tb(e.__traceback__)
        return None

    return None
    

def nodeReadyForCollection(node):
    '''
        This process checks with CSM when a node is ready for data collection
    '''
    csmState = lower(getNodeState)
    if csmState in ['maintenance','out_of_service']:
        return True
    return False


def nodeInJob(node):
    '''
        This checks to see if a node is assigned to a job
        or in the job queue. 
        @param node: dictionary. the node to check on
        @return: True if node is in a job, else false.
    '''
    return False

def getNodeCSMState(node):
    '''
        This process gets the CSM state from a node
    '''
    return False


def waitForNode(node):
    '''
        This waits for a node to be in the ready state for collecting service data.
        Node must in in CSM Maintenance or OUT_OF_Service states
    '''
    if config.pluginConfigs['esa']['CSMstateMinder']:
        time.sleep(300)
        #we must wait for the node to be in the Maintenance or OUT_OF_SERVICE states
        #wait for the node state to change
        #we must also check if the node is part of a job
        if nodeReadyForCollection(node):
            while nodeInJob(node):
                time.sleep(600)
        else:
            time.sleep(600)


def collectNodeData(node):
    '''
        This function is called to collect the service data from the node.
        This updates the subprocess dictionary with the filepath if successful
        @param node: The Node to collect service data from
        @return: A string containing the path to the service data if collection was successful
                 If collection failed, return None
    '''
    filePath = None
    #Figure out which script to call
    if 'collectionscript' in config.pluginConfigs['esa']:
        if config.pluginConfigs['esa']['collectionscript'].strip().lower() == 'default':
            if node['accessType'] == 'openbmcRest':
                #use /opt/ibm/ras/bin/openbmctool.py collect_service data
                try:
                    dataBytes = subprocess.check_output([config.pyString, '/opt/ibm/ras/bin/openbmctool.py', '-H', node['bmcHostname'], '-U', node['username'], '-P', node['password'], 'collect_service_data'])
                    dataList = dataBytes.decode('utf-8').split('\n')
                    print("Output from openbmctool for bmc: ",node['bmcHostname'],'\n',dataList)
                    for str in dataList:
                        if str.startswith('Zip file with all collected data created and stored in:'):
                            filePath = str.split(':')[1].strip()
                except subprocess.CalledProcessError as e:
                    errorContent = e.output.decode('utf-8')
                    if 'Address lookup' in errorContent:
                        config.errorLogger(syslog.LOG_ERR, "Failed to connect to the BMC for {node}. Ensure the specified address is correct.".format(node=node['bmcHostname']))
                    else:
                        config.errorLogger(syslog.LOG_ERR, "Failed to collect service data from the BMC for {node}.".format(node=node['bmcHostname']))
                        config.errorLogger(syslog.LOG_DEBUG, errorContent)
                except Exception as e:
                    config.errorLogger(syslog.LOG_ERR, "Failed to collect service data from the BMC for {node}.".format(node=node['bmcHostname']))
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
                    traceback.print_tb(e.__traceback__)
            elif node['accessType'] == 'ipmi':
                #use plc script
                try:
                    tempoutput = subprocess.check_output([config.pluginConfigs['esa']['plcdirectory'], 
                                                          '-b', node['bmcHostname'], 
                                                          '-a', node['password'], 
                                                          '-d', config.pluginConfigs['esa']['datadirectory']], 
                                                          stderr=subprocess.STDOUT).decode('utf-8')
                    for line in tempoutput.split("\n"):
                        if '-gdp.powerlc.tar' in line:
                             fileName  = line.split()[len(line.split())-1].strip() + '.gz'
                             filePath = config.pluginConfigs['esa']['datadirectory']+ '/'+ fileName
                             print('Original EED filePath-------->',filePath)  #Original EED filePath: the file path generated by plc eed data collection
                             break  
                except subprocess.CalledProcessError as e:
                    errorContent = e.output.decode('utf-8')
                    if 'Address lookup' in errorContent:
                        config.errorLogger(syslog.LOG_ERR, "Failed to connect to the BMC for {node}. Ensure the specified address is correct.".format(node=hostIP))
                    else:
                        config.errorLogger(syslog.LOG_ERR, "Failed to collect service data from the BMC for {node}.".format(node=nodeIP))
                        config.errorLogger(syslog.LOG_DEBUG, errorContent)
                except Exception as e:
                    config.errorLogger(syslog.LOG_ERR, "Failed to collect service data from the BMC for {node}.".format(node=nodeIP))
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
                    traceback.print_tb(e.__traceback__)
            else:
                #unsupported type
                filePath = None
        else:
            #use custom collection script
            #For example /path/to/mycollectionscript.sh
            scriptToCall = config.pluginVars['esa']['collectionScript']
            #This is a list of the script options to use
            #ForExample scriptOptionList=['-U', '-P', '-H', '-f /tmp']
            scriptOptions = config.pluginVars['esa']['scriptOptionList']
            #this specifies the values to use from the node properties for the scriptOptions
            #for hardcoded option values like the above example, use an empty string
            #for example: scriptOptionValues=['username', 'password', 'bmcHostname', '']
            optionMapper = config.pluginVars['esa']['scriptOptionValues']
            
            ## Try to Run the script!
    return filePath 

def sendServiceDatatoESA(node, fileLoc):
    '''
        Send service data to ESA for the node
        EV004
        @param node: The node that the service data is for
        @param fileLoc: The location of the service data in the file system
        @return: True if successful, False if failed
    '''
    esasess = config.pluginVars['esa']['session']
    result = False
    if (fileLoc is not None and os.path.isfile(fileLoc)):
        basefilename = os.path.basename(fileLoc)    
        if len(config.nodeProperties[node['xcatNodeName']]['eventIDlist'])>0:
            eventId = config.nodeProperties[node['xcatNodeName']]['eventIDlist'].pop()
            newFileLoc = config.pluginConfigs['esa']['datadirectory'] + '/' + node['xcatNodeName'] + '/' + eventId + '/'+  basefilename
            moveFile(fileLoc, newFileLoc)
            try:
                headers = {'Content-type': 'multipart/form-data', 'Accept': 'application/json'}
                files = {'data': (basefilename, open(newFileLoc, 'rb'))}
                parameters = {
                        'system.id': config.nodeProperties[node['xcatNodeName']]['esaID'],
                        'filename': basefilename
                }

                resp3 = esasess.post(config.pluginVars['esa']['baseurl'] + 'event/' + eventId + '/data', files=files, data=parameters, verify=False)
                if resp3.status_code == 200:
                    content = resp3.json()
                    if content['status']['code'] == 200:
                        config.errorLogger(syslog.LOG_INFO, 'Success sending the data to ESA for EventID: {eventid}'.format(eventid=eventId))
                        result = True
                    else:
                        config.errorLogger(syslog.LOG_ERR, 'An error occurred trying to send the EED file to the ESA application. EventID: {eventid}'.format(eventid=eventId))
                        config.errorLogger(syslog.LOG_ERR, 'ESA Application Response: {errorInfo}'.format(errorInfo=content['status']['message']))
                else:
                    config.errorLogger(syslog.LOG_ERR, 'An error occurred when reaching the ESA application REST API')
                    config.errorLogger(syslog.LOG_ERR, 'Error Code {errcode}: {desc}'.format(errcode=resp.status_code, desc=requests.status_codes._codes[resp3.status_code][0]))
            except Exception as e:
                config.errorLogger(syslog.LOG_ERR, 'Failed to send the EED file to ESA for EventID: {eventid}'.format(eventid=eventId))
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
                traceback.print_tb(e.__traceback__)
            os.remove(newFileLoc)
            os.rmdir(config.pluginConfigs['esa']['datadirectory'] + '/' + node['xcatNodeName'] + '/' + eventId + '/')
    return result    

def moveFile(srcfile, dstfile):
    fpath,fname=os.path.split(dstfile)
    if not os.path.exists(fpath):
        os.makedirs(fpath)
    shutil.move(srcfile,dstfile)

def getEventStatus(eventID):
    '''
        Gets the status of a reported event from ESA
        EV002
        @param eventID: String containing the id for the event
        @return: None if unable to get the status, otherwise the event
        portion of the ESA response
    '''
    return None

def collectionThread(node):
    '''
        This thread handles collecting the service data in the background
    '''
    #don't check the node for now
    #waitForNode(node)
    fileLoc = collectNodeData(node)
    sendServiceDatatoESA(node,fileLoc)
	    
def my_listener(event):
    if event.exception:
        print('The job executed unsuccessfully :',event.job_id)
    else:
        print('The job missed execution :',event.job_id)
        
def sendEmail(body):
    host_name = socket.gethostname()
    host_ip = socket.gethostbyname(host_name)
    if host_name == host_ip :
       sender = 'crassd@localhost.com'
    else :
       sender = 'crassd@' + host_name 
    #receivers = [config.pluginConfigs['esa']['email']]
    receivers = str(config.pluginConfigs['esa']['email']).split(',')
    subject = 'Summary of open problems'    
    
    mail = [
        "From: %s <%s>" % ('', sender),
        "To: %s" % ','.join(receivers),   # Convert to a string, separating elements by commas
        "Subject: %s" % subject,
        #"Cc: %s" % ','.join(ccers),
        "",
        body
        ]
    msg = '\n'.join(mail)    
    try:
      smtpserver = config.pluginConfigs['esa']['smtpserver']
      smtpport = config.pluginConfigs['esa']['smtpport']
      smtpObj = smtplib.SMTP(smtpserver, smtpport)     
      smtpObj.sendmail(sender, receivers, msg)       
      print('Successfully sent email')
    except SMTPException:
      print('Error: unable to send email')
      
def getOpenProblems():
    esasess= config.pluginVars['esa']['session']
    baseurl = config.pluginVars['esa']['baseurl']
    resp = esasess.get(baseurl + 'event/status:open', verify=False)
    if resp.status_code == 200:
        jsonData = resp.json()
        status = jsonData['status']
        if status['code'] == 200:
           items = jsonData['items']
           if items is not None and len(items)>0:
              jsonStr = json.dumps(items)
              items = json.loads(jsonStr)

              emailList = []
              for item in items :
                  for node in config.mynodelist :
                       if node['esaRegistered'] and item['System ID'] == node['esaID'] :
                          emailList.append(item)
                  if config.pluginVars['esa']['crassdID'] is not None and item['System ID'] == config.pluginVars['esa']['crassdID'] :
                      emailList.append(item)

              if emailList is not None and len(emailList)>0 :
                  sendEmail(convertFormat(emailList))
              else :
                  print('No open problems')    
           else :
              print('No open problems')
                 
        else :
           #print('Unable to get open problems. Code: {code} Message: {message}'.format(code= status['code'], message=status['message']))
           config.errorLogger(syslog.LOG_ERR, 'Unable to get open problems. Code: {code} Message: {message}'.format(code= status['code'], message=status['message']))       
    else :
        config.errorLogger(syslog.LOG_ERR, 'Unable to get open problems')

def convertFormat(items):
    strDest = '    System name    ' + '    Service Request    '+ '    Status    ' + '    Time of Occurrence    ' + '\n' + '-------------------------------------------------------------------------------------------\n'
    for item in items :
         strDest = strDest + '      ' + item['Name'] + '            ' + item['Service Request'] + '            ' + item['Service Request Status'] + '        '+item['Time of Occurrence'] + '\n'
    return strDest


def primaryMonitoringProcess():
    '''
        This is run as a sub process and handles the main work with collecting service data
        and with daily routines       
    ''' 
    if config.pluginVars['esa']['runDaily'].is_set():
        if not 'scheduler' in dir():
            #Using default MemoryJobStore , default maximum thread count 10 , default job instance 1
            scheduler = BackgroundScheduler(daemonic=True) 
            scheduler.add_job(esaHeartbeat, 'cron', day_of_week='*', hour=0, minute=0, second=1, id='esaHeartbeat')
            scheduler.add_job(getOpenProblems, 'cron', day_of_week='*', hour=0, minute=0, second=1, id='getOpenProblems')
            #scheduler.add_job(esaHeartbeat, 'interval', seconds=5, id='esaHeartbeat')
            #scheduler.add_job(task2, 'cron', day_of_week='*', hour=0, minute=0, second=1, id='esaHeartbeat')
            #scheduler.add_job(task3, 'cron', day_of_week='*', hour=0, minute=0, second=1, id='esaHeartbeat')
            #EVENT_JOB_MISSED - A job’s execution was missed, EVENT_JOB_ERROR - A job raised an exception during execution
            scheduler.start()  
            scheduler.add_listener(my_listener, EVENT_JOB_ERROR | EVENT_JOB_MISSED)
            jobList=[]
            jobs = scheduler.get_jobs()
            if jobs is not None and len(jobs)>0:
               for job in scheduler.get_jobs():
                  jobList.append(job.name)
            config.pluginVars['esa']['runDailyExists']=True
            config.pluginVars['esa']['runDaily'].clear() 
          
    while not config.pluginVars['esa']['killSig'].is_set():
        time.sleep(0.5)
        try: 
            if config.pluginVars['esa']['runDailyExists']:
                if 'esaHeartbeat' not in jobList:
                    scheduler.add_job(esaHeartbeat, 'cron', day_of_week='*', hour=0, minute=0, second=1, id='esaHeartbeat') 
                    jobList.append('esaHeartbeat')  
                if 'getOpenProblems' not in jobList:
                    scheduler.add_job(getOpenProblems, 'cron', day_of_week='*', hour=0, minute=0, second=1, id='getOpenProblems') 
                    jobList.append('getOpenProblems')            
            if len(config.pluginVars['esa']['nodesToCollectData'])>0:
                node = config.pluginVars['esa']['nodesToCollectData'].pop()
                t = threading.Thread(target=collectionThread, args=[node])
                t.daemon = True
                t.start()
            if len(config.pluginVars['esa']['nodesToRegister']) > 0:
                node = config.pluginVars['esa']['nodesToRegister'].pop()
                nodeProps = nodeInfoCollection(node)
                if nodeProps['esaRegistered']:
                    #registration was successful
                    config.updateManagedDict(config.nodeProperties[node['xcatNodeName']], nodeProps)
                else:
                    #node registration failed again
                    pass

        except Exception as e:
            config.errorLogger(syslog.LOG_ERR, "Encountered an error in the ESA Plugin primary process.")
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            config.errorLogger(syslog.LOG_DEBUG, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
            traceback.print_tb(e.__traceback__)
            

def initialize():
    """
        Establish a connection with the ESA application.
        Kick off registration of the monitored systems.
        Starts long running process for managing the systems. 
        @return: True if connection to ESA is possible
                False if connection to ESA failed
    """
    requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
    try:
        host = config.pluginConfigs['esa']['host']
        port = int(config.pluginConfigs['esa']['port'])
    except KeyError:
        config.errorLogger(syslog.LOG_ERR, "Host and port configurations missing for IBM ESA plugin. Defaulting to 127.0.0.1:5024")
        host="127.0.0.1"
        port='5024'
    config.pluginVars['esa'] = {'crassd_uuid':config.crassd_uuid, 'esa_ip':host, 'esa_port':port, 'esa_header': {'Content-Type': 'application/json'}}
    config.pluginVars['esa']['manager'] = multiprocessing.Manager()
    config.pluginVars['esa']['nodesToRegister'] = config.pluginVars['esa']['manager'].list()
    config.pluginVars['esa']['nodesToCollectData'] = config.pluginVars['esa']['manager'].list()
    config.pluginVars['esa']['nodesCollectedDataLocations'] = config.pluginVars['esa']['manager'].dict()
    config.pluginVars['esa']['killSig'] = multiprocessing.Event()
    config.pluginVars['esa']['runDaily'] = multiprocessing.Event()
    config.pluginVars['esa']['lastSentEventTime'] = None
        
    #Validate connection parameters to ESA
    connected = checkESAConnection(host, port)
    
    #register systems if esa is reachable, and start monitoring subprocess
    if connected:
        registerCRASSD(host, port)
        
        if not config.pluginVars['esa']['runDaily'].is_set():
            config.pluginVars['esa']['runDaily'].set()
            
        if config.pluginVars['esa']['crassdID'] is not None:
            with multiprocessing.Pool(min(40, len(config.mynodelist))) as p:
                updatedNodeList = p.map(nodeInfoCollection, config.mynodelist)
                with config.lock:
                    config.mynodelist = updatedNodeList
                for node in config.mynodelist:
                    config.updateManagedDict(config.nodeProperties[node['xcatNodeName']], node)
                    config.nodeProperties[node['xcatNodeName']]['eventIDlist'] = config.pluginVars['esa']['manager'].list()

        monitorProcess = multiprocessing.Process(target=primaryMonitoringProcess, args=[])
        monitorProcess.daemon = True
        monitorProcess.start()
        config.pluginVars['esa']['monitoringProcess'] = monitorProcess
        monThread = threading.Thread(target=monitorThread, args=[])
        monThread.daemon = True
        monThread.start()
        


    return connected
   

def notifyESA(cerEvent, impactedNode, entityAttr):
    """
         parses log entry from ibm-crassd and sends it to ESA
           
         @param cerEvent: dict, the cerEvent (logEntry) to send
         @param impactedNode: the node that had the alert dictionary
         @param entityAttr: dictionary, contains the list of known attributes for the entity to report to
         @return: True if notification was successful, false if it was unable to send the alert
    """
    
    newAlert = {'type':'ibm-crasssd-bmc-alerts', 'source': impactedNode, 
                'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'data': cerEvent
             }
    #send alert to ESA
    if config.nodeProperties[impactedNode]['esaRegistered']:
        # Send the alert
############
        try:
            lastSentEventTime = config.pluginVars['esa']['lastSentEventTime']
            temp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            currentTime = datetime.datetime.strptime(temp,"%Y-%m-%d %H:%M:%S")
            if lastSentEventTime is not None:
                diff = (currentTime - lastSentEventTime).total_seconds()
                waitTime = 5 - diff
                if(waitTime > 0):
                    config.pluginVars['esa']['lastSentEventTime'] =  currentTime + datetime.timedelta(seconds=waitTime)
                    time.sleep(waitTime)
                else:
                    config.pluginVars['esa']['lastSentEventTime'] =  currentTime    
            else:
                config.pluginVars['esa']['lastSentEventTime'] =  currentTime
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            config.errorLogger(syslog.LOG_ERR, "Exception: Error: {err}, Details: {etype}, {fname}, {lineno}".format(err=e, etype=exc_type, fname=fname, lineno=exc_tb.tb_lineno))
            traceback.print_tb(e.__traceback__)                    
############
        if config.pluginConfigs['esa']['autocollection']:
            config.pluginVars['esa']['nodesToCollectData'].append(config.nodeProperties[impactedNode])
        config.errorLogger(syslog.LOG_ERR, "Sending event to ESA, systemId = {systemId}, errorCode = {errorCode}".format(systemId=config.nodeProperties[impactedNode]['esaID'], errorCode=cerEvent['CerID']))
        eventID = sendEventToESA(impactedNode, cerEvent)
        if eventID is not None:
            config.nodeProperties[impactedNode]['eventIDlist'].append(eventID)
            return True

    return False
    
     
