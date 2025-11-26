import json
from django.http import JsonResponse, HttpResponseBadRequest, HttpRequest

def json_body_guard(func):
    def _wrapper(*args, **kargs):
        try:
            return func(*args, **kargs)
        except json.JSONDecodeError:
            return HttpResponseBadRequest("잘못된 JSON 형식입니다.")
        except Exception as e:
            print(f"Error saving camera config: {e}")
            return JsonResponse({'status': 'error', 'message': '서버 오류로 시간 저장에 실패했습니다.'}, status=500)
    return _wrapper