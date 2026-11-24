# test_main.py — Cloud Functions 진입점·store ncp 분기 시험 (작업 58 ①). 네트워크·AI를 부르지 않는다.
# 실행: python -X utf8 functions/cloud/test_main.py   하나라도 틀리면 종료코드 1.
#   1. main(): OPTIONS·CORS, Raw HTTP 아님 거절, login → 토큰 → getMe, base64 본문, 없는 함수, 로그인 필요, logout
#   2. store ncp: _s3를 메모리 가짜로 바꿔 load·save·next_id·begin_request·clear_all 왕복
#      (실제 버킷 왕복은 test_store_ncp_live.py)
import base64
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

r, out = call("/getMe", origin="https://evil.example")
check("다른 origin에는 Allow-Origin 없음", "Access-Control-Allow-Origin" not in r["headers"])

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
check("_diag는 값 없이 이름만", out.get("ow_path") == "/_diag" and "본문값" not in r["body"] and "VCC_LOGIN_PW" not in r["body"])

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
