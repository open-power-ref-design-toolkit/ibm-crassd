FROM netdata/netdata
RUN apk add python3 py3-pip && \
pip3 install requests
COPY ibm-crassdPlugin.py /usr/libexec/netdata/plugins.d/ibm-crassdPlugin.plugin
RUN chmod 755 /usr/libexec/netdata/plugins.d/ibm-crassdPlugin.plugin

