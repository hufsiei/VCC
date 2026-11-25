# test_store_ncp_live.py — 실제 Object Storage 버킷 왕복 시험 (작업 58 ①). AI는 부르지 않는다.
# 실행: python -X utf8 functions/cloud/test_store_ncp_live.py
# 필요: .env(또는 환경변수)에 NCP_OS_BUCKET·NCP_OS_ACCESS_KEY·NCP_OS_SECRET_KEY. 값은 출력하지 않는다.
# 시험용 접두어(test-<시각>/)에만 쓰고 끝나면 지운다 — 시연 기록(runtime/)은 건드리지 않는다.
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths  # noqa: E402

paths.load_env()
os.environ["STORE_BACKEND"] = "ncp"
os.environ["NCP_OS_PREFIX"] = f"test-{int(time.time())}/"
import store  # noqa: E402

fails = []


def check(label, ok, detail=None):
    print(("통과 " if ok else "실패 ") + label + ("" if ok or detail is None else f"  ← {detail}"))
    if not ok:
        fails.append(label)


t0 = time.time()
store.begin_request()
check("없는 기록 → 기본값", store.load("probe", {"empty": True}) == {"empty": True})
rec = store.load("probe", {})
rec["한글"] = "쪽지 왕복"
store.save("probe")
check("next_id 1", store.next_id("T") == "T-0001")
store.begin_request()   # 다른 요청처럼 캐시를 비우고 버킷에서 다시 읽는다
check("다시 읽은 기록이 같음", store.load("probe", {}) == {"empty": True, "한글": "쪽지 왕복"})
check("next_id 2", store.next_id("T") == "T-0002")

# 조건부 쓰기(If-Match, 작업 58 ③): 다시 읽기와 쓰기 사이에 다른 컨테이너가 끼어들면 412 → 다시 읽어 합친다
# save()는 쓰기 직전에 다시 읽으므로, 끼어든 쓰기는 「다시 읽기 뒤 · PUT 앞」 틈에 넣어야 실제 412가 난다.
# spy가 PUT 직전에 다른 컨테이너처럼 조건 없이 통째로 쓴다(ETag가 바뀜) → 진짜 버킷이 412를 돌려주는지 본다.
real_s3, put_log, intruders = store._s3, [], {}


def spy(method, key="", body=b"", query=None, extra=None):
    if method == "PUT" and key in intruders:
        real_s3("PUT", key, json.dumps(intruders.pop(key), ensure_ascii=False).encode("utf-8"))
    r = real_s3(method, key, body, query, extra)
    if method == "PUT":
        put_log.append((r[0], sorted(k.lower() for k in (extra or {}))))
    return r


store._s3 = spy
store.begin_request()
rec = store.load("probe", {})
rec["mine"] = 1
intruders[store._os_key("probe")] = {**rec, "theirs": 2}
del intruders[store._os_key("probe")]["mine"]
store.save("probe")
check("있는 기록: 틈에 끼어든 쓰기 → If-Match 412 → 다시 합쳐 200", put_log == [(412, ["if-match"]), (200, ["if-match"])], put_log)
store.begin_request()
check("다시 읽으면 내 것·끼어든 것 모두", store.load("probe", {}) == {"empty": True, "한글": "쪽지 왕복", "mine": 1, "theirs": 2})
put_log.clear()
store.load("probe2", {})["mine"] = 1   # 없던 기록
intruders[store._os_key("probe2")] = {"theirs": 2}
store.save("probe2")
check("새 기록: 틈에 끼어든 쓰기 → If-None-Match:* 412 → If-Match 200", put_log == [(412, ["if-none-match"]), (200, ["if-match"])], put_log)
store.begin_request()
check("probe2도 둘 다", store.load("probe2", {}) == {"mine": 1, "theirs": 2})
store._s3 = real_s3
store.clear_all()
store.begin_request()
check("clear_all 뒤 비어 있음", store.load("probe", None) is None)
print(f"\n{'실패 ' + str(len(fails)) + '건' if fails else '모두 통과'} · {time.time() - t0:.1f}초")
sys.exit(1 if fails else 0)
