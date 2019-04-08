#!/usr/bin/env python3
# 
#  Copyright 2017 IBM Corporation
# 
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
# 
#        http://www.apache.org/licenses/LICENSE-2.0
# 
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import socket
import struct
import json


def recvall(sock, n):
    """
        Helper function to receive n bytes or return None if EOF is hit
        @param sock: The socket to read data from
        @param n: The number of bytes to read from the socket
        @return: The data that was received and is ready to process
    """
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

def crassdClientSocket(servSocket, sn):
    """
        Function to manage the opened socket with ibm-crassd
        @param servSocket: The socket to read data from and write filters to
        @param sn: The hostname/IP of the service node running ibm-crassd
    """
#----------------------------------------------------------------------
    #Create a filter to send to ibm-crassd service
    #frequency must be an integer >=1
    #sensornames can be any of the names from `openbmctool sensors print/list` sent as a list
    #sensortypes can be any of: temperature, current, power, voltage, fan_tach
    #sensornames takes priority over sensor types
    sensfilters = {'frequency': 1, 'sensortypes': ['power']}
    data2send = (json.dumps(sensfilters, indent=0, separators=(',', ':')).replace('\n','') +"\n").encode()
    msg = struct.pack('>I', len(data2send)) + data2send
    servSocket.sendall(msg)
#----------------------------------------------------------------------
    
    while True:
        raw_msglen = recvall(servSocket, 4)
        if not raw_msglen:
            break
        msglen = struct.unpack('>I', raw_msglen)[0]
        data = recvall(servSocket, msglen)
        if not data:
            break
        
        sensData = json.loads(data.decode()) 
#----------------------------------------------------------------------
#Process the received data
#         print("Total Nodes: {ncount}".format(ncount=len(sensData)))
        for node in sensData:
#             print('{Node} Sensor Count: {scount}'.format(Node=node, scount=len(sensData[node].keys())))
            for sensName in sensData[node]:
                print("{Node} Sensor: {sname}: {svalue} * (10^{sscale}) {sunits}".format(Node=node, sname=sensName, 
                                                                            svalue=sensData[node][sensName]['value'], 
                                                                            sscale=sensData[node][sensName]['scale'],
                                                                            sunits=sensData[node][sensName]['type'][1]))
#---------------------------------------------------------------------
    servSocket.close()      

if __name__ == "__main__":
    HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
    PORT = 53322        # Port to listen on (non-privileged ports are > 1023)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print("Connecting to ", HOST)
    s.connect((HOST, PORT))
    print('connected')
    #prepare to start receiving data
    crassdClientSocket(s, HOST)    

    print('Socket closed, terminating')
    
