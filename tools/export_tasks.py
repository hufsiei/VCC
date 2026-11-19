# -*- coding: utf-8 -*-
"""작업내역 엑셀 + 작업일지 → docs/tasks.json (팀 문서함 「이틀 가이드」가 읽는 파일)

실행(미리 PC, 저장소 루트에서):
    python -X utf8 tools/export_tasks.py
기본 입력:
    엑셀    = 저장소 위 드라이브 폴더 @VCC 의 가장 최신 "@VCC작업내역 v*.xlsx"
    작업일지 = 같은 폴더의 작업일지/*.md  → docs/작업일지/ 로 복사
출력:
    docs/tasks.json  { generatedAt, source, tasks[], notices[], roles[], journals[] }
작업내역을 고치거나 작업일지가 올라오면 다시 실행하고 커밋한다(작업 49와 함께, 하루 끝에).
담당: 미리(이 스크립트만 tools/ 안에서 미리가 관리한다).
"""
import glob, json, os, re, shutil, sys, datetime
import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVE = os.environ.get("VCC_DRIVE", r"H:\내 드라이브\@VCC")

def latest_xlsx():
    files = glob.glob(os.path.join(DRIVE, "@VCC작업내역 v*.xlsx"))
    if not files:
        sys.exit("작업내역 xlsx를 찾지 못했습니다: " + DRIVE)
    def ver(p):
        m = re.search(r"v(\d+(?:\.\d+)?)", os.path.basename(p)); return float(m.group(1)) if m else 0
    return max(files, key=ver)

def cell(v):
    if v is None: return ""
    if isinstance(v, (datetime.datetime, datetime.date)): return v.strftime("%Y-%m-%d")
    if isinstance(v, float):
        if 40000 < v < 60000:  # 엑셀 날짜 일련번호
            return (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(v))).strftime("%Y-%m-%d")
        if v.is_integer(): return str(int(v))
    return str(v).strip()

def norm_date(s):
    s = cell(s)
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3))) if m else s

def main():
    xlsx = latest_xlsx()
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    out = {"generatedAt": datetime.datetime.now().astimezone().isoformat(timespec="minutes"),
           "source": os.path.basename(xlsx), "tasks": [], "notices": [], "roles": [], "journals": []}

    ws = wb["작업목록"]
    heads = [cell(c.value) for c in ws[1]]
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] is None: continue
        d = {heads[i]: cell(v) for i, v in enumerate(row) if i < len(heads) and heads[i]}
        try: d["번호"] = str(int(float(d["번호"])))
        except Exception: pass
        for k in ("시작", "기한"): d[k] = norm_date(d.get(k))
        d["담당자들"] = [x.strip() for x in re.split(r"[,·/]", d.get("담당", "")) if x.strip()]
        d["함께들"] = [x.strip() for x in re.split(r"[,·/]", d.get("함께", "")) if x.strip()]
        d["선행들"] = [x.strip() for x in re.split(r"[,·/\s]+", d.get("선행 작업(번호)", "")) if x.strip()]
        out["tasks"].append(d)

    ws = wb["전달사항"]
    heads = [cell(c.value) for c in ws[1]]
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] is None and row[2] is None: continue
        out["notices"].append({heads[i]: cell(v) for i, v in enumerate(row) if i < len(heads) and heads[i]})

    ws = wb["팀원별 역할"]
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] is None: continue
        out["roles"].append({"주차": cell(row[0]), "단계": cell(row[1]), "미리": cell(row[2]), "원우": cell(row[3]), "민지": cell(row[4])})

    jdir_src = os.path.join(DRIVE, "작업일지"); jdir_dst = os.path.join(ROOT, "docs", "작업일지")
    os.makedirs(jdir_dst, exist_ok=True)
    for p in sorted(glob.glob(os.path.join(jdir_src, "*.md"))):
        name = os.path.basename(p)
        shutil.copy2(p, os.path.join(jdir_dst, name))
        who = next((w for w in ("미리", "원우", "민지") if w in name), "")
        out["journals"].append({"path": "docs/작업일지/" + name, "author": who,
                                "updated": datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d")})

    dst = os.path.join(ROOT, "docs", "tasks.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", dst, "tasks", len(out["tasks"]), "notices", len(out["notices"]), "journals", len(out["journals"]), "from", out["source"])

if __name__ == "__main__":
    main()
