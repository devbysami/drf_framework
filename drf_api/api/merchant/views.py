from rest_framework.response import Response
import logging
from core.utils import WalletView
import traceback
from core.redis_ops import rds_cache
from django.apps import apps

log = logging.getLogger("django")


def get_voucher_data():

    cache_value = rds_cache.get_value(type="vouchers")
    
    if cache_value:
        return cache_value

    data=[]
    
    popular = ['Free Fire', 'PUBG [US]', 'RazerGold [USA]']
    
    all_vendors=apps.get_model('vouchers', 'vendor').objects.filter(
        active=True, name__in=popular
    )

    for vendor in all_vendors:
        
        insertion = {
            'vendor_name' : vendor.name,
            'icon' : vendor.icon, 
            'commission' : vendor.commission,
            'favicon':vendor.favicon,
            'vouchers' : []
        }
        
        for voucher in vendor.vouchers.filter(active=True):
            
            dc = { 
                'voucher_id':voucher.id,
                'voucher_type':voucher.name, 
                'price':voucher.cost_original,
                'short_description':voucher.short_description,
                'long_description':voucher.long_description
            }

            if voucher.cost_discounted < voucher.cost_original:
                dc['dicounted_price']= voucher.cost_discounted
                
            else:
                dc['dicounted_price']= None

            icons = voucher.icon
            icons = icons.split(',') 
            dc['icon']= icons             
            
            insertion['vouchers'].append(dc)

        if insertion['vouchers']:
            data.append(insertion)

    rds_cache.set_value(type="vouchers", obj=data)
    
    return data

def get_billers_data(earning_rule=None):
    
    cache_value = rds_cache.get_value(type="billers")

    if cache_value:
        return cache_value

    biller_model=apps.get_model('bills', 'billers')
    
    available_business_type = list(biller_model.objects.filter(
        active=True,
        business__in=['Electricity', 'Gas', 'Internet']
    ).values_list('business', flat=True))
    
    available_business_types= list(set(available_business_type))

    res = []
    
    for business_type in available_business_types:
        
        dict_type = {}
        dict_type['business'] = business_type
        
        logo = biller_model.objects.filter(business=business_type)[0].business_icon
        
        dict_type['business_icon'] = logo
        
        dict_type['business_list'] = list(biller_model.objects.filter(
            business=business_type,
            active=True
        ).values(
            'name',
            'icon',
            'commission',
            'commission_type',
            'start',
            'len_of_consumer_number'
        ))
        
        dict_type["earning_rule"] = earning_rule
        
        res.append(dict_type)
        
    rds_cache.set_value(type="billers", obj=res)

    return res

# Create your views here.

class Wallet(WalletView):
    
    def is_active_wallet_user(self, merchant):
        return merchant.merchant_accout_action.exists()
    
    def fetch_data_type_obj(self, merchant, data_type, earning_rules):
        
        data = {}
        
        if data_type == "billers":
            data['available_billers'] = get_billers_data(earning_rules.get("pay-bill"))
            
        elif data_type == "vouchers":
            data['available_vouchers'] = get_voucher_data()
            
        return data
        
    
    def post(self, request, format=None, **kwargs):
        
        try:
            
            log.info("Data Reveived for Wallet V5")
            log.info(request.data)
        
            merchant = request.user.merchant_profile
            earning_rules = request.data.get("earning_rules", {})
            
            data = {
                "current_balance" : merchant.current_balance / 100
            }
            
            data_type = request.data.get("data_type", None)
            
            if data_type:
                optimized_data = self.fetch_data_type_obj(merchant, data_type, earning_rules)
                optimized_data["success"] = True
                return Response(optimized_data, status=200)
            
            data['available_vouchers'] = get_voucher_data()
            data['available_billers'] = get_billers_data(earning_rules.get("pay-bill"))
            data["is_active_wallet_user"] = self.is_active_wallet_user(merchant)
            
            data["success"] = True
            
            return Response(data, status=200)

        except Exception as e:
            log.exception(traceback.format_exc())
            return Response({
                "success" : False,
                "message" : "Internal Server Error"
            }, status=500)