# Copyright (c) 2017 International Business Machines.  All right reserved.
%define _binaries_in_noarch_packages_terminate_build   0
Summary: IBM POWER LC Cluster RAS Service Package
Name: ibm-crassd
Version: 0.6
Release: 1
License: BSD
Group: System Environment/Base
BuildArch: noarch
URL: http://www.ibm.com/
Source0: %{name}-%{version}-%{release}.tgz
Prefix: /opt
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root

BuildRequires: java-devel >= 1.7.0

Requires: java >= 1.7.0
#Requires: python >= 3.4.5
Requires: python34
Requires: python34-requests
#Requires: python-configparser
Requires: python34-PyYAML
#Requires: python-webpy

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

%build
%{__make}

%install
#rm -rf $RPM_BUILD_ROOT
export DESTDIR=$RPM_BUILD_ROOT/opt/ibm/ras
mkdir -p $DESTDIR/bin
mkdir -p $DESTDIR/etc
mkdir -p $DESTDIR/lib
mkdir -p $RPM_BUILD_ROOT/usr/lib/systemd/system
%{__make} install

cp ibmhwmonitor/*.py openbmctool/*.py $DESTDIR/bin
cp ibmhwmonitor/ibmpowerhwmon.config $DESTDIR/etc
cp ibmhwmonitor/ibmpowerhwmon.service $RPM_BUILD_ROOT/usr/lib/systemd/system
cp openbmctool/*.yml $DESTDIR/lib
#cp errl/hbotStringFile $DESTDIR/lib

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
/opt/ibm/ras/lib/crassd.jar
/opt/ibm/ras/etc/ibmpowerhwmon.config
/opt/ibm/ras/bin/ibmpowerhwmon.py
/opt/ibm/ras/bin/openbmctool.py
/opt/ibm/ras/lib/policyTable.yml
#/opt/ibm/ras/lib/hbotStringFile
/usr/lib/systemd/system/ibmpowerhwmon.service

%post
#%systemd_post ibmpowerhwmon.service

%changelog