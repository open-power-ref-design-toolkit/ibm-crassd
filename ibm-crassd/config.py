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
try:
    import Queue as queue
except ImportError:
    import queue
import threading


global nodes2poll
nodes2poll = queue.Queue()
global updateConfFile
updateConfFile = queue.Queue()
global mynodelist
mynodelist = []
global missingEvents
missingEvents = {}
global lock
lock = threading.Lock()
global killNow
killNow = False
global networkErrorList
networkErrorList = ['FQPSPIN0000M','FQPSPIN0001M', 'FQPSPIN0002M','FQPSPIN0003M','FQPSPCR0020M', 'FQPSPSE0004M']

global pluginPolicies
pluginPolicies = {}