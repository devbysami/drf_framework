
from pymongo import MongoClient
from django.conf import settings

if settings.MONGO_DB_AUTH:
    mongo_client = MongoClient(
        'mongodb://%s:%s@%s:%s/?authSource=admin' % (
            settings.MONGO_USER, 
            settings.MONGO_PASSWORD, 
            settings.MONGO_IP, 
            settings.MONGO_PORT),
        connect=False)

else:
    mongo_client = MongoClient(
        'mongodb://%s:%s'%(
            settings.MONGO_IP, 
            settings.MONGO_PORT), 
        connect=False)

db =  mongo_client[settings.MONGO_DB]