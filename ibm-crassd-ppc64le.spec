# Copyright (c) 2017 International Business Machines.  All right reserved.
%define _binaries_in_noarch_packages_terminate_build   0
Summary: IBM POWER LC Cluster RAS Service Package
Name: ibm-crassd
Version: 0.7
Release: 3
License: BSD
Group: System Environment/Base
BuildArch: ppc64le
URL: http://www.ibm.com/
Source0: %{name}-%{version}-%{release}.tgz
#Remove for specific versions of libstdc as errl files have requirements not satisfied by base os. Still runs fine with newer versions. 
AutoReqProv: no
Prefix: /opt
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root

BuildRequires: java-devel >= 1.7.0

Requires: java >= 1.7.0
Requires: python 
Requires: python-requests
Requires: libstdc++

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
installList=""
python_websocket=$(ls /usr/lib/python2.7/site-packages/ | grep -ie websocket_client)
python_configparser=$(ls /usr/lib/python2.7/site-packages/ | grep -ie configparser)
if [ -z "$python_websocket" ]; then
	installList+=" websocket-client"	
fi

if [ -z "$python_configparser" ]; then
	installList+=" configparser"	
fi
if [ -n "$installList" ];then
	message="The following python packages are are required:$installList"
	echo $message
	echo "Install these packages from pypi.python.org using the following command: "
	echo "easy_install$installList"
	echo "Once complete, run this installer again. "
	exit 1
fi

%build
%{__make}

%install
#rm -rf $RPM_BUILD_ROOT
export DESTDIR=$RPM_BUILD_ROOT/opt/ibm/ras
mkdir -p $DESTDIR/bin
mkdir -p $DESTDIR/bin/plugins
mkdir -p $DESTDIR/bin/ppc64le
mkdir -p $DESTDIR/etc
mkdir -p $DESTDIR/lib
mkdir -p $RPM_BUILD_ROOT/usr/lib/systemd/system

%{__make} install

cp ibm-crassd/*.py $DESTDIR/bin
cp -r ibm-crassd/plugins/* $DESTDIR/bin/plugins
cp ibm-crassd/ibm-crassd.config $DESTDIR/etc
cp ibm-crassd/ibmcrassd.service $RPM_BUILD_ROOT/usr/lib/systemd/system
cp ibm-crassd/85-ibm-crassd.preset $RPM_BUILD_ROOT/usr/lib/systemd/system-preset
cp errl/ppc64le/errl $DESTDIR/bin/ppc64le
#cp rastools/gard $DESTDIR/bin/ppc64le
#cp rastools/putscom $DESTDIR/bin/ppc64le
#cp rastools/getscom $DESTDIR/bin/ppc64le

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
/opt/ibm/ras/lib/crassd.jar
/opt/ibm/ras/etc/ibm-crassd.config
/opt/ibm/ras/bin/ibm-crassd.py
/opt/ibm/ras/bin/config.py
/opt/ibm/ras/bin/notificationlistener.py
/opt/ibm/ras/bin/plugins/
/opt/ibm/ras/bin/plugins/ibm_csm/
/opt/ibm/ras/bin/plugins/ibm_csm/__init__.py
/opt/ibm/ras/bin/plugins/ibm_csm/csmnotify.py
/opt/ibm/ras/bin/plugins/ibm_csm/CSMpolicyTable.json
/opt/ibm/ras/bin/plugins/__init__.py
/opt/ibm/ras/bin/plugins/ibm_ess/
/opt/ibm/ras/bin/plugins/ibm_ess/essnotify.py
/opt/ibm/ras/bin/plugins/ibm_ess/__init__.py
/opt/ibm/ras/bin/ppc64le/errl
/usr/lib/systemd/system/ibm-crassd.service
/usr/lib/systemd/system-preset/85-ibm-crassd.preset
#/opt/ibm/ras/bin/ppc64le/getscom
#/opt/ibm/ras/bin/ppc64le/putscom
#/opt/ibm/ras/bin/ppc64le/gard


%post
#%systemd_post ibmpowerhwmon.service
#ln -s -f /opt/ibm/ras/bin/openbmctool.py /usr/bin/openbmctool
#ls -s -f /opt/ibm/ras/bin/ppc64le/plc/plc.pl /usr/bin/plc.pl
%changelog
