#!/usr/bin/env python
from __future__ import with_statement

import base64
import logging
import logging.handlers
import os
import subprocess
import stomp
import sys
import uuid
import http as requests
import shutil
import traceback

from ewafermap import *
from tempfile import mkdtemp
from config import WMDS_WEBSERVICE
from config import LOGLEVEL

MAPMERGE = '/usr/share/ink-tool/bin/inkless'

logger = logging.getLogger(__name__)

def format_stacktrace(e):
  """Format an exception with the stacktrace"""
  exc_type, exc_value, exc_traceback = sys.exc_info()
  return "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

def save_wafermap_formats_to_dir(wafermaps, d):
  """Save a wafermap in the given directory.

     Wafermaps is a list of tuples containing the name of the wafermap and the wafermap
  """
  logger.info("Saving the wafermaps to directory %s" % d)
  for name, wafermap in wafermaps:
    filename = d + '/' + uuid.uuid1().hex
    with open(filename, 'wb') as f:
      logger.debug("Saving wafermap to file %s" % filename)
      f.write(wafermap)
      f.flush()
      f.close()

def th01_wafermaps_generator(wafer):
  """Generator that selects all th01 wafermaps from a given wafername

     First create a wafer object containing a list of wafermaps.
     >>> wm1 = Wafermap('wafermap1', {'th01': Format('c3fe9bd4777d868cea2dd79ebfe569cc6bcbed02', None)})
     >>> wm2 = Wafermap('wafermap2', {'th01': Format('716c6b31cc6f3be514269de58c4097da89abdcdc', None), 'amkor': 'blubber'})
     >>> w = Wafer(1, 100, [wm1, wm2])

     Now we can iterator all th01 wafermaps for a wafer by calling the th01_wafermaps_generator
     >>> [(name, ref) for name, ref in th01_wafermaps_generator(w)]
     [('wafermap1', 'c3fe9bd4777d868cea2dd79ebfe569cc6bcbed02'), ('wafermap2', '716c6b31cc6f3be514269de58c4097da89abdcdc')]
  """
  logger.info('Creating a generator for all TH01 wafermaps in the wafer')
  for wafermap in wafer.wafermaps:
      logger.debug("Generating TH01 wafermaps for wafermap %s" % wafermap.name)
      if wafermap.formats.has_key('th01'):
          logger.debug('Found a TH01 key in the wafermap')
          format = wafermap.formats['th01']
          yield (wafermap.name, format.reference)
          

def th01_reference_to_map_generator(references):
  """Generator that fetches the th01 wafermaps for a list containing the name and reference

     >>> [(name, wmap[:4]) for name, wmap in th01_reference_to_map_generator([('test', '716c6b31cc6f3be514269de58c4097da89abdcdc')])]
     [('test', 'WMAP')]"""
  for name,ref in references:
    url = WMDS_WEBSERVICE + ref
    logger.debug('Getting %s' % url) 
    r = requests.get(url)
    if r.status_code > 300:
        raise BaseException("Wafermap with key %s was not found in the datastore" % ref)
    yield (name, r.text)


class MapMergeException(BaseException):

  def __init__(self, errcode, stdout, stderr):
    self.errcode = errcode
    self.stdout = stdout
    self.stderr = stderr

  def __repr__(self):
     return """Got return code different then 0:  %d
                 stdout: %s
                 stderr: %s""" % (self.errcode, self.stdout, self.stderr)
    
def mapmerge(lot, wafer):
  """Call mapmerge for a given wafermap.  Save the result of mapmerge in a new wafermap."""
  # create the temporary directoy for the input wafermaps
  try:
    ind = mkdtemp(suffix='input')
    outd = mkdtemp(suffix='output')

    logger.debug("Created temporary directories %s for input and %s for output" % (ind, outd))

    # select all th0x wafermaps to save in the in directory
    wafermaps = th01_reference_to_map_generator(th01_wafermaps_generator(wafer))

    # save all selected wafermaps in the in directory
    save_wafermap_formats_to_dir(wafermaps, ind)

    child = None

    try:
      logger.debug('Creating a subprocess for mapmerge')
      logger.debug('Starting command %s' % ('%s lot=%s wafer=%d ProcessStep=%s noDB localFolder=%s DestinationDir=%s' % (MAPMERGE, lot.name, int(wafer.number), lot.config['processStep'], ind, outd)))
      # spawn a new subprocess for mapmerge
      child = subprocess.Popen([
        MAPMERGE,
        "lot=%s" % lot.name, 
        "wafer=%d" % int(wafer.number), 
        "ProcessStep=%s" % lot.config['processStep'],
        "noDB",
        "localFolder=%s" % ind,
        "DestinationDir=%s" % outd
        ], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        bufsize=200000)

      stdout = ""
      stderr = ""
 
      while child.returncode == None:
        stdout = stdout + child.stdout.read()
        stderr = stderr + child.stderr.read()
        child.poll()
      
      # trigger an exception when the returncode isn't 0
      if child.returncode != 0:
        logger.warning("Mapmerge returned with exit code %d" % child.returncode)
        raise MapMergeException(child.returncode, stdout, stderr)

    finally:
      if child != None:
        child.stdout.close()
        child.stderr.close()

    # check for generated wafermaps in the out directory
    files = [outd + '/' + f for f in os.listdir(outd)]

    logger.debug("Found the following files in the output directory %s" % files)
    
    for filename in files:
      with open(filename, 'rb') as f:
        contents = f.read()
        wafermap = Wafermap('Postprocessing', {'th01': Format(None, contents)})
        wafer.wafermaps.append(wafermap)

  finally:
    shutil.rmtree(ind, ignore_errors=True, onerror=None)
    shutil.rmtree(outd, ignore_errors=True, onerror=None)
    

class MessageListener(stomp.listener.ConnectionListener):

  def __init__(self, conn):
    self.conn = conn

  def on_error(self, headers, message):
    print 'Got error %s' % message

  def on_message(self, headers, message):
    lot = decode(message)
    logger.debug("Received a lot %s" % lot)

    try:
      # perform mapmerge on each wafer
      eachWafer(lot, mapmerge)
      logger.debug('Finished mapmerge for %s' % lot.name)
 
      def _push_postprocessing_wafermap_to_wmds(lot, wafer):
        # filter all wafermaps that don't have a reference
        wafermaps_to_upload = filter(
            lambda wafermap:  wafermap.formats.has_key('th01') and wafermap.formats['th01'].reference == None, 
            wafer.wafermaps)

        logger.debug('Number of wafermaps to upload:  %d' % len(wafermaps_to_upload))
 
        for wafermap in wafermaps_to_upload:
          logger.debug('Starting the upload of %d bytes to %s' % (len(wafermap.formats['th01'].wafermap), WMDS_WEBSERVICE))
          resp = requests.put(WMDS_WEBSERVICE, headers={'Content-Type': 'application/octet-stream'}, data=wafermap.formats['th01'].wafermap)
          logger.debug('Got response %s' % resp)
          if resp.status_code < 300:
            logger.debug('Uploaded wafermap %s-%d Postprocessing to the wmds: %s' % (lot.name, int(wafer.number), resp.text))
            # the service returns the reference in the body of the put
            wafermap.formats['th01'].reference = resp.text
          else:
            logger.warning('Unable to upload wafermap to the wmds:  %d - %s' % (resp.status_code, resp.text))
            raise BaseException('Unable to push wafermap to the wmds: %d - %s' % (resp.status_code, resp.text))

      # save the postprocessing wafermap to the wmds            
      eachWafer(lot, _push_postprocessing_wafermap_to_wmds)
      response = encode(lot)
      # send the result back
      self.conn.send(response, destination='/topic/postprocessing.mapmerge.out')
    except BaseException, e:
      stacktrace = format_stacktrace(e)
      msg = "Got exception while processing message %s:\t\n%s" % (message, stacktrace)
      logger.warning(msg)
      self.conn.send(msg, destination='/topic/exceptions.postprocessing')

  def on_disconnect(self):
    logger.warn('Lost connection to stomp server')
    
def listen(hostname, port):
  import time
  logger.info('Starting to listen')
  conn = None
  while True:
    logger.debug('Trying to connect to stomp server')
    try: 
      conn = stomp.Connection([(hostname, port)])
      conn.set_listener('', MessageListener(conn))
      conn.start()
      conn.connect()
      conn.subscribe(destination='/queue/postprocessing.mapmerge.erfurt.in', ack='auto')
      time.sleep(1000)
      while True and conn.is_connected(): time.sleep(1000)
    except (stomp.exception.NotConnectedException, stomp.exception.ConnectFailedException):
      time.sleep(1000)
      pass
    except e:
      logger.debug('Got exception %s' % e)
    finally: 
      if conn != None and conn.is_connected():    
        conn.disconnect()

def usage():
  print("Usage:  %s <<hostname>> <<port>>" % sys.argv[0])

def main():
  logger.setLevel(logging.DEBUG)
  logger.addHandler(logging.StreamHandler())

  if len(sys.argv) == 2 and sys.argv[1] == 'test':
    import doctest
    doctest.testmod()
  elif len(sys.argv) != 3:
    usage()
  else:
    [program, hostname, port] = sys.argv
    logger.debug("Starting mapmerge for esb %s and port %d" % (hostname, int(port)))
    listen(hostname, int(port))

if __name__ == '__main__':
  main()
