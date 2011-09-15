from django.shortcuts import get_object_or_404, get_list_or_404, render_to_response
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template import RequestContext
from django.template.defaultfilters import slugify, dictsort, dictsortreversed
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required

from spots.constants import COUNTRY_CHOICES
from spots.forms import *
from spots.models import *

def format_qs(q):
  """
  Utility method that formats a query string into Django QuerySet selectors.
  """
  kw = {}
  for k,v in q.items():
    if k.endswith('__in') and isinstance(v, basestring):
      v = v.split(',')
    kw[str(k)] = v
  return kw


def get_city_from_url_bits(country, city, state=None):
  """
  Utility function to find a city object from parts of a URL. If the city
  is not found, returns a 404.
  """
  if state: 
    city_slug = slugify(city + " " + state + " " + country)
  else: 
    city_slug = slugify(city + " " + country)
  city = get_object_or_404(City, slug=city_slug)
  return city


def build_breadcrumbs(country=None, state=None, city=None, spot=None):
  """
  Builds the dict for use in breadcrumb trails through spots. Pass it:
  country: Two-letter country code, lowercase
  state: If USA, pass it the two-letter state code. Otherwise, the full state or province name.
  city: The City object.
  spot: The Spot object.
  """
  breadcrumbs = [{'name': 'Spots', 'url': reverse('spot_list')}]
  view_name = "spots"
  if country:
    country_display = City.objects.filter(country=country)[0].get_country_display()
    country_code = City.objects.filter(country=country)[0].country
    breadcrumbs.append({'view': 'country', 'name': country_display, 'url': reverse('spot_list_for_country', args=[country_code])})
    view_name = "country-%s" % country
  if state:
    breadcrumbs.append({'view': 'state/province', 'name': state, 'url': reverse('spot_list_for_state', args=[country, slugify(state)])})
    view_name = "state-%s-%s" % (country, slugify(state))
  if city:
    breadcrumbs.append({'view': 'city','name': city.city, 'url': reverse('city_detail', args=[country, slugify(state), slugify(city.city)])})
    view_name = "city-%s-%s-%s" % (country, slugify(state), slugify(city.city))
  if spot:
    breadcrumbs.append({'view': 'spot', 'name': spot.name, 'url': reverse('spot_detail', args=[country, slugify(state), slugify(city.city), spot.slug])})
    view_name = "spot-%s-%s-%s-%s" % (country, slugify(state), slugify(city.city), spot.slug)
  return breadcrumbs, view_name


def spot_list(request, queryset=Spot.objects.all(), template="spots/spot_list.html", relevant_to_spot=None, extra_context={}):
  """
  Renders a list of spots. Defaults to all spots, but takes an optional
  QuerySet argument. If a Spot is passed to the "relevant_to_spot" argument, the output
  will include details as to the distance and direction of each spot from the 
  relevant_to_spot.
  """
  spots         = queryset
  query         = dict(request.REQUEST.items())
  order_by      = query.pop('order_by', '-date_created')
  
  # If a Django QS filter was submited with the request, apply it.
  if len(query):
    spots = spots.filter(**format_qs(query))
  
  # If order_by was specified, apply it (unless it's distance -- we'll handle that later).
  if order_by:
    if not order_by == "-distance" and not order_by == "distance":
      spots = spots.order_by(*order_by.split(','))
  
  # Create the spot dicts for rendering in templates. If relevant_to_spot was speficied,
  # include the distance and direction from that spot.
  if relevant_to_spot:
    spots = [ {'spot': spot, 'distance': relevant_to_spot._get_distance_to_spot(spot), 'direction': relevant_to_spot._get_compass_direction_to_spot(spot) } for spot in spots ]
    if order_by == '-distance': spots = dictsort(spots, 'distance')
    if order_by == 'distance': spots = dictsortreversed(spots, 'distance')
  else:
    spots = [ {'spot': spot, 'distance': None, 'direction': None } for spot in spots ]
  
  # Create a list of countries that have spots, for rendering in the templates.
  cities_with_spots = City.objects.filter(spots__isnull=False).distinct()
  countries = []
  for city in cities_with_spots:
    for country in COUNTRY_CHOICES:
      if country[0] == city.country:
        country_dict = { 'code': city.country, 'name': country[1], 'url': reverse('spot_list_for_country', args=[city.country])}
        if country_dict not in countries:
          countries.append(country_dict)
        break
  
  # Build the breadcrumbs for this list.
  breadcrumbs, view_name = build_breadcrumbs()
  
  # Create the context and render the template.
  context = { 
    'spots': spots, 
    'order_by': order_by, 
    'view_name': view_name, 
    'countries': countries,
  }
  context.update(extra_context)
  return render_to_response(template, context, context_instance=RequestContext(request))


def spot_detail(request, country, city, slug, state=None, template='spots/spot_detail.html', relevant_to_spot=None, extra_context={}):
  """
  Renders a individual spot's detail page. If a Spot is passed to the "relevant_to_spot" 
  argument, the output will include details as to the distance and direction of each spot 
  from the relevant_to_spot.
  """
  # Find the spot. If it's not found, 404.
  city = get_city_from_url_bits(country, city, state)
  spot = get_object_or_404(Spot, city=city, slug=slug)
  
  # If relevant_to_spot was specified, get the distance and direction calculations.
  if relevant_to_spot:
    distance = relevant_to_spot._get_distance_to_spot(spot)
    direction = relevant_to_spot._get_compass_direction_to_spot(spot)
  else:
    distance = None
    direction = None
  
  # Build the breadcrumbs for this spot.
  if spot.city.country == "us": state = spot.city.state
  else: state = spot.city.province
  
  # Create the context and render the template.
  breadcrumbs, view_name = build_breadcrumbs(country=spot.city.country, state=state, city=spot.city)
  context = { 
    'spot': spot, 
    'directions_form': directions_form, 
    'breadcrumbs': breadcrumbs,
    'view_name': view_name, 
    'distance': distance, 
    'direction': direction,
  }
  context.update(extra_context)
  return render_to_response(template, context, context_instance=RequestContext(request))


@login_required
def add_spot(request, template="spots/add_spot.html", extra_context={}):
  """
  Renders a simple form for entering spots by address.
  """
  # If this is a POST, bind the data to the form and try to save the spot.
  if request.method == 'POST':
    spot_form = SpotForm(request.POST, prefix="spot")
    if spot_form.is_valid():
      spot = spot_form.save(commit=False)
      spot.save()
      return HttpResponseRedirect(spot.get_absolute_url())
  # If it's not a POST, use an empty form.
  else:
    spot_form = SpotForm(prefix="spot")
    
  # Build the breadcrumbs for this page.
  breadcrumbs, view_name = build_breadcrumbs()
  
  # Create the context and render the template.
  context = { 'spot_form': spot_form, 'breadcrumbs': breadcrumbs, 'view_name': view_name }
  context.update(extra_context)
  return render_to_response(template, context, context_instance=RequestContext(request))


@login_required
def edit_spot(request, country, city, slug, state=None, template="spots/edit_spot.html", extra_context={}):
  """
  Renders a simple form for edit existing spots.
  """
  # Find the spot. If it's not found, 404.
  city = get_city_from_url_bits(country, city, state)
  spot = get_object_or_404(Spot, city=city, slug=slug)
  
  # If this is a POST, bind the data to the form and try to save the spot.
  if request.method == 'POST':
    spot_form = SpotForm(request.POST, prefix="spot", instance=spot)
    if spot_form.is_valid():
      spot = spot_form.save(commit=False)
      spot.save()
      return HttpResponseRedirect(spot.get_absolute_url())
  # If it's not a POST, use an empty form.
  else:
    spot_form = SpotForm(prefix="spot", instance=spot)
    
  # Build the breadcrumbs for this page.
  if spot.city.country == "us": state = spot.city.state
  else: state = spot.city.province
  breadcrumbs, view_name = build_breadcrumbs(country=spot.city.country, state=state, city=spot.city, spot=spot)
  
  # Create the context and render the template.
  context = { 'spot_form': spot_form, 'breadcrumbs': breadcrumbs, 'spot': spot, 'view_name': view_name }
  context.update(extra_context)
  return render_to_response(template, context, context_instance=RequestContext(request))


def spot_list_for_country(request, country, queryset=Spot.objects.all()):
  """
  Displays a list of spots for a given country.
  """
  # Find all the cites in this county.
  cities = City.objects.filter(country=country)
  
  # Build the breadcrumbs for this list.
  breadcrumbs, view_name = build_breadcrumbs()
  
  # Get a list of all states (or provinces) in this country.
  if country == "us":
    states = City.objects.filter(country=country, spots__isnull=False).distinct().values('state').distinct()
  else:
    states = City.objects.filter(country=country, spots__isnull=False).distinct().values('province').distinct()
  
  # For each state (or province), create a dictionary for inclusion in template. 
  # Dict keys are: name, url, code, count
  state_list = []
  for state in states:
    if country == "us":
      state = state['state']
      state_dict = { 'name': cities.filter(state=state)[0].get_state_display(), 'url': reverse('spot_list_for_state', args=[country, slugify(state)]), 'code': state.lower(), 'count': Spot.objects.filter(city__in=cities, city__state=state).count() }
    else:
      province = state['province']
      try:
        province_url = reverse('spot_list_for_state', args=[country, slugify(province)])
      except:
        province_url = ''
      state_dict = { 'name': province, 'url': province_url, 'code': province.lower(), 'count': Spot.objects.filter(city__in=cities, city__province=province).count() }
    state_list.append(state_dict)
  
  # Create the context and render the template.
  context = { 
    'view': 'country', 
    'states': state_list, 
    'cities': cities, 
    'country': cities[0].get_country_display(), 
    'breadcrumbs': breadcrumbs, 
    'view_name': view_name
  }
  return spot_list(request,queryset=Spot.objects.filter(city__in=cities), extra_context=context)


def spot_list_for_state(request, country, state, queryset=Spot.objects.all()):
  """
  Displays a list of spots for a given state (or province).
  """
  # Get a list of all cities in this state (or province).
  cities = City.objects.filter(slug__endswith=slugify(state + " " + country), spots__isnull=False).distinct()
  
  # Determine the country for this city.
  country = cities[0].country
  
  # Because some countris have states (or provinces) and some don't, this could be
  # either a city or state view. Figure it out. If this should be a city view, redirect
  # to city_detail().
  try:
    if slugify(cities[0].city) == state: 
      raise Exception
  except:
    try:
      return city_detail(request=request, country=country, city=state) # This is probably supposed to be a city view, not a state view.
    except:
      raise Http404
  
  # Determine the state code.
  if country == "us":
    state = cities[0].get_state_display()
    state_code = cities[0].state
  else:
    state = cities[0].province
    state_code = cities[0].province
    
  # Build the breadcrumbs for this list.
  breadcrumbs, view_name = build_breadcrumbs(country=cities[0].country)
  
  # Create the context and render the template.
  context = { 
    'view': 'state', 
    'cities': cities, 
    'state': state, 
    'breadcrumbs': breadcrumbs, 
    'view_name': view_name,
  }
  return spot_list(request,queryset=Spot.objects.filter(city__in=cities), extra_context=context)


def city_detail(request, country, city, state=None, queryset=Spot.objects.all()):
  """
  Displays the details of a particular city.
  """
  # Determine the city. If this fails, it'll 404.
  city = get_city_from_url_bits(country, city, state)
  
  # Determine the state (if there is one).
  if city.country == "us": state = city.state
  else: state = city.province
  
  # Build the breadcrumbs for this list.
  if state:
    breadcrumbs, view_name = build_breadcrumbs(country=city.country, state=state)
  else:
    breadcrumbs, view_name = build_breadcrumbs(country=city.country)
    
  # Create the context and render the template.
  context = { 
    'view': 'city', 
    'city': city, 
    'breadcrumbs': breadcrumbs, 
    'view_name': view_name,
  }
  return spot_list(request, queryset=Spot.objects.filter(city=city), extra_context=context)
  
  
def spot_list_for_neighborhood(request, country, city, slug, state=None, queryset=Spot.objects.all()):
  """
  Displays a list of spots for a given neighborhood (or province).
  """
  # Determine the city. If this fails, it'll 404.
  city = get_city_from_url_bits(country, city, state)
  
  # Find the neighborhood. If it doesn't exist, 404.
  neighborhood = get_object_or_404(Neighborhood, city=city, slug=slug)
  
  # Determine the state (if there is one).
  if city.country == "us": state = city.state
  else: state = city.province
  
  # Build the breadcrumbs for this page.
  breadcrumbs, view_name = build_breadcrumbs(country=city.country, state=state, city=city)
  
  # Create the context and render the template.
  context = { 
    'view': 'neighborhood', 
    'city': city, 
    'neighborhood': neighborhood, 
    'breadcrumbs': breadcrumbs, 
    'view_name': view_name,
  }
  return spot_list(request, queryset=Spot.objects.filter(city=city, neighborhoods=neighborhood), extra_context=context)
  
  
def neighborhood_list_for_city(request, country, city, state=None, template="spots/city_neighborhood_list.html", extra_context={}):
  """
  Displays a list of neighborhoods for a given city.
  """
  # Determine the city. If this fails, it'll 404.
  city = get_city_from_url_bits(country, city, state)
  
  # Find the neighborhood. If it doesn't exist, 404.
  neighborhoods = get_list_or_404(Neighborhood, city=city)
  
  # Determine the state (if there is one).
  if city.country == "us": state = city.state
  else: state = city.province
  
  # Build the breadcrumbs for this list.
  breadcrumbs, view_name = build_breadcrumbs(country=city.country, state=state, city=city)
  
  # Create the context and render the template.
  context = { 
    'neighborhoods': neighborhoods, 
    'city': city, 
    'breadcrumbs': breadcrumbs, 
    'view_name': view_name,
  }
  context.update(extra_context)
  return render_to_response(template, context, context_instance=RequestContext(request))