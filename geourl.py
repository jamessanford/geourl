#!/usr/bin/env python3
# coding=utf-8

"""Given a geolocation url, output other urls that show the same location.

Example usage:
geourl '30°34′15″N 104°3′38″E'
geourl 27.175015,78.042155
geourl 'https://www.google.com/maps/@30.57,104.061,16z'

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
import urllib.parse
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple, Union

# The input is broken down into a sequence of numbers and 'NSEW' letters.
# Look inside that sequence for the below patterns.
# The pattern definition keywords (lat_h, lat_dec) are names of validator methods,
# those methods validate an element or fail the sequence.
#
# If a pattern completes successfully, a coordinate is built from the extracted values.
PATTERNS = (
  # lat/long are reversed
  ('labs.strava.com', 'degrees', 'lon_dec lat_dec'),
  ('strava.com', 'degrees', 'lon_dec lat_dec'),

  ('.', 'compass', 'north_south lat_h lat_m lat_s east_west lon_h lon_m lon_s'),
  ('.', 'compass', 'lat_h lat_m lat_s north_south lon_h lon_m lon_s east_west'),

  ('.', 'compass', 'north_south lat_h lat_m_dec east_west lon_h lon_m_dec'),
  ('.', 'compass', 'lat_h lat_m_dec north_south lon_h lon_m_dec east_west'),

  ('.', 'degrees', 'lat_dec lon_dec'),

  # notation where NSEW keyword can set negative degrees
  ('.', 'degrees', 'north_south lat_dec east_west lon_dec'),
  ('.', 'degrees', 'lat_dec north_south lon_dec east_west'),
)


OUTPUT = (
  '{lat},{lon}',
  'https://wikimapia.org/#lat={lat}&lon={lon}&z=12&m=b',
  'https://hikebikemap.org/?zoom=12&lat={lat}&lon={lon}&layers=B0000FFFFF',
  'https://www.openstreetmap.org/#map=14/{lat}/{lon}',
  'https://www.panoramio.com/map/#lt={lat}&ln={lon}&z=3&k=2&a=1&tab=1&pl=all',
  'https://labs.strava.com/heatmap/#13/{lon}/{lat}/gray/both',
  'https://bing.com/maps/default.aspx?cp={lat}~{lon}&lvl=14',
  'https://here.com/?map={lat},{lon},16,normal',
  'https://www.google.com/maps/@{lat},{lon},16z',
  'https://wiki-map.com/map/?locale=en&lat={lat}&lng={lon}',
  'https://geohack.toolforge.org/geohack.php?params={lat};{lon}',
  'https://ngmdb.usgs.gov/topoview/viewer/#15/{lat}/{lon}',
  'https://www.flickr.com/search/?lat={lat}&lon={lon}&radius=0.50&has_geo=1&view_all=1&sort=interestingness-desc',
  'https://explore.osmaps.com/?lat={lat}&lon={lon}&zoom=13.0000&style=Standard&type=2d',
  'https://wikimap.wiki/?base=map&lat={lat}&lon={lon}&showAll=true&wiki=enwiki&zoom=15',
  'https://openinframap.org/#9/{lat}/{lon}',
  'https://www.openrailwaymap.org/?style=standard&lat={lat}&lon={lon}&zoom=13'
)


REGEX_KNOWN_WORDS = r'^([nsew]|north|south|west|east|nord|sur|norte|sul|est|ouest|este|oeste)$'
WORDS_N_NORTH_ELSE_SOUTH = ['n', 's', 'north', 'south', 'nord', 'sur', 'norte', 'sul']
WORDS_E_EAST_ELSE_WEST = ['e', 'w', 'east', 'west', 'est', 'ouest', 'este', 'oeste']


PatternState = Dict[str, Any]


class PatternFail(Exception):
  pass


@dataclass
class Coordinate:
  """Represents a geographic coordinate with confidence score."""
  latitude: str
  longitude: str
  confidence: int = 0
  pattern_type: str = ''
  pattern_definition: str = ''

  def __str__(self) -> str:
    return f'{self.latitude},{self.longitude}'

  def __repr__(self) -> str:
    return f'{self.pattern_type}:"{self.pattern_definition}" {self.latitude},{self.longitude} {self.confidence}'


class PatternDefinition:
  """Immutable pattern configuration."""

  def __init__(self, url_regex: str, pattern_type: str, definition: str):
    self.url_regex = url_regex
    self.pattern_type = pattern_type
    self.definition = definition
    self.validators = definition.split()

  def matches_url(self, url: str) -> bool:
    return bool(re.search(self.url_regex, url))


class PatternMatcher:
  """Stateless pattern matching against elements."""

  def __init__(self, pattern_def: PatternDefinition):
    self.pattern_def = pattern_def

  def match(self, elements: List[Union[str, decimal.Decimal]], start_offset: int = 0) -> Optional[PatternState]:
    """Try to match pattern against elements starting at offset.

    Returns extracted values dict if successful, None otherwise.
    """
    state: PatternState = {}

    for i, validator_name in enumerate(self.pattern_def.validators):
      try:
        element_index = start_offset + i
        if element_index >= len(elements):
          return None

        element = elements[element_index]
        validator = getattr(self, validator_name)
        validator(element, state)
      except PatternFail:
        return None

    return state

  # Validator methods
  def _assert_string(self, element: Any) -> str:
    if not isinstance(element, str):
      raise PatternFail('Not string')
    return element

  def _assert_decimal(self, element: Any) -> decimal.Decimal:
    if not isinstance(element, decimal.Decimal):
      raise PatternFail('Not decimal')
    return element

  def _assert_integer(self, element: Any) -> decimal.Decimal:
    dec = self._assert_decimal(element)
    # We only care if there is a decimal point '.' in the text
    if '.' in str(element):
      raise PatternFail('Not integer')
    return dec

  def north_south(self, element: Any, state: PatternState) -> None:
    s = self._assert_string(element).lower()
    if s in WORDS_N_NORTH_ELSE_SOUTH:
      state['ns'] = 'n' if s[0] in 'n' else 's'
    else:
      raise PatternFail('Not North/South')

  def east_west(self, element: Any, state: PatternState) -> None:
    s = self._assert_string(element).lower()
    if s in WORDS_E_EAST_ELSE_WEST:
      state['ew'] = 'e' if s[0] in 'e' else 'w'
    else:
      raise PatternFail('Not East/West')

  def lat_h(self, element: Any, state: PatternState) -> None:
    dec = self._assert_integer(element)
    if dec < 0 or dec >= 90:
      raise PatternFail('out of range')
    state['lat_h'] = dec

  def lat_m(self, element: Any, state: PatternState) -> None:
    dec = self._assert_integer(element)
    if dec < 0 or dec >= 60:
      raise PatternFail('out of range')
    state['lat_m'] = dec

  def lat_s(self, element: Any, state: PatternState) -> None:
    dec = self._assert_decimal(element)
    if dec < 0 or dec >= 60:
      raise PatternFail('out of range')
    state['lat_s'] = dec

  def lat_m_dec(self, element: Any, state: PatternState) -> None:
    dec = self._assert_decimal(element)
    if dec < 0 or dec >= 60:
      raise PatternFail('out of range')
    minutes = dec.to_integral(rounding=decimal.ROUND_DOWN)
    state['lat_m'] = minutes
    state['lat_s'] = (dec - minutes) * 60

  def lon_h(self, element: Any, state: PatternState) -> None:
    dec = self._assert_integer(element)
    if dec < 0 or dec >= 180:
      raise PatternFail('out of range')
    state['lon_h'] = dec

  def lon_m(self, element: Any, state: PatternState) -> None:
    dec = self._assert_integer(element)
    if dec < 0 or dec >= 60:
      raise PatternFail('out of range')
    state['lon_m'] = dec

  def lon_s(self, element: Any, state: PatternState) -> None:
    dec = self._assert_decimal(element)
    if dec < 0 or dec >= 60:
      raise PatternFail('out of range')
    state['lon_s'] = dec

  def lon_m_dec(self, element: Any, state: PatternState) -> None:
    dec = self._assert_decimal(element)
    if dec < 0 or dec >= 60:
      raise PatternFail('out of range')
    minutes = dec.to_integral(rounding=decimal.ROUND_DOWN)
    state['lon_m'] = minutes
    state['lon_s'] = (dec - minutes) * 60

  def lat_dec(self, element: Any, state: PatternState) -> None:
    dec = self._assert_decimal(element)
    if dec < -90 or dec >= 90:
      raise PatternFail('out of range')
    state['lat_dec'] = dec

  def lon_dec(self, element: Any, state: PatternState) -> None:
    dec = self._assert_decimal(element)
    if dec <= -180 or dec >= 180:
      raise PatternFail('out of range')
    state['lon_dec'] = dec


class CoordinateBuilder:
  """Builds Coordinate objects from matched pattern values."""

  @staticmethod
  def build(pattern_def: PatternDefinition, values: PatternState) -> Coordinate:
    """Convert extracted values to a Coordinate based on pattern type."""

    if pattern_def.pattern_type == 'compass':
      latitude = (values['lat_h'] +
                  (values['lat_m'] / 60) +
                  (values['lat_s'] / 60 / 60))
      if values['ns'] == 's':
        latitude *= -1
      longitude = (values['lon_h'] +
                   (values['lon_m'] / 60) +
                   (values['lon_s'] / 60 / 60))
      if values['ew'] == 'w':
        longitude *= -1

      confidence = 1000  # compass patterns are fairly strict

    elif pattern_def.pattern_type == 'degrees':
      # Check for overriding NSEW designation
      lat_dec = values['lat_dec']
      lon_dec = values['lon_dec']

      if 'ns' in values and values['ns'] == 's':
        lat_dec = -1 * abs(lat_dec)
      if 'ew' in values and values['ew'] == 'w':
        lon_dec = -1 * abs(lon_dec)

      latitude = str(lat_dec)
      longitude = str(lon_dec)

      # Calculate confidence based on decimal precision
      confidence = (CoordinateBuilder._get_decimal_places(lat_dec) *
                    CoordinateBuilder._get_decimal_places(lon_dec))
    else:
      raise ValueError(f"Unknown pattern type: {pattern_def.pattern_type}")

    return Coordinate(
      latitude=str(latitude),
      longitude=str(longitude),
      confidence=confidence,
      pattern_type=pattern_def.pattern_type,
      pattern_definition=pattern_def.definition
    )

  @staticmethod
  def _get_decimal_places(num: decimal.Decimal) -> int:
    """Return number of decimal places in a Decimal."""
    sign, digits, exponent = num.as_tuple()
    if isinstance(exponent, str):
        return 0
    return max(0, -exponent)


class ParseLocation:
  def __init__(self, geo_string: str):
    self.result: List[Coordinate] = []
    self.apply_patterns(urllib.parse.unquote(geo_string))

  def _break_apart(self, geo_string: str) -> List[Union[str, decimal.Decimal]]:
    elements: List[Union[str, decimal.Decimal]] = []
    for m in re.finditer(r'([a-z]+)|(-?[0-9]+\.?[0-9]*)', geo_string, re.I):
      element = m.group()
      if re.match(REGEX_KNOWN_WORDS, element, re.I):
        elements.append(element)
      elif re.match(r'^(-?[0-9]+\.?[0-9]*)$', element):
        elements.append(decimal.Decimal(element))
    return elements

  def apply_patterns(self, geo_string: str) -> None:
    """Try all patterns at all offsets, sort by confidence."""

    elements = self._break_apart(geo_string)

    for url_regex, pattern_type, definition in PATTERNS:
      pattern_def = PatternDefinition(url_regex, pattern_type, definition)

      if pattern_def.matches_url(geo_string):
        matcher = PatternMatcher(pattern_def)

        for start_offset in range(len(elements)):
          values = matcher.match(elements, start_offset)
          if values:
            coord = CoordinateBuilder.build(pattern_def, values)
            self.result.append(coord)

    self.result.sort(key=lambda x: x.confidence, reverse=True)

  def best_match(self) -> Optional[Coordinate]:
    if not self.result:
      return None
    elif self.result[0].confidence == 0:
      return None
    else:
      return self.result[0]

  def matches(self) -> List[Coordinate]:
    if not self.result:
      return []
    elif self.result[0].confidence == 0:
      return []
    else:
      return self.result


# Used by unit tests.
def find(geo_string: str) -> Optional[Coordinate]:
  loc = ParseLocation(geo_string)
  if not loc.matches():
    return None
  return loc.best_match()


def print_location(loc: Coordinate) -> None:
  for template in OUTPUT:
    print(template.format(lat=loc.latitude, lon=loc.longitude))


# TODO: repl mode that waits for 200ms of silence before showing answers
#       (to help output with multiline pastes)


def main(args: List[str]) -> int:
  format = '%(filename)s:%(lineno)d %(levelname)s: %(message)s'
  logging.basicConfig(format=format, level=logging.ERROR)

  ARGS = argparse.ArgumentParser(description='Translate geo location urls '
                                             'into other destination urls.')
  ARGS.add_argument('geo_string', nargs='+', metavar='<geo url>',
                    help='geo location url or string')
  ARGS.add_argument('-a', '--all', dest='all', action='store_true',
                    help='show all matches (where confidence > 0)')
  # TODO: arg to force lon/lat instead of lat/lon pattern.
  # TODO: accept some basic geocoding for place names? wikipedia/wikimapia lookup?

  if len(args) == 1:
    # Force full help output when run without args.
    ARGS.print_help()
    ARGS.exit(2, '\nerror: no geo locations given\n')
  parsed_args = ARGS.parse_args()

  # NOTE: precision is open to discussion.
  decimal.getcontext().prec = 9

  exit_code = 0

  for geo_string in parsed_args.geo_string:
    loc = ParseLocation(geo_string)
    if not loc.matches():
      sys.stderr.write('No match\n')
      exit_code = 1
    elif parsed_args.all:
      for result in loc.matches():
        if result.confidence > 0:
          print('confidence:{} '.format(result.confidence), end='')
          print_location(result)
    else:
      best = loc.best_match()
      if best:
        print_location(best)

  return exit_code


if __name__ == '__main__':
  sys.exit(main(sys.argv))
