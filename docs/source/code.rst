==========================
Developer's Guide
==========================

ibm-crassd.py
**************************
This is the main module of the ibm-crassd service. It is responsible for setup, loading the configuration, starting the plugins, and then monitoring the defined BMCs for new log entries. 

.. automodule:: ibm_crassd
   :members:

config.py
**************************
This module contains shared data structures used by ibm-crassd and the various other modules in the project. 

.. automodule:: config
   :members:

