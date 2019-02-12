# Upgrading
## Before you begin
If you are updating from 0.8-9 to version 0.8-10 or newer, the package requirements changed. Specifically python 3 based packages are used. During this upgrade, the ibm-crassd service will stop temporarily and monitoring will cease during this time. 

## Upgrading ibm-crassd
1.	Backup the ibm-crassd.config file found at `/opt/ibm/ras/etc/ibm-crassd.config`. This location may vary and the default is shown. 
2.	Backup the bmclastreports.ini file found at `/opt/ibm/ras/etc/bmclastreports.ini` This location may vary and the default is shown.
3.	Stop the service using `systemctl stop ibm-crassd`. 
4.	Install ibm-crassd using the instructions above.
5.	Restore the two backed up files to their original locations.
6.	Start the service using `systemctl start ibm-crassd`. 
