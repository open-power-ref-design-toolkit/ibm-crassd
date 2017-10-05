# Makefile for IBM POWER hardware monitor
# Copyright (c) 2017 International Business Machines.  All rights reserved.
JAVAHOME=/etc/alternatives/java_sdk
JAVAC=$(JAVAHOME)/bin/javac
JAR=$(JAVAHOME)/bin/jar
JAVAH=$(JAVAHOME)/bin/javah
JAVA=$(JAVAHOME)/bin/java
CLASSPATH=./classes

# Need to test DESTDIR to see if it is set.  Otherwise set it.

default: java jar
java: ;mkdir -p classes && $(JAVAC) -d  ./classes `find . -name *.java`
clean: ;rm -rf ./classes ./lib
jar: java;mkdir -p ./lib && cd classes/ && $(JAR) -cvfe ../lib/crassd.jar ipmiSelParser.ipmiSelParser * ../ipmiSelParser/*.properties ../ipmiSelParser/resources/*
install: ;cp ./lib/* $(DESTDIR)/lib/
