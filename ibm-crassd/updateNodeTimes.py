#!/usr/bin/python
'''
#================================================================================
#
#    ibm-crassd.py
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
import configparser
import os
import config
import time
import json
import signal
import sys
from __builtin__ import True

def getCRASSDPID():
    """
         Gets the pid for the running ibm-crassd service
         
         @return: The pid for the crassd service. -1 if the service is not running. 
            
    """ 
    pid = -1
    procs = subprocess.check_output(['ps', '-ef']).decode('utf-8')
    for line in procs.splitlines():
        if 'ibm-crassd.py' in line:
            pid = int(line.split()[1])
    
    return pid

def createCommandParser():
    """
         creates the parser for the command line along with help for each command and subcommand
           
         @return: returns the parser for the command line
    """ 
    programDescription = ("This utility is used to update the last reported BMC alert time to the current time. "
                            "This utility should be run after a node has been serviced.")
    programUsage = ("Example usage:\n"
                    "Update one BMC last reported event time for CSM to the current time: \n"
                    "updateNodeTime.py -p CSM -n cn15\n\n"
                    "Update one BMC's last reported event time to all enabled plugins:\n"
                    "updateNodeTime.py -a -n sn1\n\n"
                    "Update multiple BMC's last reported event time to a list of enabled plugins: \n"
                    "updateNodeTime.py -p csm logstash -n cn1 cn8 sn16")
    
    parser = argparse.ArgumentParser(description=programDescription, epilog=programUsage, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-a", "--all", action='store_true', help='Update all enabled plugins last reported bmc alerts')
    parser.add_argument('-l', '--list', action='store_true', help='lists the valid plugins enabled for ibm-crassd')
    parser.add_argument("-p", "--plugins", nargs='+',help='The list of enabled plugins to update, separated by a space')
    parser.add_argument("-n", "--nodes", nargs='+', help='The list of nodes that need to be updated')
    parser.add_argument("-e", "--listnodes", action='store_true', help='Lists the valid nodes for ibm-crassd')
    
    return parser
def getConfiguration():
    confparser = configparser.ConfigParser()
    
    if (os.path.exists(config.configFileName)):
        try:
            confparser.read(config.configFileName)
        except:
            print("Failed to read the ibm-crassd configuration file")
    else:
        print("Unable to find configuration file at {filename}. Aborting".format(filename=config.configFileName))
    
    return confparser
    
def getEnabledPlugins(confparser):
    
    """
        Gets a list of currently enabled plugins for ibm-crassd service
        
        @return: list of enabled plugins. Empty if unable to get the list or no plugins enabled. 
    """
    pluginList = []
    try:
        for key in confparser['notify']:
            if confparser['notify'][key] == 'True':
                pluginList.append(key) 
    except:
        print("No section notify in ibm-crassd configuration file located at {filename}".format(filename=config.configFileName))
   
    return pluginList    
    
def getValidBMCsToUpdate(args, confparser):
    """ Checks the list of provided nodes and validates which ones can be updated
    
        @return: A list containing the validated nodes
    """
    bmcList = []
    invalidBMCs = []
    try:
        for node in args.nodes:
            for key in confparser['nodes']:
                crassdNode = json.loads(confparser['nodes'][key])
                if crassdNode['xcatNodeName'] == node:
                    bmcList.append(node) 
                    break
            if node not in bmcList:
                invalidBMCs.append(node)
    except Exception as e:
        print("An error occurred validating nodes against ibm-crassd configuration file located at {filename}".format(filename=config.configFileName))
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print("exception: ", exc_type, fname, exc_tb.tb_lineno)
        print(e)
    if len(invalidBMCs)>0:
        print("The following provided nodes are not valid: {nodeList}".format(nodeList=", ".join(invalidBMCs)))
    return bmcList  
    
def getValidPluginsToUpdate(args, enabledPlugins):
    """
        Checks the list of provided plugins for valid plugins to updates. 
        
        @return: List of valid plugins to update. Empty list if no valid plugins specified
    """  
    invalidPlugins = []
    validPlugins = []
    if args.all:
        return enabledPlugins
    else:
        for plugin in args.plugins:
            if plugin in enabledPlugins:
                validPlugins.append(plugin)
            else:
                invalidPlugins.append(plugin)
    if len(invalidPlugins)>0:
        print("The following plugins are not valid or are currently disabled: {pluginList}".format(pluginList=", ".join(invalidPlugins)))
    return validPlugins

def writeCrassdFile(confWriter):
    """
        Writes the file that will be ingested by ibm-crassd to process the updates.  
        
        @return: True if the file was created, false if unable to create the file
    """ 
    try:
        with open(config.updateNodeTimesfile, 'w') as updatefile:
            confWriter.write(updatefile)
        return True
    except Exception as e:
        print("Failed to write file for crassd located at {filename}. Exiting".format(filename=config.updateNodeTimesfile))
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print("exception: ", exc_type, fname, exc_tb.tb_lineno)
        print(e)
        return False

def createFileforCrassd(plugins, nodes):
    """
        Creates the content and writes the file that will be ingested by ibm-crassd to process the updates
        
        @return: True if the ini file was created, False if it was unable to create
    """ 
    
    confWriter = configparser.ConfigParser()
    ts = int(time.time())
    sectionItems= {}
    for node in nodes:
        sectionItems[node] = ts
    
    for plugin in plugins:
        confWriter[plugin] = sectionItems
        
    return writeCrassdFile(confWriter)

def getValidNodes(confParser):
    """
        returns a list of node names
    """
    nodelist = []
    try:
        nodes = dict(confParser.items('nodes'))
        for key in nodes:
            nodelist.append(json.loads(nodes[key])['xcatNodeName'])
            
        return nodelist        
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print("exception: ", exc_type, fname, exc_tb.tb_lineno)
        print(e)
        sys.exit()
              
                
if __name__ == '__main__':
    """
         main function when called from the command line
            
    """ 

    parser = createCommandParser()
    args = parser.parse_args()
    
    crassdConfig = getConfiguration()
    eplugins = getEnabledPlugins(crassdConfig)
    cpid = getCRASSDPID()
    if len(eplugins)>0 and cpid!= -1:
        if args.list:
            print("Enabled Plugins: {pluginList}".format(pluginList = ", ".join(eplugins)))
        elif args.listnodes:
            nodeList = getValidNodes(crassdConfig)
            print("Enabled Nodes: \n{nodes}".format(nodes=", ".join(nodeList)))
        else:
            plugins2Update = getValidPluginsToUpdate(args, eplugins)
            bmcs2update = getValidBMCsToUpdate(args,crassdConfig)
            if len(plugins2Update)>0 and len(bmcs2update) >0:
                if createFileforCrassd(plugins2Update,bmcs2update):
                    os.kill(cpid, signal.SIGUSR2)
                    print("Waiting for ibm-crassd to update: ")
                    while(os.path.exists(config.updateNodeTimesfile)):
                        sys.stdout.write('.')
                        sys.stdout.flush()
                        time.sleep(5)
                    print("\nibm-crassd has updated the node times")
    elif cpid == -1:
        print("ibm-crassd service is not running. Exiting.")
    else:
        print("No plugins are enabled")
