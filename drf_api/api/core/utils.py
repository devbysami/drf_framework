from core.permissions import IsMerchantActive
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from core.permissions import UserAuthentication


class WalletView(APIView):
    """
    It is a Base View for user authentication on wallet.
    Every Wallet API Must be inherited from this View.
    """
    authentication_classes = (UserAuthentication, )
    permission_classes = (IsAuthenticated, IsMerchantActive)
    
    SUCCESS = "SUCCESS"
    FRAUD_USER = "FRAUDULENT_USER"
    CASHOUT_DISABLED = "CASHOUT_DISABLED"
    MERCHANT_NOT_FOUND = "MERCHANT_NOT_FOUND"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    INVALID_AMOUNT = "INVALID_AMOUNT"
    LIMIT_OUT = "LIMIT_OUT"
    NOT_VERIFIED = "NOT_VERIFIED"
    ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
    SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    
    RESPONSE_CODES = {
        SUCCESS : "00",
        FRAUD_USER : "14",
        CASHOUT_DISABLED : "50",
        MERCHANT_NOT_FOUND : "30",
        INSUFFICIENT_BALANCE : "51",
        LIMIT_OUT : "61",
        NOT_VERIFIED : "62",
        ACCOUNT_NOT_FOUND : "14",
        INVALID_AMOUNT : "13",
        SERVER_ERROR : "96",
    }
    
    def get_response_code(self, message):
        return {
            "response_code" : self.RESPONSE_CODES.get(message),
            "response_description" : message
        }