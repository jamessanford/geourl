### Given a geolocation url, output other urls that show the same location.

Ever find yourself looking at Google Maps but want to see the same location in Wikimapia or Panoramio?  This is your tool.

Accepts input in any format, from `30°34′15″N` to complex encoded URLs.  See the unit tests for ideas.

**Example inputs:**
> - geourl '30°34′15″N 104°3′38″E'
> - geourl 27.175015,78.042155
> - geourl 'https://www.google.com/maps/@30.571,104.06,16z'

**Example output:**

> - 30.5708334,104.060556
> - http://wikimapia.org/#lat=30.5708334&lon=104.060556&z=12&m=b
> - http://hikebikemap.org/?zoom=12&lat=30.5708334&lon=104.060556&layers=B0000FFFFF
> - http://www.openstreetmap.org/#map=14/30.5708334/104.060556
> - http://labs.strava.com/heatmap/#13/104.060556/30.5708334/gray/both
> - [...]

