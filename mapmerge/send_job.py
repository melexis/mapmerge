from stomp import Connection

import sys

hostname = sys.argv[1]

class MessageListener:

  def on_message(self, headers, message):
    print "Got message %s" % message


c = Connection([(hostname, 61613)])
c.set_listener('', MessageListener())
c.start()
c.connect()
c.subscribe(destination='/topic/postprocessing.mapmerge.out', ack='auto')
f = open('example.xml', 'rb').read()
c.send(f, destination='/queue/postprocessing.mapmerge.erfurt.in')
print 'sent'

import time
time.sleep(100)
