#!/usr/bin/env python
from __future__ import with_statement

import base64
import logging
import os
import subprocess
import stomp
import sys
import uuid
import http as requests
import shutil

from ewafermap import *
from tempfile import mkdtemp
from config import WMDS_WEBSERVICE

MAPMERGE = '/usr/share/ink-tool/bin/inkless'

def save_wafermap_formats_to_dir(wafermaps, d):
  """Save a wafermap in the given directory.

     Wafermaps is a list of tuples containing the name of the wafermap and the wafermap
  """
  logging.info("Saving the wafermaps to directory %s" % d)
  for name, wafermap in wafermaps:
    filename = d + '/' + uuid.uuid1().hex
    with open(filename, 'wb') as f:
      logging.debug("Saving wafermap to file %s" % filename)
      f.write(wafermap)
      f.flush()
      f.close()

def th01_wafermaps_generator(wafer):
  """Generator that selects all th01 wafermaps from a given wafername

     First create a wafer object containing a list of wafermaps.
     >>> wm1 = Wafermap('wafermap1', {'th01': Format('raw','c3fe9bd4777d868cea2dd79ebfe569cc6bcbed02')})
     >>> wm2 = Wafermap('wafermap2', {'th01': Format('raw','716c6b31cc6f3be514269de58c4097da89abdcdc'), 'amkor': 'blubber'})
     >>> w = Wafer(1, 100, [wm1, wm2])

     Now we can iterator all th01 wafermaps for a wafer by calling the th01_wafermaps_generator
     >>> [(name, ref) for name, ref in th01_wafermaps_generator(w)]
     [('wafermap1', 'c3fe9bd4777d868cea2dd79ebfe569cc6bcbed02'), ('wafermap2', '716c6b31cc6f3be514269de58c4097da89abdcdc')]
  """
  logging.info('Creating a generator for all TH01 wafermaps in the wafer')
  for wafermap in wafer.wafermaps:
      logging.debug("Generating TH01 wafermaps for wafermap %s" % wafermap.name)
      if wafermap.formats.has_key('th01'):
          logging.debug('Found a TH01 key in the wafermap')
          wkey = wafermap.formats['th01']
          yield (wafermap.name, wkey.wafermap)
          

def th01_reference_to_map_generator(references):
  """Generator that fetches the th01 wafermaps for a list containing the name and reference

     >>> [(name, wmap[:4]) for name, wmap in th01_reference_to_map_generator([('test', '716c6b31cc6f3be514269de58c4097da89abdcdc')])]
     [('test', 'WMAP')]"""
  for name,ref in references:
    r = requests.get(WMDS_WEBSERVICE + ref)
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

    logging.debug("Created temporary directories %s for input and %s for output" % (ind, outd))

    # select all th0x wafermaps to save in the in directory
    wafermaps = th01_reference_to_map_generator(th01_wafermaps_generator(wafer))

    # save all selected wafermaps in the in directory
    save_wafermap_formats_to_dir(wafermaps, ind)

    child = None

    try:
      logging.debug('Creating a subprocess for mapmerge')
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
        stderr=subprocess.PIPE)

      # block until the command is completed
      child.wait()

      # trigger an exception when the returncode isn't 0
      if child.returncode != 0:
        logging.warning("Mapmerge returned with exist code %d" % child.returncode)
        stdout = child.stdout.read()
        stderr = child.stderr.read()
        raise MapMergeException(child.returncode, stdout, stderr)

    finally:
      if child != None:
        child.stdout.close()
        child.stderr.close()

    # check for generated wafermaps in the out directory
    files = [outd + '/' + f for f in os.listdir(outd)]

    logging.debug("Found the following files in the output directory %s" % files)
    
    for filename in files:
      with open(filename, 'rb') as f:
        contents = f.read()
        wafermap = Wafermap('Postprocessing', {'th01': Format('base64', base64.b64encode(contents))})
        wafer.wafermaps.append(wafermap)

  finally:
    shutil.rmtree(ind, ignore_errors=True, onerror=None)
    shutil.rmtree(outd, ignore_errors=True, onerror=None)
    

class MessageListener:

  def __init__(self, conn):
    self.conn = conn

  def on_error(self, headers, message):
    print 'Got error %s' % message

  def on_message(self, headers, message):
    lot = decode(message)
    logging.debug("Received a lot %s" % lot)

    # perform mapmerge on each wafer
    try:
      eachWafer(lot, mapmerge)
      logging.debug("Sending a lot %s" % lot)
      response = encode(lot)
      # send the result back
      self.conn.send(response, destination='/topic/postprocessing.mapmerge.out')
    except BaseException, e: 
      self.conn.send(e.__repr__(), destination='/topic/exceptions.postprocessing')
    
def listen(hostname, port):
  conn = None
  try: 
    conn = stomp.Connection([(hostname, port)])
    conn.set_listener('', MessageListener(conn))
    conn.start()
    conn.connect()
    conn.subscribe(destination='/queue/postprocessing.mapmerge.erfurt.in', ack='auto')

    import time
    while True: time.sleep(1000)
  finally: 
    if conn != None:    
      conn.disconnect()

def usage():
  print("Usage:  %s <<hostname>> <<port>>" % sys.argv[0])

def main():
  if len(sys.argv) == 2 and sys.argv[1] == 'test':
    import doctest
    doctest.testmod()
  elif len(sys.argv) != 3:
    usage()
  else:
    [program, hostname, port] = sys.argv
    logging.debug("Starting mapmerge for esb %s and port %d" % (hostname, int(port)))
    listen(hostname, int(port))

if __name__ == '__main__':
  logging.basicConfig(level=logging.DEBUG)
  main()
