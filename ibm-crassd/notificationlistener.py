import websocket
try:
    import thread
except ImportError:
    import _thread as thread
import time
import openbmctool
import ssl
import json
import config

def on_message(ws, message):
    """
        websocket message handler
    """
    print(message)
    global bmcHostname
    for node in config.mynodelist:
        if node['bmcHostname'] == bmcHostname:
            config.nodes2poll.put(node)
            break

def on_error(ws, error):
    """
        websocket error handler
    """
    print(error)

def on_close(ws):
    """
        websocket close event handler
    """
    print("### closed ###")

def on_open(ws):
    """
        sends the filters needed to listen to the logging interface. 
    """
    data = {"paths": ["/xyz/openbmc_project/logging"]}
    ws.send(json.dumps(data))


def reportNodeDown(jsonEvent):
    """
        This is called to configure a notification that a bmc is not able to be reached
    """
    global bmcHostname
    for node in config.mynodelist:
        if node['bmcHostname'] == bmcHostname:
            node['pollFailedCount'] = 1
            config.nodes2poll.put(node)
            break
    
def openSocket(hostname, username, password):
    """
        opens a long running websocket to the specified bmc
    """
    global bmcHostname
    bmcHostname = hostname
    websocket.enableTrace(True)
    failedConCount = 0
    for i in range(3):
        mysession = openbmctool.login(hostname,username, password, True)
        if not isinstance(mysession,basestring):
            break;
        else:
            failedConCount += 1
    if failedConCount >=3:
        reportNodeDown(mysession)
    else:
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


    