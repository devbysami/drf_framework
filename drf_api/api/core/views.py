import logging
from core.models import UserToken
import secrets
import traceback
from rest_framework.response import Response
from datetime import timedelta
from django.contrib.auth.models import User
from django.utils import timezone
from core.permissions import IsTokenValid
from rest_framework.views import APIView
from rest_framework.response import Response
import logging
import traceback

log = logging.getLogger("django")



log = logging.getLogger("django")

class AuthView(APIView):
    
    permission_classes = [IsTokenValid]
    
    PROCESSED_OK = "Success"
    INVALID_USERNAME = "Invalid Username"
    INVALID_PASSWORD = "Invalid Password"
    TOKEN_EXPIRED = "Authorization Token Expired"
    USER_INACTIVE = "User Not Authorized"
    TECHNICAL_PROBLEM = "Cancellation requested following technical problems resulting in an erroneous transaction"
    CREDENTIALS_NOT_PROVIDED = "Authentication Token not provided"
    INVALID_CREDENTIALS = "Invalid Authentication Token"
    INCORECT_ACCOUNT_NUMBER = "Account number is invalid or missing."
    ACCOUNT_INACTIVE = "Account Inactive"
    NO_ORIGINAL_TRANSACTION_RECEIVED = "Original credit transfer never received"
    ALREADY_RETURNED_TRANSACTION = "Already returned original SCT"
    BANK_NOT_FOUND = "Bank not found"
    BLOCKED_ACCOUNT = "Account specified is blocked prohibiting posting of transactions against it"
    DUPLICATE_PAYMENT = "Payment is a duplicate of another payment"
    INVALID_AMOUNT = "Amount is invalid or missing"
    LIMIT_OUT = "Specific transaction/message amount is greater than allowed maximum"
    
    RESPONSE_CODES = {
        PROCESSED_OK : "000",
        INVALID_USERNAME : "049",
        INVALID_PASSWORD : "050",
        TOKEN_EXPIRED : "051",
        USER_INACTIVE : "052",
        TECHNICAL_PROBLEM : "021",
        CREDENTIALS_NOT_PROVIDED : "053",
        INVALID_CREDENTIALS : "054",
        INCORECT_ACCOUNT_NUMBER : "001",
        ACCOUNT_INACTIVE : "008",
        NO_ORIGINAL_TRANSACTION_RECEIVED : "015",
        ALREADY_RETURNED_TRANSACTION : "011",
        BANK_NOT_FOUND : "020",
        BLOCKED_ACCOUNT : "004",
        DUPLICATE_PAYMENT : "012",
        INVALID_AMOUNT : "010",
        LIMIT_OUT : "007"
    }

class TokenGenerationView(AuthView):
    
    permission_classes = []
    
    def generate_token(self, user, expiration_seconds=31536000):
        
        try:
            user_token = UserToken.objects.filter(user=user).order_by('-id').first()

            if user_token and not user_token.is_expired():
                return {
                    "access_token": user_token.token,
                    "token_type": "Bearer",
                    "expires_in": user_token.expires_in,
                    "userName": user.username,
                    "issued_at": user_token.issued_at_gmt.strftime('%a, %d %b %Y %H:%M:%S GMT'),
                    "expires_at": user_token.expires_at_gmt.strftime('%a, %d %b %Y %H:%M:%S GMT')
                }
                
        except UserToken.DoesNotExist:
            pass
        
        token = secrets.token_urlsafe(64)

        issued_at = timezone.now() + timedelta(hours=5)
        expires_at = issued_at + timedelta(seconds=expiration_seconds)

        UserToken.objects.create(
            user=user,
            token=token,
            expires_at_gmt=expires_at,
            expiry_time=expiration_seconds,
            issued_at_gmt=issued_at
        )

        return {
            "access_token" : token,
            "token_type" : "Bearer",
            "expires_in" : expiration_seconds,
            "userName" : user.username,
            "issued_at" : issued_at.strftime('%a, %d %b %Y %H:%M:%S GMT'),
            "expires_at" : expires_at.strftime('%a, %d %b %Y %H:%M:%S GMT')
        }
    
    def post(self, request, *args, **kwargs):
                
        try:
        
            username = request.data.get("username")
            password = request.data.get("password")
            
            auth_response = self.authenticate_user(
                username, password
            )
            auth_success = auth_response.pop("success")
            
            if not auth_success:
                return Response(auth_response, status=200)
            
            user = auth_response.get("user")
            token_response = self.generate_token(user)
            
            return Response(token_response, status=200)

        except Exception as e:
            log.exception(traceback.format_exc())
            return Response({
                "responseDescription" : self.SYSTEM_EXEPTION,
                "responseCode" : self.RESPONSE_CODES.get(self.SYSTEM_EXEPTION)
            }, status=200)
        
    
    def authenticate_user(self, username, password):
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return {
                "success" : False,
                "responseDescription" : self.INVALID_USERNAME,
                "responseCode" : self.RESPONSE_CODES.get(self.INVALID_USERNAME)
            }
        
        if not user.is_active:
            return {
                "success" : False,
                "responseDescription" : self.USER_INACTIVE,
                "responseCode" : self.RESPONSE_CODES.get(self.USER_INACTIVE)
            }
        
        if not user.check_password(password):
            return {
                "success" : False,
                "responseDescription" : self.INVALID_PASSWORD,
                "responseCode" : self.RESPONSE_CODES.get(self.INVALID_PASSWORD)
            }
        
        return {
            "success" : True,
            "user" : user
        }