# 수요 설문 집계 (원우 담당, 작업 56) — 구글폼 응답 csv → 문항별 집계표 + 파급효과 슬라이드용 한 줄 수치
#
# 사용 (저장소 폴더에서):
#   python tools/survey_summary.py <응답 csv>                 # 결과 md를 csv와 같은 폴더에 저장
#   python tools/survey_summary.py <응답 csv> --out <폴더>
#
# - 응답 csv: 구글폼 [응답] 탭 → 「Sheets에 연결」 또는 ⋮ → 「응답 다운로드(.csv)」. 이름·학번·연락처·이메일은 받지 않는 폼이다.
# - 응답 원본 csv와 결과는 저장소 밖에만 둔다(자유 의견 원문이 있어서). csv가 저장소 안에 있으면 실행하지 않는다.
# - 자유 의견(Q15)은 원문을 옮기지 않고 응답 건수만 센다. 원문은 폼에서 사람이 읽는다.
# - 문항·보기는 설문\수요설문_구글폼_생성.gs(11/19 확정 15문항)와 같다. 폼 문구를 바꾸면 아래 Q 표도 같이 바꾼다.
# - 분모: Q4 답에 따라 건너뛰는 문항이 있어(섹션 2·3은 '찾아봄', 섹션 4는 '찾아봄·못 찾음'만) 문항마다 응답한 사람 수를 분모로 쓴다.
import argparse, csv, sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SOURCES = ["학교·부서 공지와 홈페이지", "귀국보고서·실습 후기 등 학교에 남은 기록", "아는 선배에게 직접",
           "학과 행사·설명회", "교수님·조교", "에브리타임 등 학내 커뮤니티", "오픈채팅방", "블로그·유튜브"]
EXP = ["교환학생·파견", "현장실습·인턴십", "비교과 프로그램"]
# (번호, 폼 제목, 종류, 보기) — 종류: one(하나) · multi(여럿, 기타 가능) · grid(행별 1~5) · text(자유)
Q = [
    ("Q1", "학년", "one", ["1학년", "2학년", "3학년", "4학년", "5학년 이상·졸업유예"]),
    ("Q2", "해 봤거나 지금 하고 있는 경험", "multi", EXP + ["아직 없음"]),
    ("Q3", "앞으로 해 보고 싶은 경험", "multi", EXP + ["없음"]),
    ("Q4", "위 경험을 준비하며 ‘먼저 다녀온 사람의 경험담’을 찾아본 적이 있나요?", "one",
     ["자주 찾아봤다", "한두 번 찾아봤다", "찾아보고 싶었지만 못 찾았다", "찾아볼 생각을 안 했다"]),
    ("Q5", "선배 경험 정보를 얻은 곳을 모두 골라 주세요", "multi", SOURCES),
    ("Q6", "그중 가장 도움이 된 곳 하나는?", "one", SOURCES),
    ("Q7", "각 정보원을 얼마나 믿을 수 있었나요?", "grid",
     ["학교·부서 공지와 홈페이지", "귀국보고서·실습 후기 등 학교 기록", "아는 선배에게 직접 들은 이야기",
      "학내 커뮤니티·오픈채팅방 글", "블로그·유튜브"]),
    ("Q8", "믿기 어려웠던 이유", "multi",
     ["정보가 오래됐다", "작성자가 누구인지, 정말 다녀왔는지 모르겠다", "나와 학과·상황이 달랐다",
      "사람마다 말이 달랐다", "공식 규정인지 개인 경험인지 구분이 안 됐다"]),
    ("Q9", "필요한 선배 경험 정보를 찾기 어려웠던 적이 있나요?", "one", ["자주 있었다", "가끔 있었다", "거의 없었다"]),
    ("Q10", "어떤 점이 어려웠나요?", "multi",
     ["정보가 여러 곳에 흩어져 있다", "내가 가려는 학교·기관 정보가 아예 없다", "물어볼 선배가 주변에 없다",
      "선배에게 먼저 연락하기가 부담스럽다", "비용·생활 등 구체적인 내용이 없다"]),
    ("Q11", "정보가 부족해서 지원을 미루거나 포기한 적이 있나요?", "one", ["포기한 적 있다", "미루기만 한 적 있다", "없다"]),
    ("Q12", "정보를 찾느라 한 프로그램당 대략 얼마나 걸렸나요?", "one",
     ["1시간 미만", "1~3시간", "3~10시간", "10시간 이상", "모르겠다"]),
    ("Q13", "아래 기능이 있다면 얼마나 쓰고 싶나요?", "grid",
     ["질문하면 선배 후기·보고서를 근거로 답하고 출처를 보여 주는 AI(근거가 없으면 답하지 않음)",
      "나와 학과·이중전공·경험이 비슷한 선배 추천",
      "서로 이름·학번을 모르는 상태로 선배에게 보내는 익명 쪽지",
      "학생들이 많이 묻는 질문을 담당 부서에 정기적으로 전달"]),
    ("Q14", "국제교류·인턴십·비교과 경험이 있는 분께: 후배를 위해 3분짜리 AI 인터뷰로 경험을 남길 의향이 있나요?", "one",
     ["있다", "공개 범위를 내가 정할 수 있으면 있다", "없다", "해당 경험 없음"]),
    ("Q15", "선배 경험 정보를 찾다가 답답했던 일이나 바라는 점이 있다면 자유롭게 적어 주세요", "text", []),
]
SHORT13 = ["근거·출처 보여 주는 AI", "비슷한 선배 추천", "익명 쪽지", "부서에 질문 전달"]


def norm(s):
    return " ".join((s or "").replace(" ", " ").split())


def find_col(head, title, row=None):
    """폼 제목으로 csv 열을 찾는다. 격자 문항은 「제목 [행]」 모양."""
    for i, h in enumerate(head):
        h_ = norm(h)
        if row is None and h_ == norm(title):
            return i
        if row is not None and h_.startswith(norm(title)) and h_.endswith(f"[{norm(row)}]"):
            return i
    return None


def split_multi(cell, options):
    """체크박스 칸: 구글폼은 ', '로 잇는데 보기 안에도 쉼표가 있어(Q8) 아는 보기를 먼저 뗀다. 남은 글자는 기타."""
    rest, got = norm(cell), []
    for o in sorted(options, key=len, reverse=True):
        if o in rest:
            got.append(o)
            rest = rest.replace(o, "")
    other = rest.strip(" ,")
    return got, bool(other)


def pct(n, d):
    return f"{n / d:.0%}" if d else "–"


def score(cell):
    c = norm(cell)
    return int(c[0]) if c[:1] in "12345" and c[:1] else None


def build(rows, head):
    out, facts, miss = [], {}, []
    n_all = len(rows)
    for qid, title, kind, opts in Q:
        if kind == "grid":
            lines = [f"### {qid}. {title}", "", "| 항목 | 응답 | 평균(1~5) | 4~5 비율 | 이용 안 함 |", "|---|---|---|---|---|"]
            found = False
            for k, r in enumerate(opts):
                col = find_col(head, title, r)
                if col is None:
                    miss.append(f"{qid} [{r}]")
                    continue
                found = True
                cells = [norm(x[col]) for x in rows if norm(x[col])]
                sc = [s for s in (score(c) for c in cells) if s]
                unused = sum("이용 안 함" in c for c in cells)
                avg = sum(sc) / len(sc) if sc else None
                hi = sum(s >= 4 for s in sc)
                name = SHORT13[k] if qid == "Q13" else r
                lines.append(f"| {name} | {len(sc)} | {avg:.1f} | {pct(hi, len(sc))} |" if avg else f"| {name} | 0 | – | – |")
                lines[-1] += f" {unused} |" if qid == "Q7" else " – |"
                facts[(qid, name)] = (hi, len(sc), avg)
            if found:
                out += lines + [""]
            continue
        col = find_col(head, title)
        if col is None:
            miss.append(qid)
            continue
        cells = [x[col] for x in rows if norm(x[col])]
        d = len(cells)
        if kind == "text":
            out += [f"### {qid}. {title}", "", f"응답 {d}건 (원문은 폼에서 읽는다 — 이 파일에 옮기지 않음)", ""]
            continue
        cnt, other = Counter(), 0
        for c in cells:
            if kind == "multi":
                got, oth = split_multi(c, opts)
                cnt.update(got)
                other += oth
            else:
                c = norm(c)
                if c in opts:
                    cnt[c] += 1
                else:
                    other += 1
        lines = [f"### {qid}. {title}", "", f"응답 {d}명" + (" (여럿 고름 — 합이 100%를 넘음)" if kind == "multi" else ""),
                 "", "| 보기 | 수 | 비율 |", "|---|---|---|"]
        for o in opts:
            lines.append(f"| {o} | {cnt[o]} | {pct(cnt[o], d)} |")
        if other:
            lines.append(f"| 기타(직접 입력) | {other} | {pct(other, d)} |")
        out += lines + [""]
        facts[qid] = (cnt, d)
    return out, facts, miss, n_all


def one_liners(f, n):
    """파급효과 슬라이드용 한 줄. 분모를 함께 적는다(문항마다 응답한 사람이 다름)."""
    L = []
    if "Q9" in f:
        c, d = f["Q9"]
        k = c["자주 있었다"] + c["가끔 있었다"]
        L.append(f"선배 경험 정보를 찾기 어려웠던 적이 있다 {pct(k, d)} ({k}/{d}명)")
    if "Q11" in f:
        c, d = f["Q11"]
        k = c["포기한 적 있다"] + c["미루기만 한 적 있다"]
        L.append(f"정보가 부족해 지원을 미루거나 포기한 적이 있다 {pct(k, d)} ({k}/{d}명, 포기 {c['포기한 적 있다']}명)")
    if "Q10" in f:
        c, d = f["Q10"]
        top = c.most_common(1)
        if top:
            L.append(f"가장 큰 어려움: 「{top[0][0]}」 {pct(top[0][1], d)} ({top[0][1]}/{d}명)")
    if "Q4" in f:
        c, d = f["Q4"]
        k = c["찾아보고 싶었지만 못 찾았다"]
        L.append(f"경험담을 찾아보고 싶었지만 못 찾았다 {pct(k, d)} ({k}/{d}명)")
    if "Q6" in f:
        c, d = f["Q6"]
        top = c.most_common(1)
        if top:
            L.append(f"가장 도움이 된 정보원 1위: 「{top[0][0]}」 {pct(top[0][1], d)} ({top[0][1]}/{d}명)")
    if "Q8" in f:
        c, d = f["Q8"]
        k = c["공식 규정인지 개인 경험인지 구분이 안 됐다"]
        L.append(f"공식 규정인지 개인 경험인지 구분이 안 돼 믿기 어려웠다 {pct(k, d)} ({k}/{d}명)")
    for name in SHORT13:
        if ("Q13", name) in f:
            hi, d, avg = f[("Q13", name)]
            L.append(f"「{name}」 쓰고 싶다(4~5점) {pct(hi, d)} ({hi}/{d}명, 평균 {avg:.1f})" if d else f"「{name}」 응답 없음")
    if "Q14" in f:
        c, d = f["Q14"]
        d2 = d - c["해당 경험 없음"]
        k = c["있다"] + c["공개 범위를 내가 정할 수 있으면 있다"]
        L.append(f"경험자 중 3분 AI 인터뷰로 경험을 남기겠다 {pct(k, d2)} ({k}/{d2}명, 공개 범위 조건부 {c['공개 범위를 내가 정할 수 있으면 있다']}명)")
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    src = Path(a.csv)
    out_dir = Path(a.out) if a.out else src.parent
    for p in (src, out_dir):
        try:
            p.resolve().relative_to(ROOT.resolve())
            sys.exit(f"응답 csv와 결과는 저장소 밖에 둡니다(자유 의견 원문): {p}")
        except ValueError:
            pass
    with open(src, encoding="utf-8-sig") as fh:
        rd = csv.reader(fh)
        head = next(rd)
        rows = [r + [""] * (len(head) - len(r)) for r in rd if any(x.strip() for x in r)]
    body, facts, miss, n = build(rows, head)
    lines = [f"# 수요 설문 집계 (작업 56) — 응답 {n}명", "",
             f"> 만든 때 {datetime.now():%Y-%m-%d %H:%M} · 원본 `{src.name}` · 이름·학번·연락처를 받지 않는 익명 설문. 자유 의견은 건수만.",
             f"> 목표 50명 대비 {n}명({pct(n, 50)})." + (" **응답 30명 미만 — 비율은 참고로만 쓴다.**" if n < 30 else ""), ""]
    if miss:
        lines += [f"> ⚠ csv에서 찾지 못한 문항: {', '.join(miss)} — 폼 문구가 바뀌었는지 확인", ""]
    lines += ["## 파급효과 슬라이드용 한 줄", ""] + [f"- {x}" for x in one_liners(facts, n)] + ["", "## 문항별 집계", ""] + body
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"설문집계_{datetime.now():%Y%m%d-%H%M}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:4 + len(one_liners(facts, n)) + 4]))
    print(f"\n저장: {out}")
    sys.exit(1 if miss else 0)


if __name__ == "__main__":
    main()
