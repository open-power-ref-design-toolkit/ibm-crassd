#!/usr/bin/python3
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
    actionType.add_argument('-t', '--test', action='store_true', help='Test for a problem and report whether the power supply is healthy or not')
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
    
        
    