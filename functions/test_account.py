# test_account.py — account.login 시험 (작업 73). 실행: cd functions && python test_account.py
# VCC_LOGIN_PW는 시험용 값으로 덮어쓴다(실제 .env 값을 쓰지 않는다). 하나라도 틀리면 종료코드 1.
import json
import os
import sys

import account
import sessions
import store

store.save = lambda name: None
store._cache["sessions"] = {}
os.environ["VCC_LOGIN_PW"] = json.dumps({"H0143": "test-pw", "staff01": "staff-pw"})

fails = []


def check(label, ok):
    if not ok:
        fails.append(label)


r = account.login("", {"id": "H0143", "pw": "test-pw"})
check("맞는 비번 → ok+token", r.get("ok") is True and r["user"].get("token") and sessions.resolve(r["user"]["token"]) == "H0143")
r2 = account.login("", {"id": "h0143", "pw": "test-pw"})
check("소문자 h0143도 ok, user.colreg_no는 H0143", r2.get("ok") is True and r2["user"]["colreg_no"] == "H0143")
check("틀린 비번 → FAIL", account.login("", {"id": "H0143", "pw": "1"}) == account.FAIL)
# H0469는 students.json에 있지만 VCC_LOGIN_PW에는 없다 → 거절
check("표에 없는 학번 → FAIL", account.login("", {"id": "H0469", "pw": "1"}) == account.FAIL)
# 데이터 행에 비번 필드가 끼어 들어와도 서버는 믿지 않는다(옛 students.json 모양)
_orig = account.student
account.student = lambda uid: {**(_orig(uid) or {}), "비번": "1"}
check("행의 비번 필드는 무시 → FAIL", account.login("", {"id": "H0469", "pw": "1"}) == account.FAIL)
account.student = _orig
check("없는 학번 → FAIL", account.login("", {"id": "H9999", "pw": "test-pw"}) == account.FAIL)
check("빈 비번 → FAIL", account.login("", {"id": "H0143", "pw": ""}) == account.FAIL)
s0 = account.login("", {"id": "STAFF01", "pw": "staff-pw"})
check("대문자 STAFF01도 ok, colreg_no는 staff01", s0.get("ok") is True and s0["user"]["colreg_no"] == "staff01")
s = account.login("", {"id": "staff01", "pw": "staff-pw"})
check("직원 로그인 → token 포함", s.get("ok") is True and s["user"].get("token") and s["user"]["status"] == "직원")
check("응답에 비번 없음", "비번" not in json.dumps(r, ensure_ascii=False) and "test-pw" not in json.dumps(r))
check("getMe에 비번 없음", "비번" not in account.getMe("H0143", {}))

os.environ["VCC_LOGIN_PW"] = json.dumps({"*": "common-pw", "H0143": "test-pw", "staff01": "staff-pw"})
check("공용 비번(*)으로 표에 없는 학생 ok", account.login("", {"id": "H0469", "pw": "common-pw"}).get("ok") is True)
check("개별 항목이 공용보다 우선 → H0143은 common-pw로 FAIL", account.login("", {"id": "H0143", "pw": "common-pw"}) == account.FAIL)
check("공용 비번은 직원에 적용 안 됨 → staff02 FAIL", account.login("", {"id": "staff02", "pw": "common-pw"}) == account.FAIL)
check("공용 비번도 없는 학번(H9999)은 FAIL", account.login("", {"id": "H9999", "pw": "common-pw"}) == account.FAIL)
store._cache["loginFails"] = {}   # 위에서 H0143을 틀린 횟수를 비운다(아래 두 줄이 실패 한도에 걸리지 않게)
os.environ["VCC_LOGIN_PW"] = "깨진 JSON"
check("VCC_LOGIN_PW 형식 오류 → 모두 FAIL", account.login("", {"id": "H0143", "pw": "test-pw"}) == account.FAIL)
os.environ.pop("VCC_LOGIN_PW")
check("VCC_LOGIN_PW 없음 → 모두 FAIL", account.login("", {"id": "H0143", "pw": "1"}) == account.FAIL)

os.environ["VCC_LOGIN_PW"] = json.dumps({"H0143": "test-pw"})
tok = account.login("", {"id": "H0143", "pw": "test-pw"})["user"]["token"]
check("logout 후 토큰 무효", account.logout("H0143", {"token": tok}).get("ok") and sessions.resolve(tok) == "")

# ---------- 로그인 실패 한도 (작업 38): 1분에 5번 틀리면 60초 막힘 ----------
import types
import limits

clock = [1_800_000_000.0]
limits.time = types.SimpleNamespace(time=lambda: clock[0])
store._cache["loginFails"] = {}
os.environ["VCC_LOGIN_PW"] = json.dumps({"H0143": "test-pw", "staff01": "staff-pw"})


def tick(sec):
    clock[0] += sec


res = []
for _ in range(4):
    res.append(account.login("", {"id": "staff01", "pw": "x"}))
    tick(5)
check("4번째 실패까지는 평소 FAIL", all(r == account.FAIL for r in res))
r5 = account.login("", {"id": "staff01", "pw": "x"})
check("5번째 실패 → 막힘 + retryAfter 60", r5.get("ok") is False and r5.get("retryAfter") == limits.LOGIN_LOCK
      and "60초 뒤" in r5.get("reason", ""))
tick(20)
r6 = account.login("", {"id": "staff01", "pw": "staff-pw"})
check("막힌 동안은 맞는 비번도 막힘 + 남은 40초", r6.get("ok") is False and r6.get("retryAfter") == 40 and "token" not in json.dumps(r6))
check("막힌 동안 대문자 STAFF01도 같은 계정으로 막힘", account.login("", {"id": "STAFF01", "pw": "staff-pw"}).get("retryAfter") == 40)
check("다른 계정(H0143)은 영향 없음", account.login("", {"id": "H0143", "pw": "test-pw"}).get("ok") is True)
tick(40)
check("60초 지나면 풀림 → 맞는 비번 ok", account.login("", {"id": "staff01", "pw": "staff-pw"}).get("ok") is True)
check("성공하면 실패 기록 지움", "staff01" not in store._cache["loginFails"])

# 성공 로그인은 세지 않는다 — 두 창·여러 창 시연
check("맞는 비번 30번 연속 → 모두 ok", all(account.login("", {"id": "staff01", "pw": "staff-pw"}).get("ok") for _ in range(30)))
# 틀림 4번 → 성공 → 틀림 4번: 성공이 기록을 지우므로 막히지 않는다
for _ in range(4):
    account.login("", {"id": "staff01", "pw": "x"})
account.login("", {"id": "staff01", "pw": "staff-pw"})
res = [account.login("", {"id": "staff01", "pw": "x"}) for _ in range(4)]
check("성공 사이에 낀 실패는 이어 세지 않음", all(r == account.FAIL for r in res))
# 1분이 지나면 실패 수가 새로 시작
store._cache["loginFails"] = {}
for _ in range(4):
    account.login("", {"id": "staff01", "pw": "x"})
tick(61)
check("창(60초)이 지나면 다시 5번", account.login("", {"id": "staff01", "pw": "x"}) == account.FAIL)
# 없는 계정은 세지도 저장하지도 않는다
for _ in range(10):
    account.login("", {"id": "H9999", "pw": "x"})
check("없는 계정 10번 → 계속 FAIL, 기록 없음", account.login("", {"id": "H9999", "pw": "x"}) == account.FAIL
      and "H9999" not in store._cache["loginFails"])
# 지난 기록은 다른 실패가 올 때 정리된다
store._cache["loginFails"] = {"H0469": {"since": clock[0] - 120, "fails": 2, "until": 0}}
account.login("", {"id": "staff01", "pw": "x"})
check("창·잠금 끝난 기록 정리", "H0469" not in store._cache["loginFails"])

print("\n".join(fails) or "test_account: 모두 통과")
sys.exit(1 if fails else 0)
