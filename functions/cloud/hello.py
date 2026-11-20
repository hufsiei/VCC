# hello.py — 작업 47 ③ 헬로월드 웹 액션 (작성: 미리)
#
# NCP Cloud Functions · Python 3 · 웹 액션. 외부 호출이 없어서 NAT 없이도 동작한다.
# 콘솔 > 액션 생성 > 코드에 이 파일 전체를 붙여 넣고, 웹 액션(Web Action)을 켠다.
#
# 기본 파라미터(선택)
#   ALLOW_ORIGIN  (선택) CORS를 허용할 화면 origin, 쉼표로 여러 개. 없으면 아래 ALLOWED_ORIGINS
#                 (GitHub Pages 공개 주소 + 로컬 시연 주소). "*"는 쓰지 않는다(공개 저장소, PRD 9장).
#
# 확인
#   curl -i -H "Origin: https://hufsiei.github.io" <공개 URL> → 200, {"ok": true, "msg": "hello"},
#                                     Access-Control-Allow-Origin: https://hufsiei.github.io
#   curl -i -H "Origin: https://example.com" <공개 URL>      → 200이지만 Access-Control-Allow-Origin 없음(브라우저가 막음)
#   curl -i -X OPTIONS <공개 URL> → 204 (브라우저 사전 요청)

import json


# 화면 공개 주소(https://hufsiei.github.io/VCC/의 origin)와 로컬 시연 주소(python -m http.server 8000)만 허용한다.
# origin은 경로 없이 "프로토콜://호스트[:포트]"까지만 쓴다.
ALLOWED_ORIGINS = ("https://hufsiei.github.io", "http://localhost:8000", "http://127.0.0.1:8000")


def _cors(args):
    """요청 Origin이 허용 목록에 있을 때만 그 Origin을 돌려준다. 없으면 허용 헤더를 붙이지 않아 브라우저가 막는다."""
    allowed = [o.strip() for o in str(args.get("ALLOW_ORIGIN") or "").split(",") if o.strip()] or ALLOWED_ORIGINS
    origin = (args.get("__ow_headers") or {}).get("origin", "")  # 웹 액션은 헤더 이름을 소문자로 넘긴다
    headers = {
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-Token",
        "Access-Control-Max-Age": "600",
        "Vary": "Origin",
    }
    if origin in allowed:
        headers["Access-Control-Allow-Origin"] = origin
    return headers


def main(args):
    headers = _cors(args)
    if str(args.get("__ow_method", "")).lower() == "options":
        return {"statusCode": 204, "headers": headers, "body": ""}
    headers["Content-Type"] = "application/json; charset=utf-8"
    return {
        "statusCode": 200,
        "headers": headers,
        "body": json.dumps({"ok": True, "msg": "hello"}, ensure_ascii=False),
    }
