#!/usr/bin/env python

import logging
import logging.handlers

logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

STOMP_HOSTNAME='ewaf-test.colo.elex.be'
STOMP_PORT=61613

WMDS_WEBSERVICE = 'http://ewaf-test.colo.elex.be:8181/cxf/api/wafermap/'

LOGFILE = '/var/log/mapmerge.log'
LOGLEVEL = logging.DEBUG
LOGHANDLER = logging.handlers.RotatingFileHandler(LOGFILE, maxBytes=524288, backupCount=10)
