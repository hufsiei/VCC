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
check("틀린 비번 → FAIL", account.login("", {"id": "H0143", "pw": "1"}) == account.FAIL)
# H0469는 students.json에 있지만 VCC_LOGIN_PW에는 없다(비번 열이 `1`이어도 거절)
check("표에 없는 학번 → FAIL", account.login("", {"id": "H0469", "pw": "1"}) == account.FAIL)
check("없는 학번 → FAIL", account.login("", {"id": "H9999", "pw": "test-pw"}) == account.FAIL)
check("빈 비번 → FAIL", account.login("", {"id": "H0143", "pw": ""}) == account.FAIL)
s = account.login("", {"id": "staff01", "pw": "staff-pw"})
check("직원 로그인 → token 포함", s.get("ok") is True and s["user"].get("token") and s["user"]["status"] == "직원")
check("응답에 비번 없음", "비번" not in json.dumps(r, ensure_ascii=False) and "test-pw" not in json.dumps(r))
check("getMe에 비번 없음", "비번" not in account.getMe("H0143", {}))

os.environ["VCC_LOGIN_PW"] = "깨진 JSON"
check("VCC_LOGIN_PW 형식 오류 → 모두 FAIL", account.login("", {"id": "H0143", "pw": "test-pw"}) == account.FAIL)
os.environ.pop("VCC_LOGIN_PW")
check("VCC_LOGIN_PW 없음 → 모두 FAIL", account.login("", {"id": "H0143", "pw": "1"}) == account.FAIL)

os.environ["VCC_LOGIN_PW"] = json.dumps({"H0143": "test-pw"})
tok = account.login("", {"id": "H0143", "pw": "test-pw"})["user"]["token"]
check("logout 후 토큰 무효", account.logout("H0143", {"token": tok}).get("ok") and sessions.resolve(tok) == "")

print("\n".join(fails) or "test_account: 모두 통과")
sys.exit(1 if fails else 0)
