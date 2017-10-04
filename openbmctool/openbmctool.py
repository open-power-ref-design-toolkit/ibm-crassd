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
import time
from dns.rdatatype import NULL

#isTTY = sys.stdout.isatty()

"""
     Used to add highlights to various text for displaying in a terminal
       
     @param textToColor: string, the text to be colored
     @param color: string, used to color the text red or green
     @param bold: boolean, used to bold the textToColor
     @return: Buffered reader containing the modified string. 
"""    
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

"""
     Error handler various connection errors to bmcs
       
     @param jsonFormat: boolean, used to output in json format with an error code. 
     @param errorStr: string, used to color the text red or green
     @param err: string, the text from the exception 
"""    
def connectionErrHandler(jsonFormat, errorStr, err):
    if errorStr == "Timeout":
        if not jsonFormat:
            print("FQPSPIN0000M: Connection timed out. Ensure you have network connectivity to the bmc")
        else:
            errorMessageStr = ("{\n\t\"Event\":{\n" +
            "\t\t\"CerID\": \"FQPSPIN0000M\",\n"+
            "\t\t\"sensor\": \"N/A\",\n"+
            "\t\t\"state\": \"N/A\",\n" +
            "\t\t\"additonalDetlails\": \"N/A\",\n" +
            "\t\t\"message\": \"Connection timed out. Ensure you have network connectivity to the BMC\",\n" +
            "\t\t\"serviceable\": \"Yes\",\n" +
            "\t\t\"callHome\": \"No\",\n" +
            "\t\t\"severity\": \"Critical\",\n" +
            "\t\t\"eventType\": \"Communication Failure/Timeout\",\n" +
            "\t\t\"vmMigration\": \"Yes\",\n" +
            "\t\t\"subSystem\": \"Interconnect (Networking)\",\n" +
            "\t\t\"timestamp\": \""+str(time.time())+"\",\n" +
            "\t\t\"userAction\": \"Verify network connectivity between the two systems and the bmc is functional.\"" +
            "\t\n}, \n" +
            "\t\"numAlerts\": \"1\" \n}");
            print(errorMessageStr)
    elif errorStr == "ConnectionError":
        if not jsonFormat:
            print("FQPSPIN0001M: " + str(err))
        else:
            errorMessageStr = ("{\n\t\"Event\":{\n" +
            "\t\t\"CerID\": \"FQPSPIN0001M\",\n"+
            "\t\t\"sensor\": \"N/A\",\n"+
            "\t\t\"state\": \"N/A\",\n" +
            "\t\t\"additonalDetlails\": \"" + str(err)+",\n" +
            "\t\t\"message\": \"Connection Error. View additional details for more information\",\n" +
            "\t\t\"serviceable\": \"Yes\",\n" +
            "\t\t\"callHome\": \"No\",\n" +
            "\t\t\"severity\": \"Critical\",\n" +
            "\t\t\"eventType\": \"Communication Failure/Timeout\",\n" +
            "\t\t\"vmMigration\": \"Yes\",\n" +
            "\t\t\"subSystem\": \"Interconnect (Networking)\",\n" +
            "\t\t\"timestamp\": \""+time.time()+"\",\n" +
            "\t\t\"userAction\": \"Correct the issue highlighted in additional details and try again\"" +
            "\t\n}, \n" +
            "\t\"numAlerts\": \"1\" \n}");
            print(errorMessageStr)
    else:
        print("Unknown Error: "+ str(err))

"""
     Sets the output width of the columns to display
       
     @param keylist: list, list of strings representing the keys for the dictForOutput 
     @param numcols: the total number of columns in the final output
     @param dictForOutput: dictionary, contains the information to print to the screen
     @param colNames: list, The strings to use for the column headings, in order of the keylist
     @return: A list of the column widths for each respective column. 
"""
def setColWidth(keylist, numCols, dictForOutput, colNames):
    colWidths = []
    for x in range(0, numCols):
        colWidths.append(0)
    for key in dictForOutput:
        for x in range(0, numCols):
            colWidths[x] = max(colWidths[x], len(str(dictForOutput[key][keylist[x]])))
    
    for x in range(0, numCols):
        colWidths[x] = max(colWidths[x], len(colNames[x])) +2
    
    return colWidths

"""
     Logs into the BMC and creates a session
       
     @param host: string, the hostname or IP address of the bmc to log into
     @param username: The user name for the bmc to log into
     @param pw: The password for the BMC to log into
     @param jsonFormat: boolean, flag that will only allow relevant data from user command to be display. This function becomes silent when set to true. 
     @return: Session object
"""
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
        connectionErrHandler(jsonFormat, "Timeout", None)
        sys.exit(1)
    except(requests.exceptions.ConnectionError) as err:
        connectionErrHandler(jsonFormat, "ConnectionError", err)
        sys.exit(1)

"""
     Logs out of the bmc and terminates the session
       
     @param host: string, the hostname or IP address of the bmc to log out of
     @param username: The user name for the bmc to log out of
     @param pw: The password for the BMC to log out of
     @param session: the active session to use
     @param jsonFormat: boolean, flag that will only allow relevant data from user command to be display. This function becomes silent when set to true. 
"""    
def logout(host, username, pw, session, jsonFormat):
    httpHeader = {'Content-Type':'application/json'}
    r = session.post('https://'+host+'/logout', headers=httpHeader,json = {"data": [username, pw]}, verify=False, timeout=10)
    if(jsonFormat==False):
        print(r.text)

"""
     prints out the system inventory. deprecated see fruPrint and fruList
       
     @param host: string, the hostname or IP address of the bmc
     @param args: contains additional arguments used by the fru sub command
     @param session: the active session to use
     @param args.json: boolean, if this flag is set to true, the output will be provided in json format for programmatic consumption 
"""   
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
"""
     prints out all inventory
       
     @param host: string, the hostname or IP address of the bmc
     @param args: contains additional arguments used by the fru sub command
     @param session: the active session to use
     @param args.json: boolean, if this flag is set to true, the output will be provided in json format for programmatic consumption 
""" 
def fruPrint(host, args, session):   
    url="https://"+host+"/xyz/openbmc_project/inventory/enumerate"
    httpHeader = {'Content-Type':'application/json'}
    res = session.get(url, headers=httpHeader, verify=False)
    print(res.text)

"""
     prints out all inventory or only a specific specified item
       
     @param host: string, the hostname or IP address of the bmc
     @param args: contains additional arguments used by the fru sub command
     @param session: the active session to use
     @param args.json: boolean, if this flag is set to true, the output will be provided in json format for programmatic consumption 
""" 
def fruList(host, args, session):
    if(args.items==True):
        fruPrint(host, args, session)
    else:
        print("not implemented at this time")


"""
     prints out the status of all FRUs
       
     @param host: string, the hostname or IP address of the bmc
     @param args: contains additional arguments used by the fru sub command
     @param session: the active session to use
     @param args.json: boolean, if this flag is set to true, the output will be provided in json format for programmatic consumption 
"""         
def fruStatus(host, args, session):
    print("fru status to be implemented")

"""
     prints out all sensors
       
     @param host: string, the hostname or IP address of the bmc
     @param args: contains additional arguments used by the sensor sub command
     @param session: the active session to use
     @param args.json: boolean, if this flag is set to true, the output will be provided in json format for programmatic consumption 
"""        
def sensor(host, args, session):
#     url="https://"+host+"/org/openbmc/sensors/enumerate"
    httpHeader = {'Content-Type':'application/json'}
#     print(url)
#     res = session.get(url, headers=httpHeader, verify=False, timeout=20)
#     print(res.text)
    url="https://"+host+"/xyz/openbmc_project/sensors/enumerate"
    res = session.get(url, headers=httpHeader, verify=False, timeout=20)
    colNames = ['sensor', 'type', 'units', 'value', 'target']
    if not args.json:
        sensors = json.loads(res.text)["data"]
        output = {}
        for key in sensors:
            senDict = {}
            keyparts = key.split("/")
            senDict['sensorName'] = keyparts[-1]
            senDict['type'] = keyparts[-2]
            senDict['units'] = sensors[key]['Unit'].split('.')[-1]
            if(sensors[key]['Scale'] != NULL): 
                scale = 10 ** sensors[key]['Scale'] 
            else: 
                scale = 1
            senDict['value'] = str(sensors[key]['Value'] * scale)
            if 'Target' in sensors[key]:
                senDict['target'] = str(sensors[key]['Target'])
            else:
                senDict['target'] = 'N/A'
            output[senDict['sensorName']] = senDict
        keylist = ['sensorName', 'type', 'units', 'value', 'target']
        colWidth = setColWidth(keylist, len(colNames), output, colNames)
        row = ""
        for i in range(len(colNames)):
            if (i != 0): row = row + "| "
            row = row + colNames[i].ljust(colWidth[i])
        print(row)
        sortedKeys = list(output.keys()).sort
        for key in sorted(output.keys()):
            row = ""
            for i in range(len(output[key])):
                if (i != 0): row = row + "| "
                row = row + output[key][keylist[i]].ljust(colWidth[i])
            print(row)
    else:
        print(res.text)
"""
     prints out the bmc alerts
       
     @param host: string, the hostname or IP address of the bmc
     @param args: contains additional arguments used by the sel sub command
     @param session: the active session to use
     @param args.json: boolean, if this flag is set to true, the output will be provided in json format for programmatic consumption 
"""     
def sel(host, args, session):

    url="https://"+host+"/xyz/openbmc_project/logging/enumerate"
    httpHeader = {'Content-Type':'application/json'}
    #print(url)
    res = session.get(url, headers=httpHeader, verify=False, timeout=20)
    return res
"""
     prints out all bmc alerts
       
     @param host: string, the hostname or IP address of the bmc
     @param args: contains additional arguments used by the fru sub command
     @param session: the active session to use
     @param args.json: boolean, if this flag is set to true, the output will be provided in json format for programmatic consumption 
""" 
def selPrint(host, args, session):
    print(sel(host, args, session).text)
"""
     prints out all all bmc alerts, or only prints out the specified alerts
       
     @param host: string, the hostname or IP address of the bmc
     @param args: contains additional arguments used by the fru sub command
     @param session: the active session to use
     @param args.json: boolean, if this flag is set to true, the output will be provided in json format for programmatic consumption 
"""     
def selList(host, args, session):
    print(sel(host, args, session).text)

"""
     clears all alerts
       
     @param host: string, the hostname or IP address of the bmc
     @param args: contains additional arguments used by the fru sub command
     @param session: the active session to use
     @param args.json: boolean, if this flag is set to true, the output will be provided in json format for programmatic consumption 
"""      
def selClear(host, args, session):
    print("to be implemented")
"""
     gathers the esels
       
     @param host: string, the hostname or IP address of the bmc
     @param args: contains additional arguments used by the fru sub command
     @param session: the active session to use
     @param args.json: boolean, if this flag is set to true, the output will be provided in json format for programmatic consumption 
"""     
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
"""
     controls the different chassis commands
       
     @param host: string, the hostname or IP address of the bmc
     @param args: contains additional arguments used by the fru sub command
     @param session: the active session to use
     @param args.json: boolean, if this flag is set to true, the output will be provided in json format for programmatic consumption 
""" 
def chassis(host, args, session):
    if(args.powcmd is not None):
        chassisPower(host,args,session)
    else:
        print ("to be completed")
"""
     called by the chassis function. Controls the power state of the chassis, or gets the status
       
     @param host: string, the hostname or IP address of the bmc
     @param args: contains additional arguments used by the fru sub command
     @param session: the active session to use
     @param args.json: boolean, if this flag is set to true, the output will be provided in json format for programmatic consumption 
""" 
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


"""
     handles various bmc level commands, currently bmc rebooting
       
     @param host: string, the hostname or IP address of the bmc
     @param args: contains additional arguments used by the fru sub command
     @param session: the active session to use
     @param args.json: boolean, if this flag is set to true, the output will be provided in json format for programmatic consumption 
"""         
def bmc(host, args, session):
    if(args.info):
        print("to be completed")
    if(args.type is not None):
        bmcReset(host, args, session)
"""
     controls resetting the bmc. warm reset reboots the bmc, cold reset removes the configuration and reboots. 
       
     @param host: string, the hostname or IP address of the bmc
     @param args: contains additional arguments used by the fru sub command
     @param session: the active session to use
     @param args.json: boolean, if this flag is set to true, the output will be provided in json format for programmatic consumption 
""" 
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
"""
     creates the parser for the command line along with help for each command and subcommand
       
     @return: returns the parser for the command line
""" 
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

"""
     main function for running the command line utility as a sub application
       
""" 
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


"""
     main function when called from the command line
        
""" 
if __name__ == '__main__':
    import sys
    
    isTTY = sys.stdout.isatty()
    assert sys.version_info >= (2,7)
    main()
