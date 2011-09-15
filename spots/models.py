import unicodedata

from django.db import models
from django.db.models import permalink, signals
from django.contrib.contenttypes.models import ContentType
from django.template.defaultfilters import slugify
from django.utils.encoding import force_unicode
from django.contrib.auth.models import User
from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.localflavor.us.models import USStateField, PhoneNumberField
from django.contrib.localflavor.us.us_states import STATE_CHOICES

from geopy import geocoders
from geopy.geocoders.google import Google

from spots.constants import *
from spots.managers import *
from spots.utils import *


class City(models.Model):
  city            = models.CharField(max_length=100, help_text="Enter the name of the city.")
  state           = USStateField(blank=True, help_text="If USA, select the state.", choices=STATE_CHOICES)
  county          = models.CharField(blank=True, max_length=200, help_text="Enter the name of the county.")
  province        = models.CharField(blank=True, max_length=100, help_text="If not USA, enter province or state here.")
  country         = models.CharField(max_length=100, default='us', help_text="Select the country", choices=COUNTRY_CHOICES,)
  slug            = models.SlugField(unique=True, help_text='The slug is a URL-friendly version of the city name. It is auto-populated.')
  latitude        = models.DecimalField(blank=True, null=True, max_digits=11, decimal_places=6, editable=False)
  longitude       = models.DecimalField(blank=True, null=True, max_digits=11, decimal_places=6, editable=False)
  
  description     = models.TextField(blank=True)

  def __unicode__(self):
    return self.full_name()

  def name(self):
    """ Returns the name of the City in City, State, Province format. """
    return force_unicode(", ".join(b for b in (self.city, self.state, self.province) if b))

  def full_name(self):
    """ Returns the full name of the City in City, State, Province, Country format. """
    return force_unicode(", ".join(b for b in (self.city, self.state, self.province, self.get_country_display()) if b))

  def full_name_ascii(self):
    """ Returns the name of the City in City, State, Province, Country format. Forces ASCII output, which is useful for passing to a geocoder. """
    return unicodedata.normalize('NFKD', self.full_name()).encode('ascii','ignore')

  def us_bias_name(self):
    """ If the city is in the USA, returns "Topeka, KS". If it's not, returns, "Sydney, New South Wales, Australia". """
    if self.country == "us":
      return force_unicode(", ".join(b for b in (self.city, self.state) if b))
    else:
      return force_unicode(", ".join(b for b in (self.city, self.state, self.province, self.get_country_display()) if b))
      
  def us_bias_name_ascii(self):
    return unicodedata.normalize('NFKD', self.us_bias_name()).encode('ascii','ignore')

  def nearby_cities(self, num=None, mile_limit=25):
    """ 
    Returns the "num" closest cities to this one. Limits to spots within
    a given mile_limit, which defaults to 25 miles.
    """
    radius_miles = Decimal(str(mile_limit))
    radius = Decimal(radius_miles/Decimal("69.04"))
    return City.objects.filter(latitude__range=(self.latitude - radius,self.latitude + radius)).filter(longitude__range=(self.longitude - radius,self.longitude + radius)).exclude(id=self.id)

  @permalink
  def get_absolute_url(self):
    """ Returns the URL to this city's detail view page. """
    if self.country == "us":
      return ('city_detail', None, {'country': slugify(self.country), 'state': slugify(self.state), 'city': slugify(self.city)})
    else:
      if self.province:
        return ('city_detail', None, {'country': slugify(self.country), 'state': slugify(self.province), 'city': slugify(self.city)})
      else:
        # Sort of ugly hack -- state detail view will check for cites without a state or province and
        # redirect them to the city detail view if appropriate.
        return ('state_detail', None, {'country': slugify(self.country), 'state': slugify(self.city)})

  @permalink
  def get_state_url(self):
    """ Returns the URL to the state detail view for the state or province of this city. """
    if self.country == "us":
      return ('state_detail', None, {'country': slugify(self.country), 'state': slugify(self.state)})
    else:
      return ('state_detail', None, {'country': slugify(self.country), 'state': slugify(self.province)})

  @permalink
  def get_country_url(self):
    """ Returns the URL to the city detail view for the country of this city. """
    return ('country_detail', None, {'country': slugify(self.country)})
  
  def save(self, *args, **kwargs):
    """ Saves the city """
    if self.province:
      self.slug = slugify(self.city + " " + self.province + " " + self.country)
    else:
      self.slug = slugify(self.city + " " + self.state + " " + self.country)
    if not self.latitude and not self.longitude:
      place, (latitude, longitude) = get_location_from_address(self.full_name().encode('ascii', 'xmlcharrefreplace'))
      if latitude and longitude:
        self.latitude = str(latitude)
        self.longitude = str(longitude)
      else:
        pass
    super(City, self).save(*args, **kwargs)

  class Meta:
    verbose_name_plural = 'cities'
    unique_together = (('city', 'state', 'province', 'country'),)


class Neighborhood(models.Model):
  """ A distinct area within a city. """
  city        = models.ForeignKey(City, help_text="Select the city this neighborhood is in.", related_name="neighborhoods")
  name        = models.CharField(max_length=200, help_text='Enter the name of the neighborhood.')
  slug        = models.SlugField(help_text="The slug is a URL-friendly version of the name. It is auto-populated.")

  def __unicode__(self):
    return self.name

  def full_name(self):
    """ Returns the full name of the neighborhood in Neighborhood, City, State, Country format."""
    return ", ".join(b for b in (self.name, self.city.full_name()) if b)

  @permalink
  def get_absolute_url(self):
    """ Returns the URL to the detail page for this Neighborhood. """
    if self.city.country == "us":
      return ('neighborhood_detail', None, {'country': slugify(self.city.country), 'state': slugify(self.city.state), 'city': slugify(self.city.city), 'neighborhood_slug': self.slug})
    else:
      if self.city.province:
        return ('neighborhood_detail', None, {'country': slugify(self.city.country), 'state': slugify(self.city.province), 'city': slugify(self.city.city), 'neighborhood_slug': self.slug})
    return

  class Meta:
    unique_together = (("city", "name"),)


class Spot(models.Model):
  """
  Base class for spot models. Use this directly, or inherit it as a base class in your models (multi-table inheritance)
  if you want to add additional attributes. For example, you may have a Restaurant model that subclasses Spot. Then,
  any Restaurant will have a "spot" attribute with all of these fields and methods.
  """
  address             = models.CharField(blank=True, max_length=500)
  city                = models.ForeignKey(City, blank=True, null=True, related_name="%(class)ss", editable=False)
  neighborhoods       = models.ManyToManyField(Neighborhood, blank=True, null=True, related_name="%(class)ss", editable=False)
  latitude            = models.DecimalField(blank=True, null=True, max_digits=11, decimal_places=6, editable=False)
  longitude           = models.DecimalField(blank=True, null=True, max_digits=11, decimal_places=6, editable=False)
  
  class Meta:
    abstract = True
  
  def __unicode__(self):
    return u"%s" % self.address
  
  def location(self):
    """
    Returns a tuple of this spot, like (latitude, longitude).
    """
    return (self.latitude, self.longitude)

  def neighborhood_list(self):
    """
    Returns a comma-delimited list of neighborhoods this spot is in.
    Primary for use in the admin list view.
    """
    return ", ".join([ neighborhood.name for neighborhood in self.neighborhoods.all() ])

  def nearby_spots(self, num=10, mile_limit=25):
    """ 
    Returns the "num" closest spots to this one. Limits to spots within
    a given mile_limit, which defaults to 25 miles.
    """
    from django.template.defaultfilters import dictsort
    spots_within_limit = Spot.objects.within_radius_of_location(location=self.location(), radius_miles=mile_limit)
    spot_dict_list = []
    for spot in spots_within_limit:
      if spot != self:
        distance = self._get_distance_to_spot(spot)
        direction = self._get_compass_direction_to_spot(spot)
        spot_dict_list.append({ 'distance': float(distance), 'spot': spot, 'direction': direction })
    return dictsort(spot_dict_list, 'distance')[:num]
  
  def _get_distance_to_location(self, location):
    """ 
    Returns the distance, in miles, between the current Spot and a (lat, lng) tuple.
    """
    import math
    latitude, longitude = location
    rad = math.pi / 180.0
    y_distance = (float(latitude) - float(self.latitude)) * 69.04
    x_distance = (math.cos(float(self.latitude) * rad) + math.cos(float(latitude) * rad)) * (float(longitude) - float(self.longitude)) * (69.04 / 2)
    distance = math.sqrt( y_distance**2 + x_distance**2 )
    return distance
  
  def _get_distance_to_spot(self, spot):
    """ 
    Returns the distance, in miles, between the current Spot and another one.
    """
    return self._get_distance_to_location(spot.location())
  
  def _get_bearing_to_location(self, location):
    import math
    latitude, longitude = location
    lat1 = float(latitude)
    lat2 = float(self.latitude)
    lon1 = float(longitude)
    lon2 = float(self.longitude)
    dLon = lon2 - lon1
    y = math.sin(dLon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dLon)
    degrees_180 = math.degrees(math.atan2(y, x))
    return (degrees_180 + 360) % 360
  
  def _get_bearing_to_spot(self, spot):
    return self._get_bearing_to_location(spot.location())
  
  def _get_compass_direction_to_location(self, location):
    if self._get_distance_to_location(location) < 100.00:
      bearing = self._get_bearing_to_location(location)
      return get_compass_direction_from_bearing(bearing)
    else:
      return None
      
  def _get_compass_direction_from_location(self, location):
    if self._get_distance_to_location(location) < 100.00:
      bearing = self._get_bearing_to_location(location)
      return get_compass_direction_from_bearing(bearing, reverse=True)
    else:
      return None
  
  def _get_compass_direction_to_spot(self, spot):
    return self._get_compass_direction_to_location(spot.location())
    
  def _get_compass_direction_from_spot(self, spot):
    return self._get_compass_direction_from_location(spot.location())

  def _create_bounding_box(self, miles=1.0):
    """
    Returns a four-tuple of two-tuples representing a bounding box 
    using this spot as it's center. Takes a "miles" argument, which 
    should be a float representing the distance from the point that 
    should be included in the bounding box.
    """
    degrees_delta = miles/69.0
    upper_left = (float(self.latitude) + degrees_delta, float(self.longitude) + degrees_delta)
    upper_right = (float(self.latitude) + degrees_delta, float(self.longitude) - degrees_delta)
    lower_left = (float(self.latitude) - degrees_delta, float(self.longitude) + degrees_delta)
    lower_right = (float(self.latitude) - degrees_delta, float(self.longitude) - degrees_delta)
    return (upper_left, upper_right, lower_left, lower_right)
  
  def _get_location_from_address(self):
    """
    Geocodes this spot based on the address entered.
    Returns a tuple like (place, (latitude, longitude)).
    """
    return get_location_from_address(self.address)

  def _get_address_from_location(self):
    """
    Reverse geocodes this spot based on the latitude and longitude entered.
    Returns a string containing the full address, like "1525 NW 57th St, Seattle, WA 98107, USA".
    """
    return get_address_from_location(self.location())

  def _update_neighborhoods(self):
    """
    Gets the neighborhoods associated with this spot from Urban Mapping, creates
    them if necessary, and relates them to this spot.
    """
    if hasattr(settings, 'URBAN_MAPPING_API_KEY'):
      self.neighborhoods.clear()
      urban_mapping_api = UrbanMappingClient(method="getNeighborhoodsByLatLng")
      params = { 'apikey': settings.URBAN_MAPPING_API_KEY, 'lat': self.latitude, 'lng': self.longitude, 'results': 'many' }
      try: neighborhoods = urban_mapping_api(**params)
      except: return []
      for neighborhood in neighborhoods.getiterator('neighborhood'):
        neighborhood_name = neighborhood.find('name').text.replace('  ', '').replace('\n', '').replace('\t', '')
        neighborhood, created = Neighborhood.objects.get_or_create(
          name = neighborhood_name,
          slug = slugify(neighborhood.find('name').text),
          city = self.city,
        )
        self.neighborhoods.add(neighborhood)
    return self
