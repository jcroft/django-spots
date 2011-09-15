from django.forms.fields import CharField
from django.forms.util import ErrorList
from django.core.exceptions import ValidationError

from spots.widgets import *
from spots.utils import *

class CityField(CharField):
  default_error_messages = {
    'invalid': 'The city you entered was unable to be parsed. Perhaps you can be more specific?',
  }
  
  widget = CityInput
  def clean(self, value):
    if value:
      city = get_city_from_address(value.encode('ascii', 'xmlcharrefreplace'))
      if city is None:
        raise ValidationError(self.error_messages['invalid'])
      return city
    else:
      return None
    