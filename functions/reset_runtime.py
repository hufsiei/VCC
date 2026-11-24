# reset_runtime.py — 리허설 전에 쓰기 기록을 시연 시작 상태로 되돌린다 (작업 51, spec 2-1)
# 실행: cd C:\dev\VCC\functions
#   python reset_runtime.py         로컬(data/runtime). 서버(local_fn.py)가 켜져 있으면 먼저 끄고 실행한 뒤 다시 켠다.
#   python reset_runtime.py --ncp   공개 주소(Cloud Functions)의 기록 — Object Storage 버킷의 runtime/ 객체를 지운다(작업 58).
#                                   .env의 NCP_OS_BUCKET·NCP_OS_ACCESS_KEY·NCP_OS_SECRET_KEY를 쓴다. 액션은 요청마다 새로 읽으므로 재배포 필요 없음.
import os
import sys

import paths

if __name__ == "__main__":
    ncp = "--ncp" in sys.argv[1:]
    if ncp:
        paths.load_env()
        os.environ["STORE_BACKEND"] = "ncp"
        os.environ.setdefault("NCP_OS_PREFIX", "runtime/")
    import store

    store.clear_all()
    # 시연 시작 상태: 지금은 빈 상태. 미리 넣어 둘 기록이 생기면 여기에 store.load/save로 추가한다.
    if ncp:
        print(f"초기화했어요: Object Storage {os.environ.get('NCP_OS_BUCKET', '?')}/{os.environ['NCP_OS_PREFIX']}")
    else:
        print(f"초기화했어요: {store.RUNTIME}")
