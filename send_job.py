from stomp import Connection

class MessageListener:

  def on_message(self, headers, message):
    print "Got message %s" % message


c = Connection([('ewaf-test.colo.elex.be', 61613)])
c.set_listener('', MessageListener())
c.start()
c.connect()
c.subscribe(destination='/queue/postprocessing.mapmerge.out', ack='auto')
f = open('example.xml', 'rb').read()
c.send(f, destination='/topic/postprocessing.mapmerge.erfurt.in')
print 'sent'

import time
time.sleep(100)
