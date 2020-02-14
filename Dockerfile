FROM centos:8 AS centos8-systemd
ENV container docker
RUN (cd /lib/systemd/system/sysinit.target.wants/; for i in *; do [ $i == \
systemd-tmpfiles-setup.service ] || rm -f $i; done); \
rm -f /lib/systemd/system/multi-user.target.wants/*;\
rm -f /etc/systemd/system/*.wants/*;\
rm -f /lib/systemd/system/local-fs.target.wants/*; \
rm -f /lib/systemd/system/sockets.target.wants/*udev*; \
rm -f /lib/systemd/system/sockets.target.wants/*initctl*; \
rm -f /lib/systemd/system/basic.target.wants/*;\
rm -f /lib/systemd/system/anaconda.target.wants/*;
VOLUME [ "/sys/fs/cgroup" ]

FROM centos8-systemd
RUN yum install -y epel-release && yum update -y && \
yum groupinstall -y 'Development Tools' && \
yum install -y libgcc && \
yum install -y python3-requests python3-websocket-client python3-pycparser && \
yum install -y java && \
yum install -y openssh openssh-server openssh-clients openssl-libs && \
yum install -y java-devel && \
yum -y clean all

COPY . /crassdBase
WORKDIR /crassdBase
RUN yum install -y openbmctool/*
RUN make && make install
RUN systemctl enable ibm-crassd

EXPOSE 53322

ENTRYPOINT ["/usr/sbin/init"]
