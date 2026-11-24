# main.py — NCP Cloud Functions 진입점 (작업 58 ①, 작성: 미리)
#
# 서버 함수 전체를 웹 액션 하나로 돌린다. build.py가 이 파일을 zip 맨 위 __main__.py로 넣는다.
#   zip/__main__.py   (이 파일)
#   zip/functions/    서버 함수(test_·eval_ 제외)
#   zip/data/*.json   읽기 전용 데이터(data/runtime 제외)
#   zip/docs/prompts/ AI 프롬프트
#   zip/lib/          의존성(anthropic, 리눅스용 wheel)
#
# 주소: POST <웹 액션 공개 주소>/<함수 이름>  (data.js의 `${FN_BASE}/${name}` 그대로)
#   경로 대신 본문 "_fn" 필드로도 받는다(API Gateway가 경로를 넘기지 않는 경우).
#   액션은 반드시 「웹 액션 + Raw HTTP」로 켠다. Raw가 아니면 요청 본문이 기본 파라미터(키)를 덮어쓸 수 있어 거절한다.
#
# 흐름은 local_fn.py Handler.do_POST와 같다:
#   토큰 확인 → NEEDS_NO_LOGIN → AI_ROUTES 한도 → logout 토큰 → 예외 시 error 응답
#   라우팅 표(ROUTES·NEEDS_NO_LOGIN·AI_ROUTES)는 local_fn에서 import한다(복사하지 않는다 — 함수가 늘면 다시 배포만).
#
# 기본 파라미터(콘솔 > 액션 > 기본 파라미터). 값은 콘솔에만 — 코드·zip·커밋·화면에 쓰지 않는다.
#   CLAUDE_KEY (→ ANTHROPIC_API_KEY)  CLOVA_KEY  VCC_LOGIN_PW  ALLOW_ORIGIN  STORE_BACKEND=ncp
#   NCP_OS_BUCKET  NCP_OS_ACCESS_KEY  NCP_OS_SECRET_KEY  (선택) NCP_OS_ENDPOINT NCP_OS_REGION NCP_OS_PREFIX
#   (선택) CLOVA_URL  CLAUDE_MODEL
import base64
import json
import os
import socket
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote

HERE = Path(__file__).resolve().parent
for p in (HERE / "lib", HERE / "functions"):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

# 기본 파라미터 중 환경변수로 옮길 것(이 목록 밖의 값은 환경으로 가지 않는다)
ENV_PARAMS = ("CLOVA_KEY", "CLOVA_URL", "CLAUDE_MODEL", "VCC_LOGIN_PW", "STORE_BACKEND",
              "NCP_OS_BUCKET", "NCP_OS_ACCESS_KEY", "NCP_OS_SECRET_KEY", "NCP_OS_ENDPOINT", "NCP_OS_REGION", "NCP_OS_PREFIX")
ALLOWED_ORIGINS = ("https://hufsiei.github.io",)   # ALLOW_ORIGIN이 없을 때. "*"는 쓰지 않는다(PRD 9장)

_app = None   # 첫 요청에서 한 번 import(컨테이너가 살아 있는 동안 재사용)


def _set_env(args):
    os.environ["VCC_LOGS"] = "/tmp/vcc-logs"   # 액션 안에서는 /tmp만 쓸 수 있다(paths.LOGS → ai-calls.jsonl)
    for k in ENV_PARAMS:
        v = args.get(k)
        if v is None or v == "":
            continue
        # VCC_LOGIN_PW를 객체로 넣어도 JSON 문자열로. 콘솔에 붙여 넣을 때 섞인 앞뒤 공백은 지운다
        os.environ[k] = v.strip() if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    if args.get("CLAUDE_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = str(args["CLAUDE_KEY"]).strip()
    os.environ.setdefault("STORE_BACKEND", "ncp")   # 액션에서 file로 쓰면 재시작 때 기록이 사라진다


def _load_app():
    global _app
    if _app is None:
        import limits
        import local_fn
        import sessions
        import store
        _app = {"local_fn": local_fn, "limits": limits, "sessions": sessions, "store": store}
    return _app


def _cors(args):
    allowed = [o.strip() for o in str(args.get("ALLOW_ORIGIN") or "").split(",") if o.strip()] or ALLOWED_ORIGINS
    origin = (args.get("__ow_headers") or {}).get("origin", "")   # 웹 액션은 헤더 이름을 소문자로 넘긴다
    headers = {
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-Token",
        "Access-Control-Max-Age": "600",
        "Vary": "Origin",
    }
    if origin in allowed:
        headers["Access-Control-Allow-Origin"] = origin
    return headers


def _reply(args, out, status=200):
    # API Gateway(/{fn} 리소스)가 OPTIONS 응답과 CORS 헤더를 직접 붙인다. 여기서도 붙이면 Allow-Origin이 두 개가 되어
    # 브라우저가 응답을 막는다(11/24 확인). 그래서 본 응답에는 붙이지 않는다. OPTIONS가 액션까지 오는 경우만 _cors.
    headers = {"Content-Type": "application/json; charset=utf-8"}
    return {"statusCode": status, "headers": headers, "body": json.dumps(out, ensure_ascii=False)}


def _payload(args):
    """Raw HTTP 웹 액션의 본문(__ow_body)을 JSON으로. 바이너리로 보면 base64로 온다."""
    raw = args.get("__ow_body") or ""
    if isinstance(raw, dict):
        return raw
    text = raw.strip()
    if text and not text.startswith("{"):
        try:
            text = base64.b64decode(text).decode("utf-8").strip()
        except (ValueError, UnicodeDecodeError):
            raise ValueError
    data = json.loads(text or "{}")
    if not isinstance(data, dict):
        raise ValueError
    return data


def handle(name, payload, token):
    """local_fn.py Handler.do_POST와 같은 순서. 응답 dict를 돌려준다."""
    app = _load_app()
    lf, sessions, limits = app["local_fn"], app["sessions"], app["limits"]
    app["store"].begin_request()   # 컨테이너가 여럿이어도 이번 요청은 저장소에서 새로 읽는다
    me = sessions.resolve(token)

    if name in ("", "연습"):
        # local_fn의 연결 확인용 AI 연습 호출은 공개 주소에서 열지 않는다(로그인 없이 AI를 부르는 구멍)
        return {"error": "함수 이름이 없어요"}
    fn = lf.ROUTES.get(name)
    if fn is None:
        return {"error": f"아직 서버에 없는 함수예요: {name}"}
    if not me and name not in lf.NEEDS_NO_LOGIN:
        return {"error": "로그인이 필요해요"}
    if name in lf.AI_ROUTES:   # 토큰 확인(위) → 전역 상한 → 사용자별 한도
        over = limits.check(me)
        if over:
            return over
    if name == "logout":   # 폐기할 토큰은 헤더의 것만 쓴다(본문 값은 믿지 않는다)
        payload = {**payload, "token": token}
    return fn(me, payload)


def _can_connect(host):
    try:
        socket.create_connection((host, 443), timeout=3).close()
        return True
    except OSError as e:
        return type(e).__name__


def _diag(args):
    """배포 점검용(API Gateway가 경로·본문을 어떻게 넘기는지 + 밖으로 나가는 길). 값은 돌려주지 않는다 — 이름·경로·여부만."""
    return {"ow_path": args.get("__ow_path"), "ow_method": args.get("__ow_method"),
            "fn_arg": args.get("fn"), "has_ow_query": "__ow_query" in args, "has_ow_body": "__ow_body" in args,
            "body_type": type(args.get("__ow_body")).__name__,
            "arg_keys": sorted(k for k in args if not k.isupper() and k not in ("__ow_body", "__ow_query")),
            "net": {h: _can_connect(h) for h in ("kr.object.ncloudstorage.com", "clovastudio.stream.ntruss.com")}}


def _fn_name(args, payload=None):
    """함수 이름: 경로(__ow_path 끝) → API Gateway 경로 변수 {fn} → 쿼리 fn= → 본문 _fn."""
    path = unquote(str(args.get("__ow_path") or "").strip("/")).split("/")[-1]
    if path:
        return path
    if isinstance(args.get("fn"), str) and args["fn"]:
        return unquote(args["fn"])
    q = parse_qs(str(args.get("__ow_query") or "")).get("fn")
    if q:
        return q[0]
    return str((payload or {}).pop("_fn", "") or "")


def main(args):
    method = str(args.get("__ow_method", "")).lower()
    if method == "options":
        return {"statusCode": 204, "headers": _cors(args), "body": ""}
    if _fn_name(args) == "_diag" or "_diag" in args:
        return _reply(args, _diag(args))
    if "__ow_method" in args and "__ow_body" not in args and method == "post":
        # Raw HTTP가 꺼져 있으면 본문 필드가 args에 섞여 들어온다(기본 파라미터를 덮어쓸 수 있음)
        return _reply(args, {"error": "서버 설정 오류: 웹 액션의 Raw HTTP를 켜 주세요", "diag": _diag(args)}, 500)
    if method and method != "post":
        return _reply(args, {"error": "POST로 불러 주세요"}, 405)
    try:
        payload = _payload(args)
    except ValueError:
        return _reply(args, {"error": "요청 형식이 JSON이 아니에요"})
    headers = args.get("__ow_headers") or {}
    token = str(headers.get("x-token") or "").strip()
    name = _fn_name(args, payload)
    try:
        _set_env(args)
        return _reply(args, handle(name, payload, token))
    except Exception as e:   # 시연 중 서버가 죽지 않게(local_fn과 같은 문구)
        return _reply(args, {"error": f"서버 처리 중 문제가 생겼어요: {e}"})
