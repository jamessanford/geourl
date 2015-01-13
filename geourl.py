#!/usr/bin/env python
# coding=utf-8

"""Given a geolocation url, output other urls that show the same location.

Example inputs:
30°34′15″N 104°3′38″E
49.440603,11.004759
https://www.google.com/maps/@45.876349,9.655686,10z

Example outputs:
http://wikimapia.org/#lang=en&lat=37.491400&lon=-122.211000&z=10&m=b
http://hikebikemap.org/?zoom=12&lat=50.95942&lon=14.1342&layers=B0000FFFFF
http://labs.strava.com/heatmap/#13/-122.30854/37.50493/gray/both
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
# TODO: arg to force lon/lat instead of lat/lon pattern.
# TODO: accept some basic geocoding for place names? wikipedia/wikimapia lookup?


args = None  # ARGS.parse_args()
log = logging.getLogger('geourl')


# The input is broken down into a sequence of numbers and 'NSEW' letters.
# Look inside that sequence for the below patterns.
# The pattern definition keywords (lat_h, lat_dec) are names of functions,
# those functions store an element or fail the sequence.
# If a pattern completes successfully, finish() is called to store the result.
PATTERNS = (
  # lat/long are reversed
  ('labs.strava.com', 'degrees', 'lon_dec lat_dec'),

  ('.', 'compass', 'north_south lat_h lat_m lat_s east_west lon_h lon_m lon_s'),
  ('.', 'compass', 'lat_h lat_m lat_s north_south lon_h lon_m lon_s east_west'),

  ('.', 'compass', 'north_south lat_h lat_m_dec east_west lon_h lon_m_dec'),
  ('.', 'compass', 'lat_h lat_m_dec north_south lon_h lon_m_dec east_west'),

  ('.', 'degrees', 'lat_dec lon_dec'),

  # an uncommon notation where NSEW keyword can set negative degrees
  ('.', 'degrees', 'north_south lat_dec east_west lon_dec')
)


OUTPUT = (
  '{lat},{lon}',
  'http://wikimapia.org/#lat={lat}&lon={lon}&z=12&m=b',
  'http://hikebikemap.org/?zoom=12&lat={lat}&lon={lon}&layers=B0000FFFFF',
  'http://www.openstreetmap.org/#map=14/{lat}/{lon}',
  'http://www.panoramio.com/map/#lt={lat}&ln={lon}&z=3&k=2&a=1&tab=1&pl=all',
  'http://labs.strava.com/heatmap/#13/{lon}/{lat}/gray/both',
  'http://www.bing.com/maps/#BASE64(cp={lat}~{lon}&lvl=16&q={lat},{lon})',
  'http://here.com/{lat},{lon},15,0,0,normal.day',
  'http://tools.wmflabs.org/geohack/geohack.php?params={lat};{lon}',
  'https://www.google.com/maps/@{lat},{lon},16z'
)


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
    self.confidence = 0  # higher values are more likely to be a real match
    self.latitude = None  # string of signed degrees latitude
    self.longitude = None # string of signed degrees longitude

    for item in definition.split():
      self.funcs.append(getattr(self, item))

  def __str__(self):
    return '{},{}'.format(self.latitude, self.longitude)

  def debugstr(self):
    return '{}:"{}" {},{} {}'.format(self.pattern_type, self.definition, self.latitude, self.longitude, self.confidence)

  def matches(self, elements):
    log.debug('TESTING: %s', elements)
    for (offset, testfunc) in enumerate(self.funcs):
      try:
        # TODO: really should 'autosave' each element into 'state'.
        self.element = elements[offset]
        testfunc()
      except (IndexError, PatternFail), e:
#        log.debug('EXCEPT, %s', e)
        return False
    self.finish(self.pattern_type)

    log.debug('SEEMS OK')
    return True

  def finish(self, pattern_type):
    # store output
    if pattern_type == 'compass':
      self.latitude =  self.state['lat_h'] + (self.state['lat_m'] / 60) + (self.state['lat_s'] / 60 / 60)
      if self.state['ns'] == 's':
        self.latitude *= -1
      self.longitude = self.state['lon_h'] + (self.state['lon_m'] / 60) + (self.state['lon_s'] / 60 / 60)
      if self.state['ew'] == 'w':
        self.longitude *= -1
    elif pattern_type == 'degrees':
      # First check for an overriding NSEW designation.
      if 'ns' in self.state and self.state['ns'] == 's':
        self.state['lat_dec'] = -1 * abs(self.state['lat_dec'])
      if 'ew' in self.state and self.state['ew'] == 'w':
        self.state['lon_dec'] = -1 * abs(self.state['lon_dec'])

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

  # TODO: use a decorator for the 'state' storage?  or not?
  def north_south(self):
    self.assertStringElement()
    element = self.element.lower()
    if element in ['n', 's', 'north', 'south']:
      self.state['ns'] = element[0]
    else:
      raise PatternFail('Not North/South')

  def east_west(self):
    self.assertStringElement()
    element = self.element.lower()
    if element in ['e', 'w', 'east', 'west']:
      self.state['ew'] = element[0]
    else:
      raise PatternFail('Not East/West')

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

  def lat_m_dec(self):
    self.assertDecimalElement()
    if self.element < 0 or self.element > 60:
      raise PatternFail('out of range')
    minutes = self.element.to_integral(rounding=decimal.ROUND_DOWN)
    self.state['lat_m'] = minutes
    self.state['lat_s'] = (self.element - minutes) * 60

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

  def lon_m_dec(self):
    self.assertDecimalElement()
    if self.element < 0 or self.element > 60:
      raise PatternFail('out of range')
    minutes = self.element.to_integral(rounding=decimal.ROUND_DOWN)
    self.state['lon_m'] = minutes
    self.state['lon_s'] = (self.element - minutes) * 60

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
      output.append(element)
    elif re.match('^(-?[0-9]+\.?[0-9]*)$', element):
      output.append(decimal.Decimal(element))

  log.debug('LAME: %s', output)
  return output


def find(input):
  """Input: unicode string
     Output: [lat, lon] floats
  """
  lat = None
  lon = None

  elements = break_apart(input)

  # For each possible pattern, try a search starting at each element from the broken apart list.
  # Sort by the confidence that it is a good match.

  maybe = []
  for pattern_re, pattern_type, pattern_definition in PATTERNS:
    if re.search(pattern_re, input):
      for element_start in xrange(len(elements)):
        # TODO FIXME: the 'match' needs to return an actual state...fuck.
        # FIXME: The Pattern thing should not mutate...should have a Match object
        pattern = Pattern(pattern_type, pattern_definition)
        match = pattern.matches(elements[element_start:])
        if match:
          maybe.append(pattern)

  maybe.sort(cmp=lambda x, y: cmp(y.confidence, x.confidence))
  for m in maybe:
    log.debug('MAYBE: {}'.format(m.debugstr()))
  if maybe and maybe[0].confidence != 0:
    log.info('GOOD: {}'.format(maybe[0].debugstr()))
    return maybe[0]

  return None


def output(foo):
  for template in OUTPUT:
    yield template.format(lat=foo.latitude, lon=foo.longitude)


# TODO: output display class with templates at the top
# repl mode that waits for 200ms of silence before showing answers
# (to help output with multiline pastes)


if __name__ == '__main__':
  format = '%(filename)s:%(lineno)d %(levelname)s: %(message)s'
  logging.basicConfig(format=format, level=logging.ERROR)

  if len(sys.argv) == 1:
    # Force full help output when run without args.
    ARGS.print_help()
    ARGS.exit(2, '\nerror: no geo locations given\n')
  args = ARGS.parse_args()

  # NOTE: precision is open to discussion.
  decimal.getcontext().prec = 9

  for geo_string in args.geo_string:
    foo = find(geo_string)
    for url in output(foo):
      sys.stdout.write('%s\n' % url)

  sys.exit(0)
