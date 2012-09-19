#!/usr/bin/env python
""" Abstraction for urllib2 to make it act as requests
    ( we couldn't use requests as it didn't support python 2.5 )
"""
import urllib2

def get(url, headers={}):
  opener = urllib2.build_opener(urllib2.HTTPHandler)
  request = urllib2.Request(url)
  for k,v in headers.iteritems():
    request.add_header(k,v)
  resp = opener.open(request)
  return Response(resp.getcode(), resp.read())

def put(url, headers={}, data=''):
  opener = urllib2.build_opener(urllib2.HTTPHandler)
  request = urllib2.Request(url, data=data)
  request.get_method = lambda: 'PUT'
  for k,v in headers.iteritems():
    request.add_header(k,v)
  resp = opener.open(request)
  return Response(resp.getcode(), resp.read())

class Response:

  def __init__(self, status_code, text):
    self.status_code = status_code
    self.text = text
  