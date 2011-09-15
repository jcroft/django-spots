from decimal import Decimal

from django.db import models
from django.db.models import signals
from django.contrib.contenttypes.models import ContentType

from spots.models import *

class SpotManager(models.Manager):
  
  def within_radius_of_location(self, location, radius_miles=1):
    """
    Given a radius in miles (defaults to 1), returns a QuerySet of Spot objects within 
    that distance from the given location tuple (latitude, longitude). 
    """
    latitude = location[0]
    longitude = location[1]
    radius_miles = Decimal(str(radius_miles))
    radius = Decimal(radius_miles/Decimal("69.04"))
    return self.filter(latitude__range=(latitude - radius,latitude + radius)).filter(longitude__range=(longitude - radius,longitude + radius))
    
  def closest_spots(self, this_spot, mile_limit=25):
    """ 
    Returns the "num" closest spots to this one. Limits to spots within
    a given mile_limit, which defaults to 25 miles.
    """
    from django.template.defaultfilters import dictsort
    spots_within_limit = self.within_radius_of_location(location=this_spot.location(), radius_miles=mile_limit)
    spot_dict_list = []
    for spot in spots_within_limit:
      if spot != this_spot:
        distance = this_spot._get_distance_to_spot(spot)
        direction = this_spot._get_compass_direction_to_spot(spot)
        spot_dict_list.append({ 'distance': float(distance), 'spot': spot, 'direction': direction })
    return dictsort(spot_dict_list, 'distance')