import requests
import datetime
import time
import json
import syslog
import config

def errorHandler(severity, message):
    """
         Used to handle creating entries in the system log for this service
           
         @param severity: the severity of the syslog entry to create
         @param message: string, the message to post in the syslog
    """
    print("Creating syslog entry")
    syslog.openlog(ident="IBMPowerHWMonitor", logoption=syslog.LOG_PID|syslog.LOG_NOWAIT)
    syslog.syslog(severity, message)    


def notifyCSM(cerEvent, impactedNode, entityAttr):
    """
         sends alert to CSM
           
         @param cerEvent: dict, the cerEvent to send
         @param impactedNode; the node that had the alert
         @param entityAttr: dictionary, contains the list of known attributes for the entity to report to
         @return: True if notification was successful, false if it was unable to send the alert
    """
    
    httpHeader = {'Content-Type':'application/json'}
    with config.lock:
        failedFirstFlag = entityAttr['csm']['failedFirstTry']
        csmDown = entityAttr['csm']['receiveEntityDown']
    if(cerEvent['serviceable'] == 'No'):
        return True
    if(failedFirstFlag == False):
        msgID = "bmc." + "".join(cerEvent['eventType'].split()) + "." + cerEvent['CerID']
        eventTime =datetime.datetime.fromtimestamp(int(cerEvent['timestamp'])).strftime("%Y-%m-%d %H:%M:%S")
        eventEntry = {'msg_id': msgID, 'location_name':impactedNode, 'time_stamp':eventTime,
                      "raw_data": "serviceable:"+ cerEvent['serviceable'] + " || subsystem: "+ cerEvent['subSystem'] }
    else:
        msgID = "bmc.Firmware/SoftwareFailure.FQPSPEM0003G"
        eventEntry = {'msg_id': msgID, 'location_name':impactedNode, 'time_stamp':time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                      "raw_data":(cerEvent['CerID'] + "|| "+cerEvent['message']+"|| serviceable:"+ cerEvent['serviceable']+ "|| severity: "+ 
                                  cerEvent['severity'])}
    if("additionalDetails" in cerEvent):
        eventEntry['raw_data'] = eventEntry['raw_data'] + cerEvent['sensor'] + " || " + cerEvent['state'] + " || " + cerEvent['additionalDetails']
    try:
        r = requests.post('http://127.0.0.1:4213/csmi/V1.0/ras/event/create', headers=httpHeader, data=json.dumps(eventEntry), timeout=30)
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
