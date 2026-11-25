# test_store_ncp_live.py — 실제 Object Storage 버킷 왕복 시험 (작업 58 ①). AI는 부르지 않는다.
# 실행: python -X utf8 functions/cloud/test_store_ncp_live.py
# 필요: .env(또는 환경변수)에 NCP_OS_BUCKET·NCP_OS_ACCESS_KEY·NCP_OS_SECRET_KEY. 값은 출력하지 않는다.
# 시험용 접두어(test-<시각>/)에만 쓰고 끝나면 지운다 — 시연 기록(runtime/)은 건드리지 않는다.
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


def check(label, ok):
    print(("통과 " if ok else "실패 ") + label)
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
store.clear_all()
store.begin_request()
check("clear_all 뒤 비어 있음", store.load("probe", None) is None)
print(f"\n{'실패 ' + str(len(fails)) + '건' if fails else '모두 통과'} · {time.time() - t0:.1f}초")
sys.exit(1 if fails else 0)
