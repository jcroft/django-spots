from django import template
from django.template import Library
from django.template import RequestContext
from django.template import resolve_variable
from django.conf import settings

from spots.models import *
from spots.forms import *

register = Library()

INCLUDE_TEMPLATE = """
<script src="http://maps.google.com/maps?file=api&amp;v=2&amp;key=%s" type="text/javascript"></script>
"""

BASIC_TEMPLATE = """
<div class="map" id="map-%(name)s" style="width:%(width)spx;height:%(height)spx;"></div>
<script type="text/javascript">
  function create_map_%(name)s() {
    if (GBrowserIsCompatible()) {
    
      // Create a GLatLng for the photo's position
      point = new GLatLng(%(latitude)s,%(longitude)s)
    
      // Draw the basic map.
      var map = new GMap2(document.getElementById("map-%(name)s"));
      map.setCenter(point, %(zoom)s, %(view)s);
    
      // Add controls to the map
      map.addControl(new GSmallZoomControl());
      var ov = new GOverviewMapControl(new GSize(167,160));
      map.addControl(ov);
      
    
      // Add a marker to the map for the photo.
      markerOptions = { clickable:%(clickable)s, draggable:%(draggable)s }
      marker = new GMarker(point, markerOptions);
      GEvent.addListener(marker, "click", function() {
         marker.openInfoWindowHtml("%(message)s");
      });
      map.addOverlay(marker);
      return map;
    }
  }
  jQuery(document).ready(function(){ create_map_%(name)s(); });
</script>
"""
# {% gmap name:mimapa width:300 height:300 latitude:x longitude:y zoom:20 view:G_PHYSICAL_MAP clickable:true %} Message for a marker at that point {% endgmap %}

class GMapNode (template.Node):
    def __init__(self, params, nodelist):
        self.params = params
        self.nodelist = nodelist
        
    def render (self, context):
        for k,v in self.params.items():
            try:
                self.params[k] = resolve_variable(v, context)
            except:
                pass
        self.params["message"] = self.nodelist.render(context).replace("\n", "<br />")
        return BASIC_TEMPLATE % self.params
def do_gmap(parser, token):
    items = token.split_contents()

    nodelist = parser.parse(('endgmap',))
    parser.delete_first_token()
    
    #Default values 
    parameters={
            'name'      : "default",
            'width'     : "300",
            'height'    : "300",
            'latitude'  : "38.92522904714051",
            'longitude' : "-95.3173828125",
            'zoom'      : "15",
            'view'      : "G_PHYSICAL_MAP",
            'message'   : "No message",
            'clickable' : "true",
            'draggable' : "false",
    }
    for item in items[1:]:
        param, value = item.split(":")
        param = param.strip()
        value = value.strip()
        
        if parameters.has_key(param):
            if value[0]=="\"":
                value = value[1:-1]
            parameters[param] = value
        
    return GMapNode(parameters, nodelist)

class GMapScriptNode (template.Node):
    def __init__(self):
        pass        
    def render (self, context):
        return INCLUDE_TEMPLATE % (settings.GOOGLE_MAPS_API_KEY)

def do_gmap_script(parser, token):
    try:
        tag_name = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError("La etiqueta no requiere argumentos" % token.contents[0])
    return GMapScriptNode()

register.tag('gmap', do_gmap)
register.tag('gmap-script', do_gmap_script)


@register.inclusion_tag('snippets/forms/current_location_form.html', takes_context=True)
def render_current_location_form(context):
  """
  Renders the current location form for a given user.
  
  {% render_current_location_form %}
  """
  user = context['request'].user
  if user.is_authenticated:
    try:
      user_location = UserLocation.objects.get(user=user)
    except UserLocation.DoesNotExist:
      user_location = UserLocation(user=user, created_by=user)
    return { 'location_form': UserLocationForm(instance=user_location, prefix="location"), }
  else:
    return ""
  
@register.inclusion_tag('snippets/lists/spot_dict.html', takes_context=True)
def render_spot_list_item(context, spot):
  request = context['request']
  if request.user.is_authenticated():
    try:
      spot = {'spot': spot, 'distance': spot._get_distance_to_spot(request.user.location), 'direction': spot._get_compass_direction_to_spot(request.user.location) }
    except UserLocation.DoesNotExist:
      spot = {'spot': spot, 'distance': None, 'direction': None }
  else:
    spot = {'spot': spot, 'distance': None, 'direction': None }
  return { 'item': spot, 'request': request }