# eval_overlap.py — 겹쳐 돌리기(작업 35 · #278 3-3)가 응답을 바꾸지 않는지 90문항으로 확인 (미리)
#   python -X utf8 functions/eval_overlap.py          # AI 없음(가짜 callAI) — 돈 안 듦
# 질문: data/eval-questions.csv + eval-questions-multi.csv(run_eval --all90과 같은 90문항, 이전대화 포함).
# 질문마다 질문정리 결과를 5가지(경험질문·탐색·대화·규정·실패)로 바꿔 가며 VCC_ASK_OVERLAP=0/1 두 번 돌려
# 응답 전체(status·lines·sources·message …)가 같은지 본다. 가짜 답쓰기는 질문 글과 무관하게 같은 답을 내므로,
# 다른 점이 나오면 길(순서·조건)이 바뀐 것이다. 실제 답 글이 원래 질문/다듬은 질문 차이로 달라지는지는 eval_overlap_live로.
# 결과: 바뀐 응답 수(0이어야 함) · 미리 시작한 답쓰기 쓰임/버림 수.
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "functions"))
sys.path.insert(0, str(ROOT / "tools"))
os.environ["VCC_ASK_FULL"] = "1"
import askboo  # noqa: E402
import run_eval  # noqa: E402


def ok(j):
    return {"ok": True, "text": "", "json": j, "model": "fake"}


def make_fake(plan):
    def fake(작업명, messages, system=None, cache=None, **_):
        if 작업명 == "질문정리":
            return ok(plan) if plan else {"ok": False, "json": None}
        if 작업명 == "답쓰기-전문":   # 1번 문단 첫 문장을 해요체로 옮기고 1-1을 단다
            m = re.search(r"^  \[1-1\] (.+)$", cache or "", re.M)
            return ok({"답": [{"text": "선배들은 이렇게 말했다고 해요.", "근거": ["1-1"]}]} if m else {"답": []})
        return run_eval.dry_call(작업명, messages, system)
    return fake


def plans(q):
    base = {"분야": None, "나라": None, "프로그램후보": [], "제외": [], "칸": None, "정리된질문": q.rstrip("?") + "?"}
    return {"경험질문": {**base, "의도": "경험질문"}, "탐색": {**base, "의도": "탐색"},
            "대화": {**base, "의도": "대화"}, "규정": {**base, "의도": "규정"}, "실패": None}


def main():
    rows = run_eval.read_questions(ROOT / "data" / "eval-questions.csv") \
        + run_eval.read_questions(ROOT / "data" / "eval-questions-multi.csv")
    print(f"질문 {len(rows)}개 × 질문정리 5가지 × 겹쳐 돌리기 끔/켬")
    diff, used, status = [], Counter(), Counter()
    for r in rows:
        q, hist = r["질문"], run_eval.read_history(r.get("이전대화"))
        for label, plan in plans(q).items():
            out = {}
            for flag in ("0", "1"):
                os.environ["VCC_ASK_OVERLAP"] = flag
                askboo.callAI = make_fake(plan)
                trace = {}
                # askBoo 뒤처리(officialCheck)는 응답만 보고 붙으므로 _answer끼리 비교하면 충분하다(trace를 보려고 _answer를 부름)
                res = askboo._answer("eval", {"question": q, "history": hist}, False, trace)
                sp = trace.get("overlap")
                if sp:
                    sp["future"].result()
                    used["쓰임" if sp.get("used") else "버림"] += 1
                out[flag] = res
            status[out["0"].get("status")] += 1
            if out["0"] != out["1"]:
                diff.append((r["번호"], label, out["0"].get("status"), out["1"].get("status")))
    print("응답 status(끔 기준):", dict(status.most_common()))
    print(f"미리 시작한 답쓰기: 쓰임 {used['쓰임']} · 버림 {used['버림']}")
    print(f"끔/켬 응답이 다른 경우: {len(diff)}건")
    for d in diff[:20]:
        print("  ", d)
    os.environ.pop("VCC_ASK_OVERLAP", None)
    return 1 if diff else 0


if __name__ == "__main__":
    sys.exit(main())
