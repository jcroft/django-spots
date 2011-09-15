from django import forms
from django.db.models import get_model
from django.utils import simplejson
from django.utils.safestring import mark_safe
from django.conf import settings
from django.utils.encoding import smart_unicode

from spots.models import *

class CityInput(forms.TextInput):
  def render(self, name, value, attrs=None):
    if value:
      try:
        city = City.objects.get(id=int(value))
        value = city.full_name()
      except:
        value = ""
    return super(CityInput, self).render(name, value, attrs=attrs)

class AddressInput(forms.TextInput):
  
  def __init__(self, start_latitude=38.95483687118436, start_longitude=-95.2528381347, *args, **kwargs):
    super(AddressInput, self).__init__(*args, **kwargs)
    self.const_value = None
    self.start_latitude = start_latitude
    self.start_longitude = start_longitude
  
  def value_from_datadict(self, *args, **kwargs):
    if not self.const_value:
      return super(forms.TextInput, self).value_from_datadict(*args, **kwargs)
    return self.const_value
  
  def render(self, name, value, attrs=None):
    output = super(AddressInput, self).render(name, value, attrs)
    output = output + mark_safe(u'''<div id="address-map-wrapper"><a href="#" id="address-map-open" class="button">Map</a><div id="address-map"></div></div>''')
    return output + mark_safe(u'''
      <script src="http://maps.google.com/maps?file=api&amp;v=2&amp;key=%s" type="text/javascript"></script>
      <script type="text/javascript">
        function create_map() {
          if (GBrowserIsCompatible()) {
          
            if (typeof(spot) !== 'undefined') {
              if (spot.latitude && spot.longitude) {
                point = new GLatLng(spot.latitude,spot.longitude);
              }
            } else if (typeof(user) !== 'undefined') {
              if (user.latitude && user.longitude) {
                point = new GLatLng(user.latitude,user.longitude);
              } else {
                  point = new GLatLng(%s,%s);
                }
            } else {
              point = new GLatLng(%s,%s);
            }
            
            var map = new GMap2(document.getElementById("address-map"));
            map.setCenter(point, 14, G_PHYSICAL_MAP);
            map.addControl(new GSmallZoomControl());
            markerOptions = { clickable:true, draggable:true }
            marker = new GMarker(point, markerOptions);
            GEvent.addListener(marker, "dragend", function(){
              var point = marker.getPoint();
              $('#%s').val(point);
            });
            map.addOverlay(marker);
            return map;
          }
        }
        jQuery(document).ready(function(){
          map = create_map();
          $('#address-map-open').click(function(e){
            e.preventDefault();
            $('#address-map').toggle();
            map.zoomIn();
          });
          $('#address-map').hide();
        });
      </script>
    ''' % (settings.GOOGLE_MAPS_API_KEY, self.start_latitude, self.start_longitude, self.start_latitude, self.start_longitude, attrs['id']))