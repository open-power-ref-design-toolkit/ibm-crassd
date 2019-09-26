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
try:
    import Queue as queue
except ImportError:
    import queue
import threading
import syslog
import sys
import multiprocessing

global nodespercore
nodespercore = 15

global nodes2poll
nodes2poll = queue.Queue()
global updateConfFile
updateConfFile = queue.Queue()
global notifyList
notifyList = {}
global mynodelist
mynodelist = []
global missingEvents
missingEvents = {}
global lock
lock = threading.Lock()
global killNow
killNow = False
global networkErrorList
networkErrorList = ['FQPSPIN0000M','FQPSPIN0001M', 'FQPSPIN0002M','FQPSPIN0003M','FQPSPIN0004M','FQPSPCR0020M', 'FQPSPSE0004M']
global useTelem
useTelem = False

global enableDebug
enableDebug = False

global pluginPolicies
pluginPolicies = {}

global pluginConfigs
pluginConfigs = {}

global pluginVars
pluginVars = {}

global telemPort
telemPort = 53322

global alertMessageQueue
alertMessageQueue = multiprocessing.Queue()

global configFileName
configFileName = '/opt/ibm/ras/etc/ibm-crassd.config'
updateNodeTimesfile = '/opt/ibm/ras/etc/updateNodes.ini'
bmclastreports = '/opt/ibm/ras/etc'
if(sys.version_info<= (3,0)):
    pyString = 'python'
else:
    pyString = 'python3'
    
analyzeIDList = []
analyzeIDcount = {}
analysisOptions = {}

def set_procname(newname):
    from ctypes import cdll, byref, create_string_buffer
    libc = cdll.LoadLibrary('libc.so.6')    #Loading a 3rd party library C
    buff = create_string_buffer(len(newname)+1) #Note: One larger than the name (man prctl says that)
    buff.value = newname                 #Null terminated string as it should be
    libc.prctl(15, byref(buff), 0, 0, 0) #Refer to "#define" of "/usr/include/linux/prctl.h" for the misterious value 16 & arg[3..5] are zero as the man page says.

def errorLogger(severity, message):
    """
         Used to handle creating entries in the system log for this service
           
         @param severity: the severity of the syslog entry to create
         @param message: string, the message to post in the syslog
    """
    if severity == syslog.LOG_DEBUG and not enableDebug:
        pass
    else:
        syslog.openlog(ident="ibm-crassd", logoption=syslog.LOG_PID|syslog.LOG_NOWAIT)
        syslog.syslog(severity, message)    
