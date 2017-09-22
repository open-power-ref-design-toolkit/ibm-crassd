#!/usr/bin/python

'''
#================================================================================
#
#    openbmctool.py
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
import requests
import getpass
import json
import os
import urllib3

#isTTY = sys.stdout.isatty()


def hilight(textToColor, color, bold):
    if(sys.platform.__contains__("win")):
        if(color == "red"):
            os.system('color 04')
        elif(color == "green"):
            os.system('color 02')
        else:
            os.system('color') #reset to default
        return textToColor
    else:
        attr = []
        if(color == "red"):
            attr.append('31')
        elif(color == "green"):
            attr.append('32')
        else:
            attr.append('0')
        if bold:
            attr.append('1')
        else:
            attr.append('0')
        return '\x1b[%sm%s\x1b[0m' % (';'.join(attr),textToColor)

def setColWidth(keylist, numCols, dictForOutput, colNames):
    colWidths = []
    for x in range(0, numCols):
        colWidths.append(0)
    for key in dictForOutput:
        keyParts = key.split("/")
        colWidths[0] = max(colWidths[0], len(keyParts[len(keyParts) - 1].encode('utf-8')))
        for x in range(1,numCols):
            colWidths[x] = max(colWidths[x], len(str(dictForOutput[key][keylist[x]])))
    
    for x in range(0, numCols):
        colWidths[x] = max(colWidths[x], len(colNames[x])) +2
    
    return colWidths
def login(host, username, pw,jsonFormat):
    if(jsonFormat==False):
        print("Attempting login...")
    httpHeader = {'Content-Type':'application/json'}
    mysess = requests.session()
    try:
        r = mysess.post('https://'+host+'/login', headers=httpHeader, json = {"data": [username, pw]}, verify=False, timeout=30)
        loginMessage = json.loads(r.text)
        if (loginMessage['status'] != "ok"):
            print(loginMessage["data"]["description"].encode('utf-8')) 
            sys.exit()
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return mysess
    except(requests.exceptions.Timeout):
        print("Connection timed out. Ensure you have network connectivity to the bmc")
        sys.exit(1)
    except(requests.exceptions.ConnectionError) as err:
        print(err)
        sys.exit(1)
    
def logout(host, username, pw, session, jsonFormat):
    httpHeader = {'Content-Type':'application/json'}
    r = session.post('https://'+host+'/logout', headers=httpHeader,json = {"data": [username, pw]}, verify=False, timeout=10)
    if(jsonFormat==False):
        print(r.text)

    
def fru(host, args, session):
    #url="https://"+host+"/org/openbmc/inventory/system/chassis/enumerate"
    
    #print(url)
    #res = session.get(url, headers=httpHeader, verify=False)
    #print(res.text)
    #sample = res.text
    
    #inv_list = json.loads(sample)["data"]
    
    url="https://"+host+"/xyz/openbmc_project/inventory/enumerate"
    httpHeader = {'Content-Type':'application/json'}
    res = session.get(url, headers=httpHeader, verify=False)
    sample = res.text
#     inv_list.update(json.loads(sample)["data"])
#     
#     #determine column width's
#     colNames = ["FRU Name", "FRU Type", "Has Fault", "Is FRU", "Present", "Version"]
#     colWidths = setColWidth(["FRU Name", "fru_type", "fault", "is_fru", "present", "version"], 6, inv_list, colNames)
#    
#     print("FRU Name".ljust(colWidths[0])+ "FRU Type".ljust(colWidths[1]) + "Has Fault".ljust(colWidths[2]) + "Is FRU".ljust(colWidths[3])+ 
#           "Present".ljust(colWidths[4]) + "Version".ljust(colWidths[5]))
#     format the output
#     for key in sorted(inv_list.keys()):
#         keyParts = key.split("/")
#         isFRU = "True" if (inv_list[key]["is_fru"]==1) else "False"
#         
#         fruEntry = (keyParts[len(keyParts) - 1].ljust(colWidths[0]) + inv_list[key]["fru_type"].ljust(colWidths[1])+
#                inv_list[key]["fault"].ljust(colWidths[2])+isFRU.ljust(colWidths[3])+
#                inv_list[key]["present"].ljust(colWidths[4])+ inv_list[key]["version"].ljust(colWidths[5]))
#         if(isTTY):
#             if(inv_list[key]["is_fru"] == 1):
#                 color = "green"
#                 bold = True
#             else:
#                 color='black'
#                 bold = False
#             fruEntry = hilight(fruEntry, color, bold)
#         print (fruEntry)
    print(sample)
def fruPrint(host, args, session):   
    url="https://"+host+"/xyz/openbmc_project/inventory/enumerate"
    httpHeader = {'Content-Type':'application/json'}
    res = session.get(url, headers=httpHeader, verify=False)
    print(res.text)
def fruList(host, args, session):
    if(args.items==True):
        fruPrint(host, args, session)
    else:
        print("not implemented at this time")
        
def fruStatus(host, args, session):
    print("fru status to be implemented")
       
def sensor(host, args, session):
#     url="https://"+host+"/org/openbmc/sensors/enumerate"
    httpHeader = {'Content-Type':'application/json'}
#     print(url)
#     res = session.get(url, headers=httpHeader, verify=False, timeout=20)
#     print(res.text)
    url="https://"+host+"/xyz/openbmc_project/sensors/enumerate"
    res = session.get(url, headers=httpHeader, verify=False, timeout=20)
    print(res.text)
    
def sel(host, args, session):

    url="https://"+host+"/xyz/openbmc_project/logging/enumerate"
    httpHeader = {'Content-Type':'application/json'}
    #print(url)
    res = session.get(url, headers=httpHeader, verify=False, timeout=20)
    return res

def selPrint(host, args, session):
    print(sel(host, args, session).text)
    
def selList(host, args, session):
    print(sel(host, args, session).text)
    
def selClear(host, args, session):
    print("to be implemented")
    
def getESEL(host, args, session):
    selentry= args.selNum
    url="https://"+host+"/xyz/openbmc_project/logging/entry" + str(selentry)
    httpHeader = {'Content-Type':'application/json'}
    print(url)
    res = session.get(url, headers=httpHeader, verify=False, timeout=20)
    e = res.json()
    if e['Message'] != 'org.open_power.Error.Host.Event' and\
       e['Message'] != 'org.open_power.Error.Host.Event.Event':
        raise Exception("Event is not from Host: " + e['Message'])
    for d in e['AdditionalData']:
        data = d.split("=")
        tag = data.pop(0)
        if tag != 'ESEL':
            continue
        data = "=".join(data)
        if args.binary:
            data = data.split(" ")
            if '' == data[-1]:
                data.pop()
            data = "".join(map(lambda x: chr(int(x, 16)), data))
        print(data)

def chassis(host, args, session):
    if(args.powcmd is not None):
        chassisPower(host,args,session)
    else:
        print ("to be completed")

def chassisPower(host, args, session):
    if(args.powcmd == 'on'):
        print("Attempting to Power on...:")
        url="https://"+host+"/xyz/openbmc_project/state/host0/attr/RequestedHostTransition"
        httpHeader = {'Content-Type':'application/json'}
        data = '{"data":"xyz.openbmc_project.State.Host.Transition.On"'
        res = session.post(url, headers=httpHeader, data=data, verify=False, timeout=20)
        print(res.text)
    elif(args.powcmd == 'off'):
        print("Attempting to Power off...:")
        url="https://"+host+"/xyz/openbmc_project/state/host0/attr/RequestedHostTransition"
        httpHeader = {'Content-Type':'application/json'}
        data = '{"data":"xyz.openbmc_project.State.Host.Transition.Off"'
        res = session.post(url, headers=httpHeader, data=data, verify=False, timeout=20)
        print(res.text)
    elif(args.powcmd == 'status'):
        url="https://"+host+"/xyz/openbmc_project/state/chassis0/attr/CurrentPowerState"
        httpHeader = {'Content-Type':'application/json'}
        print(url)
        res = session.get(url, headers=httpHeader, verify=False, timeout=20)
        print(res.text)
    else:
        print("Invalid chassis power command")
        
def bmc(host, args, session):
    if(args.info):
        print("to be completed")
    if(args.type is not None):
        bmcReset(host, args, session)

def bmcReset(host, args, session):
    if(args.type == "warm"):
        print("\nAttempting to reboot the BMC...:")
        url="https://"+host+"/xyz/openbmc_project/state/bmc0/attr/RequestedBMCTransition"
        httpHeader = {'Content-Type':'application/json'}
        data = '{"data":"xyz.openbmc_project.State.BMC.Transition.Reboot"'
        res = session.post(url, headers=httpHeader, data=data, verify=False, timeout=20)
        print(res.text)
    elif(args.type =="cold"):
        print("cold reset not available at this time.")
    else:
        print("invalid command")

def createCommandParser():
    parser = argparse.ArgumentParser(description='Process arguments')
    parser.add_argument("-H", "--host", required=True, help='A hostname or IP for the BMC')
    parser.add_argument("-U", "--user", required=True, help='The username to login with')
    #parser.add_argument("-v", "--verbose", help='provides more detail')
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-A", "--askpw", action='store_true', help='prompt for password')
    group.add_argument("-P", "--PW", help='Provide the password in-line')
    parser.add_argument('-j', '--json', action='store_true', help='output json data only')
    subparsers = parser.add_subparsers(title='subcommands', description='valid subcommands',help="sub-command help")
    
    #fru command
    parser_inv = subparsers.add_parser("fru", help='Work with platform inventory')
    #fru print
    inv_subparser = parser_inv.add_subparsers(title='subcommands', description='valid inventory actions', help="valid inventory actions")
    inv_print = inv_subparser.add_parser("print", help="prints out a list of all FRUs")
    inv_print.set_defaults(func=fruPrint)
    #fru list [0....n]
    inv_list = inv_subparser.add_parser("list", help="print out details on selected FRUs. Specifying no items will list the entire inventory")
    inv_list.add_argument('items', nargs='?', help="print out details on selected FRUs. Specifying no items will list the entire inventory")
    inv_list.set_defaults(func=fruList)
    #fru status
    inv_status = inv_subparser.add_parser("status", help="prints out the status of all FRUs")
    inv_status.set_defaults(func=fruStatus)
    #parser_inv.add_argument('status', action='store_true', help="Lists the status of all BMC detected components")
    #parser_inv.add_argument('num', type=int, action='store_true', help="The number of the FRU to list")
    #inv_status.set_defaults(func=fruStatus)
    
    #sensors command
    parser_sens = subparsers.add_parser("sensors", help="Work with platform sensors")
    sens_subparser=parser_sens.add_subparsers(title='subcommands', description='valid sensor actions', help='valid sensor actions')
    #sensor print
    sens_print= sens_subparser.add_parser('print', help="prints out a list of all Sensors.")
    sens_print.set_defaults(func=sensor)
    #sensor list[0...n]
    sens_list=sens_subparser.add_parser("list", help="Lists all Sensors in the platform. Specify a sensor for full details. ")
    sens_list.add_argument("sensNum", nargs='?', help="The Sensor number to get full details on" )
    sens_list.set_defaults(func=sensor)
    
    
    #sel command
    parser_sel = subparsers.add_parser("sel", help="Work with platform alerts")
    sel_subparser = parser_sel.add_subparsers(title='subcommands', description='valid SEL actions', help = 'valid SEL actions')
    
    #sel print
    sel_print = sel_subparser.add_parser("print", help="prints out a list of all sels in a condensed list")
    sel_print.set_defaults(func=selPrint)
    #sel list
    sel_list = sel_subparser.add_parser("list", help="Lists all SELs in the platform. Specifying a specific number will pull all the details for that individual SEL")
    sel_list.add_argument("selNum", nargs='?', type=int, help="The SEL entry to get details on")
    sel_list.set_defaults(func=selList)
    
    sel_get = sel_subparser.add_parser("get", help="Gets the verbose details of a specified SEL entry")
    sel_get.add_argument('selNum', type=int, help="the number of the SEL entry to get")
    sel_get.set_defaults(func=selList)
    
    sel_clear = sel_subparser.add_parser("clear", help="Clears all entries from the SEL")
    sel_clear.set_defaults(func=selClear)
    
    parser_chassis = subparsers.add_parser("chassis", help="Work with chassis power and status")
    chas_sub = parser_chassis.add_subparsers(title='subcommands', description='valid subcommands',help="sub-command help")
    
    parser_chassis.add_argument('status', action='store_true', help='Returns the current status of the platform')
    parser_chassis.set_defaults(func=chassis)
    
    parser_chasPower = chas_sub.add_parser("power", help="Turn the chassis on or off, check the power state")
    parser_chasPower.add_argument('powcmd',  choices=['on','off', 'status'], help='The value for the power command. on, off, or status')
    parser_chasPower.set_defaults(func=chassisPower)
    
    #esel command
    esel_parser = subparsers.add_parser("esel", help ="Work with an ESEL entry")
    esel_subparser = esel_parser.add_subparsers(title='subcommands', description='valid SEL actions', help = 'valid SEL actions')
    esel_get = esel_subparser.add_parser("get", help="Gets the details of an ESEL entry")
    esel_get.add_argument('selNum', type=int, help="the number of the SEL entry to get")
    esel_get.set_defaults(func=getESEL)
    
    
    parser_bmc = subparsers.add_parser('bmc', help="Work with the bmc")
    bmc_sub = parser_bmc.add_subparsers(title='subcommands', description='valid subcommands',help="sub-command help")
    parser_BMCReset = bmc_sub.add_parser('reset', help='Reset the bmc' )
    parser_BMCReset.add_argument('type', choices=['warm','cold'], help="Warm: Reboot the BMC, Cold: CLEAR config and reboot bmc")
#     parser_BMCReset.add_argument('cold', action='store_true', help="Reboot the BMC and CLEAR the configuration")
    parser_bmc.add_argument('info', action='store_true', help="Displays information about the BMC hardware, including device revision, firmware revision, IPMI version supported, manufacturer ID, and information on additional device support.")
    parser_bmc.set_defaults(func=bmc)
#     parser_BMCReset.set_defaults(func=bmcReset)
    
    #add alias to the bmc command
    parser_mc = subparsers.add_parser('mc', help="Work with the management controller")
    mc_sub = parser_mc.add_subparsers(title='subcommands', description='valid subcommands',help="sub-command help")
    parser_MCReset = mc_sub.add_parser('reset', help='Reset the bmc' )
    parser_MCReset.add_argument('type', choices=['warm','cold'], help="Reboot the BMC")
    #parser_MCReset.add_argument('cold', action='store_true', help="Reboot the BMC and CLEAR the configuration")
    parser_mc.add_argument('info', action='store_true', help="Displays information about the BMC hardware, including device revision, firmware revision, IPMI version supported, manufacturer ID, and information on additional device support.")
    parser_mc.set_defaults(func=bmc)
    #parser_MCReset.set_defaults(func=bmcReset)
    return parser
def main(argv=None):

    
    parser = createCommandParser()
    
    #host power on/off
    #reboot bmc
    #host current state
    #chassis power
    #error collection - nonipmi
    #clear logs
    #bmc state
    
    args = parser.parse_args(argv)
    if (args.askpw):
        pw = getpass.getpass()
    elif(args.PW is not None):
        pw = args.PW
    else:
        print("You must specify a password")
        sys.exit()
    if (args.json):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    mysess = login(args.host, args.user, pw, args.json)
    args.func(args.host, args, mysess)
    logout(args.host, args.user, pw, mysess, args.json)       
if __name__ == '__main__':
    import sys
    
    isTTY = sys.stdout.isatty()
    assert sys.version_info >= (2,7)
    main()
