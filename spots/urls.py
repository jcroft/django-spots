from django.conf.urls.defaults import *
from django.db import models

from spots.views import *

urlpatterns = patterns('',
  url(
    regex   = r'^$',
    view    = spot_list,
    name    = 'spot_list',
    ),
  url(
    regex   = r'^(?P<country>[a-z]{2})/$',
    view    = spot_list_for_country,
    name    = 'spot_list_for_country',
    ),
  url(
    regex   = r'^(?P<country>[a-z]{2})/(?P<state>[-\w]+)/$',
    view    = spot_list_for_state,
    name    = 'spot_list_for_state',
    ),
  url(
    regex   = r'^(?P<country>[a-z]{2})/(?P<state>[-\w]+)/(?P<city>[-\w]+)/$',
    view    = city_detail,
    name    = 'city_detail',
    ),
  url(
    regex   = r'^(?P<country>[a-z]{2})/(?P<state>[-\w]+)/(?P<city>[-\w]+)/neighborhoods/$',
    view    = neighborhood_list_for_city,
    name    = 'neighborhood_list_for_city',
    ),
  url(
    regex   = r'^(?P<country>[a-z]{2})/(?P<state>[-\w]+)/(?P<city>[-\w]+)/neighborhoods/(?P<slug>[-\w]+)/$',
    view    = spot_list_for_neighborhood,
    name    = 'spot_list_for_neighborhood',
    ),
  url(
    regex   = r'^(?P<country>[a-z]{2})/(?P<state>[-\w]+)/(?P<city>[-\w]+)/(?P<slug>[-\w]+)/$',
    view    = spot_detail,
    name    = 'spot_detail',
    ),
  url(
    regex   = r'^(?P<country>[a-z]{2})/(?P<state>[-\w]+)/(?P<city>[-\w]+)/(?P<slug>[-\w]+)/directions/$',
    view    = spot_directions,
    name    = 'spot_directions',
    ),
  url(
    regex   = r'^(?P<country>[a-z]{2})/(?P<state>[-\w]+)/(?P<city>[-\w]+)/(?P<slug>[-\w]+)/edit/$',
    view    = edit_spot,
    name    = 'edit_spot',
    ),
  url(
    regex   = r'^add/$',
    view    = add_spot,
    name    = 'add_spot',
  ),
)