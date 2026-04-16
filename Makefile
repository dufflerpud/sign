#@HDR@	$Id$
#@HDR@		Copyright 2026 by
#@HDR@		Christopher Caldwell/Brightsands
#@HDR@		P.O. Box 401, Bailey Island, ME 04003
#@HDR@		All Rights Reserved
#@HDR@
#@HDR@	This software comprises unpublished confidential information
#@HDR@	of Brightsands and may not be used, copied or made available
#@HDR@	to anyone, except in accordance with the license under which
#@HDR@	it is furnished.
PROGRAMS=
PROJECTSDIR?=$(shell echo $(CURDIR) | sed -e 's+/projects/.*+/projects+')
include $(PROJECTSDIR)/common/Makefile.std

install:
		$(INSTALL) -d -m 777 -o $(SYSTEMUSER) -g $(SYSTEMGROUP) $(PROJECTDIR)/documents
		$(INSTALL) -d -m 777 -o $(SYSTEMUSER) -g $(SYSTEMGROUP) $(PROJECTDIR)/keys
		$(MAKE) ORIGINAL_TARGET=$@ std_$@

fresh:
		$(GIT) pull
		@$(MAKE) install

%:
		@echo "Invoking std_$@ rule:"
		@$(MAKE) ORIGINAL_TARGET=$@ std_$@
