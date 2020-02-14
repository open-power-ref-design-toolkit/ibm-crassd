# Copyright (c) 2017 International Business Machines.  All right reserved.
%define _binaries_in_noarch_packages_terminate_build   0
Summary: IBM POWER LC Cluster RAS Service Package
Name: ibm-crassd
Version: %{_version}
Release: %{_release}
License: Apache 2.0
Group: System Environment/Base
BuildArch: x86_64
URL: http://www.ibm.com/
Source0: %{name}-%{version}-%{release}.tgz
#Remove for specific versions of libstdc as errl files have requirements not satisfied by base os. Still runs fine with newer versions. 
AutoReqProv: no
Prefix: /opt
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root

BuildRequires: java-devel >= 1.7.0

Requires: java >= 1.7.0
Requires: python3
Requires: python3-requests
#Requires: python-configparser
Requires: python3-websocket-client
Requires: libstdc++
Requires: python3-pexpect

%if 0%{?_unitdir:1}
Requires(post): systemd-units
Requires(preun): systemd-units
Requires(postun): systemd-units
%endif

# Turn off the brp-python-bytecompile script
%global __os_install_post %(echo '%{__os_install_post}' | sed -e 's!/usr/lib[^[:space:]]*/brp-python-bytecompile[[:space:]].*$!!g')

%description
This package is to be applied to service nodes in a POWER 9 LC cluster.  It serv
es to aggregate BMC node data, apply service policy, and forward recommendation 
to cluster service management utilities.  Node data includes hardware machine st
ate including environmental, reliability, service, and failure data.

%prep
%setup -q -n %{name}-%{version}-%{release}

%pre

%build
%{__make}

%install
#rm -rf $RPM_BUILD_ROOT
export DESTDIR=$RPM_BUILD_ROOT/opt/ibm/ras
mkdir -p $DESTDIR/bin
mkdir -p $DESTDIR/bin/plugins
mkdir -p $DESTDIR/bin/x86_64
mkdir -p $DESTDIR/etc
mkdir -p $DESTDIR/lib
mkdir -p $RPM_BUILD_ROOT/usr/lib/systemd/system
mkdir -p $RPM_BUILD_ROOT/usr/lib/systemd/system-preset

%{__make} install

cp ibm-crassd/*.py $DESTDIR/bin
cp -r ibm-crassd/plugins/* $DESTDIR/bin/plugins
cp ibm-crassd/ibm-crassd.config $DESTDIR/etc
cp ibm-crassd.service $RPM_BUILD_ROOT/usr/lib/systemd/system
cp 85-ibm-crassd.preset $RPM_BUILD_ROOT/usr/lib/systemd/system-preset
cp errl/x86_64/errl $DESTDIR/bin/x86_64

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
/opt/ibm/ras/lib/crassd.jar
%config /opt/ibm/ras/etc/ibm-crassd.config
%attr(755,root,root) /opt/ibm/ras/bin/ibm_crassd.py
/opt/ibm/ras/bin/telemetryServer.py
/opt/ibm/ras/bin/config.py
/opt/ibm/ras/bin/notificationlistener.py
%attr(755,root,root) /opt/ibm/ras/bin/updateNodeTimes.py
%attr(755,root,root) /opt/ibm/ras/bin/buildNodeList.py
%attr(755,root,root) /opt/ibm/ras/bin/analyzeFQPSPPW0034M.py
%attr(755,root,root) /opt/ibm/ras/bin/analyzeFQPSPAA0001M.py
/opt/ibm/ras/bin/plugins/
/opt/ibm/ras/bin/plugins/ibm_csm/
/opt/ibm/ras/bin/plugins/ibm_csm/__init__.py
/opt/ibm/ras/bin/plugins/ibm_csm/csmnotify.py
/opt/ibm/ras/bin/plugins/ibm_csm/CSMpolicyTable.json
/opt/ibm/ras/bin/plugins/__init__.py
/opt/ibm/ras/bin/plugins/ibm_ess/
/opt/ibm/ras/bin/plugins/ibm_ess/essnotify.py
/opt/ibm/ras/bin/plugins/ibm_ess/__init__.py
/opt/ibm/ras/bin/plugins/logstash/
/opt/ibm/ras/bin/plugins/logstash/logstashnotify.py
/opt/ibm/ras/bin/plugins/logstash/__init__.py
/opt/ibm/ras/bin/x86_64/errl
/usr/lib/systemd/system/ibm-crassd.service
/usr/lib/systemd/system-preset/85-ibm-crassd.preset


%post

%changelog
