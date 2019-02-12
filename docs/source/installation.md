# Installing IBM CRASSD
## Prerequisites version < 0.8-10
-	Python 2.7 or greater
-	Java 1.7.0 or greater
-	python-configparser (found in EPEL)
-	python-websocket-client
-	python-requests if monitoring 8335-GTG, 8335-GTC, 8335-GTW
-	openbmctool if monitoring 8335-GTG, 8335-GTC, 8335-GTW
-	ipmitool
## Prerequisites for ibm-crassd 0.8-10 and above
This version switches to python 3 compatibility
- Python 3.4 or greater
-	Java 1.7.0 or greater
-	python-configparser (found in EPEL)
-	python34-websocket-client
-	python34-requests if monitoring 8335-GTG, 8335-GTC, 8335-GTW
-	openbmctool if monitoring 8335-GTG, 8335-GTC, 8335-GTW
-	ipmitool
-	pexpect
## Installation
### ESS
1.	From the ESS management node type `yum install /install/gss/otherpkgs/rhels7/ppc64le/gss/ibm-crassd-0.8-1.ppc64le.rpm`
### RHEL Based Systems
1.	Transfer the rpm to the management system or service node you wish to install this service on. 
2.	Type `yum install /path/to/rpm`, where /path/to/rpm is the full path to the rpm you just copied to the system. 




