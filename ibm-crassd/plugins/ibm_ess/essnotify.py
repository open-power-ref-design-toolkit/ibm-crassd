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
import syslog
import config
import os
import subprocess

def errorLogger(severity, message):
    """
         Used to handle creating entries in the system log for this service
           
         @param severity: the severity of the syslog entry to create
         @param message: string, the message to post in the syslog
    """
    print("Creating syslog entry")
    syslog.openlog(ident="ibm-crassd", logoption=syslog.LOG_PID|syslog.LOG_NOWAIT)
    syslog.syslog(severity, message)    

def notifymmhealth(cerEvent, impactedNode, entityAttr):
    """
         sends alert to mmhealth
           
         @param cerEvent: dict, the cerEvent to send
         @param impactedNode; the node that had the alert
         @param entityAttr: dictionary, contains the list of known attributes for the entity to report to
    """  
    mmHealthDown = entityAttr['ess']['receiveEntityDown']
    eventsToReportList = ["FQPSPPW0006M","FQPSPPW0019I","FQPSPPW0007M","FQPSPPW0016I","FQPSPPW0008M","FQPSPPW0020I",
                          "FQPSPPW0009M","FQPSPPW0017I","FQPSPPW0010M","FQPSPPW0021I","FQPSPPW0011M","FQPSPPW0018M"]
    eventsToReportList.sort()
    if os.path.exists('/usr/lpp/mmfs/bin/mmsysmonc'):
        if(cerEvent['CerID'] in eventsToReportList):
            result = subprocess.check_output(['/usr/lpp/mmfs/bin/mmsysmonc', 'event', 'powerhw', cerEvent['CerID'], str(cerEvent['compInstance']), impactedNode]).decode('utf-8')
            if mmHealthDown:
                with config.lock:
                    entityAttr['ess']['receiveEntityDown'] = False
                
            if "Event "+ cerEvent['CerID'] + " raised" in result:
                return True
            else: 
                errorLogger(syslog.LOG_ERR, "Failed to raise event to mmhealth:" + str(cerEvent['CerID']) + ": "+ str(cerEvent['message']))
                return False
        else:
            return True
    else:
        if not mmHealthDown:
            errorLogger(syslog.LOG_CRIT, "Unable to find mmsysmonc. Ensure the utility is installed properly and part of the PATH")
            with config.lock:
                entityAttr['ess']['receiveEntityDown'] = True
    
    return False

def initialize():
    """
        Initializes the plugin and checks to see if the powerhw component of mmhealth has been initialized.
        
    """
    result = subprocess.check_output(['/usr/lpp/mmfs/bin/mmhealth', 'node', 'show', 'powerhw']).decode('utf-8')
    lines = result.split('\n')
    healthyAlert = {'CerID': 'FQPSPPW0018M', 'compInstance': 1}
    for line in lines:
        if 'POWERHW' in line:
            if 'CHECKING' in line:
                for node in config.mynodelist:
                    notifymmhealth(healthyAlert, node['xcatNodeName'], config.notifyList)
                break
    return True
