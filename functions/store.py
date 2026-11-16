# store.py — 쓰기 저장소 (작업 51, 원본: docs/spec-v1.md 2-1절)
#
# 쪽지·질문함·동의·신고처럼 사용자가 만드는 기록을 저장한다.
# 다른 코드는 파일을 직접 열지 않고 load()·save()·next_id()만 쓴다.
# Cloud Functions로 옮길 때는 아래 "저장 방식" 부분만 Object Storage로 바꾼다.
#
#   기록 = store.load("messages", {})   # 처음이면 기본값
#   기록["T-0001"] = {...}
#   store.save("messages")             # 바뀐 기록을 저장
import json
import os
import threading
from pathlib import Path

RUNTIME = Path(__file__).resolve().parent.parent / "data" / "runtime"
BACKEND = os.environ.get("STORE_BACKEND", "file")   # file | ncp

_cache = {}
_lock = threading.RLock()


# ---------- 저장 방식 (이사할 때 여기만 바꾼다) ----------
def _read(name):
    if BACKEND == "file":
        path = RUNTIME / f"{name}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    raise NotImplementedError("Object Storage 저장은 Cloud Functions 이사(작업 58) 때 만든다")


def _write(name, data):
    if BACKEND == "file":
        RUNTIME.mkdir(parents=True, exist_ok=True)
        path = RUNTIME / f"{name}.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)   # 반쯤 쓰인 파일이 남지 않게 바꿔 끼운다
        return
    raise NotImplementedError("Object Storage 저장은 Cloud Functions 이사(작업 58) 때 만든다")


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


def clear_all():
    """초기화(reset_runtime.py)용. 메모리와 파일을 모두 비운다."""
    with _lock:
        _cache.clear()
        if BACKEND == "file" and RUNTIME.exists():
            for p in RUNTIME.glob("*.json*"):
                p.unlink()
