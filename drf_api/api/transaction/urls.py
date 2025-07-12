from .views import *
from django.conf.urls import url


urlpatterns = [
    url(r'^credit$', CreditView.as_view(), {'auth': False,'ip_security':'all'}),
    url(r'^title/fetch$', TitleFetch.as_view(), {'auth': False,'ip_security':'all'}),
    url(r'^reversal$', ReversalView.as_view(), {'auth': False,'ip_security':'all'}),
]