#!/usr/bin/env python

from base64 import b64decode
from jinja2 import Template
from xml.sax import handler, parseString

class Lot:

    def __init__(self, name, item, wafersInLot, organization, probelocation, subcontractor, wafers=[], config={}):
        self.name = name
        self.item = item
        self.wafersInLot = wafersInLot
        self.organization = organization
        self.probelocation = probelocation
        self.subcontractor = subcontractor
        self.wafers = wafers
        self.config = config

    def __repr__(self):
        return "Lot {name: %s, item: %s, wafersInLot: %s, organization: %s, probelocation: %s, subcontractor: %s, wafers: %s, config: %s}" % (self.name, self.item, self.wafersInLot, self.organization, self.probelocation, self.subcontractor, self.wafers, self.config)

class Wafer:

    def __init__(self, number, passdies, wafermaps = [], config={}):
        self.number = number
        self.passdies = passdies
        self.wafermaps = wafermaps
        self.config = config

    def __repr__(self):
        return "Wafer {number: %s, passdies: %s, wafermaps: %s, config: %s}" % (self.number, self.passdies, self.wafermaps, self.config)

class Wafermap:

    def __init__(self, name, formats={}):
        self.name = name
        self.formats = formats

    def __repr__(self):
        return "Wafermap {name: %s, formats: %s}" % (self.name, self.formats)

class Format:

    def __init__(self, encoding, wafermap):
        self.encoding = encoding
        self.wafermap = wafermap

    def decode(self):
        if self.encoding == 'base64':
          return b64decode(self.wafermap)
        else:
          raise "Invalid type"

    def __repr__(self):
        return "Format {encoding: %s, wafermap: %s}" % (self.encoding, self.wafermap)

class LotHandler(handler.ContentHandler):

    def __init__(self):
        self.inLot = False
        self.inConfig = False
        self.inWafer = False
        self.inWaferProperties = False
        self.inWafermaps = False
        self.inWafermap = False
        self.inFormats = False
        self.inFormat = False
        self.lotconfig = {}

    def startElement(self, name, attrs):
        if name == 'lot':
            self.inLot = True
            self.la = dict(attrs)
            self.wafers = []
        elif name == 'configuration-parameters':
            self.inConfig = True
            self.lotconfig = {}
        elif name == 'parameter' and self.inConfig == True:
            self.lotconfig[attrs.get('key')] = attrs.get('value')
        elif name == 'wafer':
            self.inWafer = True
            self.wa = dict(attrs)
            self.wafermaps = []
            self.waferProperties = {}
        elif name == 'wafer-properties':
            self.inWaferProperties = True
        elif self.inWaferProperties and name == 'parameter':
            self.waferProperties[attrs.get('key')] = attrs.get('value')
        elif name == 'wafermaps':
            self.inWafermaps = True
            self.wafermaps = []
        elif name == 'wafermap':
            self.inWafermap = True
            self.wafermapName = attrs.get('name')
        elif name == 'formats':
            self.inFormats = True
            self.formats = {}
        elif name == 'format':
            self.inFormat = True
            self.formatName = attrs.get('name')
            self.formatEncoding = attrs.get('encoding')
            self.formatContent = ""

    def endElement(self, name):
        if name == 'lot':
            self.inLot = False
            self.lot = Lot(self.la.get("name"), self.la.get('item'), self.la.get('wafersInLot'), self.la.get('organization'), self.la.get('probelocation'), self.la.get('subcontractor'), self.wafers, self.lotconfig)
        elif name == 'configuration-parameters':
            self.inConfig = False
        elif name == 'wafer':
            self.inWafer = False
            self.wafers.append(Wafer(self.wa.get("number"), self.wa.get("passdies"), self.wafermaps, self.waferProperties))
        elif name == 'wafer-properties':
            self.inWaferProperties = False
        elif name == 'wafermaps':
            self.inWafermaps = False
        elif name == 'wafermap':
            self.inWafermap = False
            self.wafermaps.append(Wafermap(self.wafermapName, self.formats))
        elif name == 'formats':
            self.inFormats = False
        elif name == 'format':
            self.formats[self.formatName] = Format(self.formatEncoding, self.formatContent)
            self.inFormat = False
            
    def characters(self, content):
        if self.inFormat == True:
            self.formatContent = self.formatContent + content.strip()


def decode(body):
  """Parse an xml body to objects

     This function will convert an xml message according to the lot.xsd schema to a lot object.

     As an xml message can be big,  we load it from file.
     >>> msg = open('example.xml').read()

     Now call parse with the xml message,  this should return a parsed lot object.
     >>> l = decode(msg)
     >>> l.name
     u'M31265'
     >>> l.wafersInLot
     u'4'
     >>> l.config['config']
     u'test'
     >>> l.wafers[0].config
     {u'buildAt': u'20120302T11:53', u'origin': u'MapMerge', u'site': u'erfurt', u'processStep': u'pactech'}
     >>> l.wafers[0].wafermaps[0].formats['TH01'].decode()[:4]
     'WMAP'
  """
  handler = LotHandler()
  parseString(body, handler)
  return handler.lot

def encode(lot):
  """Encode a lot to xml.

     First create the lot you want to encode
     >>> w1 = Wafer(1, 100, [Wafermap("blaat", {"TH01": Format("base64", "aGVsbG8gd29ybGQ=")})])
     >>> w2 = Wafer(2, 200, [Wafermap("blubber", {"TH01": Format("base64", "a3J1c3R5")})])
     >>> l = Lot("A12345", "201210600", 2, "IEPER", "IEPER", "MLX_BOGUS", [w1, w2], {'val1': 'blub'})
  
     Now encode the lot to xml    
     >>> s = encode(l)

     Read the expected format
     >>> with open('expected_lot.xml', 'r') as f:
     ...   expected = f.read()
     ...   s == expected
     True
  """
  t = open('lot.xml').read()
  template = Template(t)
  return template.render(lot=lot)

def eachWafer(l, f):
  """Iterate each wafer in a lot and call f on the wafer

     F is a function that takes two parameters ( Lot, Wafer )

     Example:
     
     A lot with two wafers
     >>> l = Lot('A12345', '201210600', 2, 'IEPER', 'IEPER', 'MLX_BOGUS', [Wafer(1, 100), Wafer(2, 200)])

     When we call eachWafer with the lot the function should be executed on both wafers.
     Create a real function as lambda is limited.
     >>> def printNumber(l, w): print w.number
     >>> eachWafer(l, printNumber)
     1
     2
  """
  for w in l.wafers:
      f(l, w)

def eachWafermap(l, f):
  """Iterate each wafermap in a lot and call f on the wafermap

     F is a function that takes two parameters ( Wafer, Wafermap )

     Example:
     
     A lot with two wafers

     >>> w1 = Wafer(1, 100, [Wafermap('test'), Wafermap('test2')])
     >>> w2 = Wafer(2, 200, [Wafermap('blubber')])
     >>> l = Lot('A12345', '201210600', 2, 'IEPER', 'IEPER', 'MLX_BOGUS', [w1, w2])
     
     When we call eachWafermap with the lot the function should be executed on every wafermap.
     >>> def printWafermapName(_, wm): print wm.name
     >>> eachWafermap(l, printWafermapName)
     test
     test2
     blubber
  """
  def _iterateWafermap(l, w): 
    for wm in w.wafermaps:
      f(w, wm)
  eachWafer(l, _iterateWafermap)

def _test():
  import doctest
  doctest.testmod()

if __name__ == '__main__':
  _test()
