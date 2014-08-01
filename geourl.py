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
  def __init__(self, pattern_type, definition):
    """A pattern object that can match and convert.

    pattern_type:
      'compass' or 'degrees': type of input pattern
    definition:
      pattern definition, a string containing a the test function name
                          for each element of the pattern
    """

    self.pattern_type = pattern_type
    self.definition = definition
    self.funcs = []  # List of functions to test each element against
    self.state = {}  # The functions update this.
    self.debugstr = definition
    self.confidence = 0  # higher values are more likely to be a real match
    self.latitude = None  # string of signed degrees latitude
    self.longitude = None # string of signed degrees longitude

    for item in definition.split():
      self.funcs.append(getattr(self, item))

  def debug(self):
    return '{}:"{}" {},{} {}'.format(self.pattern_type, self.definition, self.latitude, self.longitude, self.confidence)

  def matches(self, elements):
    sys.stdout.write('TESTING: %s\n' % elements)
    for (offset, testfunc) in enumerate(self.funcs):
      try:
        # TODO: really should 'autosave' each element into 'state'.
        self.element = elements[offset]
        testfunc()
      except (IndexError, PatternFail), e:
#        sys.stdout.write('EXCEPT: %s\n' % e)
        return False
    self.finish(self.pattern_type)

    sys.stdout.write('SEEMS OK\n')
    return True

  def finish(self, pattern_type):
    # store output
    if pattern_type == 'compass':
      self.latitude =  self.state['lat_h'] + (self.state['lat_m'] / 60) + (self.state['lat_s'] / 60 / 60)
      self.longitude = self.state['lon_h'] + (self.state['lon_m'] / 60) + (self.state['lon_s'] / 60 / 60)
    elif pattern_type == 'degrees':
      self.latitude = str(self.state['lat_dec'])
      self.longitude = str(self.state['lon_dec'])

    # update confidence
    if pattern_type == 'compass':
      self.confidence = 1000  # compass patterns are a fairly strict pattern
    elif pattern_type == 'degrees':
      # The more specific a number after the decimal point, the more likely
      # it is to be a coordinate degree.
      def get_length(num):
        # ICK FIXME
        num_str = str(num)
        offset = num_str.find('.')
        if offset == -1:
          return 0
        else:
          return len(num_str) - offset + 1
      self.confidence = (get_length(self.state['lat_dec']) *
                         get_length(self.state['lon_dec']))

      # TODO: words, placement of a comma between the two, 'similar length',


  def assertStringElement(self):
    if not isinstance(self.element, basestring):
      raise PatternFail('Not string')

  def assertDecimalElement(self):
    if not isinstance(self.element, decimal.Decimal):
      raise PatternFail('Not decimal')

  def assertDecimalInteger(self):
    self.assertDecimalElement()
    # We only care if there is a decimal point '.' in the text,
    # regardless of its equivalency when converted to an integer.
    if '.' in str(self.element):
      raise PatternFail('Not integer')

  def NS(self):
    self.assertStringElement()
    element = self.element.lower()
    if element in ['n', 's', 'north', 'south']:
      self.state['ns'] = element[0]
    else:
      raise PatternFail('Not N/S')

  def EW(self):
    self.assertStringElement()
    element = self.element.lower()
    if element in ['e', 'w', 'east', 'west']:
      self.state['ew'] = element[0]
    else:
      raise PatternFail('Not N/S')

  def lat_h(self):
    self.assertDecimalInteger()
    if self.element < 0 or self.element > 90:
      raise PatternFail('out of range')
    self.state['lat_h'] = self.element

  def lat_m(self):
    self.assertDecimalInteger()
    if self.element < 0 or self.element > 60:
      raise PatternFail('out of range')
    self.state['lat_m'] = self.element

  def lat_s(self):
    self.assertDecimalElement()
    if self.element < 0 or self.element > 60:
      raise PatternFail('out of range')
    self.state['lat_s'] = self.element

  def lon_h(self):
    self.assertDecimalInteger()
    if self.element < 0 or self.element > 180:
      raise PatternFail('out of range')
    self.state['lon_h'] = self.element

  def lon_m(self):
    self.assertDecimalInteger()
    if self.element < 0 or self.element > 60:
      raise PatternFail('out of range')
    self.state['lon_m'] = self.element

  def lon_s(self):
    self.assertDecimalElement()
    if self.element < 0 or self.element > 60:
      raise PatternFail('out of range')
    self.state['lon_s'] = self.element

  def lat_dec(self):
    self.assertDecimalElement()
    if self.element < -90 or self.element > 90:
      raise PatternFail('out of range')
    self.state['lat_dec'] = self.element

  def lon_dec(self):
    self.assertDecimalElement()
    if self.element < -180 or self.element > 180:
      raise PatternFail('out of range')
    self.state['lon_dec'] = self.element


# The input is broken down into a sequence of numbers and 'NSEW' letters.
# We then look inside that sequence for a pattern.
# Each item in each pattern below is the name of a test function.
PATTERNS = (
  ('labs.strava.com', 'degrees', 'lon_dec lat_dec'),
  ('.', 'compass', 'NS lat_h lat_m lat_s EW lon_h lon_m lon_s'),
  ('.', 'compass', 'lat_h lat_m lat_s NS lon_h lon_m lon_s EW'),
  ('.', 'degrees', 'lat_dec lon_dec')
)


def break_apart(input):
  output = []
# NOTE: FIXME: to get standalone nsew?  though it really doesnt matter.
#   (or actual words north/south/west/east) -> 'west' breaks it. (WE)
#  for m in re.finditer('([nsew])|(-?[0-9]+\.?[0-9]*)', input,
#                       re.I):
# TODO: should probably split by actual words and numbers, so that
# the numbers actually have to be 'in sequence'.  could also remove
# words like 'and', 'by', 'at', 'hour[s]/minute[s]/second[s]'
# 'latitude', 'longitude'
# (also allow 'anything' between two compass locations?)

# Uhh, yikes, this ignores anything except elements we know about.
  for m in re.finditer('([a-z]+)|(-?[0-9]+\.?[0-9]*)', input, re.I):
    element = m.group()
    if re.match('^([nsew]|north|south|west|east)$', element, re.I):
      pass
    elif re.match('^(-?[0-9]+\.?[0-9]*)$', element):
      element = decimal.Decimal(element)
    else:
      continue
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
  for pattern_re, pattern_type, pattern_definition in PATTERNS:
    if re.search(pattern_re, input):
      for element_start in xrange(len(elements)):
        # TODO FIXME: the 'match' needs to return an actual state...fuck.
        # This is SHIT.  The Pattern thing should not mutate...
        #   it should be only for 'testing'...and returning a result object.
        pattern = Pattern(pattern_type, pattern_definition)  # FIXME TODO FUCKUP ICK
        match = pattern.matches(elements[element_start:])
        if match:
          maybe.append(pattern)

  maybe.sort(cmp=lambda x, y: cmp(y.confidence, x.confidence))
  for m in maybe:
    sys.stdout.write('MAYBE: {}\n'.format(m.debug()))
  if maybe and maybe[0].confidence != 0:
    sys.stdout.write('GOOD: {}\n'.format(maybe[0].debug()))
    return maybe[0]

  return None

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
