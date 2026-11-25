# export_runtime.py — 쓰기 기록을 드라이브 엑셀로 내보낸다 (작업 33, 11/25 미리 결정 2A·3A·4A)
#
# 신고·물어보기(질문+답)·들려주기·쪽지 기록을 읽어 시트 4개짜리 엑셀 하나로 쓴다.
# 미리 PC에서 1시간마다 돌리고(작업 스케줄러 — docs/운영노트.md 5절), 구글 드라이브 앱이 올린다.
#
# 실행: cd C:\dev\VCC\functions
#   python -X utf8 export_runtime.py          공개 주소 기록(Object Storage 버킷 runtime/) → 드라이브 @VCC\로그\VCC-로그.xlsx
#   python -X utf8 export_runtime.py --dry    파일을 쓰지 않고 시트 내용을 화면에 보여 준다(드라이브 없어도 됨)
#   python -X utf8 export_runtime.py --local  버킷 대신 이 PC의 data/runtime을 읽는다(개발 확인용)
#   .env의 NCP_OS_BUCKET·NCP_OS_ACCESS_KEY·NCP_OS_SECRET_KEY를 쓴다(reset_runtime.py --ncp와 같은 방식). 읽기만 한다.
#
# 지키는 것
#   · 글은 모두 mask.py로 가린다(연락처·메일·학번·링크·주소).
#   · 학번(colreg_no) 칸이 없다. 쪽지는 역할(후배/선배)만, 신고는 누가 했는지 남기지 않는다.
#   · 들려주기는 공개 동의를 통과한 문장만 싣는다(나만 보기 문장은 싣지 않는다).
#   · 키·토큰·비번이 든 기록(sessions·aiUsage 등)은 읽지 않는다. 엑셀은 저장소 밖(드라이브)에만 쓴다.
#   · 드라이브 폴더를 못 찾으면 쓰지 않고 멈춘다.
#   · 대회 종료(12/9) 뒤 runtime을 지울 때 드라이브 「로그」 폴더도 함께 지운다(spec 0장 보관기간).
import os
import string
import sys
from pathlib import Path

import paths

FILE_NAME = "VCC-로그.xlsx"
FOLDER = "로그"
ROLE = {"asker": "후배", "senior": "선배"}
STATUS_WORD = {"ok": "답함", "hold": "보류", "official": "공식 안내", "notes": "노트 안내", "chat": "대화"}


def find_drive():
    """드라이브 @VCC 폴더. 환경변수 VCC_DRIVE가 먼저, 없으면 드라이브 글자(D:~Z:)의 「내 드라이브/@VCC」를 찾는다. 없으면 None."""
    env = os.environ.get("VCC_DRIVE")
    if env and Path(env).is_dir():
        return Path(env)
    for letter in string.ascii_uppercase[3:]:
        for my in ("내 드라이브", "My Drive"):
            p = Path(f"{letter}:/") / my / "@VCC"
            try:
                if p.is_dir():
                    return p
            except OSError:
                pass
    return None


def _m(text):
    import mask
    return mask.mask(text) if isinstance(text, str) else ("" if text is None else text)


def _line_info(line_id, r):
    """신고 기록에 문장 글이 없으면(11/25 이전 기록) 노트에서 찾아 채운다."""
    if r.get("text") or r.get("noteId"):
        return r
    import notes
    return {**r, **(notes.find_line(line_id) or {})}


def build_sheets(load):
    """load(이름, 기본값) → {시트 이름: [머리 줄, 행…]}. 여기서 만든 값만 엑셀·화면에 나간다."""
    reported = load("reported", {})
    thread_reports = load("threadReports", [])
    ask_log = load("askLog", [])
    note_lines = load("noteLines", [])
    threads = load("messages", {})

    rows = [["시각", "종류", "노트", "프로그램", "칸", "문장", "사유", "상태", "문장 id"]]
    for line_id, r in reported.items():
        r = _line_info(line_id, r)
        kind = "요약 문장" if r.get("kind") == "summary" or str(line_id).startswith("S-") else "원문 문장"
        rows.append([r.get("at"), kind, r.get("noteId"), r.get("program"), r.get("section"), _m(r.get("text")),
                     _m(r.get("reason")), r.get("status"), line_id])
    for r in thread_reports:
        rows.append([r.get("at"), "쪽지 대화(" + ROLE.get(r.get("role"), "–") + "가 신고)", None, None, None, None,
                     _m(r.get("reason")), "차단" if r.get("block") else "신고만", r.get("threadId")])
    sheets = {"신고": _sorted(rows)}

    rows = [["시각", "결과", "질문", "답", "근거 번호", "프로그램", "노트", "안내 문구"]]
    for r in ask_log:
        lines = r.get("lines") or []
        rows.append([r.get("at"), STATUS_WORD.get(r.get("status"), r.get("status")), _m(r.get("question")),
                     "\n".join(_m(ln.get("text")) + (" (근거 원문)" if ln.get("fallback") else "") for ln in lines),
                     "\n".join(", ".join(str(c) for c in ln.get("cites") or []) for ln in lines),
                     ", ".join(r.get("programs") or []), r.get("noteId"), _m(r.get("message"))])
    sheets["물어보기"] = _sorted(rows)

    rows = [["시각", "프로그램", "칸", "공개 문장", "경험 학기", "공식 확인", "후배 질문", "노트", "문장 id"]]
    for r in note_lines:
        rows.append([r.get("at"), r.get("program"), r.get("section"), _m(r.get("text")), r.get("semester"),
                     "예" if r.get("official") else "", _m(r.get("asked")), r.get("noteId"), r.get("sourceId")])
    sheets["들려주기"] = _sorted(rows)

    rows = [["시각", "대화", "대화 상태", "보낸 사람", "글"]]
    for tid, t in threads.items():
        for msg in t.get("messages") or []:
            who = "후배" if msg.get("from") == t.get("asker") else "선배" if msg.get("from") == t.get("senior") else "–"
            rows.append([msg.get("at"), tid, t.get("status"), who, _m(msg.get("text"))])
    sheets["쪽지"] = _sorted(rows)
    return sheets


def _sorted(rows):
    """머리 줄은 두고 최근 것이 위로."""
    return [rows[0]] + sorted(rows[1:], key=lambda r: str(r[0] or ""), reverse=True)


def write_xlsx(sheets, path):
    import openpyxl
    from openpyxl.styles import Alignment, Font

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append([None] * len(row))
            for col, v in enumerate(row, 1):
                cell = ws.cell(row=ws.max_row, column=col)
                cell.value = v
                if isinstance(v, str):
                    cell.data_type = "s"   # 「=」로 시작하는 글이 수식으로 읽히지 않게(사용자가 쓴 글)
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
        for cell in ws[1]:
            cell.font = Font(bold=True)
        ws.freeze_panes = "A2"
        for col, head in enumerate(rows[0], 1):
            wide = head in ("문장", "질문", "답", "공개 문장", "글", "안내 문구", "후배 질문")
            ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 60 if wide else 18
    wb.save(path)


def print_sheets(sheets):
    for name, rows in sheets.items():
        print(f"\n[{name}] {len(rows) - 1}행")
        print(" | ".join(rows[0]))
        for row in rows[1:]:
            print(" | ".join(str("" if v is None else v).replace("\n", " / ") for v in row))


def main(argv):
    dry, local = "--dry" in argv, "--local" in argv
    if not local:
        paths.load_env()
        os.environ["STORE_BACKEND"] = "ncp"
        os.environ.setdefault("NCP_OS_PREFIX", "runtime/")
    import store

    sheets = build_sheets(store.load)
    if dry:
        print_sheets(sheets)
        return 0
    drive = find_drive()
    if not drive:
        print("멈춤: 드라이브 @VCC 폴더를 찾지 못했어요(구글 드라이브 앱이 켜져 있는지, 또는 VCC_DRIVE를 확인).")
        return 1
    folder = drive / FOLDER
    folder.mkdir(exist_ok=True)
    out = folder / FILE_NAME
    try:
        write_xlsx(sheets, out)
    except PermissionError:   # 엑셀에서 열어 둔 채면 덮어쓸 수 없다 → 다음 회차에 다시
        print(f"멈춤: {out} 을 쓸 수 없어요(엑셀에서 열려 있으면 닫아 주세요).")
        return 1
    print("내보냈어요: " + str(out) + " — " + ", ".join(f"{k} {len(v) - 1}행" for k, v in sheets.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
