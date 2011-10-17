import urllib2
import xml.etree.ElementTree as ET
from urllib import urlencode
from decimal import Decimal

from django.conf import settings

from geopy.geocoders.google import Google

from spots.models import *

BEARING_MAPPING = {
  0.0   : 'S',
  22.5  : 'SSE',
  45.0  : 'SE',
  67.5  : 'SEE',
  90.0  : 'E',
  112.5 : 'NEE',
  135.0 : 'NE',
  157.5 : 'NNE',
  180.0 : 'N',
  202.5 : 'NNW',
  225.0 : 'NW',
  247.5 : 'NWW',
  270.0 : 'W',
  292.5 : 'SWW',
  315.0 : 'SW',
  337.5 : 'SSW',
  360.0 : 'S',
}

REVERSE_BEARING_MAPPING = {
  0.0   : 'N',
  22.5  : 'NNW',
  45.0  : 'NW',
  67.5  : 'NWW',
  90.0  : 'W',
  112.5 : 'SWW',
  135.0 : 'SW',
  157.5 : 'SSW',
  180.0 : 'S',
  202.5 : 'SSE',
  225.0 : 'SE',
  247.5 : 'SEE',
  270.0 : 'E',
  292.5 : 'NEE',
  315.0 : 'NE',
  337.5 : 'NNE',
  360.0 : 'N',
}

USER_AGENT = "BarStar 1.0"

def fetch_and_parse_json(url, auth_info=None):
  """
  Fetch an XML document (possibly given auth info) and return an ElementTree.
  """
  import simplejson
  resource = fetch_resource(url, auth_info).read()
  return simplejson.loads(resource)

def fetch_and_parse_xml(url, auth_info=None):
  """
  Fetch an XML document (possibly given auth info) and return an ElementTree.
  """
  return ET.parse(fetch_resource(url, auth_info))

def fetch_resource(url, auth_info):
  """
  Fetch a resource and return the file-like object.
  """
  if auth_info:
    handler = urllib2.HTTPBasicAuthHandler()
    handler.add_password(*auth_info)
    opener = urllib2.build_opener(handler)
  else:
    opener = urllib2.build_opener()

  request = urllib2.Request(url)
  request.add_header("User-Agent", USER_AGENT)
  return opener.open(request)


class GoogleMapsClient(object):
  def __init__(self, method=''):
    self.method = method

  def __getattr__(self, method):
    return GoogleMapsClient('%s.%s' % (self.method, method))

  def __repr__(self):
    return "<GoogleMapsClient: %s>" % self.method

  def __call__(self, **params):
    url = "http://maps.google.com/maps/geo" + self.method + "?" + urlencode(params) + "&output=json"
    response = fetch_and_parse_json(url)
    return response


class UrbanMappingClient(object):
  def __init__(self, method=''):
    self.method = method

  def __getattr__(self, method):
    return UrbanMappingClient('%s.%s' % (self.method, method))

  def __repr__(self):
    return "<UrbanMappingClient: %s>" % self.method

  def __call__(self, **params):
    url = "http://api0.urbanmapping.com/neighborhoods/rest/" + self.method + "?" + urlencode(params) + "&format=xml"
    response = fetch_and_parse_xml(url)
    return response
            

def get_location_from_address(address):
  """
  Geocodes this spot based on the address entered.
  Returns a tuple like (place, (latitude, longitude)).
  If the address could not be geocoded, returns ("", (None, None)).
  """
  google_geocoder = Google(settings.GOOGLE_MAPS_API_KEY)
  location_list = [ (place, (lat,lng)) for place, (lat, lng) in google_geocoder.geocode(address, exactly_one=False) ]
  if len(location_list):
    return location_list[0]
  else:
    return ("", (None, None))


def get_address_from_location(location):
  """
  Reverse geocodes this spot based on the location tuple entered.
  Returns a string containing the full address, like "1525 NW 57th St, Seattle, WA 98107, USA".
  Requires the reverse-ceocode branch of geopy.
  """
  latitude = location[0]
  longitude = location[1]
  try:
    google_geocoder = Google(settings.GOOGLE_MAPS_API_KEY)
    (place,point) = google_geocoder.reverse((latitude, longitude))
  except:
    return None
  return place
  

def get_street_address(address):
  """
  Returns a string of the street address, like "1525 NW 57th St".
  """
  try: return address.split(", ")[0]
  except: return ""


def get_city_from_google_results(google_results):
  """
  Gets or creates, and returns, a Django City object based on the city in the Google results from GeoPy.
  This is fairly ugly, as Google's results aren't exactly the cleanest thing in the world.
  """
  from spots.models import City
  city = None
  # Ugly parsing to get the city name from one of many different places it can be in Google's results.
  try: city_name          = google_results['Placemark'][0]['AddressDetails']['Country']['AdministrativeArea']['Locality']['LocalityName']
  except:
    try: city_name        = google_results['Placemark'][0]['AddressDetails']['Country']['AdministrativeArea']['SubAdministrativeArea']['Locality']['LocalityName']
    except:
      try: city_name      = google_results['Placemark'][0]['AddressDetails']['Country']['Locality']['LocalityName']
      except:
        try: city_name    = google_results['Placemark'][0]['AddressDetails']['Country']['AddressLine']
        except: city_name = None
  # For some reason, the city name is sometimes the first item in a list.
  if type(city_name) == list:
    city_name = city_name[0]
  try: state              = google_results['Placemark'][0]['AddressDetails']['Country']['AdministrativeArea']['AdministrativeAreaName']
  except: state           = ""
  try: country_code       = google_results['Placemark'][0]['AddressDetails']['Country']['CountryNameCode'].lower()
  except: country_code    = None
  # At this point, we should have all the attributes required to create and return a City object.
  if city_name and country_code == "us":
    if state:
      try:
        city, created = City.objects.get_or_create(city=city_name, state=state, country=country_code)
      except:
        pass
  elif city_name:
    city, created = City.objects.get_or_create(city=city_name, province=state, country=country_code)
  elif city_name and state != '':
    city, created = City.objects.get_or_create(city=state, country=country_code)
  else:
    pass
  return city
  

def get_city_from_address(address):
  """
  Uses Google Maps API to identity the precise city details, and creates and/or returns a City object.
  """
  google_maps_api         = GoogleMapsClient()
  params                  = {'key': settings.GOOGLE_MAPS_API_KEY, 'q': address, }
  google_results          = google_maps_api(**params)
  return get_city_from_google_results(google_results)


def get_city_from_point(latitude, longitude):
  """
  Uses Google Maps API to identity the precise city details, and creates and/or returns a City object.
  """
  google_maps_api         = GoogleMapsClient()
  params                  = {'key': settings.GOOGLE_MAPS_API_KEY, 'q': "%s,%s" % (latitude, longitude) }
  google_results          = google_maps_api(**params)
  return get_city_from_google_results(google_results)


def get_compass_direction_from_bearing(number, reverse=False):
  from math import fabs
  key = None
  closest = 1000
  for bearing in BEARING_MAPPING:
    diff = fabs(bearing - number)
    if diff <= closest:
      key = bearing
      closest = diff
  if reverse:
    return REVERSE_BEARING_MAPPING[key]
  else:
    return BEARING_MAPPING[key]
  
def get_neighborhood_from_urban_mapping(latitude, longitude, city=None):
  neighborhood = None
  try:
    if not city:
      city = get_city_from_point(latitude, longitude)
    urban_mapping_api = UrbanMappingClient(method="getNeighborhoodsByLatLng")
    params = {
      'apikey'    : settings.URBAN_MAPPING_API_KEY,
      'lat'       : latitude,
      'lng'       : longitude,
      'results'   : 'one',
    }
    neighborhoods = urban_mapping_api(**params)
    for neighborhood in neighborhoods.getiterator('neighborhood'):
      try:          
        # The name tends to have crazy whitespace in it. Strip it out!
        neighborhood_name = neighborhood.find('name').text.replace('  ', '').replace('\n', '').replace('\t', '')
        # Get or save the neighborhood
        neighborhood, created = Neighborhood.objects.get_or_create(
          name = neighborhood_name,
          slug = slugify(neighborhood.find('name').text),
          city = city,
        )
        if created:
          neighborhood.save()
      except:
        raise
  except:
    raise
  return neighborhood