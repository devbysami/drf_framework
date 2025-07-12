from django.db import models
from merchant.models import Merchant, Actions
import requests
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import transaction
import logging
import traceback
import json
from core.mongodb import db as udhaar_db
from core.async_recharge_utilities import record_deposit_to_rnp
from django.core.exceptions import ObjectDoesNotExist
from transaction.constants import RAAST_TILL_CODE_PREFIX, TILL_CODE_BASE_NUM


sucess_dictionary = {'COMPLETED': True, 'FAILED': False, 'PENDING': None}

log = logging.getLogger("django")

    
class Customer(models.Model):

    merchant = models.OneToOneField(Merchant, on_delete=models.CASCADE, related_name='raast_customer')
    record_id = models.CharField(max_length=255, unique=True)
    cnic = models.CharField(max_length=25)
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100, blank=True, null=True)
    nickname = models.CharField(max_length=100, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    json = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    biomatric_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} {self.merchant}"



class Account(models.Model):
    LEVEL_CHOICES = [
        ('L0', 'L0'),
        ('L1', 'L1'),
        ('L2', 'L2')
    ]
    
    ACCOUNT_STATUS_UNAVAILABLE = "unavailable"
    ACCOUNT_STATUS_AVAILABLE = "available"
    ACCOUNT_STATUS_ACTIVE = "active"
    ACCOUNT_STATUS_INACTIVE = "inactive"
    ACCOUNT_STATUS_CHOICES = [
        (ACCOUNT_STATUS_UNAVAILABLE, ACCOUNT_STATUS_UNAVAILABLE),
        (ACCOUNT_STATUS_AVAILABLE, ACCOUNT_STATUS_AVAILABLE),
        (ACCOUNT_STATUS_ACTIVE, ACCOUNT_STATUS_ACTIVE),
        (ACCOUNT_STATUS_INACTIVE, ACCOUNT_STATUS_INACTIVE),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='accounts')
    record_id = models.CharField(max_length=255, unique=True)
    iban = models.CharField(max_length=34)
    title = models.CharField(max_length=255)
    level = models.CharField(max_length=30, choices=LEVEL_CHOICES, default='L0')
    opening_date = models.DateField()
    closing_date = models.DateField(blank=True, null=True)
    json = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=50, choices=ACCOUNT_STATUS_CHOICES, default='available')


    def __str__(self):
        return self.iban
    
    @classmethod
    def credit(
        cls,
        amount,
        account_id,
        from_iban,
        to_iban,
        bank_name,
        rrn,
        stan,
        transmission_date_time,
        sender_name,
        comment=None
    ):
        
        try:
            
            
            with transaction.atomic():
                
                account = cls.objects.get(id=account_id)
                merchant = account.customer.merchant
                
                
                maa_deposit_kwargs = {
                    'uid': merchant.uid,
                    'deposited_by' : merchant.user,
                    'amount' : amount,
                    'asof': timezone.now(),
                    'comment' : comment,
                    'transaction_verified' : True,
                    'bank_name' : bank_name,
                    "telco_uid" : None,
                    "remote_reference_id" : rrn,
                    "partner" : "raast"
                }
                
                deposit_response = merchant.deposit(
                    **maa_deposit_kwargs
                )
                action = deposit_response["deposit"]
                
                reference = f"{action.id:012}"
                
                action.reference = reference
                action.save()
                
                raast_transaction_kwargs = {
                    "amount" : amount,
                    "account" : account,
                    "from_iban" : from_iban,
                    "to_iban" : to_iban,
                    "bank_name" : bank_name,
                    "reference" : reference,
                    "rrn" : rrn,
                    "stan": stan,
                    "transmission_date_time" : transmission_date_time,
                    "sender_name" : sender_name,
                    "created_at" : action.created,
                    "action" : action,
                    "type" : Transaction.TYPE_CREDIT
                }
                
                raast_transaction = Transaction.create(
                    **raast_transaction_kwargs
                )
                
                try:
                    
                    business = udhaar_db.businesses.find_one({
                        "user_cloud_id": merchant.user.username,
                        "is_active": True},{ "id":1, "_id":0, "name": 1 })

                    if not business:
                        business = { "id": None, "name": None}
                    
                    notify_rnp_json = {
                        "phone_number" : merchant.user.username,
                        "amount" : amount,
                        "account_number" : from_iban[-4:],
                        "account_title" : sender_name,
                        "account_bank" : bank_name,
                        "secret_key": merchant.secret_key,
                        "business_id" : business.get("id", ""),
                        "deposit_key": action.id,
                        "reference_id": reference,
                        "status": "COMPLETED",
                        "message": "COMPLETED",
                        "remote_reference_id" : rrn,
                        "service": "raast",
                        "recon" : True
                    }
                    
                    record_deposit_to_rnp(**notify_rnp_json)
                    
                except Exception as e:
                    log.exception(traceback.format_exc()) 
                    
                    
                return {
                    "transaction" : raast_transaction,
                    "action" : action,
                    "success" : True
                }
                
        except Exception as e:
            log.exception(traceback.format_exc())
            return {"success" : False}
    
    @classmethod
    def reversal(
        cls,
        amount,
        account_id,
        rrn,
        stan,
        transmission_date_time,
        bank_name,
        withdraw_transaction_id,
        to_iban
    ):
        
        try:
            
            with transaction.atomic():
                
                account = cls.objects.get(id=account_id)
                merchant = account.customer.merchant
                
                withdraw_transaction = Transaction.objects.get(account=account, id=withdraw_transaction_id)
                withdraw_action = withdraw_transaction.action
                withdraw_action.status = Actions.STATUS_TYPE_FAILED
                withdraw_action.failure_reason = "Raast Service Error"
                
                try:
                    comment = json.loads(withdraw_action.comment)
                except (TypeError, json.JSONDecodeError):
                    comment = {}
                    
                comment["failed_transaction"] = withdraw_action.id
                
                refund_action = merchant.refund(
                    uid=merchant.uid, 
                    user=merchant.user, 
                    amount=amount, 
                    comment = json.dumps(comment)
                )
                
                refund_reference = refund_action.id
                refund_action.reference = refund_reference
                refund_action.save()
                
                withdraw_action.reference = refund_reference
                withdraw_action.save()
                
                # FROM WHOM THE REFUND IS BEING DONE
                from_iban = comment.get("to_iban")
                
                raast_transaction_kwargs = {
                    "amount" : amount,
                    "account" : account,
                    "from_iban" : from_iban,
                    "to_iban" : to_iban,
                    "bank_name" : bank_name,
                    "reference" : withdraw_action.transaction.reference,
                    "rrn" : rrn,
                    "stan" : stan,
                    "transmission_date_time" : transmission_date_time,
                    "created_at" : refund_action.created,
                    "action" : refund_action,
                    "type" : Transaction.TYPE_REVERSAL
                }
                
                raast_transaction = Transaction.create(
                    **raast_transaction_kwargs
                )
                
                return {"transaction" : raast_transaction, "action" : refund_action, "success" : True}
            
        except Exception as e:
            log.exception(traceback.format_exc())
            return {"success" : False}

    @classmethod
    def process_withdraw(
        cls,
        amount,
        account_id,
        bank_name,
        to_iban,
        transaction_id,
        status,
        payment_identifier,
        transaction_identifier,
        transmission_date_time,
        stan,
        rrn,
        failure_reason
    ):
        
        try:
        
            with transaction.atomic():
                
                account = cls.objects.get(id=account_id)
                merchant = account.customer.merchant
                
                
                withdraw_response = Merchant.process_withdraw_v2(
                    user=merchant.user,
                    uid=merchant.uid, 
                    transaction_id=transaction_id, 
                    success=status,
                    failure_reason=failure_reason,
                    partner="raast"
                )
                
                if not status:
                    return {
                        "success" : False,
                        "status" : "FAILED",
                        "refund" : withdraw_response.get("refund")
                    }
                
                withdraw = withdraw_response["action"]
                
                raast_transaction_kwargs = {
                    "amount" : amount,
                    "account" : account,
                    "from_iban" : account.iban,
                    "to_iban" : to_iban,
                    "bank_name" : bank_name,
                    "reference" : withdraw.reference,
                    "payment_identifier" : payment_identifier,
                    "transaction_identifier" : transaction_identifier,
                    "transmission_date_time" : transmission_date_time,
                    "stan" : stan,
                    "rrn" : rrn,                 
                    "created_at" : withdraw.created,
                    "action" : withdraw,
                    "type" : Transaction.TYPE_DEBIT
                }
                
                raast_transaction = Transaction.create(
                    **raast_transaction_kwargs
                )
                
                return {"success" : True,  "action" : withdraw, "transaction" : raast_transaction}
        
        except Exception as e:
            log.exception(traceback.format_exc())
            return {"success" : False}

class Alias(models.Model):
    TYPE_CHOICE_MOBILE = "MOBILE"
    TYPE_CHOICE_TILL_CODE = "TILL_CODE"
    TYPE_CHOICES = [
        (TYPE_CHOICE_MOBILE, TYPE_CHOICE_MOBILE),
        (TYPE_CHOICE_TILL_CODE, TYPE_CHOICE_TILL_CODE),
    ]
    
    STATUS_LINKED = 'linked'
    STATUS_UNLINKED = 'unlinked'
    STATUS_CHOICES = [
        (STATUS_LINKED, STATUS_LINKED),
        (STATUS_UNLINKED, STATUS_UNLINKED)
    ]

    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='aliases')
    record_id = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    raast_id = models.CharField(max_length=100)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='unlinked')
    json = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.type}: {self.raast_id}"


class TillCode(models.Model):
    alias = models.OneToOneField(Alias, on_delete=models.CASCADE, null=True, blank=True, related_name='till_code')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def till_code(self):
        return f"{RAAST_TILL_CODE_PREFIX}{TILL_CODE_BASE_NUM}{str(self.id).zfill(5)}"

    def __str__(self):
        return self.till_code()


class Transaction(models.Model):
    
    TYPE_REVERSAL = "REVERSAL"
    TYPE_CREDIT = "CREDIT"
    TYPE_DEBIT = "DEBIT"
    
    TYPES_CHOICES = (
        (TYPE_CREDIT, TYPE_CREDIT),
        (TYPE_REVERSAL, TYPE_REVERSAL),
        (TYPE_DEBIT, TYPE_DEBIT),
    )
    
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name="transactions"
    )
    
    action = models.OneToOneField(
        Actions,
        on_delete=models.CASCADE,
        related_name="transaction"
    )
    
    from_iban = models.CharField(max_length=50, null=True, blank=True)
    to_iban = models.CharField(max_length=50)
    bank_name = models.CharField(max_length=50)
    reference = models.CharField(max_length=256, blank=True, null=True)
    payment_identifier = models.CharField(max_length=256, blank=True, null=True)
    transaction_identifier = models.CharField(max_length=256, blank=True, null=True)
    transmission_date_time = models.CharField(max_length=256, blank=True, null=True)
    stan = models.CharField(max_length=256, blank=True, null=True)
    rrn = models.CharField(max_length=256, blank=True, null=True)
    sender_name = models.CharField(max_length=256, blank=True, null=True)
    amount = models.IntegerField()
    created_at = models.DateTimeField()
    type = models.CharField(max_length=50, choices=TYPES_CHOICES)

    def merchant(self):
        return self.action.merchant
    
    @classmethod
    def create(
        cls,
        amount,
        account,
        from_iban,
        to_iban,
        bank_name,
        reference,
        created_at,
        type,
        action,
        sender_name=None,
        rrn=None,
        stan=None,
        transmission_date_time=None,
        transaction_identifier=None,
        payment_identifier=None
    ):
        
        transaction = cls.objects.create(
            account=account,
            action=action,
            from_iban=from_iban,
            to_iban=to_iban,
            bank_name=bank_name,
            reference=reference,
            rrn=rrn,
            stan=stan,
            transmission_date_time=transmission_date_time,
            transaction_identifier=transaction_identifier,
            payment_identifier=payment_identifier,
            sender_name=sender_name,
            amount=amount,
            created_at=created_at,
            type=type
        )
        
        return transaction

class AccountOpening(models.Model):

    STATUS_PENDING = "PENDING"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_READY = "READY"
    STATUS_FAILED = "FAILED"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_OPENING = "OPENING"
    
    STATUS_CHOICES = (
        (STATUS_PENDING, STATUS_PENDING),
        (STATUS_IN_PROGRESS, STATUS_IN_PROGRESS),
        (STATUS_READY, STATUS_READY),
        (STATUS_FAILED, STATUS_FAILED),
        (STATUS_COMPLETED, STATUS_COMPLETED),
        (STATUS_CANCELLED, STATUS_CANCELLED),
        (STATUS_OPENING, STATUS_OPENING),
    )

    merchant = models.ForeignKey(Merchant, 
                on_delete=models.CASCADE, related_name='account_opening')
    
    # citizen API response 
    citizen_verified = models.BooleanField(null=True, blank=True)
    full_name = models.CharField(max_length=50, null=True, blank=True)
    cnic = models.CharField(max_length=15, null=True, blank=True)
    dob = models.DateField(max_length=50, null=True, blank=True)
    gender = models.CharField(max_length=10, null=True, blank=True)
    phone_number = models.CharField(max_length=11, null=True, blank=True)
    nationality = models.CharField(max_length=20, null=True, blank=True)
    mother_name = models.CharField(max_length=20, null=True, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    place_of_birth = models.CharField(max_length=50, null=True, blank=True)

    # AML API response 
    aml_verified = models.BooleanField(null=True, blank=True)
    pephit = models.BooleanField(default=False)
    sanction_hit = models.BooleanField(default=False)
    enforcement_hit = models.BooleanField(default=False)
    blackList_hit = models.BooleanField(default=False)
    clientList_hit = models.BooleanField(default=False)
    adversemedia_hit = models.BooleanField(default=False)
    risk_level = models.CharField(max_length=10, null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    failure_reason = models.CharField(max_length=256, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def aml_id(self):
        try:
            return self.merchant.aml_screening.idenfo_id
        except ObjectDoesNotExist:
            return None
    class Meta:
        permissions = [
            ("can_verify_citizen", "Can mark citizen as verified"),
            ("can_verify_aml", "Can mark AML as verified"),
            ("can_open_raast_account", "Can open Raast account"),
        ]
    