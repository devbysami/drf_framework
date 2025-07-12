from .views import *
from django.conf.urls import url

urlpatterns = [
    url(r'^wallet/$', Wallet.as_view(), {'auth': True,'ip_security':'all'}),
] 