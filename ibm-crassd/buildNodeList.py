#!/usr/bin/python -u
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
import subprocess
import argparse
import json

def createCommandParser():
    """
         creates the parser for the command line along with help for each command and subcommand
           
         @return: returns the parser for the command line
    """ 
    programDescription = ("This utility is used to assess alert FQPSPPW0034M and ensure a fault has occurred.")
   
    parser = argparse.ArgumentParser(description=programDescription, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-j", "--json", action='store_true', help='Returns a JSON structure containing the data')
    return parser

def getxcatData():
    output = None
    try:
        output = subprocess.check_output(['/opt/xcat/bin/lsdef', 'compute', '-i', 'bmc,servicenode,mgt', '-c']).decode('utf-8')
    except Exception as e:
        print("Error: Unable to get info from xcat, aborting.")
        print(e)
    return output
    
def parseXcatOutput(output):
    
    bysnDict = {}
    entry = ""
    lastNodeName = ""
    nodeInfo = {}
    count = 1
    for line in output.split('\n'):
        nodeName = line.split(':')[0]
        if lastNodeName == "": lastNodeName = nodeName
        if nodeName != lastNodeName:
            if nodeInfo['serviceNode'] not in bysnDict:
                bysnDict[nodeInfo['serviceNode']] = {}
                bysnDict[nodeInfo['serviceNode']][nodeInfo['xcatNodeName']] = nodeInfo
            else:
                bysnDict[nodeInfo['serviceNode']][nodeInfo['xcatNodeName']] = nodeInfo
            count +=1
            nodeInfo = {}
            lastNodeName = nodeName
        info = " ".join(line.split(':')[1:])
        nodeInfo['xcatNodeName'] = nodeName
        if 'bmc=' in info:
            nodeInfo['bmcHostname'] = " ".join(info.split('=')[1:])
        elif 'mgt=' in info:
            if 'openbmc' in info.split('='):
                nodeInfo['accessType'] = 'openbmcRest'
            else:
                nodeInfo['accessType'] = 'ipmi'
        elif 'servicenode=' in info:
            nodeInfo['serviceNode'] = info.split('=')[1].split(',')[0]
        else: 
            continue
    return bysnDict

def createConfOutput(myData):
    
    for key in myData:
        if key is not None:
            print ("For nodes monitored by {serviceNode}: ".format(serviceNode=key))
            count = 1
            for node in myData[key]:
                print('node{number} = {{"bmcHostname": "{bmc}", "xcatNodeName": "{host}", "accessType":"{access}"}}').format(
                    number=count, 
                    bmc = myData[key][node]['bmcHostname'],
                    host= myData[key][node]['xcatNodeName'],
                    access = myData[key][node]['accessType'])
                count+=1
            print("\n")
        
        
if __name__ == '__main__':
    parser = createCommandParser()
    args = parser.parse_args()
    xCatInfo = ""
    xCatInfo = getxcatData()
#     filename = '/tmp/lsdef output'
#     with open(filename, 'r') as f:
#         xCatInfo = f.read()
    if xCatInfo is not None:
        parsedData = parseXcatOutput(xCatInfo)
        if not args.json:
            createConfOutput(parsedData)
        else:
            print(json.dumps(parsedData, sort_keys=True, indent=4, separators=(',', ': ')))  
        