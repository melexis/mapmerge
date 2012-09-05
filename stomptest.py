import stomp

class Listener:

  def on_message(self, headers, message):
    print "got %s" % message

conn = stomp.Connection([("ewaf-test.colo.elex.be", 61616)])
conn.set_listener('', Listener())
conn.start()
conn.connect()

conn.subscribe(destination='/queue/test', ack='auto')

conn.send('test', destination='/queue/test')

import time
time.sleep(100)