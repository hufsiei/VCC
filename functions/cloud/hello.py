# hello.py — 작업 47 ③ 헬로월드 웹 액션 (작성: 미리)
#
# NCP Cloud Functions · Python 3 · 웹 액션. 외부 호출이 없어서 NAT 없이도 동작한다.
# 콘솔 > 액션 생성 > 코드에 이 파일 전체를 붙여 넣고, 웹 액션(Web Action)을 켠다.
#
# 기본 파라미터(선택)
#   ALLOW_ORIGIN  CORS를 허용할 화면 주소. 예: https://hufsiei.github.io (없으면 "*")
#
# 확인
#   curl -i <공개 URL>            → 200, {"ok": true, "msg": "hello"}, Access-Control-Allow-Origin 헤더
#   curl -i -X OPTIONS <공개 URL> → 204 (브라우저 사전 요청)

import json


def _cors(args):
    return {
        "Access-Control-Allow-Origin": args.get("ALLOW_ORIGIN") or "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-User",
        "Access-Control-Max-Age": "600",
    }


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
