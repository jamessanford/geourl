#!/usr/bin/env python
# coding=utf-8

import decimal
import unittest
import geourl

# TODO: FIXME: check extra zeroes at the end, ie '123.40000', should strip('0')?


class TestFindNumbers(unittest.TestCase):
  # Testing notes:
  #   Lat 0-180
  #   Long 0-90
  #   minute/seconds 0-60
  #   seconds can have '.xxx'
  # in compass mode, N/S/E/W/, should be close to, or next to, the input

  def setUp(self):
    super(TestFindNumbers, self).setUp()

    # NOTE: precision is open to discussion.
    decimal.getcontext().prec = 9

  def testBasic(self):
    def d(n):
      return decimal.Decimal(n)
    self.assertEqual(geourl.break_apart('37.618889, -122.375'),
                     [d('37.618889'), d('-122.375')])
    # TODO: FIXME: check utf-8 vs unicode
    self.assertEqual(
        geourl.break_apart('37° 37′ 8″ N, 122° 22′ 30″ W'.decode('utf-8')),
        [d('37'), d('37'), d('8'), 'N', d('122'), d('22'), d('30'), 'W'])

  def testSmokeTest(self):
    # No crashing allowed.
    geourl.find('37° 37′ 8″ N, 122° 22′ 30″ W'.decode('utf-8'))
    geourl.find('1 2 3 4 5 6 7'.decode('utf-8'))
    geourl.find('37.6188888, -122.375 z=3.0'.decode('utf-8'))
    geourl.find('37.6188888, -12.375 z=3.00'.decode('utf-8'))
    geourl.find('37.6188888, -12.375 z=3.0000'.decode('utf-8'))

  def testSignedDecimal(self):
    match = geourl.find('49.440603,11.004759')
    self.assertEqual(match.latitude, '49.440603')
    self.assertEqual(match.longitude, '11.004759')

    match = geourl.find('49.440603,-11.004759')
    self.assertEqual(match.latitude, '49.440603')
    self.assertEqual(match.longitude, '-11.004759')

    match = geourl.find('-49.45,-11.01')
    self.assertEqual(match.latitude, '-49.45')
    self.assertEqual(match.longitude, '-11.01')

  def testInvalidSignedDecimal(self):
    # latitude out of bounds
    match = geourl.find('-91,0.0')
    self.assertEqual(None, match)

    # latitude out of bounds
    match = geourl.find('-103.410,10.310')
    self.assertEqual(None, match)

    # longitude out of bounds
    match = geourl.find('36.1003, 187.4171')
    self.assertEqual(None, match)

    # longitude out of bounds
    match = geourl.find('36.1003, -180.5')
    self.assertEqual(None, match)

  def testBestMatch(self):
    # no matches
    match = geourl.find('1 2 3 4 5 6 7'.decode('utf-8'))
    self.assertEqual(None, match)

    # Even with the 'z' float at the end, we find the correct entry.
    expected = '37.6188888,-122.375'
    match = geourl.find('37.6188888, -122.375 z=3')
    self.assertEqual(str(match), expected)
    match = geourl.find('37.6188888, -122.375 z=3.0')
    self.assertEqual(str(match), expected)
    match = geourl.find('37.6188888, -122.375 z=3.00')
    self.assertEqual(str(match), expected)
    match = geourl.find('37.6188888, -122.375 z=3.0000')
    self.assertEqual(str(match), expected)

  def testCompassMatchWins(self):
    # Without a compass match
    match = geourl.find('-12.671, 41.014')
    self.assertEqual(str(match), '-12.671,41.014')

    # When there is a compass match and also floats, the compass match wins.
    match = geourl.find('-37.5123, 0, 37 29 49N, 122 14 25E, -12.671, 41.014')
    self.assertEqual(str(match), '37.4969444,122.240277')

  def testCompass(self):
    match = geourl.find('37° 37′ 8″ N, 122° 22′ 30″ W'.decode('utf-8'))
    self.assertEqual('37.6188889', str(match.latitude))
    self.assertEqual('-122.375000', str(match.longitude))

    # seconds can have a decimal point
    match = geourl.find('S17 33 08.352 W69 01 29.74')
    self.assertEqual('-17.55232', str(match.latitude))
    self.assertEqual('-69.0249278', str(match.longitude))

    # the word 'and' should not matter
    match = geourl.find('S17 33 08.352 and W69 01 29.74')
    self.assertEqual('-17.55232', str(match.latitude))
    self.assertEqual('-69.0249278', str(match.longitude))

  # TODO FIXME
  def testWest(self):
    pass  # 'W' is -
  def testEast(self):
    pass  # 'E' is +
  def testNorth(self):
    pass  # 'N' is +
  def testSouth(self):
    pass  # 'S' is -

  def testInvalidCompass(self):
    # normal compass works as expected
    match = geourl.find('37 37 8 N 122 22 30 W')
    self.assertEqual(str(match), '37.6188889,-122.375000')

    # latitude hours cannot have a decimal point
    match = geourl.find('37.000 37 8 N 122 22 30 W')
    self.assertTrue(match is None)

    # latitude hours cannot have a decimal point
    match = geourl.find('37.000° 37′ 8″ N, 122° 22′ 30″ W'.decode('utf-8'))
    self.assertTrue(match is None)

  def testBestGuess(self):
    # a bunch of numbers, but we still pull out the lat/long
    match = geourl.find('/47/54m/-1.4003,57.007/z=18900/t=3')
    self.assertEqual(str(match), '-1.4003,57.007')
    match = geourl.find('/47/54m/-1.4003,57.007/z=18/t=3.00000')
    self.assertEqual(str(match), '-1.4003,57.007')

  def testMultipleMatches(self):
    match = geourl.find('1.0 2.00 3.00 4.00 5.0 6.0')
    # TODO: unspecified result, could be 2,3 or 3,4


class TestBulkURLs(unittest.TestCase):
  def setUp(self):
    super(TestBulkURLs, self).setUp()

    # NOTE: precision is open to discussion.
    decimal.getcontext().prec = 9

  def testBulkURLs(self):
# expected_latitide,expected_longitude | url
    urls = """
37.618889,-122.375 | 37.618889, -122.375
None | nothing here
30.5708334,104.060556|30°34′15″N 104°3′38″E
48.8988889,12.6569444|48°53'56"N 12°39'25"E
37.6188889,-122.375000|37_37_08_N_122_22_30_W
49.440603,11.004759|49.440603,11.004759
37.6188889,-122.375000|37° 37′ 8″ N, 122° 22′ 30″ W
37.491400,-122.211000|http://wikimapia.org/#lang=en&lat=37.491400&lon=-122.211000&z=10&m=b
50.95942,14.1342|http://hikebikemap.de/?zoom=12&lat=50.95942&lon=14.1342&layers=B0000FFFFF
37.8033833,-122.176445|37 deg 48' 12.18" N 122 deg 10' 35.20" W
36.2770490,139.375149|36° 16' 37.3764" N, 139° 22' 30.5364" E
37.4969444,-122.240277|N 37 ° 29 ' 49 '', W 122 ° 14 ' 25 ''
45.876349,9.655686|https://www.google.com/maps/place/Brembana+Service+S.R.L./@45.876349,9.655686,487m/
39.2240795,-98.5418072|39 deg 13 min 26.686 sec north latitude, 98 deg 32 min 30.506 sec west longitude
37.50493,-122.30854|http://labs.strava.com/heatmap/#15/-122.30854/37.50493/gray/both
-34.9290000,138.601|Adelaide Coordinates	34°55′44.4″S 138°36′3.6″E
31.2,121.5|Shanghai with seconds 31°12′ 00N 121°30′ 00E
31.2,121.5|Shanghai 31°12′N 121°30′E
31.2083333,121.508333|Near Shanghai 31°12.5′N 121°30.5′E
-23.55,-46.6333333|23°33′S 46°38′W São Paulo
"""

    tested_url_count = 0

    for line in filter(lambda item: item, urls.split('\n')):
      expected, url = (i.strip() for i in line.split('|'))
      match = geourl.find(url)
      if expected == 'None':
        self.assertTrue(match is None)
      else:
        self.assertTrue(match is not None, msg='None result for "{}"'.format(url))
        result = '{},{}'.format(match.latitude,match.longitude)
        fail_msg = 'url "{}" expected "{}", result: "{}"'.format(url, expected, result)
        self.assertEqual(expected, result, msg=fail_msg)
      tested_url_count += 1

    self.assertTrue(tested_url_count > 10)


if __name__ == '__main__':
  unittest.main()
