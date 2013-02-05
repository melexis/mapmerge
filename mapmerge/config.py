#!/usr/bin/env python

import logging
import logging.handlers


# hosts is a list of typles containing the hostname and ports of the ewaf stomp servers
HOSTS = [("esb-a-test", 61501),("esb-b-test", 61501)]

WMDS_WEBSERVICE = 'http://ewaf-test.colo.elex.be:8181/cxf/api/wafermap/'

LOGFILE = '/var/log/mapmerge.log'
LOGLEVEL = logging.DEBUG
LOGHANDLER = logging.handlers.RotatingFileHandler(LOGFILE, maxBytes=524288, backupCount=10)

LOGHANDLER.setFormatter(logging.Formatter(fmt='%(asctime)s %(module)s %(levelname)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p'))
