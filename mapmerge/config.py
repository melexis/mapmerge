#!/usr/bin/env python

STOMP_HOSTNAME='ewaf-test.colo.elex.be'
STOMP_PORT=61613

WMDS_WEBSERVICE = 'http://ewaf-test.colo.elex.be:8181/cxf/api/wafermap/'

LOGFILE = 'log/mapmerge.log'
LOGLEVEL = logging.DEBUG
LOGHANDLER = logging.handlers.RotatingFileHandler(LOGFILE, maxBytes=524288, backupCount=10)