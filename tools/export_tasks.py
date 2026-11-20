# -*- coding: utf-8 -*-
"""작업내역 엑셀 + 작업일지 → docs/tasks.json (팀 문서함 「이틀 가이드」가 읽는 파일)

실행(어느 컴퓨터든, 저장소 루트에서):
    python -X utf8 tools/export_tasks.py
입력을 찾는 순서:
    1) 환경변수 VCC_DRIVE (드라이브 @VCC 폴더 경로를 직접 지정할 때)
    2) 이 컴퓨터에 마운트된 구글 드라이브의 「내 드라이브/@VCC」 (드라이브 문자 H:·I: 등 자동 탐색)
    3) 둘 다 없으면 작업내역 공유 링크(VCC_XLSX_URL)에서 xlsx를 받아 씀
    엑셀    = @VCC 폴더의 가장 최신 "@VCC작업내역 v*.xlsx" (3번은 링크의 파일)
    작업일지 = @VCC/작업일지/*.md → docs/작업일지/ 로 복사 (3번이면 복사 없이 저장소에 있는 docs/작업일지/ 를 그대로 씀)
출력:
    docs/tasks.json     { generatedAt, source, tasks[], notices[], roles[], journals[] }  (커밋 대상)
    docs/hub-data.json  위 내용 + 기준 문서 전문 + 최근 커밋 40개 묶음 (커밋하지 않음, 팀 문서함에 「자료 올리기」)
작업내역을 고치거나 작업일지가 올라오면 다시 실행하고 커밋한다(작업 49와 함께, 하루 끝에).
담당: 미리(이 스크립트만 tools/ 안에서 미리가 관리한다).
"""
import glob, io, json, os, re, string, sys, datetime, urllib.parse, urllib.request
import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX_PATTERN = "@VCC작업내역 v*.xlsx"
# 작업내역 공유 링크(링크가 있는 사람 누구나 보기). 파일을 새 버전으로 바꾸면 이 ID도 바꾼다.
XLSX_URL = os.environ.get("VCC_XLSX_URL",
    "https://docs.google.com/spreadsheets/d/1GHNSffY1G-lcLGAmuvjYHmj7Vz8biYHJ/export?format=xlsx")

def find_drive():
    """@VCC 폴더 경로. 컴퓨터마다 구글 드라이브 문자(H:, I: …)가 달라서 직접 찾는다. 없으면 None."""
    env = os.environ.get("VCC_DRIVE")
    if env:
        if not os.path.isdir(env): sys.exit("VCC_DRIVE 폴더가 없습니다: " + env)
        return env
    for letter in string.ascii_uppercase:
        for my in ("내 드라이브", "My Drive"):
            p = os.path.join(letter + ":\\", my, "@VCC")
            if os.path.isdir(p) and glob.glob(os.path.join(p, XLSX_PATTERN)):
                return p
    return None

def latest_xlsx(drive):
    files = glob.glob(os.path.join(drive, XLSX_PATTERN))
    if not files:
        sys.exit("작업내역 xlsx를 찾지 못했습니다: " + drive)
    def ver(p):
        m = re.search(r"v(\d+(?:\.\d+)?)", os.path.basename(p)); return float(m.group(1)) if m else 0
    return max(files, key=ver)

def git_date(path):
    """저장소 파일의 마지막 커밋 날짜(커밋 전이면 파일 수정 날짜)."""
    import subprocess
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%ad", "--date=short", "--", path],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        if r.stdout.strip(): return r.stdout.strip()
    except Exception: pass
    return datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")

def download_xlsx():
    """공유 링크에서 xlsx를 받아 (파일 이름, 메모리 파일)로 돌려준다."""
    try:
        with urllib.request.urlopen(XLSX_URL, timeout=60) as r:
            data, cd = r.read(), r.headers.get("Content-Disposition", "")
    except Exception as e:
        sys.exit("작업내역을 드라이브에서도 링크에서도 찾지 못했습니다(%s): %s" % (e, XLSX_URL))
    if not data.startswith(b"PK"):
        sys.exit("링크에서 받은 파일이 xlsx가 아닙니다. 공유 설정(링크가 있는 사람 누구나 보기)을 확인하세요: " + XLSX_URL)
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd)
    name = urllib.parse.unquote(m.group(1)) if m else "@VCC작업내역(공유 링크).xlsx"
    return name, io.BytesIO(data)

# 저장소가 공개이므로 개인 연락처는 내보내기 전에 가린다(학교 공용 @hufs.ac.kr 주소는 유지).
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@(?![A-Za-z0-9.-]*hufs\.ac\.kr\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"01[016789][-.\s]?\d{3,4}[-.\s]?\d{4}")

def mask_private(s):
    return _PHONE.sub("(연락처 생략)", _EMAIL.sub("(개인 메일 생략)", s))

def cell(v):
    return mask_private(_cell(v))

def _cell(v):
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
    drive = find_drive()
    if drive:
        xlsx = latest_xlsx(drive); source = os.path.basename(xlsx)
        print("작업내역:", xlsx)
    else:
        source, xlsx = download_xlsx()
        print("드라이브 @VCC 폴더가 없어 공유 링크에서 받았습니다:", source)
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    out = {"generatedAt": datetime.datetime.now().astimezone().isoformat(timespec="minutes"),
           "source": source, "tasks": [], "notices": [], "roles": [], "journals": []}

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

    jdir_dst = os.path.join(ROOT, "docs", "작업일지")
    os.makedirs(jdir_dst, exist_ok=True)
    if drive:  # 드라이브 원본을 연락처 가려서 복사(예전과 같음)
        srcs = sorted(glob.glob(os.path.join(drive, "작업일지", "*.md")))
    else:      # 드라이브가 없으면 저장소에 이미 있는 작업일지를 그대로 쓴다
        print("주의: 드라이브 작업일지는 복사하지 못했습니다. 저장소 docs/작업일지/ 를 그대로 씁니다.")
        srcs = sorted(glob.glob(os.path.join(jdir_dst, "*.md")))
    for p in srcs:
        name = os.path.basename(p)
        if drive:
            with open(p, encoding="utf-8") as f: text = f.read()
            with open(os.path.join(jdir_dst, name), "w", encoding="utf-8", newline="") as f: f.write(mask_private(text))
            updated = datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d")
        else:
            updated = git_date(p)
        who = next((w for w in ("미리", "원우", "민지") if w in name), "")
        out["journals"].append({"path": "docs/작업일지/" + name, "author": who, "updated": updated})
    # 드라이브에는 없고 저장소에 PR로 바로 올라온 작업일지도 목록에 넣는다
    listed = {j["path"] for j in out["journals"]}
    for p in sorted(glob.glob(os.path.join(jdir_dst, "*.md"))):
        name = os.path.basename(p)
        if "docs/작업일지/" + name in listed: continue
        who = next((w for w in ("미리", "원우", "민지") if w in name), "")
        out["journals"].append({"path": "docs/작업일지/" + name, "author": who, "updated": git_date(p)})

    dst = os.path.join(ROOT, "docs", "tasks.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote", dst, "tasks", len(out["tasks"]), "notices", len(out["notices"]), "journals", len(out["journals"]), "from", out["source"])

    # ---- 팀 문서함 「이틀 가이드」가 읽는 묶음 파일 (아티팩트는 외부 fetch가 막혀 있어 파일로 올린다) ----
    import subprocess
    def read(rel):
        try: return open(os.path.join(ROOT, rel), encoding="utf-8").read()
        except Exception as e: return ""
    docs = {"PRD": read("docs/PRD-v1.md"), "spec": read("docs/spec-v1.md"), "디자인 규칙": read("docs/design-rules.md"),
            "CLAUDE.md": read("CLAUDE.md"), "HCX 원칙": read("docs/HCX-원칙-v2.md"), "frames.json": read("data/frames.json"),
            "data/README": read("data/README.md")}
    for j in out["journals"]:
        j["text"] = read(j["path"])
    commits, sha = [], ""
    try:
        log = subprocess.run(["git", "log", "-n", "40", "--date=short", "--pretty=format:%h|%ad|%an|%s", "origin/main"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        for ln in log.stdout.splitlines():
            h, d, a, m = ln.split("|", 3); commits.append({"sha": h, "date": d, "author": a, "message": m})
        sha = commits[0]["sha"] if commits else ""
    except Exception: pass
    bundle = {"kind": "vcc-hub-data", "version": 1, "generatedAt": out["generatedAt"], "source": out["source"], "head": sha,
              "tasks": out["tasks"], "notices": out["notices"], "roles": out["roles"], "journals": out["journals"], "commits": commits, "docs": docs}
    bdst = os.path.join(ROOT, "docs", "hub-data.json")
    json.dump(bundle, open(bdst, "w", encoding="utf-8"), ensure_ascii=False)
    print("wrote", bdst, "%.0f KB" % (os.path.getsize(bdst) / 1024), "head", sha, "-> 팀 문서함 > 새 가이드 만들기 > 「자료 올리기」로 올리세요")

if __name__ == "__main__":
    main()
