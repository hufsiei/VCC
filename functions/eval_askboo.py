# eval_askboo.py — askBoo 개발 질문 70개 채점 (작업 18 완료 기준)
#
# 실행:  cd C:\dev\VCC\functions
#        python eval_askboo.py            # 70개 전부 (HCX 호출, 키는 .env)
#        python eval_askboo.py 2 23 30    # 고른 번호만
# 완료 기준: 보류 20개 전부 hold · 공식안내 10개 전부 official · 답변 40개 전부 ok이고 근거 밖 문장 0건
# 근거 밖 판정: 답변 문장마다 askboo.verify(문장, 출처 문단 원문)를 다시 돌린다(숫자·영문·고유명사·새 낱말).
#   폴백 줄(군말만 지운 원문)도 같은 검사를 거친다. 질문함에는 저장하지 않는다(save=False).
# 결과 전체는 functions/logs/eval-askboo.json (.gitignore 대상)에 남긴다 — 사람이 문장을 직접 훑어보는 용도.
import csv
import json
import sys
from pathlib import Path

import askboo

EXPECT = {"답변": "ok", "보류": "hold", "공식안내": "official"}
EVID = {e["id"]: e for rows in askboo.EVIDENCE.values() for e in rows}


def main(only):
    rows = list(csv.DictReader(open(askboo.DATA / "eval-questions.csv", encoding="utf-8-sig")))
    if only:
        rows = [r for r in rows if r["번호"] in only]
    results, wrong, outside, fallbacks = [], 0, 0, 0
    for r in rows:
        want = EXPECT[r["기대결과"]]
        res = askboo.askBoo("eval", {"question": r["질문"]}, save=False)
        got = res.get("status", "error")
        ok = got == want
        bad_lines = []
        for ln in res.get("lines", []):
            fallbacks += bool(ln.get("fallback"))
            src = EVID.get(ln["sourceId"], {}).get("text", "")
            probs = askboo.verify(ln["text"], src)   # 폴백 줄도 다시 검사한다
            if probs:
                bad_lines.append({"text": ln["text"], "problems": probs})
        outside += len(bad_lines)
        wrong += not ok
        mark = "OK" if ok and not bad_lines else "XX"
        print(f"{mark} {r['번호']:>2} [{r['기대결과']}→{got}] {r['질문']}")
        if got == "hold" and res.get("_why"):
            print(f"        보류 이유: {res['_why']}")
        for ln in res.get("lines", []):
            print(f"        {'(원문)' if ln.get('fallback') else '      '} {ln['text']}  [{ln['sourceId']}]")
        for b in bad_lines:
            print(f"        !! 근거 밖 의심: {b['problems']}")
        if got == "official":
            print(f"        → {res.get('officialUrl')}")
        results.append({"번호": r["번호"], "질문": r["질문"], "기대": want, "결과": res, "근거밖": bad_lines})

    n = {k: sum(1 for x in results if x["기대"] == v) for k, v in EXPECT.items()}
    hit = {k: sum(1 for x in results if x["기대"] == v and x["결과"].get("status") == v) for k, v in EXPECT.items()}
    print(f"\n답변 {hit['답변']}/{n['답변']} · 보류 {hit['보류']}/{n['보류']} · 공식안내 {hit['공식안내']}/{n['공식안내']}"
          f" · 근거 밖 의심 문장 {outside}건 · 원문 폴백 {fallbacks}줄")
    import paths
    out = paths.LOGS / "eval-askboo.json"   # 본 저장소 logs(paths.py)
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.exit(1 if wrong or outside else 0)


if __name__ == "__main__":
    main(set(sys.argv[1:]))
