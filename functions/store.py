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
#         _lock은 프로세스 안 잠금이라 컨테이너 사이의 동시 쓰기는 막지 못한다. 그래서 ncp의 save()는 통째로 덮어쓰지
#         않고 「저장 직전에 버킷을 다시 읽고, 이번 요청이 바꾼 것만 얹어서」 쓴다(11/25 두 창 시험에서 늦게 끝난
#         getMessages가 답장을 지운 일, 작업 58). load()가 읽은 모습을 _base에 남겨 두고 save()에서 _base → 캐시의
#         차이를 새로 읽은 기록에 합친다(_merge: dict는 키별, list는 덧붙인 항목, 정수는 더한 만큼).
#         다시 읽기와 쓰기 사이의 틈은 조건부 쓰기로 막는다(11/25, NCP가 PUT If-Match를 지키는 것 확인): 다시 읽은
#         객체의 ETag를 If-Match에 붙여 쓰고(없던 기록이면 If-None-Match: *), 그사이 다른 컨테이너가 썼으면 412가
#         오므로 다시 읽어 합쳐 쓰기를 RETRIES번까지 되풀이한다. 그래도 안 되면 RuntimeError(진입점이 고정 문구로 응답).
#         캐시·_base는 쓰기가 성공한 뒤에만 합친 모습으로 바꾼다 — 실패한 시도가 이번 요청의 변경을 잃지 않게.
#         읽기만 하는 함수는 바뀐 것이 없으면 save()를 부르지 않는다(runtime_fns.getMessages·recommendSeniors).
import copy
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
_base = {}        # ncp만: 이름 → load()가 저장소에서 읽은 그대로(깊은 복사). 없던 기록이면 None
_lock = threading.RLock()
_MISSING = object()
RETRIES = 3       # ncp save: 조건부 쓰기가 412(그사이 다른 컨테이너가 씀)면 다시 읽어 합쳐 쓰기를 이만큼 더 해 본다


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


def _s3(method, key="", body=b"", query=None, extra=None):
    """S3 호환 요청 하나(SigV4, path-style). extra는 더 보낼 헤더(if-match·if-none-match 등, 서명에 넣는다).
    돌려주는 값: (상태 코드, 본문 bytes, 응답 헤더 dict — 이름은 소문자). 404·412는 오류가 아니라 상태 코드로 돌려준다."""
    c = _os_conf()
    host = urllib.parse.urlsplit(c["endpoint"]).netloc
    path = "/" + urllib.parse.quote(c["bucket"], safe="") + ("/" + urllib.parse.quote(key, safe="/-_.~") if key else "/")
    qs = "&".join(f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(str(v), safe='-_.~')}"
                  for k, v in sorted((query or {}).items()))
    now = datetime.datetime.now(datetime.timezone.utc)
    amz_date, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(body).hexdigest()
    headers = {"host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date}
    headers.update({k.lower(): str(v).strip() for k, v in (extra or {}).items()})
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
                return r.status, r.read(), {k.lower(): v for k, v in r.getheaders()}
        except urllib.error.HTTPError as e:
            if e.code in (404, 412):   # 없는 객체 · 조건부 쓰기의 조건이 어긋남(그사이 다른 컨테이너가 씀)
                return e.code, b"", {}
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
    """돌려주는 값: (기록 또는 None, ETag 또는 None). ETag는 ncp가 읽은 객체의 버전표(조건부 쓰기용) — 없던 기록·file이면 None."""
    if _backend() == "ncp":
        status, data, hdr = _s3("GET", _os_key(name))
        if status == 404:
            return None, None
        return json.loads(data.decode("utf-8")), hdr.get("etag")
    path = RUNTIME / f"{name}.json"
    if not path.exists():
        return None, None
    return json.loads(path.read_text(encoding="utf-8")), None


def _write(name, data, etag=None):
    """저장. ncp는 늘 조건부로 쓴다 — etag(다시 읽은 객체의 ETag)가 있으면 If-Match, 없던 기록이면 If-None-Match: *.
    그사이 다른 컨테이너가 썼으면(412 — 또는 지워져서 404) False, 성공이면 True. file은 늘 True."""
    if _backend() == "ncp":
        cond = {"if-match": etag} if etag else {"if-none-match": "*"}
        status, _, _ = _s3("PUT", _os_key(name), json.dumps(data, ensure_ascii=False).encode("utf-8"), extra=cond)
        return status < 300
    RUNTIME.mkdir(parents=True, exist_ok=True)
    path = RUNTIME / f"{name}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)   # 반쯤 쓰인 파일이 남지 않게 바꿔 끼운다
    return True


# ---------- 세 갈래 합치기 (ncp) ----------
def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _merge(base, mine, theirs):
    """base(이 요청이 읽은 것) → mine(이 요청이 고친 것)의 차이를 theirs(그사이 다른 컨테이너가 저장한 것)에 얹는다.
    없는 쪽은 _MISSING. 돌려주는 값이 _MISSING이면 「지운다」.
      · 내가 안 바꿨으면 theirs 그대로, 저쪽이 안 바꿨으면 mine 그대로
      · dict: 키별로 다시 합친다(내가 지운 키는 저쪽이 그대로 둔 경우에만 지운다)
      · list: 양쪽 다 줄이지 않았으면 앞부분은 항목별로 합치고 뒤에 저쪽이 더한 것 + 내가 더한 것(쪽지 messages·질문 행)
      · 정수: 저쪽 값 + 내가 늘린 만큼(counters·aiUsage — 두 컨테이너가 같이 번호를 뽑아도 겹치지 않게)
      · 그 밖(문자열·None·모양이 다름): 둘 다 바꿨으면 mine"""
    if mine == base:
        return theirs
    if theirs == base or theirs is _MISSING:
        return mine
    if mine is _MISSING:                       # 내가 지웠지만 저쪽이 고쳤다 → 저쪽 것을 둔다
        return theirs
    if isinstance(mine, dict) and isinstance(theirs, dict):
        b = base if isinstance(base, dict) else {}
        out = dict(theirs)
        for k in set(b) | set(mine):
            m = _merge(b.get(k, _MISSING), mine.get(k, _MISSING), theirs.get(k, _MISSING))
            if m is _MISSING:
                out.pop(k, None)
            else:
                out[k] = m
        return out
    if isinstance(mine, list) and isinstance(theirs, list):
        b = base if isinstance(base, list) else []
        n = len(b)
        if len(mine) >= n and len(theirs) >= n:
            head = [_merge(x, y, z) for x, y, z in zip(b, mine[:n], theirs[:n])]
            return head + theirs[n:] + mine[n:]
        return mine
    if _is_int(mine) and _is_int(theirs):
        return theirs + (mine - (base if _is_int(base) else 0))
    return mine


def _merged_for_save(name):
    """ncp: 버킷을 다시 읽어 이번 요청의 변경만 얹은 기록과, 그 읽기의 ETag(없던 기록이면 None)를 돌려준다.
    캐시·_base는 건드리지 않는다 — 조건부 쓰기가 412로 실패하면 같은 _base로 다시 합쳐야 하므로. 성공한 뒤 _commit이 맞춘다."""
    cur = _cache[name]
    base = _base.get(name)
    fresh, etag = _read(name)
    merged = _merge(_MISSING if base is None else base, cur, _MISSING if fresh is None else fresh)
    return (cur if merged is _MISSING else merged), etag


def _commit(name, merged):
    """ncp: 쓰기가 성공한 뒤. 부르는 쪽이 들고 있는 dict/list가 그대로 최신이 되게 안에서 바꾸고,
    _base도 그 모습으로 둔다(같은 요청의 다음 save를 위해)."""
    cur = _cache[name]
    if merged is not cur:
        if isinstance(cur, dict) and isinstance(merged, dict):
            cur.clear()
            cur.update(merged)
        elif isinstance(cur, list) and isinstance(merged, list):
            cur[:] = merged
        else:
            _cache[name] = cur = merged
    _base[name] = copy.deepcopy(cur)


# ---------- 다른 코드가 쓰는 함수 ----------
def load(name, default):
    """기록 하나를 메모리로 가져온다. 처음 부르면 저장소에서 읽고, 없으면 default."""
    with _lock:
        if name not in _cache:
            data, _ = _read(name)
            if _backend() == "ncp":
                _base[name] = copy.deepcopy(data)
            _cache[name] = default if data is None else data
        return _cache[name]


def save(name):
    """메모리의 기록을 저장소에 쓴다. ncp면 저장 직전에 다시 읽어 이번 요청이 바꾼 것만 얹고, 다시 읽은 ETag를 조건으로
    쓴다. 그사이 다른 컨테이너가 썼으면(412) 다시 읽어 합치기를 RETRIES번까지 되풀이하고, 그래도 안 되면 RuntimeError(맨 위 주석)."""
    with _lock:
        if name not in _cache:
            return
        if _backend() != "ncp":
            _write(name, _cache[name])
            return
        for _attempt in range(RETRIES + 1):
            merged, etag = _merged_for_save(name)
            if _write(name, merged, etag):
                _commit(name, merged)
                return
        raise RuntimeError(f"Object Storage 저장 충돌: {name}.json을 {RETRIES + 1}번 써도 그사이 다른 컨테이너가 계속 씁니다")


def next_id(prefix):
    """T-0001, Q-0001처럼 종류별로 하나씩 늘어나는 번호. ncp에서는 save가 합친 뒤의 번호를 돌려준다
    (다른 컨테이너가 그사이 뽑은 번호를 건너뛴다)."""
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
            _base.clear()


def clear_all():
    """초기화(reset_runtime.py)용. 메모리와 저장소를 모두 비운다."""
    with _lock:
        _cache.clear()
        _base.clear()
        if _backend() == "ncp":
            _, xml, _ = _s3("GET", query={"list-type": "2", "prefix": _os_conf()["prefix"]})
            for key in re.findall(r"<Key>([^<]+)</Key>", xml.decode("utf-8")):
                _s3("DELETE", key)
        elif RUNTIME.exists():
            for p in RUNTIME.glob("*.json*"):
                p.unlink()
