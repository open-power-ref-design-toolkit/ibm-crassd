import requests
import datetime
import time
import json
import syslog
import config
import os
import traceback

def errorHandler(severity, message):
    """
         Used to handle creating entries in the system log for this service
           
         @param severity: the severity of the syslog entry to create
         @param message: string, the message to post in the syslog
    """
    print("Creating syslog entry")
    syslog.openlog(ident="ibm-crassd", logoption=syslog.LOG_PID|syslog.LOG_NOWAIT)
    syslog.syslog(severity, message)    

def initialize():
    config.pluginPolicies['csmPolicy'] = loadPolicyTable('/opt/ibm/ras/bin/plugins/ibm_csm/CSMpolicyTable.json')
    if config.pluginPolicies['csmPolicy'] is not None:
        return True
    else:
        return False
   
def createArgString(cerEvent):
    argString = ""
    index = 0
    cerMessage = config.pluginPolicies['csmPolicy'][cerEvent['CerID']]['Message']
    argInstance = 0
    while cerMessage.find('$(', index) != -1:
        index = cerMessage.find('$(', index) + 2
        arg = cerMessage[index:cerMessage.find(')',index)]
        if argString != "":
            argString = argString +','
        argString = argString + arg +'=' + cerEvent['ComponentInstance'].split(',')[argInstance]
        argInstance += 1
    return argString
def notifyCSM(cerEvent, impactedNode, entityAttr):
    """
         sends alert to CSM
           
         @param cerEvent: dict, the cerEvent to send
         @param impactedNode; the node that had the alert
         @param entityAttr: dictionary, contains the list of known attributes for the entity to report to
         @return: True if notification was successful, false if it was unable to send the alert
    """
    try:
        host=config.pluginConfigs['csm']['host']
        port=config.pluginConfigs['csm']['port']
    except KeyError:
        errorHandler(syslog.LOG_ERR, "Host and port configurations missing for CSM plugin. Defaulting to 127.0.0.1:4213")
        host="127.0.0.1"
        port="4213"
    httpHeader = {'Content-Type':'application/json'}
    with config.lock:
        failedFirstFlag = entityAttr['csm']['failedFirstTry']
        csmDown = entityAttr['csm']['receiveEntityDown']
    if(config.pluginPolicies['csmPolicy'][cerEvent['CerID']]['CSMEnabled']== False):
        return True
    if(failedFirstFlag == False):
        msgID = "bmc." + "".join(cerEvent['eventType'].split()) + "." + cerEvent['CerID']
        argString = createArgString(cerEvent)
        eventTime =datetime.datetime.fromtimestamp(int(cerEvent['timestamp'])).strftime("%Y-%m-%d %H:%M:%S")
        eventEntry = {'msg_id': msgID, 'location_name':impactedNode, 'time_stamp':eventTime,
                      "raw_data": "serviceable:"+ cerEvent['serviceable'] + " || subsystem: "+ cerEvent['subSystem'] }
        if argString != "":
            eventEntry['kvcsv'] = argString
    else:
        msgID = "bmc.Firmware/SoftwareFailure.FQPSPEM0003G"
        eventEntry = {'msg_id': msgID, 'location_name':impactedNode, 'time_stamp':time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                      "raw_data":(cerEvent['CerID'] + "|| "+config.pluginPolicies['csmPolicy'][cerEvent['CerID']]['Message']+"|| serviceable:"+ cerEvent['serviceable']+ "|| severity: "+ 
                                  cerEvent['severity'])}
    if("additionalDetails" in cerEvent):
        eventEntry['raw_data'] = eventEntry['raw_data'] + cerEvent['sensor'] + " || " + cerEvent['state'] + " || " + cerEvent['additionalDetails']
    try:
        csmurl = 'http://{host}:{port}/csmi/V1.0/ras/event/create'.format(host=host, port=port)
        r = requests.post(csmurl, headers=httpHeader, data=json.dumps(eventEntry), timeout=30)
        if (r.status_code != 200):

            with config.lock:
                entityAttr['csm']['receiveEntityDown'] = False
            return False
        else:
            print("Successfully reported to CSM: " + msgID)
#             sys.stdout.flush()
            if csmDown == True:
                with config.lock:
                    entityAttr['csm']['receiveEntityDown']=False
            return True
    except(requests.exceptions.Timeout):
        if csmDown == False:
            errorHandler(syslog.LOG_ERR, "Connection Timed out connecting to csmrestd system service. Ensure the service is running")
            with config.lock:
                entityAttr['csm']['receiveEntityDown'] = True;
        return False
    except(requests.exceptions.ConnectionError) as err:
        if csmDown == False:
            errorHandler(syslog.LOG_ERR, "Encountered an error connecting to csmrestd system service. Ensure the service is running. Error: " + str(err))
            with config.lock:
                entityAttr['csm']['receiveEntityDown'] = True;
        return False   
    
     
def loadPolicyTable(pathToPolicyTable):
    policyTable = {}
    if(os.path.exists(pathToPolicyTable)):
        with open(pathToPolicyTable, 'r') as stream:
            try:
                contents =json.load(stream)
                policyTable = contents['events']
            except Exception as err:
                print(err)
    return policyTable
