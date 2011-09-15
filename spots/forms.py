from django import forms
from django.forms.util import ErrorList

from spots.models import *
from spots.utils import *
from spots.widgets import *


class SpotForm(forms.ModelForm):    
  address = forms.CharField(widget=AddressInput(), required=True, help_text="Enter an address or intersection.")

  class Meta:
    model = Spot
    fields = ('address',)
    
  def save(self, commit=False):
    spot = super(SpotForm, self).save(commit=False)
    spot.address = self.cleaned_data.get("address")
    spot.city = self.cleaned_data.get("city")
    spot.neighbohoods = None  # Neighborhoods are updated automatically when a spot is saved.
    spot.latitude = self.cleaned_data.get("latitude")
    spot.longitude = self.cleaned_data.get("longitude")
    spot.save()
    spot._update_neighborhoods()
    return spot
    
  def clean(self):
    latitude = self.cleaned_data.get("latitude")
    longitude = self.cleaned_data.get("longitude")
    address = self.cleaned_data.get("address")
    city = self.cleaned_data.get("city")
    
    if address or latitude or longitude:
      try:
        # If the user used the map to pick a spot, we'll parse the input.
        if address.startswith('(') and address.endswith(')'):
          latitude, longitude = address.strip("(").strip(")").split(", ")
          address = None
      
        # If the input includes an address, but not lat/long, geocode the address.
        if address and not latitude and not longitude:
          place, (latitude, longitude) = get_location_from_address(address.encode('ascii', 'xmlcharrefreplace'))
          self.cleaned_data['latitude'] = str(latitude)
          self.cleaned_data['longitude'] = str(longitude)
          self.cleaned_data['address'] = place
      
        # If the input includes a lat/lng, but not an address, reverse geocode the lat/lng.
        if not address and latitude and longitude:
          address = get_address_from_location((latitude,longitude))
          place = address
          self.cleaned_data['address'] = address
          self.cleaned_data['latitude'] = str(latitude)
          self.cleaned_data['longitude'] = str(longitude)
    
        # Determine the city for this spot.
        if not city and address:
          city = get_city_from_address(address.encode('ascii', 'xmlcharrefreplace'))
        if not city and latitude and longitude:
          city = get_city_from_point(latitude, longitude)
        if city:
          self.cleaned_data['city'] = city
      
        # If we still don't have a city, lat, and long, something went wrong. Return an error.
        if city == None or latitude == None or longitude == None:
          raise Exception
    
      except:
        try:
          del self.cleaned_data["address"]
        except KeyError:
          pass
        msg = "The address you entered was unable to be processed."
        self._errors["address"] = ErrorList([msg])
    
    # Return the cleaned data dictionary.
    return self.cleaned_data