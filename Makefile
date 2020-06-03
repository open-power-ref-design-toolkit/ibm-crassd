# Makefile for IBM POWER hardware monitor
# Copyright (c) 2017 International Business Machines.
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
# 
#        http://www.apache.org/licenses/LICENSE-2.0
# 
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#.ONESHELL:
JAVAC=/usr/bin/javac
JAR=/usr/bin/jar
JAVAH=/usr/bin/javah
JAVA=/usr/bin/java
CLASSPATH=./classes
VER=1.2
REL=0
PROD=ibm-crassd
NAME=$(PROD)-$(VER)-$(REL)

# Need to test RPMDIR to see if it is set. Otherwise set it.
RPMDIR := $(if $(RPMDIR),$(RPMDIR),$(shell pwd)/build/rpm)

# Need to test DEBDIR to see if it is set. Otherwise set it.
DEBDIR := $(if $(DEBDIR),$(DEBDIR),$(shell pwd)/build/deb)

#setup the java file directory for building the jar
JAVADIR= $(shell pwd)/build

CURDIR=$(shell pwd)

default: java jar
java:	;mkdir -p $(JAVADIR)/classes &&cp -R ipmiSelParser/ $(JAVADIR) && cd $(JAVADIR)&& $(JAVAC) -d  $(JAVADIR)/classes `find . -name *.java`
clean: ;rm -rf ./build
jar: java;mkdir -p $(JAVADIR)/lib && cp -R ./ipmiSelParser $(JAVADIR) && cd $(JAVADIR)/classes/ && $(JAR) -cvfe ../lib/crassd.jar ipmiSelParser.ipmiSelParser * ../ipmiSelParser/*.properties ../ipmiSelParser/resources/* 
install: java jar
	mkdir -p $(DESTDIR)/opt/ibm/ras/{lib,etc,bin}
	cp $(JAVADIR)/lib/* $(DESTDIR)/opt/ibm/ras/lib
	cp ./ibm-crassd/*.config $(DESTDIR)/opt/ibm/ras/etc
	rsync -avr --exclude='*FQPSP*' ./ibm-crassd/*.py $(DESTDIR)/opt/ibm/ras/bin
	cp -R ./ibm-crassd/plugins $(DESTDIR)/opt/ibm/ras/bin
	cp ./*.preset $(DESTDIR)/usr/lib/systemd/system-preset
	cp ./*.service $(DESTDIR)/usr/lib/systemd/system

rpm: java jar
	rm -rf $(RPMDIR)
	mkdir -p $(RPMDIR)
	mkdir -p $(RPMDIR)/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
	mkdir -p $(RPMDIR)/BUILDROOT/$(PROD)-$(VER)
	mkdir -p $(RPMDIR)/BUILDROOT/$(PROD)-$(VER)/usr/lib/systemd/{system,system-preset}
	#cp -R $(JAVADIR)/lib $(RPMDIR)/BUILDROOT/$(PROD)-$(VER)/
	make install DESTDIR=$(RPMDIR)/BUILDROOT/$(PROD)-$(VER)
	cp $(CURDIR)/ibm-crassd.spec $(RPMDIR)/SPECS/
	cp $(CURDIR)/Makefile $(RPMDIR)/BUILDROOT/$(PROD)-$(VER)/
	cp -R $(CURDIR)/ipmiSelParser $(CURDIR)/ibm-crassd $(CURDIR)/*.preset $(CURDIR)/*.service $(RPMDIR)/BUILDROOT/$(PROD)-$(VER)/
	tar -cvzf $(RPMDIR)/SOURCES/$(PROD)-$(VER).tgz -C $(RPMDIR)/BUILDROOT $(PROD)-$(VER)
	rpmbuild --define '_topdir $(RPMDIR)' --define "_version $(VER)" --define "_release $(REL)" -bb $(RPMDIR)/SPECS/ibm-crassd.spec  

deb: java jar
	rm -rf $(DEBDIR)
	mkdir -p $(DEBDIR)
	for i in bin lib etc; do mkdir -p $(DEBDIR)/opt/ibm/ras/$$i; done
	for i in system system-preset; do mkdir -p $(DEBDIR)/usr/lib/systemd/$$i; done
	make install DESTDIR=$(DEBDIR)
	mkdir -p $(DEBDIR)/DEBIAN
	cp control $(DEBDIR)/DEBIAN
	cd $(DEBDIR); find opt -type f -exec md5sum "{}" + >> DEBIAN/md5sums
	cd $(DEBDIR); find usr -type f -exec md5sum "{}" + >> DEBIAN/md5sums
	cd $(DEBDIR); echo "/opt/ibm/ras/etc/ibm-crassd.config" >> DEBIAN/conffiles
	cd $(DEBDIR); echo "/usr/lib/systemd/system/ibm-crassd.service" >> DEBIAN/conffiles
	cd $(DEBDIR); echo "/usr/lib/systemd/system-preset/85-ibm-crassd.preset" >> DEBIAN/conffiles
	cd $(DEBDIR); echo "#!/bin/bash" >> DEBIAN/postinst
	cd $(DEBDIR); echo "systemctl daemon-reload 2> /dev/null || true" >> DEBIAN/postinst
	chmod +x $(DEBDIR)/DEBIAN/postinst
	chmod +x $(DEBDIR)/opt/ibm/ras/bin/ibm_crassd.py
	chmod +x $(DEBDIR)/opt/ibm/ras/bin/updateNodeTimes.py
	chmod +x $(DEBDIR)/opt/ibm/ras/bin/buildNodeList.py
	dpkg-deb -b $(DEBDIR) $(DEBDIR)/DEBIAN/ibm-crassd-$(VER).$(REL).deb
