# eval_pick.py — 작업 54 askBoo 고르기 정확도 실측 (작성: 미리)
#
# 실행:  cd C:\dev\VCC\functions
#        python eval_pick.py           # 답변 기대 40개 고르기 채점 + 테스트 키 한도 확인
#        python eval_pick.py --no-probe   # 한도 확인(연속 호출) 없이 채점만
#
# 기준(작업 54, HCX 원칙 v2 4절): 답변 기대 40개(11/20 확정, 처음 11/19는 25개)에 askBoo ①② 코드 단계를 그대로 돌리고 ③ 고르기(HCX)만 채점한다.
#   정답 = 고른 근거 중 하나라도 '기대 근거ID'에 있으면. 정확도 90% 미만이면 askBoo 고르기를 claude로(PROVIDER 표).
# 진단 지표(판정에는 쓰지 않음):
#   엄격     — 고른 근거가 전부 기대 근거ID 안
#   문항 일치 — 고른 근거가 기대 근거와 같은 보고서 문항(다른 선배의 같은 칸도 맞는 답이라서)
#   후보 포함 — ② 후보 문장 안에 기대 근거ID가 하나라도 있었나(없으면 고르기가 맞힐 수 없음)
# 결과는 functions/logs/eval-pick.json (.gitignore 대상).
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import ai
import askboo

EVID = {e["id"]: e for rows in askboo.EVIDENCE.values() for e in rows}


def item_of(sid):
    e = EVID.get(sid, {})
    return (e.get("프로그램명"), e.get("문항", "").split(".")[0] if e.get("docType") == "귀국보고서" else "후기")


def score():
    rows = [r for r in csv.DictReader(open(askboo.DATA / "eval-questions.csv", encoding="utf-8-sig"))
            if r["기대결과"] == "답변"]
    out, n = [], {"정답": 0, "엄격": 0, "문항 일치": 0, "후보 포함": 0, "보류·오류": 0}
    for r in rows:
        q = r["질문"]
        want = {s.strip() for s in r["기대 근거ID"].split(",") if s.strip()}
        progs = askboo.match_programs(q)
        cands, _, why = askboo.extract(q, progs) if progs else ([], None, "프로그램 없음")
        in_cands = bool(want & {c["sourceId"] for c in cands})
        picked, why2 = askboo.pick(q, cands) if cands else ([], why)
        got = [c["sourceId"] for c in picked]
        want_items = {item_of(s) for s in want}
        res = {
            "정답": bool(set(got) & want),
            "엄격": bool(got) and set(got) <= want,
            "문항 일치": bool(got) and all(item_of(s) in want_items for s in got),
            "후보 포함": in_cands,
            "보류·오류": not got,
        }
        for k, v in res.items():
            n[k] += v
        print(f"{'O' if res['정답'] else 'X'} {r['번호']:>2} 후보 {len(cands):>2} 고름 {got or why2}  기대 {sorted(want)}"
              f"{'' if in_cands else '  (기대 근거가 후보에 없음)'}")
        out.append({"번호": r["번호"], "질문": q, "기대": sorted(want), "고름": got, "후보수": len(cands),
                    "고른 문장": [c["text"] for c in picked], **res, "이유": why2})
    total = len(rows)
    print("\n" + " · ".join(f"{k} {v}/{total} ({v / total:.0%})" for k, v in n.items()))
    return out, n, total


def probe(count=15):
    """테스트 키 한도: 응답 헤더의 한도 정보와, 재시도 없이 짧게 연속 호출했을 때 429가 나오는지. 키는 출력하지 않는다."""
    key = ai.os.environ.get("CLOVA_KEY", "")
    body = json.dumps({"messages": [{"role": "user", "content": "1"}], "maxTokens": 1, "temperature": 0}).encode()
    headers_seen, codes, t0 = {}, [], time.time()
    for _ in range(count):
        req = urllib.request.Request(ai.CLOVA_URL, data=body,
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                codes.append(r.status)
                headers_seen = {k: v for k, v in r.headers.items() if "limit" in k.lower() or "retry" in k.lower()}
        except urllib.error.HTTPError as e:
            codes.append(e.code)
            if e.code == 429:
                headers_seen = {k: v for k, v in e.headers.items() if "limit" in k.lower() or "retry" in k.lower()}
    sec = time.time() - t0
    print(f"\n한도 확인: {count}회 연속 {sec:.1f}초 — 응답 코드 {codes}")
    print(f"한도 관련 헤더: {headers_seen or '없음'}")
    return {"호출": count, "초": round(sec, 1), "코드": codes, "헤더": headers_seen}


if __name__ == "__main__":
    out, n, total = score()
    lim = None if "--no-probe" in sys.argv else probe()
    import paths
    path = paths.LOGS / "eval-pick.json"   # 본 저장소 logs(paths.py)
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"결과": out, "합계": n, "전체": total, "한도": lim}, ensure_ascii=False, indent=2),
                    encoding="utf-8")
