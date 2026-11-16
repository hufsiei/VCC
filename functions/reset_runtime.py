# reset_runtime.py — 리허설 전에 쓰기 기록을 시연 시작 상태로 되돌린다 (작업 51, spec 2-1)
# 실행: cd C:\dev\VCC\functions  →  python reset_runtime.py
# 서버(local_fn.py)가 켜져 있으면 먼저 끄고 실행한 뒤 다시 켠다(서버가 메모리에 옛 기록을 들고 있음).
import store

if __name__ == "__main__":
    store.clear_all()
    # 시연 시작 상태: 지금은 빈 상태. 미리 넣어 둘 기록이 생기면 여기에 store.load/save로 추가한다.
    print(f"초기화했어요: {store.RUNTIME}")
