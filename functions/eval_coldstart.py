# eval_coldstart.py — 공개 서버 콜드 스타트 재기 (작업 35 · #278 3-1, 미리)
#   python -X utf8 functions/eval_coldstart.py                 # 쉼 5·10·10·15·20분 → 각 회차 getMe 1번(쉰 뒤) + 이어서 4번
#   python -X utf8 functions/eval_coldstart.py --idle 1,1 --burst 3   # 짧게(흐름 확인용)
# AI를 부르지 않는다(getMe만). 로그인 1회, 비번은 .env의 VCC_LOGIN_PW에서 읽고 출력하지 않는다.
# 다른 사람이 그 사이 서버를 부르면 컨테이너가 깨어 있어 「쉰 뒤」 값이 작게 나온다 — 시각을 함께 남긴다.
# 결과: 회차별 한 줄 + 끝에 「쉰 뒤 첫 응답」과 「이어진 응답」 중앙값. --out이면 JSON으로도 남긴다.
import argparse
import json
import statistics
import time
from datetime import datetime

from eval_latency import _pw, call, ID


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idle", default="5,10,10,15,20", help="회차 사이 쉬는 분(쉼표)")
    ap.add_argument("--burst", type=int, default=4, help="쉰 뒤 첫 요청 다음에 이어서 보낼 요청 수")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    dt, out = call("login", {"id": ID, "pw": _pw()})
    if not out.get("ok"):
        raise SystemExit(f"로그인 거절({out.get('error')}) — 반복하지 않고 멈춤")
    token = out["user"]["token"]
    print(f"{datetime.now():%H:%M:%S} login {dt:.2f}s (이 응답 자체가 앞선 쉼 뒤 첫 요청)", flush=True)
    rounds = [{"at": datetime.now().isoformat(timespec="seconds"), "idle_min": None, "first": dt, "warm": []}]
    for _ in range(a.burst):
        rounds[0]["warm"].append(call("getMe", {}, token)[0])
    print(f"  이어서 {' '.join(f'{x:.2f}' for x in rounds[0]['warm'])}", flush=True)
    for m in [float(x) for x in a.idle.split(",") if x.strip()]:
        time.sleep(m * 60)
        first = call("getMe", {}, token)[0]
        warm = [call("getMe", {}, token)[0] for _ in range(a.burst)]
        rounds.append({"at": datetime.now().isoformat(timespec="seconds"), "idle_min": m, "first": first, "warm": warm})
        print(f"{datetime.now():%H:%M:%S} 쉼 {m:g}분 → 첫 {first:.2f}s · 이어서 {' '.join(f'{x:.2f}' for x in warm)}",
              flush=True)
    call("logout", {}, token)
    firsts = [r["first"] for r in rounds[1:]]
    warms = [x for r in rounds[1:] for x in r["warm"]]
    if firsts:
        print(f"쉰 뒤 첫 응답 중앙 {statistics.median(firsts):.2f}s 최대 {max(firsts):.2f}s · "
              f"이어진 응답 중앙 {statistics.median(warms):.2f}s · 차이(중앙) {statistics.median(firsts) - statistics.median(warms):+.2f}s")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(rounds, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
