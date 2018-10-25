#!/usr/bin/python
'''
#================================================================================
#
#    buildNodeList.py
#
#    Copyright IBM Corporation 2015-2017. All Rights Reserved
#
#    This program is licensed under the terms of the Eclipse Public License
#    v1.0 as published by the Eclipse Foundation and available at
#    http://www.eclipse.org/legal/epl-v10.html
#
#    U.S. Government Users Restricted Rights:  Use, duplication or disclosure
#    restricted by GSA ADP Schedule Contract with IBM Corp.
#
#================================================================================
'''
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
        