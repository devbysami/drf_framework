import redis
from django.conf import settings
import logging
from django.utils import timezone
import json

django_log = logging.getLogger("django")


conn = redis.Redis(host=settings.REDIS_HOST,port=settings.REDIS_PORT, db=settings.REDIS_DB)

conn_udhaar = redis.Redis(
    host=settings.REDIS_UDHAAR_HOST, db=settings.REDIS_UDHAAR_DB, charset="utf-8", decode_responses=True)


def get_redis_list_name(phone_number):
    return settings.ENV+phone_number+'TRANSACTIONS'

    
def get_redis_head_name(phone_number):
    return settings.ENV+phone_number+'HEAD'


def update_redis_head(phone_number,id):
    try:
        head_name= get_redis_head_name(phone_number)
        conn.set(head_name,id)
    except Exception as e:
        django_log.exception(e)
        
class RedisWalletCache:
    
    TIMESTAMP_HASH_KEY = "wallet_timestamps"
    CACHE_HASH_KEY = "wallet_cache"
    
    WALLET_CACHE_IDENTIFIERS = [
        "telcos",
        "billers",
        "vouchers"
    ]
    
    def reset(self):
        
        timestamp_now = int(round(timezone.now().timestamp() * 1000))
        
        TIMESTAMPS = {
            key : timestamp_now for key in self.WALLET_CACHE_IDENTIFIERS
        }
        
        WALLET_CACHE = {
            key : "" for key in self.WALLET_CACHE_IDENTIFIERS if key != "telcos"
        }
        
        conn_udhaar.hmset(self.TIMESTAMP_HASH_KEY, TIMESTAMPS)
        conn_udhaar.hmset(self.CACHE_HASH_KEY, WALLET_CACHE)
        
    def set_value(self, type, obj):
        
        if type == "telcos":
            return
        
        conn_udhaar.hset(self.CACHE_HASH_KEY, type, json.dumps(obj))
        
    def clear_value(self, type):
        
        if type == "telcos":
            return
        
        conn_udhaar.hset(self.CACHE_HASH_KEY, type, "")
    
    def update_timestamp(self, type):
        timestamp_now = int(round(timezone.now().timestamp() * 1000))
        conn_udhaar.hset(self.TIMESTAMP_HASH_KEY, type, timestamp_now)
        
    def clear_and_update_timestamp(self, type):
        self.clear_value(type)
        self.update_timestamp(type)
        
    def get_value(self, type):
        
        value = conn_udhaar.hget(self.CACHE_HASH_KEY, type)
        
        if value:
            return json.loads(value)
        
        return None

rds_cache = RedisWalletCache()