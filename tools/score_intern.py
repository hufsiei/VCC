# 인턴 문장 분류 채점 (원우 담당, 작업 50)
# 사용: python -X utf8 tools/score_intern.py            # 기본: data/intern-sections.json 채점
#       python -X utf8 tools/score_intern.py --pred 다른결과.json   # 모델 비교 등 다른 분류 결과 채점
# 정답: data/intern-gold.csv (원우가 직접 확정한 128문장, 열 `id` `문장` `정답 칸` `비고`)
# 예측: {"I001-1": "업무내용", ...} 모양의 JSON (classify_intern.py 결과)
# 출력: 전체 정확도 n/N, 칸별 정확도, 헷갈림 표본 정확도, 틀린 문장 표, 혼동표.
# 합격선 85%(작업 50). 미달이거나 정답 id가 예측에 없으면 종료코드 1.
# 첫 결과 숫자는 고치지 않고 일지에 그대로 기록한다(팀 가이드 v6).
import argparse, csv, json, sys
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
PASS = 0.85


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default=DATA / "intern-gold.csv")
    ap.add_argument("--pred", default=DATA / "intern-sections.json")
    a = ap.parse_args()

    gold = list(csv.DictReader(open(a.gold, encoding="utf-8-sig")))
    pred = json.loads(Path(a.pred).read_text(encoding="utf-8"))
    sections = json.loads((DATA / "frames.json").read_text(encoding="utf-8"))["인턴"]
    allowed = [c for c in sections["칸"] if c not in sections.get("인터뷰로만", [])]

    bad_gold = [r["id"] for r in gold if r["정답 칸"] not in allowed]
    missing = [r["id"] for r in gold if r["id"] not in pred]
    if bad_gold:
        print(f"정답 칸이 인턴 칸 목록 밖: {bad_gold}")

    ok = 0
    per, per_ok = Counter(), Counter()
    tricky, tricky_ok = 0, 0
    confusion = Counter()
    wrong = []
    for r in gold:
        g, p = r["정답 칸"], pred.get(r["id"], "(없음)")
        per[g] += 1
        confusion[(g, p)] += 1
        hit = g == p
        ok += hit
        per_ok[g] += hit
        if r.get("비고") == "헷갈림":
            tricky += 1
            tricky_ok += hit
        if not hit:
            wrong.append((r["번호"], r["id"], g, p, r["문장"]))

    n = len(gold)
    print(f"예측 파일: {Path(a.pred).name}")
    print(f"전체 {ok}/{n} = {ok / n:.1%}  (합격선 {PASS:.0%} {'통과' if ok / n >= PASS else '미달'})")
    for c in allowed:
        if per[c]:
            print(f"  {c}: {per_ok[c]}/{per[c]} = {per_ok[c] / per[c]:.1%}")
    if tricky:
        print(f"  헷갈림 표본: {tricky_ok}/{tricky}")

    cols = allowed + (["(없음)"] if missing else [])
    print("\n혼동표 (행=정답, 열=예측)")
    print("정답\\예측\t" + "\t".join(cols))
    for g in allowed:
        print(g + "\t" + "\t".join(str(confusion[(g, p)]) for p in cols))

    if wrong:
        print(f"\n틀린 문장 {len(wrong)}건 (번호 | id | 정답 → 예측 | 문장)")
        for w in wrong:
            print(f"{w[0]} | {w[1]} | {w[2]} → {w[3]} | {w[4]}")
    if missing:
        print(f"\n예측에 없는 정답 id {len(missing)}건: {missing[:10]}")

    sys.exit(0 if ok / n >= PASS and not missing and not bad_gold else 1)


if __name__ == "__main__":
    main()
