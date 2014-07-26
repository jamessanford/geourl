#!/usr/bin/env python
# coding=utf-8

import decimal
import unittest
import geourl


class TestFindNumbers(unittest.TestCase):
  def setUp(self):
    super(TestFindNumbers, self).setUp()

    self.inputs = filter(lambda item: item, (
"""
30°34′15″N 104°3′38″E
48°53'56"N 12°39'25"E
37_37_08_N_122_22_30_W
39 deg 13 min 26.686 sec north latitude, 98 deg 32 min 30.506 sec west longitude
49.440603,11.004759
37° 37′ 8″ N, 122° 22′ 30″ W
37.618889, -122.375
http://wikimapia.org/#lang=en&lat=37.491400&lon=-122.211000&z=10&m=b
http://hikebikemap.de/?zoom=12&lat=50.95942&lon=14.1342&layers=B0000FFFFF
37 deg 48' 12.18" N 122 deg 10' 35.20" W
36° 16' 37.3764" N, 139° 22' 30.5364" E
N 37 ° 29 ' 49 '', W 122 ° 14 ' 25 ''
https://www.google.com/maps/place/Brembana+Service+S.R.L./@45.876349,9.655686,48
7m/
http://labs.strava.com/heatmap/#15/-122.30854/37.50493/gray/both
""".decode('utf-8').split('\n')))

  def testFoo(self):
    print self.inputs
    self.assertEquals(1, 1)

# Lat 0-90
# Long 0-180
# minute/seconds 0-60
# seconds can have '.xxx'
# look at the index of NS WE , they should be close to the numbers.
# re search that gives the 'index' where it was found...???
#   re.search -> start, end, span, string

# look for [^a-zA-z]N[^a-zA-Z] ? for the NSWE?

  def testBasic(self):
#    self.assertEqual(geourl.find('37.618889, -122.375'),
#                     [37.618889, -122.375])
#    self.assertEqual(
#        geourl.find('37° 37′ 8″ N, 122° 22′ 30″ W'.decode('utf-8')),
#        [37.618889, -122.375])
    def d(n):
      return decimal.Decimal(n)
    self.assertEqual(geourl.break_apart('37.618889, -122.375'),
                     [d('37.618889'), d('-122.375')])
    self.assertEqual(
        geourl.break_apart('37° 37′ 8″ N, 122° 22′ 30″ W'.decode('utf-8')),
        [d('37'), d('37'), d('8'), 'N', d('122'), d('22'), d('30'), 'W'])

    geourl.find('37° 37′ 8″ N, 122° 22′ 30″ W'.decode('utf-8'))
#    geourl.find('1 2 3 4 5 6 7'.decode('utf-8'))


# Test all sample inputs
# testSampleURLs
# testValidFormats
# testBestGuess
#   /47/54m/-1.4003,57.007/z=18900/t=3
#   /47/54m/-1.4003,57.007/z=18/t=3.00000
#   ^ tricky.  should pick the one where both have good amount of digits.
#     use a*b digits?  probably.  or (a+1)*(b+1)?
# testMultipleMatches
# Test things like 1.0 2.00 3.00 4.00 5.0 6.0
# ^ what should the result be?  "indeterminate"


if __name__ == '__main__':
  unittest.main()
