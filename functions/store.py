# store.py — 쓰기 저장소 (작업 51, 원본: docs/spec-v1.md 2-1절)
#
# 쪽지·질문함·동의·신고처럼 사용자가 만드는 기록을 저장한다.
# 다른 코드는 파일을 직접 열지 않고 load()·save()·next_id()만 쓴다.
#
#   기록 = store.load("messages", {})   # 처음이면 기본값
#   기록["T-0001"] = {...}
#   store.save("messages")             # 바뀐 기록을 저장
#
# 저장 방식(STORE_BACKEND)
#   file  (기본) data/runtime/<이름>.json — 미리 PC·worktree의 local_fn.py
#   ncp   NCP Object Storage(S3 호환) <버킷>/<접두어><이름>.json — Cloud Functions(작업 58).
#         표준 라이브러리로 SigV4 서명한다(boto3 없음). 값은 액션 기본 파라미터 → 환경변수로만 받는다:
#           NCP_OS_BUCKET  NCP_OS_ACCESS_KEY  NCP_OS_SECRET_KEY
#           NCP_OS_ENDPOINT (기본 https://kr.object.ncloudstorage.com)  NCP_OS_REGION (기본 kr-standard)
#           NCP_OS_PREFIX   (기본 runtime/)
#         컨테이너가 여럿 뜨면 서로 다른 메모리를 보므로, 진입점(functions/cloud/main.py)이 요청마다
#         begin_request()로 캐시를 비운다. 한 요청 안에서는 file과 똑같이 캐시를 쓴다
#         (같은 요청에서 load를 두 번 불러도 같은 dict — 고친 내용이 사라지지 않게).
#         _lock은 프로세스 안 잠금이라 컨테이너 사이의 동시 쓰기는 막지 못한다(시연 수준에서 감수, PR 「확인 전」).
import datetime
import hashlib
import hmac
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RUNTIME = Path(__file__).resolve().parent.parent / "data" / "runtime"
BACKEND = os.environ.get("STORE_BACKEND", "file")   # file | ncp (진입점이 import 뒤에 바꿔도 따르도록 _backend()로 다시 본다)

_cache = {}
_lock = threading.RLock()


# ---------- Object Storage (ncp) ----------
def _os_conf():
    missing = [k for k in ("NCP_OS_BUCKET", "NCP_OS_ACCESS_KEY", "NCP_OS_SECRET_KEY") if not os.environ.get(k)]
    if missing:
        raise RuntimeError("Object Storage 설정이 없습니다: " + ", ".join(missing))
    return {
        "bucket": os.environ["NCP_OS_BUCKET"],
        "access": os.environ["NCP_OS_ACCESS_KEY"],
        "secret": os.environ["NCP_OS_SECRET_KEY"],
        "endpoint": os.environ.get("NCP_OS_ENDPOINT", "https://kr.object.ncloudstorage.com").rstrip("/"),
        "region": os.environ.get("NCP_OS_REGION", "kr-standard"),
        "prefix": os.environ.get("NCP_OS_PREFIX", "runtime/"),
    }


def _hmac(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _s3(method, key="", body=b"", query=None):
    """S3 호환 요청 하나(SigV4, path-style). 돌려주는 값: (상태 코드, 본문 bytes). 404는 오류가 아니다."""
    c = _os_conf()
    host = urllib.parse.urlsplit(c["endpoint"]).netloc
    path = "/" + urllib.parse.quote(c["bucket"], safe="") + ("/" + urllib.parse.quote(key, safe="/-_.~") if key else "/")
    qs = "&".join(f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(str(v), safe='-_.~')}"
                  for k, v in sorted((query or {}).items()))
    now = datetime.datetime.now(datetime.timezone.utc)
    amz_date, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(body).hexdigest()
    headers = {"host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date}
    signed = ";".join(sorted(headers))
    canonical = "\n".join([method, path, qs, "".join(f"{k}:{headers[k]}\n" for k in sorted(headers)), signed, payload_hash])
    scope = f"{day}/{c['region']}/s3/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    k = _hmac(("AWS4" + c["secret"]).encode("utf-8"), day)
    for part in (c["region"], "s3", "aws4_request"):
        k = _hmac(k, part)
    sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    headers["Authorization"] = f"AWS4-HMAC-SHA256 Credential={c['access']}/{scope}, SignedHeaders={signed}, Signature={sig}"
    if body:
        headers["Content-Type"] = "application/json; charset=utf-8"
    url = c["endpoint"] + path + ("?" + qs if qs else "")
    for attempt in range(3):   # 5xx·네트워크 오류는 두 번까지 다시(0.3·0.6초)
        req = urllib.request.Request(url, data=body if method == "PUT" else None, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, b""
            if e.code >= 500 and attempt < 2:
                time.sleep(0.3 * (attempt + 1))
                continue
            # 응답 본문(오류 코드 XML)만 붙인다. 서명·키는 담기지 않는다
            raise RuntimeError(f"Object Storage {method} {e.code}: {e.read()[:200].decode('utf-8', 'replace')}")
        except urllib.error.URLError as e:
            if attempt < 2:
                time.sleep(0.3 * (attempt + 1))
                continue
            raise RuntimeError(f"Object Storage 연결 실패: {e.reason}")


def _os_key(name):
    return _os_conf()["prefix"] + f"{name}.json"


# ---------- 저장 방식 ----------
def _backend():
    return os.environ.get("STORE_BACKEND", BACKEND)


def _read(name):
    if _backend() == "ncp":
        status, data = _s3("GET", _os_key(name))
        return None if status == 404 else json.loads(data.decode("utf-8"))
    path = RUNTIME / f"{name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write(name, data):
    if _backend() == "ncp":
        _s3("PUT", _os_key(name), json.dumps(data, ensure_ascii=False).encode("utf-8"))
        return
    RUNTIME.mkdir(parents=True, exist_ok=True)
    path = RUNTIME / f"{name}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)   # 반쯤 쓰인 파일이 남지 않게 바꿔 끼운다


# ---------- 다른 코드가 쓰는 함수 ----------
def load(name, default):
    """기록 하나를 메모리로 가져온다. 처음 부르면 저장소에서 읽고, 없으면 default."""
    with _lock:
        if name not in _cache:
            data = _read(name)
            _cache[name] = default if data is None else data
        return _cache[name]


def save(name):
    """메모리의 기록을 저장소에 쓴다."""
    with _lock:
        if name in _cache:
            _write(name, _cache[name])


def next_id(prefix):
    """T-0001, Q-0001처럼 종류별로 하나씩 늘어나는 번호."""
    with _lock:
        counters = load("counters", {})
        counters[prefix] = counters.get(prefix, 0) + 1
        save("counters")
        return f"{prefix}-{counters[prefix]:04d}"


def lock():
    """여러 기록을 한 번에 고칠 때: with store.lock(): ..."""
    return _lock


def begin_request():
    """요청 하나를 시작할 때(Cloud Functions 진입점). ncp면 메모리를 비워 이번 요청은 저장소에서 새로 읽는다.
    file(local_fn.py)은 프로세스 하나가 기록을 쥐고 있으므로 아무것도 하지 않는다."""
    if _backend() == "ncp":
        with _lock:
            _cache.clear()


def clear_all():
    """초기화(reset_runtime.py)용. 메모리와 저장소를 모두 비운다."""
    with _lock:
        _cache.clear()
        if _backend() == "ncp":
            _, xml = _s3("GET", query={"list-type": "2", "prefix": _os_conf()["prefix"]})
            for key in re.findall(r"<Key>([^<]+)</Key>", xml.decode("utf-8")):
                _s3("DELETE", key)
        elif RUNTIME.exists():
            for p in RUNTIME.glob("*.json*"):
                p.unlink()
