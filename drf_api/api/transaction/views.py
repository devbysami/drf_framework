from core.views import AuthView
from core.permissions import IsTokenValid
from rest_framework.views import APIView
from transaction.models import Account, Transaction
from rest_framework.response import Response
from merchant.models import Merchant, MerchantLimits
import logging
import traceback
import json
from core.decorators import log_request_response

log = logging.getLogger("django")

class TitleFetch(AuthView):            
    
    @log_request_response
    def post(self, request, *args, **kwargs):
        
        account_number = request.data.get("toAccountNumber")
        
        try:
            
            account = self.fetch_account(account_number)
            
            if not account:
                return Response({
                    "responseDescription" : self.INCORECT_ACCOUNT_NUMBER,
                    "responseCode" : self.RESPONSE_CODES.get(self.INCORECT_ACCOUNT_NUMBER)
                }, status=200)
            
            return Response({
                "responseCode" : self.RESPONSE_CODES.get(self.PROCESSED_OK),
                "accountTitle" : account.title,
                "beneficiaryIBAN" : account.iban
            }, status=200)
            
        except Exception as e:
            log.exception(traceback.format_exc())
            return Response({
                "responseDescription" : self.TECHNICAL_PROBLEM,
                "responseCode" : self.RESPONSE_CODES.get(self.TECHNICAL_PROBLEM)
            }, status=200)


class CreditView(AuthView):
    
    def is_limit_available(self, merchant, amount):
        
        merchant_limit = MerchantLimits(merchant.user.username)

        available_limit = merchant_limit.available_credit_limit
        
        if amount <= available_limit:
            return True
        
        return False
    
    @log_request_response
    def post(self, request, *args, **kwargs):
        
        try:
        
            to_iban = request.data.get("toAccountNumber")
            
            try:
                amount = int(request.data.get("transactionAmount"))
            except Exception:
                return Response({
                    "responseDescription" : self.INVALID_AMOUNT,
                    "responseCode" : self.RESPONSE_CODES.get(self.INVALID_AMOUNT)
                })
            
            from_iban = request.data.get("fromAccountNumber")
            from_bank = request.data.get("fromBankIMD")
            rrn = request.data.get("rrn")
            stan = request.data.get("stan")
            transmissionDate = request.data.get("transmissionDate")
            transmissionTime = request.data.get("transmissionTime")
            
            if self.is_duplicate_transaction(rrn):
                return Response({
                    "responseDescription" : self.DUPLICATE_PAYMENT,
                    "responseCode" : self.RESPONSE_CODES.get(self.DUPLICATE_PAYMENT)
                })
                
            if not self.amount_valid(amount):
                return Response({
                    "responseDescription" : self.INVALID_AMOUNT,
                    "responseCode" : self.RESPONSE_CODES.get(self.INVALID_AMOUNT)
                })
            
            account = self.fetch_account(to_iban)
            
            if not account:
                return Response({
                    "responseDescription" : self.INCORECT_ACCOUNT_NUMBER,
                    "responseCode" : self.RESPONSE_CODES.get(self.INCORECT_ACCOUNT_NUMBER)
                }, status=200)
            
            merchant = account.customer.merchant
            
            if not self.is_limit_available(merchant, amount):
                return Response({
                    "responseDescription" : self.LIMIT_OUT,
                    "responseCode" : self.RESPONSE_CODES.get(self.LIMIT_OUT)
                }, status=200)
            
            if merchant.status != Merchant.STATUS_ACTIVE or account.status != Account.ACCOUNT_STATUS_ACTIVE:
                return Response({
                    "responseDescription" : self.ACCOUNT_INACTIVE,
                    "responseCode" : self.RESPONSE_CODES.get(self.ACCOUNT_INACTIVE)
                }, status=200)
            
            if merchant.credit_blocked is True:
                return Response({
                    "responseDescription" : self.BLOCKED_ACCOUNT,
                    "responseCode" : self.RESPONSE_CODES.get(self.BLOCKED_ACCOUNT)
                }, status=200)
            
            bank_name = self.fetch_bank_name(from_bank)
            
            if not bank_name:
                return Response({
                    "responseDescription" : self.BANK_NOT_FOUND,
                    "responseCode" : self.RESPONSE_CODES.get(self.BANK_NOT_FOUND)
                }, status=200)
            
            transaction_response = account.credit(
                amount=amount,
                account_id=account.id,
                from_iban=from_iban,
                to_iban=to_iban,
                bank_name=bank_name,
                rrn=rrn,
                stan=stan,
                sender_name=request.data.get("senderName"),
                comment=json.dumps(request.data),
                transmission_date_time=f"{transmissionDate}{transmissionTime}"
            )
            
            if not transaction_response.get("success"):
                return Response({
                    "responseDescription" : self.TECHNICAL_PROBLEM,
                    "responseCode" : self.RESPONSE_CODES.get(self.TECHNICAL_PROBLEM)
                }, status=200)
                
            transaction = transaction_response["transaction"]
            
            return Response({
                "responseCode" : self.RESPONSE_CODES.get(self.PROCESSED_OK),
                "transactionLogId" : str(transaction.id)
            }, status=200)
        
        except Exception as e:
            log.exception(traceback.format_exc())
            return Response({
                "responseDescription" : self.TECHNICAL_PROBLEM,
                "responseCode" : self.RESPONSE_CODES.get(self.TECHNICAL_PROBLEM)
            }, status=200)
            
class ReversalView(AuthView):
    
    def get_withdraw_transaction(self, account, failed_withdraw_id):
        
        try:
            withdraw_transaction = Transaction.objects.get(
                account=account, payment_identifier=failed_withdraw_id
            )
        except Transaction.DoesNotExist:
            return None
        
        return withdraw_transaction
    
    def is_refund_already_processed(self, withdraw_transaction):
        return Transaction.objects.filter(
            account=withdraw_transaction.account,
            type=Transaction.TYPE_REVERSAL,
            reference=withdraw_transaction.reference
        ).exists()
        
    
    @log_request_response
    def post(self, request, *args, **kwargs):
        
        try:
        
            amount = int(request.data.get("transactionAmount"))
            to_iban = request.data.get("accountNumber")
            rrn = request.data.get("rrn")
            stan = request.data.get("stan")
            transmissionDate = request.data.get("transmissionDate")
            transmissionTime = request.data.get("transmissionTime")
            failed_withdraw_id = request.data.get("msgid")
            
            if self.is_duplicate_transaction(rrn):
                return Response({
                    "responseDescription" : self.DUPLICATE_PAYMENT,
                    "responseCode" : self.RESPONSE_CODES.get(self.DUPLICATE_PAYMENT)
                })
                
            if not self.amount_valid(amount):
                return Response({
                    "responseDescription" : self.INVALID_AMOUNT,
                    "responseCode" : self.RESPONSE_CODES.get(self.INVALID_AMOUNT)
                })
            
            account = self.fetch_account(to_iban)
                
            if not account:
                return Response({
                    "responseDescription" : self.INCORECT_ACCOUNT_NUMBER,
                    "responseCode" : self.RESPONSE_CODES.get(self.INCORECT_ACCOUNT_NUMBER)
                }, status=200)
            
            merchant = account.customer.merchant
            
            if merchant.status != Merchant.STATUS_ACTIVE or account.status != Account.ACCOUNT_STATUS_ACTIVE:
                return Response({
                    "responseDescription" : self.ACCOUNT_INACTIVE,
                    "responseCode" : self.RESPONSE_CODES.get(self.ACCOUNT_INACTIVE)
                }, status=200)
                
            if merchant.credit_blocked is True:
                return Response({
                    "responseDescription" : self.BLOCKED_ACCOUNT,
                    "responseCode" : self.RESPONSE_CODES.get(self.BLOCKED_ACCOUNT)
                }, status=200)
                        
            withdraw_transaction = self.get_withdraw_transaction(account, failed_withdraw_id)
            
            if not withdraw_transaction:
                return Response({
                    "responseDescription" : self.NO_ORIGINAL_TRANSACTION_RECEIVED,
                    "responseCode" : self.RESPONSE_CODES.get(self.NO_ORIGINAL_TRANSACTION_RECEIVED)
                }, status=200)
                
            if self.is_refund_already_processed(withdraw_transaction):
                return Response({
                    "responseDescription" : self.ALREADY_RETURNED_TRANSACTION,
                    "responseCode" : self.RESPONSE_CODES.get(self.ALREADY_RETURNED_TRANSACTION)
                }, status=200)
            
            refund_response = account.reversal(
                amount=amount,
                account_id=account.id,
                bank_name="ucash",
                rrn=rrn,
                stan=stan,
                transmission_date_time=f"{transmissionDate}{transmissionTime}",
                withdraw_transaction_id=withdraw_transaction.id,
                to_iban=to_iban
            )
            
            if not refund_response.get("success"):
                return Response({
                    "responseDescription" : self.TECHNICAL_PROBLEM,
                    "responseCode" : self.RESPONSE_CODES.get(self.TECHNICAL_PROBLEM)
                }, status=200)
                    
            transaction = refund_response["transaction"]
            
            return Response({
                "responseCode" : self.RESPONSE_CODES.get(self.PROCESSED_OK),
                "transactionLogId" : str(transaction.id)
            }, status=200)
            
        except Exception as e:
            log.exception(traceback.format_exc())
            return Response({
                "responseDescription" : self.TECHNICAL_PROBLEM,
                "responseCode" : self.RESPONSE_CODES.get(self.TECHNICAL_PROBLEM)
            }, status=200)