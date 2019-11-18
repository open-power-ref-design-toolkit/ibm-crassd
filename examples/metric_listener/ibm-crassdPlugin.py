#!/usr/bin/python3 -u
import time
import sys
import ssl
import json
import requests
import threading
try:
    import queue
except ImportError:
    import Queue as queue
import argparse
import datetime
import socket
import struct


def argsparser():
    parser = argparse.ArgumentParser(description='IBM-crassd Telemetry Plugin POC')
    parser.add_argument('update_every', type=int, nargs='?', help='update frequency in seconds')
    return parser
   
def processMessages():
    global sensorData
    while True:
        text = messageQueue.get().decode()
        try:
            message = json.loads(text)
            with lock:
                sensorData.clear()
                sensorData = message
        except Exception as e:
            pass
        messageQueue.task_done()
    
def init():
    for sn in serviceNodeIPList:
        sockQueue.put(sn)

    sct = threading.Thread(target = socketConnector)
    sct.daemon = True
    sct.start()
    pm = threading.Thread(target = processMessages)
    pm.daemon = True
    pm.start()
    activeThreads.append(pm)
    while len(sensorData) <=0:
        time.sleep(1)
    
    #Get Chart Types
    with lock:
        for systemName in sensorData:
            if 'Time_Sent' in systemName: continue
            for key in sensorData[systemName]:
                if 'LastUpdateReceived' in key:
                    continue
                if 'Connected' in key:
                    continue
                if 'NodeState' in key:
                    continue
                if 'type' not in sensorData[systemName][key]:
                    continue
                stype = sensorData[systemName][key]['type']
                if stype not in typeList:
                    typeList.append(stype)
    time.sleep(0.1)
    #build some charts
    with lock:
        for systemName in sensorData:
            if 'Time_Sent' in systemName: continue
            else:
                for key in typeList:
                    if key is None: continue
                    chartString = 'CHART {bmc}.{type} {type} "{bmc} {desc}" {units} {type} OpenBMC line 100000 {updateFreq}'.format(bmc=systemName, units=key[1], type = key[0], desc = key[0].title(), updateFreq=update_every/1000)
                    print (chartString)
                    for sensName in sensorData[systemName]:
                        if 'LastUpdateReceived' in sensName:
                            continue
                        elif 'NodeState' in sensName:
                            continue
                        elif 'Connected' in sensName:
                            continue
                        elif 'type' not in sensorData[systemName][sensName]: continue
                        elif sensorData[systemName][sensName]['type'] is None: continue
                        elif sensorData[systemName][sensName]['type'][0] in key[0]:
                            scale = sensorData[systemName][sensName]['scale']
                            if scale <1:
                                scale = int(1/scale)
                            dimString = 'DIMENSION {sname} {sname} absolute 1 {divscale}'.format(sname=sensName, divscale = scale)
                            print(dimString)
                        else:
                            pass

def socketConnector():
    while True:
        sn = sockQueue.get()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((sn, PORT))
        snSockThread = threading.Thread(target = crassdClientSocket, args=[s, sn])
        snSockThread.daemon = True
        snSockThread.start()
        sensfilters = {'frequency': 1}
        data2send = (json.dumps(sensfilters, indent=0, separators=(',', ':')).replace('\n','') +"\n").encode()
        msg = struct.pack('>I', len(data2send)) + data2send
        s.sendall(msg) 

def recvall(sock, n):
    #helperfunction to receive n bytes or return None if EOF is hit
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

def crassdClientSocket(servSocket, sn):
    while True:
        raw_msglen = recvall(servSocket, 4)
        if not raw_msglen:
            break
        msglen = struct.unpack('>I', raw_msglen)[0]
        data = recvall(servSocket, msglen)
        if not data:
            break
        messageQueue.put(data)  
    servSocket.close()  
    sockQueue.put(sn)     


def updateCharts():
    last_run = next_run = now = get_millis()
    count = 0
    while True:
        if next_run <= now:
            count += 1
            while next_run <=now:
                next_run += update_every
            dt = now - last_run
            last_run = now
            
            if count == 1:
                dt = 0
            
            #Post some data for netdata
            with lock:
                for systemName in sensorData:
                    if 'Time_Sent' in systemName: continue
                    for key in typeList:
                        if key is None: continue
                        print('BEGIN {sysName}.{type} {dtime}'.format(sysName = systemName, type = key[0], dtime=dt*1000))
                        for sname in sensorData[systemName]:
                            if 'LastUpdateReceived' in sname:
                                continue
                            elif 'NodeState' in sname:
                                continue
                            elif 'Connected' in sname:
                                continue
                            elif 'type' not in sensorData[systemName][sname]: continue
                            elif sensorData[systemName][sname]['type'] is None: continue
                            elif sensorData[systemName][sname]['type'][0] in key[0]:
                                try:
                                    print('SET {sname} = {svalue}'.format(sname = sname, svalue = sensorData[systemName][sname]['value']))
                                except Exception as e:
                                    with open('/tmp/ibm-crassdNetdataPlugin.txt', 'w') as logf:
                                        logf.write("The plugin has terminated\n")
                                        logf.write(e)
                                        logf.write((systemName+ ' ' + key + ' ' + sname))
                                        logf.write(json.dumps(sensorData, sort_keys=True, indent=4, separators=(',', ': '), ensure_ascii=False))
                                    continue
                            else:
                                pass
                        print('END')
     
        time.sleep(update_every/1000/10)
        now = get_millis()
            
if __name__ == "__main__":
    sockQueue = queue.Queue()
    messageQueue = queue.Queue()
    sensorData = {}
    requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
    serviceNodeIPList = ['127.0.0.1']
    socketClosedList = []
    socketClosed = False
    pmClosed = False
    lock = threading.Lock()
    activeThreads = []
    get_millis = lambda: int(round(time.time() * 1000))
    args = argsparser().parse_args()
    update_every = 1
    typeList = []
    if args.update_every != None:
        update_every = args.update_every
    update_every *= 1000
    PORT = 53322        # The port ibm-crassd is listening on
    init()
    updateCharts()
    with open('/tmp/ibm-crassdNetdataPlugin.txt', 'w') as logf:
        logf.write("The plugin has terminated")
    

