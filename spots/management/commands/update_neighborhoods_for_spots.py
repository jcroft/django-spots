from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import CommandError
from django.core.management.base import BaseCommand

from spots.models import *

class Command(BaseCommand):
  help = "Updates neighborhoods for spots that don't have them."

  def handle(self, **kwargs):
    """
    For each spot that is in a city that has neighborhoods, but doesn't have
    any neighborhoods itself, try to find the neighborhoods. This is here because
    we sometimes reach the Urban Mapping API daily query limit, and some spots get
    added without neighborhoods. This runs regularly, and tries to add those missing
    neighborhoods.
    """
    city_list = []
    for neighborhood in Neighborhood.objects.all():
      if neighborhood.city not in city_list:
        city_list.append(neighborhood.city)
    for city in city_list:
      spots = Spot.objects.filter(city=city, neighborhoods=None)
      for spot in spots:
        spot.save()