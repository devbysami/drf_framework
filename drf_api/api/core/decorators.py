from functools import wraps
from core.models import RequestLog
from rest_framework.response import Response
import jsonfield
import traceback
import logging

log = logging.getLogger("django")

def log_request_response(view_func):
    """
    Decorator to log request and response data.
    Adds 'authIdResponse' with RequestLog ID in the response.
    """

    @wraps(view_func)
    def _wrapped_view(self, request, *args, **kwargs):
        
        request_data = request.data
        
        try:
            response = view_func(self, request, *args, **kwargs)
            
            response_data = response.data if isinstance(response, Response) else {}

            log_entry = RequestLog.objects.create(
                user=request.user,
                request_data=request_data,
                response_data=response_data
            )

            if isinstance(response, Response):
                
                auth_id = str(log_entry.id).zfill(6)
                if len(auth_id) > 6:
                    auth_id = auth_id[1:]
                    
                response.data["authIdResponse"] = auth_id

            return response
        
        except Exception as e:
            log.exception(traceback.format_exc())
            return Response({
                "responseDescription": "SYSTEM EXCEPTION",
                "responseCode": "099"
            }, status=500)
    
    return _wrapped_view