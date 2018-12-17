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
import argparse
import os
import sys
import subprocess
import pexpect
import tempfile
import json

def createCommandParser():
    """
         creates the parser for the command line along with help for each command and subcommand
           
         @return: returns the parser for the command line
    """ 
    programDescription = ("This utility is used to assess alert FQPSPPW0034M and ensure a fault has occurred.")
   
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


def ssh(host, cmd, user, password, timeout=30, bg_run=False):                                                                                                
    """SSH'es to a host using the supplied credentials and executes a command.                                                                                                 
    Throws an exception if the command doesn't return 0.                                                                                                                       
    bgrun: run command in the background"""                                                                                                                                    

    fname = tempfile.mktemp()                                                                                                                                                  
    fout = open(fname, 'w')                                                                                                                                                    

    options = '-q -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null -oPubkeyAuthentication=no'                                                                         
    if bg_run:                                                                                                                                                         
        options += ' -f'                                                                                                                                                       
    ssh_cmd = 'ssh {user}@{host} {options} "{cmd}"'.format(user=user, host=host, options=options, cmd=cmd)                                                                                                                 
    child = pexpect.spawn(ssh_cmd, timeout=timeout)                                                                                                                            
    child.expect(['password: '])                                                                                                                                                                                                                                                                                               
    child.sendline(password)                                                                                                                                                   
    child.logfile = fout    
    child.expect(pexpect.EOF)
    child.close()                                                                                                                                                              
    fout.close()                                                                                                                                                               

    fin = open(fname, 'r')                                                                                                                                                     
    stdout = fin.read()                                                                                                                                                        
    fin.close()                                                                                                                                                                

    if 0 != child.exitstatus:                                                                                                                                                  
        raise Exception(stdout)                                                                                                                                                

    return stdout
    
def getPowerSupplyPath(bmchostname, username, password):

    command = 'cd /sys/class/hwmon && grep -ir power-supply *'
    try:
        output = ssh(bmchostname, command, username, password).strip()
    except Exception as e:
        return "Failed to connect to the specified BMC and get data"
    ps0 = output.split('\n')[0].split('/')[0]
    ps1 = output.split('\n')[2].split('/')[0]
    
    #verify the path is indeed a power supply
    command = 'cat /sys/class/hwmon/{path}/device/name'.format(path=ps0)
    ps0Verify = ssh(bmchostname, command, username, password).strip()
    command = 'cat /sys/class/hwmon/{path}/device/name'.format(path=ps1)
    ps1Verify = ssh(bmchostname, command, username, password).strip()
    
    if ps0Verify == 'cffps1' and ps1Verify == 'cffps1':
        return [ps0, ps1]
    else:
        return []

def getPowerSupplyStatus(bmchostname, username, password, psPath):
    command = 'cat /sys/kernel/debug/pmbus/{Path}/status0'.format(Path=psPath)
#     print(command)
    try:
        output = ssh(bmchostname, command, username, password).strip()
    except Exception as e:
        return "Failed to connect to the specified BMC and get data"
    return output

def hex2bin(str):
    bin = ['0000','0001','0010','0011',
         '0100','0101','0110','0111',
         '1000','1001','1010','1011',
         '1100','1101','1110','1111']
    binStr = ''
    for i in range(len(str)):
        binStr += bin[int(str[i],16)]
    return binStr

def convertStatusWord(hexString):
    binStr = hex2bin(hexString.split('x')[-1])
#     print(hexString)
#     print(binStr)
    if binStr[-12] == '1':
        pgoodFault = True
    else:
        pgoodFault = False
#    print('Pgood Fault: {pgood}'.format(pgood=pgoodFault))
    psoff = False
    if binStr[-7] == '1':
        psoff = True
    else:
        psoff = False
#     print('Power supply off: {psoff}'.format(psoff=psoff))
    return (pgoodFault or psoff)

def checkSystemPower(host, user, pw):
    if(sys.version_info<= (3,0)):
        pyString = 'python'
    else:
        pyString = 'python3'
    
    powerStatus = subprocess.check_output([pyString, '/opt/ibm/ras/bin/openbmctool.py', '-H', host, '-U', user, '-P', pw,'-j','chassis', 'power', 'status']).decode('utf-8')
    statusDict = json.loads(powerStatus)
    if statusDict['Chassis Power State'] == 'On':
        return True
    else:
        return False
    
if __name__ == '__main__':
    """
        If called by ibm-crassd, the -c option is used. This will print True if the alert should be forwarded
        and False if the alert should not be forwarded. Otherwise human readable output is supplied. 
    """
    parser = createCommandParser()
    args = parser.parse_args()
    powerOn = checkSystemPower(args.host, args.user, args.PW)
    if powerOn:
        paths = getPowerSupplyPath(args.host, args.user, args.PW)
        if 'Failed to connect' in paths:
            if args.crassd:
                    print("True")
            sys.exit()
        if len(paths) >0:
            count = 0
            badps = False
            for path in paths:
                sw = getPowerSupplyStatus(args.host, args.user, args.PW, path)
                if convertStatusWord(sw):
                    badps = True
            if badps:
                if args.test:
                    print("A bad power supply has been detected.")
                if args.crassd:
                    print("True")
            else:
                if args.test:
                    print("The power supplies are healthy.")
                if args.crassd:
                    print("False")
                if args.auto:
                    print("This is a false report. Action will be taken on the BMC")
        else:
            print("Failed to get the directory for the power supplies")
    else:
        print("Chassis Power Must be On")
        
    