# eval_latency.py — 공개 주소 응답 시간 재기 (작업 58, 미리)
#   python -X utf8 functions/eval_latency.py            # 로그인 1회 → getMe 5회 + askBoo 비교 질문(AI 0회) 5회
# 비번은 .env의 VCC_LOGIN_PW(JSON)에서 읽고 출력하지 않는다. 로그인이 거절되면 반복하지 않고 멈춘다.
# 일반 질문은 재지 않는다(AI 비용). 끝에 총시간 표(초)를 찍는다.
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://x1ey63q7ei.apigw.ntruss.com/vcc-api/dev"
ID = "H0143"
COMPARE_Q = "독일 다른 지역 대비 어떤건가요?"


ENV_PATH = Path("C:/dev/VCC/.env")   # 작업 폴더에는 .env를 복사하지 않는다(paths.py와 같은 원칙)


def _pw():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("VCC_LOGIN_PW"):
            v = line.partition("=")[2].strip().strip("'\"")
            t = json.loads(v)
            return t.get(ID) or t.get("*")
    sys.exit(".env에 VCC_LOGIN_PW 없음")


def call(name, body, token=""):
    req = urllib.request.Request(f"{BASE}/{name}?fn={name}", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Token": token})
    t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.loads(r.read().decode("utf-8"))
    return time.perf_counter() - t, out


def main():
    dt, out = call("login", {"id": ID, "pw": _pw()})
    if not out.get("ok"):
        sys.exit(f"로그인 거절({out.get('error')}) — 반복하지 않고 멈춤")
    token = out["user"]["token"]
    print(f"login {dt:.2f}s")
    rows = {"getMe": [], "askBoo(비교)": []}
    for _ in range(int(sys.argv[1]) if len(sys.argv) > 1 else 5):
        rows["getMe"].append(call("getMe", {}, token)[0])
        dt, out = call("askBoo", {"question": COMPARE_Q}, token)
        rows["askBoo(비교)"].append(dt)
    print("마지막 askBoo status:", out.get("status") if isinstance(out, dict) else out)
    for k, v in rows.items():
        print(f"{k:10s} " + " ".join(f"{x:.2f}" for x in v) + f"  | 중앙 {statistics.median(v):.2f}s 최소 {min(v):.2f}s")
    call("logout", {}, token)


if __name__ == "__main__":
    main()
