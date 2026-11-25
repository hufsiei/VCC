# test_main.py — Cloud Functions 진입점·store ncp 분기 시험 (작업 58 ①). 네트워크·AI를 부르지 않는다.
# 실행: python -X utf8 functions/cloud/test_main.py   하나라도 틀리면 종료코드 1.
#   1. main(): OPTIONS·CORS(모든 응답에 허용 Origin 1개, 다른 Origin·"*" 설정이면 없음), Raw HTTP 아님 거절, login → 토큰 → getMe, base64 본문, 없는 함수, 로그인 필요, logout,
#      _diag는 VCC_DIAG=1일 때만, 예외 시 응답은 고정 문구·원문은 stderr(키 값 가림)
#   2. store ncp: _s3를 메모리 가짜로 바꿔 load·save·next_id·begin_request·clear_all 왕복
#      (실제 버킷 왕복은 test_store_ncp_live.py)
import base64
import io
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import store  # noqa: E402

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"   # 실제 data/runtime을 건드리지 않는다
os.environ.pop("STORE_BACKEND", None)
import main  # noqa: E402

fails = []


def check(label, ok):
    print(("통과 " if ok else "실패 ") + label)
    if not ok:
        fails.append(label)


ORIGIN = "https://hufsiei.github.io"
PARAMS = {"STORE_BACKEND": "file", "ALLOW_ORIGIN": ORIGIN, "VCC_LOGIN_PW": {"H0143": "test-pw"}}


def call(path, body=None, token="", origin=ORIGIN, method="post", raw_b64=False):
    text = json.dumps(body or {}, ensure_ascii=False)
    if raw_b64:
        text = base64.b64encode(text.encode()).decode()
    args = {**PARAMS, "__ow_method": method, "__ow_path": path, "__ow_body": text,
            "__ow_headers": {"origin": origin, **({"x-token": token} if token else {})}}
    r = main.main(args)
    return r, (json.loads(r["body"]) if r.get("body") else None)


# ---------- 1. 진입점 ----------
r = main.main({**PARAMS, "__ow_method": "options", "__ow_headers": {"origin": ORIGIN}})
check("OPTIONS 204 + 허용 origin", r["statusCode"] == 204 and r["headers"].get("Access-Control-Allow-Origin") == ORIGIN)
check("X-Token 헤더 허용", "X-Token" in r["headers"]["Access-Control-Allow-Headers"])



def allow_origin(r):
    """Allow-Origin 헤더 값 목록(대소문자 무시) — 정확히 한 줄인지 보려고 목록으로."""
    return [v for k, v in r["headers"].items() if k.lower() == "access-control-allow-origin"]


EVIL = "https://evil.example"
r, out = call("/getMe")
check("POST 허용 Origin → Allow-Origin 그 값 1개", allow_origin(r) == [ORIGIN] and r["headers"].get("Vary") == "Origin")
check("POST 응답 Allow-Methods는 POST, OPTIONS(기본 묶음 7개 아님)", r["headers"].get("Access-Control-Allow-Methods") == "POST, OPTIONS")
r, out = call("/getMe", origin=EVIL)
check("POST 다른 Origin → Allow-Origin 없음", allow_origin(r) == [] and out.get("error") == "로그인이 필요해요")
r = main.main({**PARAMS, "__ow_method": "options", "__ow_headers": {"origin": EVIL}})
check("OPTIONS 다른 Origin → Allow-Origin 없음", r["statusCode"] == 204 and allow_origin(r) == [])
r = main.main({**PARAMS, "__ow_method": "post", "__ow_path": "/getMe", "__ow_body": "{}", "__ow_headers": {}})
check("Origin 헤더 없음(curl 등) → Allow-Origin 없음", allow_origin(r) == [])
r, out = call("/getMe", origin="null")
check("Origin null → Allow-Origin 없음", allow_origin(r) == [])
for given, label in (("*", "*만"), ("", "빈 값"), (" * , https://hufsiei.github.io/ ", "* 섞임·끝 /")):
    r = main.main({**PARAMS, "ALLOW_ORIGIN": given, "__ow_method": "options", "__ow_headers": {"origin": ORIGIN}})
    r2 = main.main({**PARAMS, "ALLOW_ORIGIN": given, "__ow_method": "options", "__ow_headers": {"origin": EVIL}})
    check(f"ALLOW_ORIGIN {label} → *를 쓰지 않고 Pages만", allow_origin(r) == [ORIGIN] and allow_origin(r2) == [])
r = main.main({**PARAMS, "ALLOW_ORIGIN": ORIGIN + ",http://localhost:8000", "__ow_method": "options",
               "__ow_headers": {"origin": "http://localhost:8000"}})
check("ALLOW_ORIGIN 쉼표 목록 → 요청 Origin 하나만", allow_origin(r) == ["http://localhost:8000"])
r = main.main({**PARAMS, "__ow_method": "post", "__ow_path": "/getMe", "__ow_body": "{깨짐",
               "__ow_headers": {"origin": ORIGIN}})
check("오류 응답(JSON 아님)에도 Allow-Origin 1개 — 브라우저가 오류 문구를 읽게", allow_origin(r) == [ORIGIN])
r = main.main({**PARAMS, "__ow_method": "get", "__ow_path": "/getMe", "__ow_headers": {"origin": ORIGIN}})
check("405 응답에도 Allow-Origin 1개", r["statusCode"] == 405 and allow_origin(r) == [ORIGIN])
r = main.main({**PARAMS, "__ow_method": "post", "__ow_path": "/", "__ow_query": "fn=getMe", "__ow_body": "{}",
               "__ow_headers": {}})
check("쿼리 fn= → 함수 이름(API Gateway는 경로를 / 로 넘김)", "로그인이 필요해요" in r["body"])

r = main.main({**PARAMS, "__ow_method": "post", "__ow_path": "/login", "id": "H0143", "pw": "test-pw", "__ow_headers": {}})
check("Raw HTTP 아니면 거절(본문이 파라미터를 덮지 못하게)", r["statusCode"] == 500 and "Raw HTTP" in json.loads(r["body"])["error"])

r, out = call("/login", {"id": "h0143", "pw": "틀림"})
check("틀린 비번 → 로그인 실패", not out.get("ok"))
r, out = call("/login", {"id": "h0143", "pw": "test-pw"})
token = (out.get("user") or {}).get("token", "")
check("login → 토큰", out.get("ok") and token)
check("VCC_LOGIN_PW 객체 → JSON 문자열 환경변수", json.loads(os.environ["VCC_LOGIN_PW"]) == {"H0143": "test-pw"})
check("액션 로그 경로는 /tmp", Path(sys.modules["paths"].LOGS).as_posix().endswith("/tmp/vcc-logs"))

r, out = call("/getMe", token=token)
check("getMe(토큰) → 응답", "error" not in out)
r, out = call("/getMe", token=token, raw_b64=True)
check("base64 본문도 읽음", "error" not in out)
r, out = call("", {"_fn": "getMe"}, token=token)
check("경로 대신 본문 _fn", "error" not in out)
r, out = call("/getMe")
check("토큰 없음 → 로그인 필요", out.get("error") == "로그인이 필요해요")
r, out = call("/없는함수", token=token)
check("없는 함수 → 오류 문구", "없는 함수" in out.get("error", ""))
r = main.main({**PARAMS, "__ow_method": "post", "__ow_path": "/getMe", "__ow_body": "{깨짐", "__ow_headers": {}})
check("JSON 아님 → 오류 문구", "JSON" in json.loads(r["body"])["error"])
r, out = call("/logout", {"token": "남의토큰"}, token=token)
r, out = call("/getMe", token=token)
check("logout은 헤더 토큰을 폐기", out.get("error") == "로그인이 필요해요")
check("라우팅 표는 local_fn 것 그대로", main._load_app()["local_fn"].ROUTES is sys.modules["local_fn"].ROUTES)

main._can_connect = lambda host: True   # 시험에서는 밖으로 접속하지 않는다
r = main.main({**PARAMS, "__ow_method": "post", "__ow_path": "", "fn": "getMe", "__ow_body": "{}",
               "__ow_headers": {"x-token": token}})
check("API Gateway 경로 변수 fn → 함수 이름", "로그인이 필요해요" in r["body"])   # 위에서 logout한 토큰이라 로그인 필요까지 갔음
r, out = call("", {})
check("이름 없음 → AI 연습 호출 없이 오류", out.get("error") == "함수 이름이 없어요")
r, out = call("/_diag", {"secret": "본문값"})
check("VCC_DIAG 없음 → _diag는 없는 함수로 거절", out == {"error": "아직 서버에 없는 함수예요: _diag"})
r = main.main({**PARAMS, "__ow_method": "post", "__ow_path": "/getMe", "_diag": 1, "__ow_body": "{}", "__ow_headers": {}})
check("VCC_DIAG 없음 → _diag 파라미터도 거절", "ow_path" not in r["body"] and "_diag" in json.loads(r["body"])["error"])
r = main.main({**PARAMS, "__ow_method": "post", "__ow_path": "/login", "id": "H0143", "pw": "test-pw", "__ow_headers": {}})
check("VCC_DIAG 없음 → Raw HTTP 꺼짐 응답에 diag 없음", "diag" not in json.loads(r["body"]))
DIAG = {**PARAMS, "VCC_DIAG": "1"}
r = main.main({**DIAG, "__ow_method": "post", "__ow_path": "/_diag", "__ow_body": json.dumps({"secret": "본문값"}),
               "__ow_headers": {}})
out = json.loads(r["body"])
check("VCC_DIAG=1 → _diag는 값 없이 이름만", out.get("ow_path") == "/_diag" and "본문값" not in r["body"] and "VCC_LOGIN_PW" not in r["body"])
r = main.main({**DIAG, "__ow_method": "post", "__ow_path": "/login", "id": "H0143", "pw": "test-pw", "__ow_headers": {}})
check("VCC_DIAG=1 → Raw HTTP 꺼짐 응답에 diag", "diag" in json.loads(r["body"]))

# 예외: 응답은 고정 문구, 원문은 stderr(키 값은 가림)
lf = main._load_app()["local_fn"]
SECRETS = {"CLAUDE_KEY": "sk-ant-fake-key-1234", "NCP_OS_SECRET_KEY": "fake-secret-5678"}
BOOM = ("Object Storage GET 403: <Error><Code>AccessDenied</Code><BucketName>vcc-runtime</BucketName></Error> "
        f"{SECRETS['CLAUDE_KEY']} {SECRETS['NCP_OS_SECRET_KEY']} test-pw")


def boom(*a, **k):
    raise RuntimeError(BOOM)   # store._s3가 던지는 것과 같은 모양


def call_capture(args):
    err, sys.stderr = sys.stderr, io.StringIO()
    try:
        r = main.main(args)
        return r, sys.stderr.getvalue()
    finally:
        sys.stderr = err


lf.ROUTES["_boom"] = boom
lf.NEEDS_NO_LOGIN.add("_boom")
r, logged = call_capture({**PARAMS, **SECRETS, "__ow_method": "post", "__ow_path": "/_boom", "__ow_body": "{}",
                          "__ow_headers": {}})
del lf.ROUTES["_boom"]
lf.NEEDS_NO_LOGIN.discard("_boom")
check("예외 → 응답은 고정 문구만", json.loads(r["body"]) == {"error": "서버 처리 중 문제가 생겼어요"})
check("예외 → 응답에 원문·버킷 이름 없음", "vcc-runtime" not in r["body"] and "RuntimeError" not in r["body"])
check("예외 → 원문은 stderr(액션 로그)에", "RuntimeError" in logged and "AccessDenied" in logged and "vcc-runtime" in logged)
check("예외 → 로그에 키·비번 값 없음", not any(v in logged for v in (*SECRETS.values(), "test-pw")) and "***" in logged)

real_s3 = store._s3
store._s3 = boom
r, logged = call_capture({**PARAMS, "STORE_BACKEND": "ncp", "NCP_OS_BUCKET": "vcc-runtime", "NCP_OS_ACCESS_KEY": "a" * 8,
                          "NCP_OS_SECRET_KEY": "s" * 8, "__ow_method": "post", "__ow_path": "/login",
                          "__ow_body": json.dumps({"id": "h0143", "pw": "test-pw"}), "__ow_headers": {}})
store._s3 = real_s3
os.environ["STORE_BACKEND"] = "file"
store._cache.clear()
check("handle 안 store._s3 RuntimeError도 고정 문구 + 로그", json.loads(r["body"]) == {"error": "서버 처리 중 문제가 생겼어요"}
      and "RuntimeError" in logged and "vcc-runtime" not in r["body"])

# ---------- 2. store ncp (가짜 S3) ----------
bucket = {}


def fake_s3(method, key="", body=b"", query=None):
    if method == "GET" and query:
        keys = "".join(f"<Key>{k}</Key>" for k in bucket if k.startswith(query.get("prefix", "")))
        return 200, f"<ListBucketResult>{keys}</ListBucketResult>".encode()
    if method == "GET":
        return (200, bucket[key]) if key in bucket else (404, b"")
    if method == "PUT":
        bucket[key] = body
        return 200, b""
    if method == "DELETE":
        bucket.pop(key, None)
        return 204, b""


store._s3 = fake_s3
os.environ.update(STORE_BACKEND="ncp", NCP_OS_BUCKET="b", NCP_OS_ACCESS_KEY="a" * 8, NCP_OS_SECRET_KEY="s" * 8)
store.begin_request()
m = store.load("messages", {})
m["T-0001"] = {"text": "안녕"}
check("같은 요청 안 load 두 번 → 같은 dict", store.load("messages", {}) is m)
store.save("messages")
check("ncp save → 버킷에 runtime/messages.json", json.loads(bucket["runtime/messages.json"]) == {"T-0001": {"text": "안녕"}})
check("next_id 1", store.next_id("T") == "T-0001")
bucket["runtime/messages.json"] = json.dumps({"T-0002": {}}).encode()   # 다른 컨테이너가 쓴 것처럼
check("begin_request 전에는 캐시", "T-0001" in store.load("messages", {}))
store.begin_request()
check("begin_request 뒤에는 버킷에서 새로 읽음", list(store.load("messages", {})) == ["T-0002"])
check("next_id 이어서 2(버킷 counters 기준)", store.next_id("T") == "T-0002")
store.clear_all()
check("clear_all → 버킷 비움", bucket == {})
os.environ["STORE_BACKEND"] = "file"
store._cache.clear()
store.begin_request()   # file이면 아무것도 안 함
check("file이면 begin_request가 캐시를 비우지 않음", store.load("x", {"a": 1}) is store.load("x", {}))

print(f"\n{'실패 ' + str(len(fails)) + '건' if fails else '모두 통과'}")
sys.exit(1 if fails else 0)
