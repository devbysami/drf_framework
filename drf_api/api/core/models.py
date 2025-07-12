from django.db import models
import jsonfield
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

# Create your models here.

class UserToken(models.Model):
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=500, db_index=True)
    issued_at_gmt = models.DateTimeField()
    expires_at_gmt = models.DateTimeField()
    expiry_time = models.IntegerField()

    def is_expired(self):
        return self.expires_at_gmt <= (timezone.now() + timedelta(hours=5))

    def __str__(self):
        return f"Token for {self.user.username}"
    
    @property
    def expires_in(self):
        
        if self.is_expired():
            return 0
        
        return int((self.expires_at_gmt - (timezone.now() + timedelta(hours=5))).total_seconds())

class RequestLog(models.Model):
    
   user = models.ForeignKey(User, on_delete=models.CASCADE)
   request_data = jsonfield.JSONField(default={})
   response_data = jsonfield.JSONField(default={})
   created_at = models.DateTimeField(auto_now_add=True)