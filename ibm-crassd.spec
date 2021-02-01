# Copyright (c) 2017 International Business Machines.  All right reserved.
%define _binaries_in_noarch_packages_terminate_build   0
Summary: IBM POWER LC Cluster RAS Service Package
Name: ibm-crassd
Version: %{_version}
Release: %{_release}%{?dist}
License: Apache 2.0
Group: System Environment/Base
URL: http://www.ibm.com/
Source0: %{name}-%{version}.tgz
BuildArch: noarch
Prefix: /opt
# BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root
BuildRoot: %{_topdir}

BuildRequires: java-devel >= 1.7.0

Requires: java >= 1.7.0
Requires: libstdc++

%if 0%{?el8}
Requires: python3
Requires: python3-requests
Requires: python3-websocket-client
Requires: python3-pexpect
%endif

%if 0%{?el7}
Requires: python36
Requires: python36-requests
Requires: python-configparser
Requires: python36-websocket-client
Requires: pexpect
%endif

%if 0%{?_unitdir:1}
Requires(post): systemd-units
Requires(preun): systemd-units
Requires(postun): systemd-units
%endif

# Turn off the brp-python-bytecompile script
%global __os_install_post %(echo '%{__os_install_post}' | sed -e 's!/usr/lib[^[:space:]]*/brp-python-bytecompile[[:space:]].*$!!g')
%global debug_package %{nil}

%description
This package is to be applied to service nodes in a POWER 9 LC cluster.  It serv
es to aggregate BMC node data, apply service policy, and forward recommendation 
to cluster service management utilities.  Node data includes hardware machine st
ate including environmental, reliability, service, and failure data.

%prep
%setup

%pre

%build
%{__make}

%install
#rm -rf $RPM_BUILD_ROOT
export DESTDIR=%{buildroot}
%{__make} install

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
/opt/ibm/ras/lib/crassd.jar
%config /opt/ibm/ras/etc/ibm-crassd.config
%attr(755,root,root) /opt/ibm/ras/bin/ibm_crassd.py
/opt/ibm/ras/bin/__init__.py
/opt/ibm/ras/bin/telemetryServer.py
/opt/ibm/ras/bin/config.py
/opt/ibm/ras/bin/notificationlistener.py
%attr(755,root,root) /opt/ibm/ras/bin/updateNodeTimes.py
%attr(755,root,root) /opt/ibm/ras/bin/buildNodeList.py
/opt/ibm/ras/bin/plugins/
/usr/lib/systemd/system/ibm-crassd.service
/usr/lib/systemd/system-preset/85-ibm-crassd.preset


%post

%changelog
