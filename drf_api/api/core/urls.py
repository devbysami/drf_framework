from django.conf.urls import url
from .views import *

urlpatterns = [
    url(r'^generate/token$', TokenGenerationView.as_view(), {'auth': False,'ip_security':'all'})
]