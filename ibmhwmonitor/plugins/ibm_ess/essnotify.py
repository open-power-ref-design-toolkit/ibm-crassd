import syslog
import config
import os
import subprocess

def errorHandler(severity, message):
    """
         Used to handle creating entries in the system log for this service
           
         @param severity: the severity of the syslog entry to create
         @param message: string, the message to post in the syslog
    """
    print("Creating syslog entry")
    syslog.openlog(ident="IBMPowerHWMonitor", logoption=syslog.LOG_PID|syslog.LOG_NOWAIT)
    syslog.syslog(severity, message)    

def notifymmhealth(cerEvent, impactedNode, entityAttr):
    """
         sends alert to mmhealth
           
         @param cerEvent: dict, the cerEvent to send
         @param impactedNode; the node that had the alert
         @param entityAttr: dictionary, contains the list of known attributes for the entity to report to
    """  
    mmHealthDown = entityAttr['mmhealth']['receiveEntityDown']
    eventsToReportList = ["FQPSPPW0006M","FQPSPPW0019I","FQPSPPW0007M","FQPSPPW0016I","FQPSPPW0008M","FQPSPPW0020I",
                          "FQPSPPW0009M","FQPSPPW0017I","FQPSPPW0010M","FQPSPPW0021I","FQPSPPW0011M","FQPSPPW0018M"]
    eventsToReportList.sort()
    if os.path.exists('/usr/lpp/mmfs/bin/mmsysmonc'):
        if(cerEvent['CerID'] in eventsToReportList):
            proc = subprocess.Popen(['/usr/lpp/mmfs/bin/mmsysmonc', 'event', 'powerhw', cerEvent['CerID'], cerEvent['compInstance'], impactedNode], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            result = proc.communicate()[0]
            result = result.decode('ascii')
            if mmHealthDown:
                with config.lock:
                    entityAttr['mmhealth']['receiveEntityDown'] = False
                
            if "Event "+ cerEvent['CerID'] + " raised" in result:
                return True
            else: 
                errorHandler(syslog.LOG_ERR, "Failed to raise event to mmhealth:" + str(cerEvent['CerID']) + ": "+ str(cerEvent['message']))
                return False
        else:
            return True
    else:
        if not mmHealthDown:
            errorHandler(syslog.LOG_CRIT, "Unable to find mmsysmonc. Ensure the utility is installed properly and part of the PATH")
            with config.lock:
                entityAttr['mmhealth']['receiveEntityDown'] = True
    
    return False
