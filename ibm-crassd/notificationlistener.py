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
import websocket

import openbmctool
import ssl
import json
import config
import syslog
import threading
import sys

def getNode():
    """
        returns the hostname of the bmc
    """
    thisnode = ""
    for node in config.mynodelist:
        if 'listener' in node:
            if node['listener'].getName() == threading.currentThread().getName():
                thisnode = node
                break
    return thisnode

def on_message(ws, message):
    """
        websocket message handler
    """

    node = getNode()
    config.nodes2poll.put(node)

def on_error(ws, wserror):
    """
        websocket error handler
    """
    node = getNode()
    config.errorLogger(syslog.LOG_ERR, "Websocket error: {bmc}: {err}".format(bmc=node['bmcHostname'], err=wserror))

def on_close(ws):
    """
        websocket close event handler
    """
    node = getNode()
    config.errorLogger(syslog.LOG_INFO, "{bmc} websocket closed.".format(bmc=node['bmcHostname']))

def on_open(ws):
    """
        sends the filters needed to listen to the logging interface. 
    """
    data = {"paths": ["/xyz/openbmc_project/logging"]}
    ws.send(json.dumps(data))
    node = getNode()
    config.nodes2poll.put(node)


def reportNodeDown(jsonEvent):
    """
        This is called to configure a notification that a bmc is not able to be reached
    """
    global bmcHostname
    node = getNode()
    node['pollFailedCount'] = 1
    config.nodes2poll.put(node)
def isString(var):
    """
        Returns True if the variable is a string, otherwise false. 
    """
    if sys.version_info < (3,0):
        return isinstance(var, basestring)
    else:
        return isinstance(var, str)  
def openSocket(hostname, username, password):
    """
        opens a long running websocket to the specified bmc
    """
    global bmcHostname
    bmcHostname = hostname
    node = getNode()
    websocket.enableTrace(False)
    failedConCount = 0
    for i in range(3):
        mysession = openbmctool.login(hostname,username, password, True, allowExpiredPassword=False)
        if not isString(mysession):
            break;
        else:
            failedConCount += 1
    if failedConCount >=3:
        reportNodeDown(mysession)
    else:
        node['session'] = mysession
        cookie= mysession.cookies.get_dict()
        cookieStr = ""
        for key in cookie:
            if cookieStr != "":
                cookieStr = cookieStr + ";"
            cookieStr = cookieStr + key +"=" + cookie[key]
        ws = websocket.WebSocketApp("wss://"+hostname+"/subscribe",
                                  on_message = on_message,
                                  on_error = on_error,
                                  on_close = on_close,
                                  cookie = cookieStr)
        ws.on_open = on_open
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})


    
