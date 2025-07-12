import json
import logging
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework import status
from django.http import HttpResponse, QueryDict, JsonResponse
from django.contrib.auth.models import User
from rest_framework.request import Request as RestFrameworkRequest
from rest_framework.views import APIView
from django_pglocks import advisory_lock
import uuid
import datetime
import os
from django.conf import settings
from django.http import HttpResponseForbidden
from django.urls import resolve


if not os.path.exists(settings.LOGS_FOLDER_NAME):
    os.mkdir(settings.LOGS_FOLDER_NAME)


allowed_ips = {'all': [], 'hbl': [],'internal_data':[]}
list_of_exempted_endpoints=[('/merchant/wallet/','POST'),('merchant/list/telcos/','POST'),
                        ('available/telcos/', 'GET'), ('recharge/v2/', 'GET'),
                        ('deposit/v2/','GET'), ('/loan/agreement/','GET')]

allowed_merchants=[]

def load_ip_list():

    def get_ips(filename):
        ips_list_final=[]
        try:
            ips=open('%s_ips.txt'%filename,'r').readlines()
            for ip in ips:
                ip=ip.strip()
                if ip:
                    ips_list_final.append(ip)
        except:
            pass
        return ips_list_final

    return {f:get_ips(f) for f in ['all', 'hbl','kunda','internal_data']}


    
def load_white_listed_merchants():
    try:
        file_white_listed_merchants=open('white_listed_merchants.txt','r')
    except:
        return
    all_merchants=file_white_listed_merchants.readlines()
    
    for merchants in all_merchants:
        merchants=merchants.strip()
        allowed_merchants.append(merchants)
    


allowed_ips = load_ip_list()
load_white_listed_merchants()


class UdhaarAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def unauthorized_response(self, request):
        response = JsonResponse(
            {"detail": "Invalid Credentials"},
            content_type="application/json",
            status=status.HTTP_401_UNAUTHORIZED,
        )
        # response.accepted_renderer = JSONRenderer()
        # response.accepted_media_type = "application/json"
        # response.renderer_context = {}

        return response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if view_kwargs.get('auth') is False:
            return None
        elif view_kwargs.get('auth') is True:
            data =json.loads(request.body)
            user = User.objects.filter(username=data.get('phone_number'),
                                           merchant_profile__secret_key=data.get('secret_key'))
            if user:
                return None
            else:
                response = self.unauthorized_response(request)
                return response


        
'''
    def process_view(self, request, view_func, view_args, view_kwargs):
        data = request.POST or (type(request.body) is not bytes and json.loads(request.body))
        # try:
        #     print("try Block")
        #     print(type(request.body) == bytes)
        #     data = json.loads(request.body)
        # except Exception as e:
        #     print("Except block")
        #     print(e)
        #     response = self.unauthorized_response(request)
        #     return response

        if type(data) is bool:
            return None
        if 'BillInquiry' in data or 'BillPayment' in data:
            return None

        if view_kwargs.get('auth', False):
            if data.get('auth_type', False) == 'oscar':
                user = User.objects.filter(username=data.get('phone_number'),
                                           merchant_profile__secret_key=data.get('secret_key'))
                if user:
                    return None
                else:
                    response = self.unauthorized_response(request)
                    return response
            else:
                conn = get_db_connection()
                cur = conn.cursor()

                phone_number = data.get('phone_number')
                code = data.get('activation_code')

                cur.execute("""SELECT * from accounts_dukaanaccount
                    where phone_number = '%s' AND activation_code = '%s'""" % (phone_number, code))
                if cur.fetchall():
                    return None
                else:
                    response = self.unauthorized_response(request)
                    return response
'''








class IPBlockingMiddleware:
    
    

    def __init__(self, get_response):
        self.get_response = get_response

    def unauthorized_response(self, request):
        response = JsonResponse(
            {"detail": "IP Blocked"},
            content_type="application/json",
            status=status.HTTP_401_UNAUTHORIZED,
        )
       
        return response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self,request, view_func, view_args, view_kwargs):
        
        if settings.ENV == "LOCAL": return None

        ip = request.META['REMOTE_ADDR']
        
        if '/admin/' in request.path or '/media/' in request.path:
            return None

        if view_kwargs.get('ip_security') == 'all':
            if ip in allowed_ips['all']:
                return None
            else:
                params=json.loads(request.body)

                if params.get('phone_number') in allowed_merchants:
                    return None
        
        elif view_kwargs.get('ip_security') == 'kunda':
            if ip in allowed_ips['kunda']:
                return None
        
        elif view_kwargs.get('ip_security') == 'internal_data':
            if ip in allowed_ips['internal_data']:
                return None

        elif view_kwargs.get('ip_security') == 'disabled':
            return None
        
        return self.unauthorized_response(request)





class SyncLockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def limit_response(self):
        response = JsonResponse(
            {"detail": "Too many requests"},
            content_type="application/json",
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        return response
    
    
    def __call__(self, request):
        paybill_url = 'bills/billpay/'
        send_money_v3_url = 'api/sendmoney/v3/'
        oscar_wallet_urls = {
            "/oscar-wallet/wallet-balance/",
            "/oscar-wallet/beneficiary/",
            "/oscar-wallet/otp/",
            "/oscar-wallet/wallet-activity/",
            "/oscar-wallet/titlefetch/",
            "/oscar-wallet/wallet-withdraw-report/",
            "/oscar-wallet/current-balance/",
            "/oscar-wallet/single-payment/",
            "/oscar-wallet/banks/v2/",
            "/oscar-wallet/deposit-breakdown-report/"
        }
        whitelist_urls = {
            '/admin/',
            'sharereward',
            '/payments/deposit_funds_to_merchant/',
            '/payments/send_money_to_supplier/',
            'agent/creditaccount/',
            'agent/merchanttransactions/',
            paybill_url,
            'loyalty/balance/',
            send_money_v3_url
        }
        whitelist_urls.update(oscar_wallet_urls)
        if (paybill_url in request.path) and (request.method == 'POST'): # remove incase it is POST Request
            whitelist_urls.remove((paybill_url))

        if (send_money_v3_url in request.path) and (request.method == 'POST'): # remove incase it is POST Request
            whitelist_urls.remove((send_money_v3_url))

        if any(url in request.path for url in whitelist_urls):
            response = self.get_response(request)
            return response

        try:
            data =json.loads(request.body)
        except Exception as e:
            logging.info("REQUEST BODY")
            logging.info(request.body)
            logging.exception(e)
            data ={}
        
        
        if data.get('phone_number') or data.get('username'):
            
            for tup in list_of_exempted_endpoints:
                if tup[0] in request.path:
                    if request.method == tup[1]:
                        response = self.get_response(request)
                        return response


            
            
            try:
                phone_number = data['phone_number']
            except:
                phone_number = data['username']
            with advisory_lock(lock_id=phone_number, wait=False) as acquired:
                if acquired is False:
                    return self.limit_response()
                
                response = self.get_response(request)
                return response
        else:
            response = self.get_response(request)

            return response