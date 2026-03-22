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

test:		$(RESDIR)/.must_exist
		$(BINDIR)/* < tests/1 > $(RESDIR)/1

install:
		$(INSTALL) -d -m 777 -o $(SYSTEMUSER) -g $(SYSTEMGROUP) $(PROJECTDIR)/documents
		$(INSTALL) -d -m 777 -o $(SYSTEMUSER) -g $(SYSTEMGROUP) $(PROJECTDIR)/keys
		$(MAKE) std_$@ ORIGINAL_TARGET=$@

fresh:
		$(GIT) pull
		@make install

%:
		@echo "Invoking std_$@ rule:"
		@$(MAKE) std_$@ ORIGINAL_TARGET=$@
