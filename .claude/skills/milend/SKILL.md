---
name: milend
description: 미리(VCC 총괄)의 업무 마무리 루틴. "밀종료", "업무 마무리", "세션 마무리", "오늘 정리" 같은 말에 쓴다. 남은 작업 폴더·서버·PR을 정리하고, 오늘 병합된 코드와 작업내역서 v6를 대조해 진행상황·메모를 갱신하고, 미리 작업일지를 써서 export_tasks → PR → 병합까지 한 뒤 팀 가이드 생성 안내와 내일 리마인드를 준다.
---

# milend — 업무 마무리

미리를 위한 마무리 루틴. **작업내역서 갱신안과 작업일지 초안은 미리가 「좋아」 한 뒤에 쓴다.** 그 승인으로 export → push → PR → 병합까지 진행해도 된다.

## 1. 세션 정리
- 상태판: `python -X utf8 C:/dev/VCC/.claude/skills/milwork/board.py list`(아래 `board.py`). 줄마다 브랜치가 병합됐는지 `gh pr list --state merged --head <브랜치>`로 본다. 병합된 것은 폴더를 지우고(`cd /c/dev` 후 `git worktree remove`, 실패하면 `rm -rf`) `board.py remove <폴더>`. 병합 안 된 것은 상태·전달 대기를 알리고 미리에게 묻는다(내일 다른 PC에서 이어 한다면 브랜치를 push해 두라고 권한다). 상태판에 없는 `C:\dev\VCC-*` 폴더도 같은 기준으로 정리한다.
- **안 보낸 답장 확인**: 답장은 작업 대화창이 그때그때 쓴다(milwork 「팀원 메시지가 오면」). 여기서는 `board.py pending`으로 **아직 안 보낸 것만** 보고 "안 보낸 답장 N건"으로 알린다. 미리가 이미 보냈다고 하면 `board.py set <폴더> --sent`, 아직이면 그 요점으로 짧은 답장을 써 준다(보내지 않는다). 안 보낸 답장이 있는 줄은 `remove`가 막으므로 먼저 처리한다.
- 오늘 연 내 PR 중 병합 안 된 것, 리뷰를 기다리는 팀원 PR 목록.
- 켜 둔 서버: `netstat -ano | grep -E ":8787|:8000"`. 있으면 끌지 묻는다(local_fn.py, http.server).
- `C:\dev\VCC`가 main이고 깨끗한지. 아니면 이유를 알린다.

## 2. 작업내역서 대조·갱신
- 오늘 병합된 PR: `gh pr list -R hufsiei/VCC --state merged --search "merged:>=<오늘 YYYY-MM-DD>" --limit 50 --json number,title,mergedAt,author`. PR 제목·본문의 「작업 N」으로 작업 번호를 찾는다.
- `H:\내 드라이브\@VCC\@VCC작업내역 v6.xlsx` `작업목록` 시트와 대조해 **갱신안 표**를 먼저 보여 준다: 번호 · 칸(진행상황/비고/막힌 점) · 지금 값 → 새 값. 비고는 기존 형식대로 끝에 `[MM/DD 밤] (미리) …` 한두 줄을 덧붙인다(지우지 않는다). 참고할 점(다음 사람이 알아야 할 것)도 짧게 메모로.
- 승인 뒤 쓰기:
  1. 엑셀에서 파일이 열려 있으면 저장이 안 된다 — 닫아 달라고 한다.
  2. 백업: `H:\내 드라이브\@VCC\이전 파일\@VCC작업내역 v6_백업_MMDD_HHMM.xlsx`로 복사.
  3. openpyxl로 **해당 칸만** 바꿔 저장(차트·그림 없음). 저장 후 다시 읽어 바뀐 칸 수가 갱신안과 같은지 확인.
  4. 드라이브 동기화가 끝나야 다른 PC에서 새 파일이 보인다고 알린다.

## 3. 작업일지
- 파일: `H:\내 드라이브\@VCC\작업일지\외대인사이드_작업일지_MMDD_미리.md`. 직전 미리 일지를 형식 견본으로 읽고 같은 구성으로 쓴다('기록' 시트 기준: 하루 3줄 요약 + 작업별 내용 + 잘 된 프롬프트 원문 + 수치·PR 번호).
- 초안을 보여 주고 승인 뒤 드라이브에 저장. 같은 날 낮판이 있으면 덮지 말고 「밤판」으로 갱신한다(낮판 내용 유지 + 추가).

## 4. export → PR → 병합
- 오늘 다른 사람이 `docs/tasks.json`을 올렸는지 먼저 본다: `git -C C:/dev/VCC log --since=<오늘> --format="%an %s" -- docs/tasks.json`. 있으면 겹치니 미리에게 알린다.
- `git -C C:/dev/VCC pull` → `git worktree add -b docs/tasks-export-MMDD ../VCC-export origin/main` → 그 폴더에서 `python -X utf8 tools/export_tasks.py`.
- 커밋: `docs/tasks.json` + 작업일지는 스크립트가 「덮어씀」「새 파일」로 출력한 것만, 내용이 맞을 때만. **`주간작업일지_1120(추가)_민지.md`는 중복이라 올리지 않는다** — 새 파일로 나오면 지우고 tasks.json의 `journals`에서도 뺀다(민지가 드라이브에서 정리할 때까지 매번).
- PR 제목 `[미리] tasks.json·작업일지 MM/DD (작업 …)` → 병합 `gh pr merge <n> --merge --admin` → `git -C C:/dev/VCC pull` → worktree 정리.
- `docs/hub-data.json`은 커밋하지 않는다(gitignore). worktree를 지우기 전에 `C:\dev\VCC\docs\hub-data.json`으로 복사해 둔다.

## 5. 미리에게 넘길 것 (마지막 메시지)
- **팀 가이드**: "팀 문서함 → 자료 올리기 → `C:\dev\VCC\docs\hub-data.json` → 새 가이드 생성"(미리가 직접).
- **내일 리마인드**: 내일 어느 PC인지 묻지 말고 미리가 말한 대로. 3~5줄 —
  - 오늘 끝내지 못한 일과 다음 한 걸음
  - 팀원 답을 기다리는 것(누구에게 무엇)
  - 미리가 결정할 것
  - PC를 바꾸는 날이면: `.env`를 오늘 바꿨는지(바꿨으면 Bitwarden 갱신은 미리가), 드라이브 동기화 완료 확인
- 오늘 AI 호출 비용: `C:\dev\VCC\functions\logs\ai-calls.jsonl`에서 오늘 줄의 작업·모델·토큰을 세어 한 줄로(추정 단가 명시).

## 작업 규칙
milstart의 「작업 규칙」과 같다(pull 먼저, worktree에서만 수정, .env 비공개, heredoc 대신 Write, 폴더 삭제 시 `cd /c/dev`, 담당 폴더 존중, 팀원 메시지는 써 주되 보내기는 미리가).
