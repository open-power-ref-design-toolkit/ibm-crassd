================================================
Creating a listener for streamed sensor readings
================================================
This section discusses creating a listener for metric (telemetry) streaming. This includes filtering the data received and setting the frequency of updates. 

Overview
================
The ibm-crassd service will host collected sensor readings on a socket. This socket is setup to listen on all IP addresses for where the Host OS is installed, and uses a predefined port number. This port number is configurable in the ibm-crassd.config file. When ibm-crassd has started the telemetry service and is ready to receive a connection from a client, a system journal entry is posted indicating the telemetry service has started. It's at this point a client may connect to the socket server and start listening to the stream of readings. Additionally, once connected filters can be applied.  The data is sent from ibm-crassd to listeners in a serialized JSON format with a 4-byte header. The ibm-crassd service will also handle re-connection attempts to dropped BMC connections, should a connection to the BMC be lost. Until the connection is re-established, **ibm-crassd will forward the last known reading of the sensors**. A full example of a python metric listener can be found in the examples directory on the github repository. 

Data Structure Review
===========================
The sensor data is formatted in a dictionary at the top level. Most of this data is accessed directly using a combination of the reference name for the node ``xcatNodeName`` from the configuration file, and the name for the sensor. The AC922 systems have a maximum of 111 sensors. Below is a generic example showing dictionary representation.  

.. code-block:: JSON
    :linenos:

    {
        "Time_Sent": "String. Time in seconds since UNIX epoch when the sample was sent",
        "xcatNodeName": {
            "sensorName1": {
                "scale": "Float. Indicates what to multiple the value by.",
                "value":  "Integer. The reading of the sensor.",
                "type": ["string. Description of the sensor.", "string. Units for the sensor."] 
            },
            "LastUpdateRecieved": "String. Time in seconds since epoch, when the last update from the BMC was received.",
            "Node State": "String. The state of the node. Can be Powered On or Powered Off",
	    "Connected": "Boolean. true if the connection with the BMC is active, otherwise false."
        }
    }

The following is an example of a single node and two sensors.

.. code-block:: JSON
    :linenos:

    {
        "Time_Sent": "1563222466",
        "compute1": {
            "cpu0_temp": {
                "scale": 0.001,
                "value": null,
                "type": ["temperature", "Celsius"]
            },
            "total_power": {
                "scale": 1,
                "value": 161,
                "type": ["power", "Watts"]
            },
            "LastUpdateReceived": "1563222466",
            "Node State": "Powered Off",
            "Connected": true
        }
    }

Connecting to the Telemetry Server
===================================
Connection to the telemetry server has been simplified. All an application needs is to open a socket to the configured port number and the IP address of the system ibm-crassd is running on. Once the socket is opened, ibm-crassd will begin sending sensor readings once every second to the client. A client can then provide filters or frequency adjustments which will be discussed in the next section. Below is a simple connection created to ibm-crassd from a listener on the same server. 

.. code-block:: python
    :linenos:

    import socket
    import struct
    import json

    HOST = '127.0.0.1'  # Standard loop-back interface address (localhost)
    PORT = 53322        # Port to listen on (non-privileged ports are > 1023)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print("Connecting to ", HOST)
    s.connect((HOST, PORT))
    print('connected')

Processing the Data Received from the Telemetry Server
======================================================
Once the connection is setup as shown above we can begin processing the packets received from the ibm-crassd service. There's 2 pieces to deal with from the data packets. The first is the header. The header contains the size of the JSON structure. The struct library is used to unpack the header and get the message length. Below is an example of reading this:

.. code-block:: python
    :linenos:

    def recvall(sock, n):
        """
            Helper function to receive n bytes or return None if EOF is hit
            @param sock: The socket to read data from
            @param n: The number of bytes to read from the socket
            @return: The data that was received and is ready to process
        """
        data = b''
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data
    
    def crassd_client(servSocket, sn):
        """
            Function to manage the opened socket with ibm-crassd
            @param servSocket: The socket to read data from and write filters to
            @param sn: The hostname/IP of the service node running ibm-crassd
        """
        raw_msglen = recvall(servSocket, 4)
        if not raw_msglen:
            break
        msglen = struct.unpack('>I', raw_msglen)[0]

Next we need to continue in the crassd_client function, and get the actual sensor readings. The code snippet below uses the length collected from the header to retrieve all of the data that was sent, from the socket buffer. The data is then loaded into a dictionary to prepare for usage, using the JSON.loads function. 

.. code-block:: python
    :linenos:
    
    def crassd_client(servSocket, sn):
        # continuation from above
        data = recvall(servSocket, msglen)
        if not data:
            break
        
        sensData = json.loads(data.decode()) 

Filtering the Data ibm-crassd Sends
====================================
The telemetry server offers a few different options for filtering the data it sends to the subscribed clients. The following are a list of filtering options in prioritized order. These sensor filters can be changed and updated at any time with an active connection.

1. Sensor name - A sensor name, or a list of sensor names can be passed to ibm-crassd, and it will only return readings for sensors that match the name. This has the highest priority.
2. Sensor type - The sensor type, one of power, voltage, current, fan_tach, and/or temperature. These types can be provided in a list, and ibm-crassd will only send readings for those types.
3. Frequency - This option tells ibm-crassd how often to send sensor updates in seconds. This is provided as an integer greater than or equal to one. 

It is very important to note that the sensor names and sensor types must be sent as a list, even if it is only one item. 

Below is a python example of the client sample above sending filtering options. It's setting the frequency of updates to once every 3 seconds, and only getting sensor types of power. 

.. code-block:: python
    :linenos:
    
    def crassd_client(servSocket, sn):
        # continuation from above
        sensfilters = {'frequency': 3, 'sensortypes': ['power']}
        data2send = (json.dumps(sensfilters, indent=0, separators=(',', ':')).replace('\n','') +"\n").encode()
        msg = struct.pack('>I', len(data2send)) + data2send
        servSocket.sendall(msg)

