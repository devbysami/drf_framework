from django.db import models
from django.db import transaction
import uuid
from django.contrib.auth.models import User
from django.db.models import F, Sum
from datetime import datetime
import json
from django.core.exceptions import ValidationError
from django.core.exceptions import ObjectDoesNotExist
import re
import base64

def random_secret_key():
    return uuid.uuid4().hex

def generate_unique_id():
    """Returns a unique, 16 byte, URL safe ID by combining UUID and Base64
    """
    rv = base64.b64encode(uuid.uuid4().bytes).decode('utf-8')
    return re.sub(r'[\=\+\/]', lambda m: {'+': '-', '/': '_', '=': ''}[m.group(0)], rv)

# Create your models here.


class Merchant(models.Model):
    USER_TYPE = (
        ('consumer', 'Consumer'),
        ('business', 'Business'),
        ('rupi', 'Rupi'),
        ('booker', 'Booker'),
    )

    LEVEL_CHOICES = [
        ('L1', 'L1'),
        ('L2', 'L2')
    ]

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_INACTIVE = 'INACTIVE'
    STATUS_ON_HOLD = 'ON_HOLD'

    STATUS_CHOICES = (
        (STATUS_ACTIVE, STATUS_ACTIVE.title()),
        (STATUS_INACTIVE, STATUS_INACTIVE.title()),
        (STATUS_ON_HOLD, STATUS_ON_HOLD.title()),
    )

    MIN_BALANCE = 0

    uid = models.UUIDField(
        unique=True,
        editable=False,
        default=uuid.uuid4,
        verbose_name='Public identifier',
    )

    user = models.OneToOneField(User,
                                related_name='merchant_profile',
                                on_delete=models.PROTECT)

    merchant_type = models.CharField(max_length=25, default="Oscar")
    created = models.DateTimeField(
        blank=True,
        editable=False,
        auto_now_add=True
    )
    modified = models.DateTimeField(
        blank=True,
        editable=False,
        auto_now_add=True
    )
    current_balance = models.FloatField(
        verbose_name='Current balance',
        default=0.0,
    )
    secret_key = models.CharField(max_length=32, default=random_secret_key)
    realm_user_id = models.CharField(max_length=45, blank=True, null=True, db_index=True)
    city = models.CharField(max_length=50, blank=True, null=True)
    province = models.CharField(max_length=75, blank=True, null=True)
    user_type = models.CharField(
        max_length=100, choices=USER_TYPE, 
        default="business",
        null=True, blank=True
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    
    credit_blocked = models.BooleanField(default=False)
    
    def __str__(self):
        return self.user.username
    
    @property
    def current_balance_pkr(self):
        return self.current_balance/100
    
    
    @property
    def is_raast_active(self):
        
        try:
            raast_customer = self.raast_customer
        except Exception as e:
            raast_customer = None
        
        return raast_customer is not None



    @classmethod
    def create(cls, user, created_by, asof, secret_key=uuid.uuid4().hex):
        """Create account.
         user (User):
            Owner of the account.
        created_by (User):
            User that created the account.
        asof (datetime.datetime):
            Time of creation.

        Returns (tuple):
            [0] Account
            [1] Action
        """
        with transaction.atomic():
            account = cls.objects.create(
                user=user,
                created=asof,
                modified=asof,
                secret_key=secret_key,
                current_balance=0,
            )

            return account

class Actions(models.Model):
    
    class Meta:
        verbose_name = 'Merchant Transaction'
        verbose_name_plural = 'Merchant Transactions'

    ACTION_TYPE_CREATED = 'CREATED'
    ACTION_TYPE_PROFIT = 'PROFIT'
    ACTION_TYPE_DEPOSITED = 'DEPOSITED'
    ACTION_TYPE_RECHARGE = 'RECHARGE'
    ACTION_TYPE_COMMISSION='COMMISSION'
    ACTION_TYPE_WITHDRAW='WITHDRAW'
    ACTION_TYPE_CASH_BACK='CASH_BACK'
    ACTION_TYPE_REFUND='REFUND'
    ACTION_TYPE_SALARY='SALARY'
    ACTION_TYPE_CORRECTION='CORRECTION'
    ACTION_TYPE_PROMOTION='PROMOTION'
    ACTION_TYPE_BILLING= 'BILL_PAYMENT'
    ACTION_TYPE_FEE='FEE'
    ACTION_TYPE_TRANSFER='TRANSFER'
    ACTION_TYPE_PAYMENT='PAYMENT'
    ACTION_TYPE_RETAILER_DEPOSIT='RETAILER_DEPOSIT'
    ACTION_TYPE_RETAILER_WITHDRAW='RETAILER_WITHDRAW'
    ACTION_TYPE_LOAN='LOAN'
    ACTION_TYPE_LOAN_DISBURSE='LOAN_DISBURSE'
    ACTION_TYPE_LOAN_REPAYMENT='LOAN_REPAYMENT'
    ACTION_TYPE_BOOK_TICKET='BOOK_TICKET'
    ACTION_TYPE_CANCEL_TICKET='CANCEL_TICKET'
    ACTION_TYPE_VOUCHER_PAYMENT='VOUCHER_PAYMENT'
    ACTION_TYPE_SMS_BUNDLE_PAYMENT='SMS_BUNDLE_PAYMENT'
    
    WITHDRAWAL_TRANSACTION_TYPES = [ACTION_TYPE_WITHDRAW, ACTION_TYPE_SALARY, ACTION_TYPE_TRANSFER]

    ACTION_TYPE_CHOICES = (
        (ACTION_TYPE_CREATED, 'Created'),
        (ACTION_TYPE_PROFIT, 'Profit'),
        (ACTION_TYPE_DEPOSITED, 'Deposited'),
        (ACTION_TYPE_RECHARGE, 'Recharge'),
        (ACTION_TYPE_COMMISSION,'Commission'),
        (ACTION_TYPE_WITHDRAW,'Withdraw'),
        (ACTION_TYPE_CASH_BACK, 'CashBack'),
        (ACTION_TYPE_REFUND,'Refund'),
        (ACTION_TYPE_SALARY,'Salary'),
        (ACTION_TYPE_CORRECTION,'Correction'),
        (ACTION_TYPE_PROMOTION, 'Promotion'),
        (ACTION_TYPE_BILLING, 'BillPayment'),
        (ACTION_TYPE_FEE,'Fee'),
        (ACTION_TYPE_TRANSFER,'Transfer'),
        (ACTION_TYPE_PAYMENT,'Payment'),
        (ACTION_TYPE_RETAILER_DEPOSIT,'RetailerDeposit'),
        (ACTION_TYPE_RETAILER_WITHDRAW,'RetailerWithdraw'),
        (ACTION_TYPE_LOAN,'Loan'),
        (ACTION_TYPE_LOAN_DISBURSE,'LoanDisburse'),
        (ACTION_TYPE_LOAN_REPAYMENT,'LoanRepayment'),
        (ACTION_TYPE_BOOK_TICKET,'BookTicket'),
        (ACTION_TYPE_CANCEL_TICKET,'CancelTicket'),
        (ACTION_TYPE_VOUCHER_PAYMENT,'VoucherPayment'),


    )

    STATUS_TYPE_PENDING='PENDING'
    STATUS_TYPE_COMPLETED='COMPLETED'
    STATUS_TYPE_FAILED='FAILED'


    STATUS_TYPE_CHOICES = (
        (STATUS_TYPE_PENDING, 'Pending'),
        (STATUS_TYPE_COMPLETED, 'Completed'),
        (STATUS_TYPE_FAILED, 'Failed'))


    REFERENCE_TYPE_BANK_TRANSFER = 'BANK_TRANSFER'
    REFERENCE_TYPE_CHECK = 'CHECK'
    REFERENCE_TYPE_CASH = 'CASH'
    REFERENCE_TYPE_NONE = 'NONE'
    REFERENCE_TYPE_CHOICES = (
        (REFERENCE_TYPE_BANK_TRANSFER, 'Bank Transfer'),
        (REFERENCE_TYPE_CHECK, 'Check'),
        (REFERENCE_TYPE_CASH, 'Cash'),
        (REFERENCE_TYPE_NONE, 'None'),
    )

    TELCO_CHOICES = (
        ('TELENOR', 'Telenor'),
        ('ZONG', 'Zong'),
    )

    user_friendly_id = models.CharField(
        unique=True,
        editable=False,
        max_length=30,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        help_text='User who performed the action.',
    )

    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.PROTECT,
        related_name='merchant_accout_action',
    )
    # merchant_account = models.ForeignKey(
    #     MerchantAccounts,
    #     on_delete=models.PROTECT
    # )
    type = models.CharField(
        max_length=30,
        choices=ACTION_TYPE_CHOICES,
        db_index=True
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_TYPE_CHOICES,
        null=True,
        default=None
    )

    reference = models.CharField(max_length=60,
        blank=True, null=True, db_index=True
    )
    reference_type = models.CharField(
        max_length=30,
        choices=REFERENCE_TYPE_CHOICES,
        default=REFERENCE_TYPE_NONE,
    )
    telco = models.CharField(
        max_length=30,blank=True,null=True
    )
    bank_name = models.CharField(
        max_length=30,default=None,blank=True,null=True,
    )
    customer_phone = models.CharField(
        max_length=15,
        blank=True,
        null=True
    )
    comment = models.TextField(
        blank=True,
    )

    failure_reason=models.TextField(blank=True, null=True)

    debug_balance = models.IntegerField(
        help_text='Balance after the action.',
    )
    deposit_fee = models.FloatField(
        help_text='Deposit Fee',
        default=0
    )

    offer_key=models.CharField(
        max_length=30,
        
        null=True,
        default=None
    )
    remote_reference_id =models.CharField(
        max_length=30,
        
        null=True,
        default=None
    )

    transaction_verified= models.BooleanField(default=True,db_index=True)

    order_key=models.CharField(max_length=50,null=True, default=None)



    device_id=models.CharField(max_length=40, null=True, default=None)

    base_currency=models.CharField(max_length=10, default='PKR')
    base_currency_delta=models.FloatField(null=True)

        
    @classmethod
    def create(
        cls,
        user,
        merchant,
        # merchant_account,
        telco_uid,
        type,
        delta,
        asof,
        deposit_fee=0,
        customer_phone=None,
        reference=None,
        reference_type='CASH',
        comment=None,
        status=None,
        failure_reason=None,
        offer_key=None,
        remote_reference_id=None,
        bank_name=None,
        transaction_verified=True,
        order_key=None,
        device_id=None,
        base_currency='PKR',
        base_currency_delta=None
    ):
        """Create Action.        user (User):
            User who executed the action.
        account (Account):
            Account the action executed on.
        type (str, one of Action.ACTION_TYPE_*):
            Type of action.
        delta (int):
            Change in balance.
        asof (datetime.datetime):
            When was the action executed.
        reference (str or None):
            Reference number when appropriate.
        reference_type(str or None):
            Type of reference.
            Defaults to "NONE".
        comment (str or None):
            Optional comment on the action.        Raises:
            ValidationError        Returns (Action)
        """
        assert asof is not None

        if (type == cls.ACTION_TYPE_DEPOSITED and reference_type is None):
            raise ValidationError({
                'reference_type': 'required for deposit.',
            })

        if reference_type is None:
            reference_type = cls.REFERENCE_TYPE_NONE
        if reference is None:
            reference = ''
        if comment is None:
            comment = ''

        user_friendly_id = generate_unique_id()

        if type == cls.ACTION_TYPE_WITHDRAW or type == cls.ACTION_TYPE_SALARY:
            if user_friendly_id.startswith('-') or user_friendly_id.startswith('='):
                
                while True:
                    user_friendly_id=user_friendly_id[1:]

                    if not user_friendly_id.startswith('-') and not user_friendly_id.startswith('='):
                        break


        action=cls.objects.create(
            user_friendly_id=user_friendly_id,
            created=asof,
            user=user,
            merchant=merchant,
            # merchant_account=merchant_account,
            telco=telco_uid,
            customer_phone=customer_phone,
            type=type,
            delta=delta,
            reference=reference,
            reference_type=reference_type,
            comment=comment,
            debug_balance=min([int(merchant.current_balance),2147483647]),
            deposit_fee=deposit_fee,
            status=status,
            failure_reason=failure_reason, 
            offer_key=offer_key,
            remote_reference_id=remote_reference_id,
            bank_name = bank_name,
            transaction_verified= transaction_verified,
            order_key=order_key,
            device_id=device_id,
            base_currency=base_currency,
            base_currency_delta=base_currency_delta
        )

        #head_name= get_redis_head_name(user.username)
        #conn.set(head_name,action.id)
        
        return action
