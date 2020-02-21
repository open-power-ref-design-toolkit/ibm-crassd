# Example of a docker file to generate an image for ibm-crassd
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
yum install -y libgcc
RUN yum install -y openssh openssh-server openssh-clients openssl-libs
RUN yum install -y java

COPY *.rpm /
RUN yum install -y openbmctool-*.rpm
RUN yum install -y ibm-crassd-*.rpm
RUN systemctl enable ibm-crassd

EXPOSE 53322

ENTRYPOINT ["/usr/sbin/init"]
