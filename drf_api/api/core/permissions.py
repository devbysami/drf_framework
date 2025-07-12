from rest_framework.permissions import BasePermission
from rest_framework.exceptions import AuthenticationFailed
from core.models import UserToken
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from django.conf import settings
from rest_framework import permissions
import json
from django.contrib.auth.models import User
from rest_framework import authentication
from rest_framework import exceptions


class IsTokenValid(BasePermission):
    
    def has_permission(self, request, view):
        auth = request.headers.get('Authorization')
        
        if not auth:
            raise AuthenticationFailed({
                "responseDescription" : "Authentication Token not provided",
                "responseCode" : "053"
            })
        
        parts = auth.split(" ")
        
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            raise AuthenticationFailed({
                "responseDescription" : "Authentication Token not provided",
                "responseCode" : "053"
            })
        
        token = parts[1]
        
        try:
            user_token = UserToken.objects.get(token=token)
        except UserToken.DoesNotExist:
            raise AuthenticationFailed({
                "responseDescription" : "Invalid Authentication Token",
                "responseCode" : "054"
            })
        
        
        if user_token.is_expired():
            raise AuthenticationFailed({
                "responseDescription" : "Authorization Token Expired",
                "responseCode" : "051"
            })
            
        request.user = user_token.user
        
        return True
    
class IsMerchantActive(BasePermission):
    
    def has_permission(self, request, view):
        
        try:
            merchant = request.user.merchant_profile
        except AttributeError:
            raise PermissionDenied({"success" : False, "message" : "Wallet not found, Please contact support!"})

        if merchant.status == "ACTIVE":
            return True
        
        raise PermissionDenied({"success" : False, "message" : "Wallet not active, Please contact support!"})
    
class HasAPIKeyPermission(permissions.BasePermission):
    """
    Custom permission to check if the request contains a valid API key.
    """

    def has_permission(self, request, view):
        # Get the API key from the request headers
        api_key = request.META.get('HTTP_API_KEY')
        # Check if the API key matches the one stored in settings.py
        if api_key == settings.WALLET_API_KEY:
            return True
        return False
    
class UserAuthentication(authentication.TokenAuthentication):
    def authenticate(self, request):

        # secret_token = request.META.get('HTTP_AUTHORIZATION')
        data = json.loads(request.body)
        phone_number = data.get('phone_number')
        secret_token = data.get('secret_key')
        # if secret_token:
        #     secret_token= secret_token.split(' ')[1]
    
        if not secret_token:
            return None
        
        try:
            ua = User.objects.get(username =phone_number, merchant_profile__secret_key=secret_token)

        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('User Unauthorized')

        return (ua, None)