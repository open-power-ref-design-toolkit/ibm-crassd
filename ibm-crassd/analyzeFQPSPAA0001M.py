#!/usr/bin/python3
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
import argparse
import subprocess
import json
from openbmctool import login, connectionErrHandler
import requests
import sys

def createCommandParser():
    """
         creates the parser for the command line along with help for each command and subcommand
           
         @return: returns the parser for the command line
    """ 
    programDescription = ("This utility is used to assess alert FQPSPAA0001M and ensure a fault has occurred.")
   
    parser = argparse.ArgumentParser(description=programDescription, formatter_class=argparse.RawDescriptionHelpFormatter)
    actionType = parser.add_mutually_exclusive_group(required=True)
    actionType.add_argument("-a", "--auto", action='store_true', help='Automatically take action on the alert as needed')
    actionType.add_argument('-t', '--test', action='store_true', help='Test for a problem and report whether the INTCQ[52:54] false error is present')
    actionType.add_argument("-c", "--crassd", action='store_true', help='Used to indicate the function was called by ibm-crassd. Not intended for end-users')
    amount = parser.add_mutually_exclusive_group(required=True)
    amount.add_argument('-n', '--logNumber', help='The log number of the entry to test')
    amount.add_argument('-f', '--fullLogTest', action='store_true', help='Test all the bmc logs.')
    parser.add_argument("-H", "--host", required=True, help='A hostname or IP for the BMC')
    parser.add_argument("-U", "--user", required=True, help='The username to login with')
    parser.add_argument("-P", "--PW", required=True, help='Provide the password in-line')
    
    return parser

def selDelete(host, session, sels):
    """
        Deletes all the sel entries in list sels, using the specified session
    """
    httpHeader = {'Content-Type':'application/json'}
    data = "{\"data\": [] }"
    for logNum in sels:
        url = "https://"+ host+ "/xyz/openbmc_project/logging/entry/{entryNum}/action/Delete".format(entryNum=logNum)
        try:
            session.post(url, headers=httpHeader, data=data, verify=False, timeout=30)
        except(requests.exceptions.Timeout):
            return connectionErrHandler(args.json, "Timeout", None)
        except(requests.exceptions.ConnectionError) as err:
            return connectionErrHandler(args.json, "ConnectionError", err)
    return True
  
if __name__ == '__main__':
    """
        If called by ibm-crassd, the -c option is used. This will print True if the alert should be forwarded
        and False if the alert should not be forwarded. Otherwise human readable output is supplied. 
    """
    if(sys.version_info < (3,0)):
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    if sys.version_info >= (3,0):
        requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
    parser = createCommandParser()
    args = parser.parse_args()
    logs2Resolve = []
    if(sys.version_info<= (3,0)):
        pyString = 'python'
    else:
        pyString = 'python3'
    
    sels = subprocess.check_output([pyString, '/opt/ibm/ras/bin/openbmctool.py', '-j', '-H', args.host, '-U', args.user, '-P', args.PW, 'sel', 'print', '-d']).decode('utf-8')
    sels = json.loads(sels)

    for item in sels:
        if(type(sels[item])==int): continue
        if(args.fullLogTest or str(args.logNumber) in sels[item]['logNum'] ):
            if 'CommonEventID' not in sels[item]: continue
            if 'eselParts' in sels[item] and 'signatureDescription' in sels[item]['eselParts']:
                if('FQPSPAA0001M' in sels[item]['CommonEventID']):
                    if('INTCQFIR[52:54]' in sels[item]['eselParts']['signatureDescription'] or 'CXAFIR[37]' in sels[item]['eselParts']['signatureDescription']):
                        #False Report
                        logs2Resolve.append(sels[item]['logNum'])
    if(args.auto):
        if not args.crassd:
             print('Attempting to delete the following sel entries: {selList}'.format(selList=' '.join(logs2Resolve)))
        session = login(args.host,args.user, args.PW, True)
        status = selDelete(args.host, session, logs2Resolve)
        if(status != True):
            if not args.crassd:
                print(status)
    if args.test:
        if len(logs2Resolve)>0:
            print('A false report was detected for the following sel numbers: {selList}'.format(selList=' '.join(logs2Resolve)))
        else:
            print('No false reports were found')
    if args.crassd:
        if len(logs2Resolve)>0:
            print(False)
        else:
            print(True)
    
        
    