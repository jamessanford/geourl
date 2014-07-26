#!/usr/bin/env python
# coding=utf-8

"""Translate geo coordinates and urls into other url destinations.

Example inputs:
30°34′15″N 104°3′38″E
49.440603,11.004759
https://www.google.com/maps/place/Brembana+Service+S.R.L./@45.876349,9.655686,487m

Example outputs:
http://wikimapia.org/#lang=en&lat=37.491400&lon=-122.211000&z=10&m=b
http://hikebikemap.de/?zoom=12&lat=50.95942&lon=14.1342&layers=B0000FFFFF
http://labs.strava.com/heatmap/#15/-122.30854/37.50493/gray/both
"""

import decimal
import re
import sys
import argparse
import logging

ARGS = argparse.ArgumentParser(description='Translate geo location urls '
                                           'into other destination urls.')
ARGS.add_argument('geo_string', nargs='+', metavar='<geo url>',
                  help='geo location url or string')

args = None  # ARGS.parse_args()
log = logging.getLogger('geourl')


class PatternFail(Exception):
  pass


class Pattern(object):
  def __init__(self, definition):
    self.funcs = []  # List of functions to test each element against
    self.state = {}  # The functions update this.
    self.debugstr = definition

    for item in definition.split():
      self.funcs.append(getattr(self, item))

  def matches(self, elements):
    sys.stdout.write('TESTING: %s\n' % elements)
    for (offset, testfunc) in enumerate(self.funcs):
      try:
        self.element = elements[offset]
        testfunc()
      except (IndexError, PatternFail), e:
#        sys.stdout.write('EXCEPT: %s\n' % e)
        return False
    sys.stdout.write('SEEMS OK\n')
    return True

  def latlng(self):
    # Turn self.state into signed decimal...?  OK.
    pass

  def assertStringElement(self):
    if not isinstance(self.element, basestring):
      raise PatternFail('Not string')

  def assertDecimalElement(self):
    if not isinstance(self.element, decimal.Decimal):
      raise PatternFail('Not decimal')

  def NS(self):
    self.assertStringElement()
    element = self.element.lower()
    if element in ['n', 's']:
      self.state['ns'] = element
    else:
      raise PatternFail('Not N/S')

  def EW(self):
    self.assertStringElement()
    element = self.element.lower()
    if element in ['e', 'w']:
      self.state['ew'] = element
    else:
      raise PatternFail('Not N/S')

  def lat_h(self):
    self.assertDecimalElement()
    if self.element < 0 or self.element > 90:
      raise PatternFail('out of range')
    # TODO: MUST BE INTEGER

  def lat_m(self):
    if self.element < 0 or self.element > 60:
      raise PatternFail('out of range')
    # TODO: MUST BE INTEGER

  def lat_s(self):
    if self.element < 0 or self.element > 60:
      raise PatternFail('out of range')

  def lon_h(self):
    if self.element < 0 or self.element > 180:
      raise PatternFail('out of range')
    # TODO: MUST BE INTEGER

  def lon_m(self):
    if self.element < 0 or self.element > 60:
      raise PatternFail('out of range')
    # TODO: MUST BE INTEGER

  def lon_s(self):
    if self.element < 0 or self.element > 60:
      raise PatternFail('out of range')

  def lat_dec(self):
    if self.element < -90 or self.element > 90:
      raise PatternFail('out of range')
    # TODO: LIKELIHOOD

  def lon_dec(self):
    if self.element < -180 or self.element > 180:
      raise PatternFail('out of range')
    # TODO: LIKELIHOOD


# The input is broken down into a sequence of numbers and 'NSEW' letters.
# We then look inside that sequence for a pattern.
# Each item in each pattern below is the name of a test function.
PATTERNS = (
  Pattern('NS lat_h lat_m lat_s EW lon_h lon_m lon_s'),
  Pattern('lat_h lat_m lat_s NS lon_h lon_m lon_s EW'),
  Pattern('lat_dec lon_dec')
)


def break_apart(input):
  output = []
#  for m in re.finditer('((?=(^|[^a-z]))[nsew](?=($|[^a-z])))|(-?[0-9]+\.?[0-9]*)', input,
# NOTE: FIXME: to get standalone nsew?  though it really doesnt matter.
#   (or actual words north/south/west/east) -> 'west' breaks it. (WE)
  for m in re.finditer('([nsew])|(-?[0-9]+\.?[0-9]*)', input,
                       re.I):
    element = m.group()
    if re.match('[nsew]', element, re.I) is None:
      element = decimal.Decimal(element)
    output.append(element)
  sys.stdout.write('LAME: %s\n' % output)
  return output


def find(input):
  """Input: unicode string
     Output: [lat, lon] floats
  """
  lat = None
  lon = None

  elements = break_apart(input)

  # Try signed degrees
  # Try compass

#NOTE if these are strings, do getattr(pattern_funcs, the_str)(element)
# also save 'likelihood' and 'state';
#   offer a function to get signed decimal from state.
#   likelihood for compass is 100; likelihood for signed dec is # digits after '.'  (lowest # for the pair?  meh?  it should work though.)

  # Look for:
  # NS lat_h lat_m lat_s EW lon_h lon_m lon_s
  # lat_h lat_m lat_s NS lon_h lon_m lon_s EW
  # ^ these have a 'high likelihood'

  # lat_dec lon_dec
  #   ^ mark as unlikely if # digits after '.' gets smaller
  #   ^ mark 'likelihood' the longer the digits after '.' are...
  #   ^ then find the pair with the highest 'likelihood'


  maybe = []
  for pattern in PATTERNS:
    for element_start in xrange(len(elements)):
      match = pattern.matches(elements[element_start:])
      if match:
        maybe.append(pattern.debugstr)

  sys.stdout.write('MAYBE: %s\n' % maybe)

# Not sure, I kinda want to just find "all" numbers and NSEW, and then
# figure out what to do based on that.  but it will find 'stray' numbers,
# so we need to find 'which pair' makes sense.

# signed degrees: eliminate 0-180 0-90 constraints
# signed degrees: eliminate 'shorter after the decimal' before/after pairs with longer

# compass:
# 'N' 'S' or ''
# 0-180, 0-60, 0-60
# if '': 'N' or 'S'
# <followed by lon>

  if lat is None or lon is None:
    return None
  return [lat, lon]


if __name__ == '__main__':
  format = '%(filename)s:%(lineno)d %(levelname)s: %(message)s'
  logging.basicConfig(format=format, level=logging.ERROR)

  if len(sys.argv) == 1:
    # Force full help output when run without args.
    ARGS.print_help()
    ARGS.exit(2, '\nerror: no geo locations given\n')
  args = ARGS.parse_args()

  for geo_string in args.geo_string:
    location = GeoLocation(geo_string)
    sys.stdout.write('%s\n', location)

  sys.exit(0)
