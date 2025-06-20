from rest_framework.permissions import BasePermission
from rest_framework.exceptions import AuthenticationFailed
from core.models import UserToken
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from django.conf import settings
from rest_framework import permissions

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
    
