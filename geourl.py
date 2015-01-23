#!/usr/bin/env python
# coding=utf-8

"""Given a geolocation url, output other urls that show the same location.

Example usage:
geourl '30°34′15″N 104°3′38″E'
geourl 27.175015,78.042155
geourl 'https://www.google.com/maps/@45.876349,9.655686,10z'

Example output:
30.5708334,104.060556
http://wikimapia.org/#lat=30.5708334&lon=104.060556&z=12&m=b
http://hikebikemap.org/?zoom=12&lat=30.5708334&lon=104.060556&layers=B0000FFFFF
http://www.openstreetmap.org/#map=14/30.5708334/104.060556
http://labs.strava.com/heatmap/#13/104.060556/30.5708334/gray/both
[...]
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
  'http://bing.com/maps/default.aspx?cp={lat}~{lon}&lvl=14',
  'https://here.com/?map={lat},{lon},16,normal',
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
      pattern definition, a string containing the test function name
                          for each element of the pattern
    """
    self.pattern_type = pattern_type
    self.definition = definition
    self.funcs = []      # List of functions to test each element against.
    self.element = None  # The current element being tested by a function.

    # TODO: This state should be inside 'PatternMatch'
    self.state = {}  # The functions update this.
    self.confidence = 0  # higher values are more likely to be a real match
    self.latitude = None  # string of signed degrees latitude
    self.longitude = None # string of signed degrees longitude

    for item in definition.split():
      self.funcs.append(getattr(self, item))

  def __str__(self):
    return '{},{}'.format(self.latitude, self.longitude)

  def debugstr(self):
    return '{}:"{}" {},{} {}'.format(self.pattern_type, self.definition,
                                     self.latitude, self.longitude,
                                     self.confidence)

  def matches(self, elements):
    for (offset, testfunc) in enumerate(self.funcs):
      try:
        # TODO: really should 'autosave' each element into 'state'.
        self.element = elements[offset]
        testfunc()
      except (IndexError, PatternFail):
        return False
    self.finish(self.pattern_type)

    return True

  def finish(self, pattern_type):
    # Store output.
    if pattern_type == 'compass':
      self.latitude = (self.state['lat_h'] +
                       (self.state['lat_m'] / 60) +
                       (self.state['lat_s'] / 60 / 60))
      if self.state['ns'] == 's':
        self.latitude *= -1
      self.longitude = (self.state['lon_h'] +
                        (self.state['lon_m'] / 60) +
                        (self.state['lon_s'] / 60 / 60))
      if self.state['ew'] == 'w':
        self.longitude *= -1
    elif pattern_type == 'degrees':
      # First check for an (uncommon) overriding NSEW designation.
      if 'ns' in self.state and self.state['ns'] == 's':
        self.state['lat_dec'] = -1 * abs(self.state['lat_dec'])
      if 'ew' in self.state and self.state['ew'] == 'w':
        self.state['lon_dec'] = -1 * abs(self.state['lon_dec'])

      self.latitude = str(self.state['lat_dec'])
      self.longitude = str(self.state['lon_dec'])

    # Update confidence.
    if pattern_type == 'compass':
      self.confidence = 1000  # compass patterns are a fairly strict pattern
    elif pattern_type == 'degrees':
      # The more specific a number after the decimal point, the more likely
      # it is to be a coordinate degree.
      def get_length(num):
        # TODO: ICK
        num_str = str(num)
        offset = num_str.find('.')
        if offset == -1:
          return 0
        else:
          return len(num_str) - offset + 1
      self.confidence = (get_length(self.state['lat_dec']) *
                         get_length(self.state['lon_dec']))

      # TODO: words, placement of a comma between the two, 'similar length', ...

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


class ParseLocation(object):
  def __init__(self, geo_string):
    self.result = []

    self.apply_patterns(geo_string)

  def _break_apart(self, geo_string):
    elements = []
    for m in re.finditer(r'([a-z]+)|(-?[0-9]+\.?[0-9]*)', geo_string, re.I):
      element = m.group()
      if re.match(r'^([nsew]|north|south|west|east)$', element, re.I):
        elements.append(element)
      elif re.match(r'^(-?[0-9]+\.?[0-9]*)$', element):
        elements.append(decimal.Decimal(element))
    return elements

  def apply_patterns(self, geo_string):
    # For each possible pattern, try every offset of the broken apart list.
    # Sort by the confidence that it is a good match.

    elements = self._break_apart(geo_string)
    for pattern_re, pattern_type, pattern_definition in PATTERNS:
      if re.search(pattern_re, geo_string):
        for element_start in xrange(len(elements)):

          # This is a bit wonky, our pattern object stores the state.
          pattern = Pattern(pattern_type, pattern_definition)
          if pattern.matches(elements[element_start:]):
            self.result.append(pattern)

    self.result.sort(cmp=lambda x, y: cmp(y.confidence, x.confidence))

  def best_match(self):
    if not self.result:
      return None
    elif self.result[0].confidence == 0:
      return None
    else:
      return self.result[0]

  def matches(self):
    if not self.result:
      return []
    elif self.result[0].confidence == 0:
      return []
    else:
      return self.result


# Used by unit tests.
def find(geo_string):
  loc = ParseLocation(geo_string)
  if not loc.matches():
    return None
  return loc.best_match()


def print_location(loc):
  for template in OUTPUT:
    sys.stdout.write('%s\n' %
                     template.format(lat=loc.latitude, lon=loc.longitude))


# TODO: repl mode that waits for 200ms of silence before showing answers
#       (to help output with multiline pastes)


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

  exit_code = 0

  for geo_string in args.geo_string:
    loc = ParseLocation(geo_string)
    if loc.matches():
      print_location(loc.best_match())
    else:
      sys.stderr.write('No match\n')
      exit_code = 1

  sys.exit(exit_code)
