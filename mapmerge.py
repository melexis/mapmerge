#!/usr/bin/env python

import base64
import os
import subprocess
import stomp
import sys

from ewafermap import *
from tempfile import mkdtemp

MAPMERGE = '/usr/share/ink-tool/bin/inkless'

def save_wafermap_formats_to_dir(wafermaps, d):
  """Save a wafermap in the given directory.

     Wafermaps is a tuple containing the name of the wafermap and the base64 encoded wafermap.
  """
  for (name, wafermap) in wafermaps:
    with open(d + '/' + name, 'wb') as f:
      decoded = base64.b64decode(wf.wafermap)
      f.write(decoded)

def th01_wafermaps_generator(wafer):
  """Generator that selects all th01 wafermaps from a given wafer"""
  for wm in wafer.wafermaps:
    fm = wm.formats['TH01']
    yield (wm.name, fm.decode())
    
def mapmerge(wafer):
  """Call mapmerge for a given wafermap.  Save the result of mapmerge in a new wafermap."""
  # create the temporary directoy for the input wafermaps
  ind = mkdtemp(suffix='input')
  outd = mkdtemp(suffix='output')

    
  # select all th0x wafermaps to save in the in directory
  wafermaps = th01_wafermaps_generator(wafer)

  # save all selected wafermaps in the in directory
  save_wafermap_formats_to_dir(wafermaps, ind)

  try:
    # spawn a new subprocess for mapmerge
    child = subprocess.Popen([
        MAPMERGE, 
        "wafer=%d" % wafer.number, 
        "ProcessStep=%s" % wafer.config['ProcessStep'],
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
        stdout = child.stdout.read()
        stderr = child.stderr.read()
        raise """Got return code different then 0:  %d
                 stdout: %s
                 stderr: %s""" % (child.returncode, stdout, stderr)
  finally:
    child.stdout.close()
    child.stderr.close()

  # check for generated wafermaps in the out directory
  files = [ind + '/' + f for f in os.listdir(ind)]

  for filename in files:
    f = open(filename, 'rb').read()
    wafermap = Wafermap(filename, {'TH01': Format('base64', base64.b64encode(f))})
    wafer.wafermaps.append(wafermap)

class MessageListener:

  def __init__(self, conn):
    self.conn = conn

  def on_error(self, headers, message):
    print 'Got error %s' % message

  def on_message(self, headers, message):
    lot = decode(message)
    
    # perform mapmerge on each wafer
    eachWafer(lot, mapmerge)
    
    response = encode(lot)
    # send the result back
    self.conn.send(response, destination='/topic/postprocessing.mapmerge.out')
    
    
def listen(hostname, port):
  while True:
    conn = stomp.Connection([(hostname, port)])
    conn.set_listener('', MessageListener(conn))
    conn.start()
    conn.connect()

    conn.subscribe(destination='/queue/postprocessing.mapmerge.erfurt.in', ack='auto')
    conn.disconnect()

def usage():
  print("Usage:  %s <<hostname>> <<port>>" % sys.argv[0])

def main():
  if len(sys.argv) != 3:
    usage()
  else:
    [program, hostname, port] = sys.argv
    listen(hostname, int(port))

if __name__ == '__main__':
  main()
