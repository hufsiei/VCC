---
name: milreview
description: 미리(VCC 총괄, PR 병합 책임자)의 열린 PR 검토 루틴. "PR 검토", "올라온 PR 봐 줘", "밀리뷰", "병합해도 돼?" 같은 말에 쓴다. 열린 PR을 모두 모아 CLAUDE.md 소유 규칙·코드 규칙·spec 대조·시험 실행으로 확인하고, PR마다 병합 가능/고칠 것/미리가 정할 것을 짧게 보고한다. 병합은 미리 승인 뒤에만.
---

# milreview — 열린 PR 검토

미리가 PR 병합·권한 검사의 확인 책임자다(CLAUDE.md). 이 루틴은 **읽고 시험만 한다**. PR 댓글·승인·병합·남의 브랜치 수정은 미리가 말할 때만 한다.

## 1. 목록 모으기
```
gh pr list -R hufsiei/VCC --state open --json number,title,author,headRefName,createdAt,additions,deletions,changedFiles
gh pr view <n> --json body,files,mergeable,mergeStateStatus,statusCheckRollup
```
- 본문에 「#N 다음에 병합」이 있으면 **병합 순서**를 정리한다. 앞 PR을 그대로 품은 PR(예: 1단계 + 2단계)은 `git log --oneline main..<PR>`로 겹침을 확인한다.
- diff는 `git fetch -q origin pull/<n>/head:pr<n>` 뒤 `git diff main...pr<n>`. 끝나면 `git branch -D pr<n>`.

## 2. PR마다 확인할 것 (해당하는 것만)

**① 누가 무엇을 고치나** — 바뀐 파일이 작성자 몫인지 CLAUDE.md 표로 본다.
`common/`=미리(style.css=민지) · `data/`·`tools/`·`functions/score.py`=원우 · `functions/`=미리 · `screens/<폴더>`=맡은 사람 · `docs/design-rules.md`=민지. 남의 몫을 고쳤으면 「확인 필요」.

**② 응답 모양** — 함수 응답·payload를 바꿨으면 `docs/spec-v1.md`(원본)·`data/README.md`·`common/data.js` 세 곳이 맞는지. 화면이 쓰는 필드(`withId`·`status`·`reason`·`recommend.talk` 등)가 spec에 실제로 있는지 `grep`.

**③ 화면(screens/)** — 추가된 줄(`^+`)만 검사:
```
git diff main...pr<n> -- screens common/style.css | grep "^+" | grep -nE "#[0-9a-fA-F]{3,6}\b|innerHTML|insertAdjacentHTML|fetch\(|localStorage"
git diff main...pr<n> -- screens | grep -nE "font-size: *([0-9]|1[01])px"
```
- 이름·학번을 화면·주소에 쓰지 않는지(학번은 메모리 안 키로만), 용어 표준(인터BOO·해봤노트·닮은선배·내 보관함·쪽지 요청), 화면 깊이(안쪽 화면은 상세 헤더 + 탭 숨김), MINT·GREEN은 AI 표시에만.
- **상태 빠짐**: 서버가 돌려줄 수 있는 상태·reason을 spec에서 다 뽑아, 화면이 각각을 어떻게 보이는지 본다(예: 쪽지 `declined`·`cancelled`·`expired`). 화면이 버튼을 열어 두고 서버 거절에 맡기면 「다듬을 것」.
- **링크 대상**: 버튼이 가는 화면·`?mode=`가 실제로 그 기능을 여는지 대상 화면 코드를 `grep`.

**④ 서버(functions/)** — AI는 `callAI`로만, `mask.py` 통과, 남의 기록 막기(`볼 수 없는 기록이에요`), 키를 코드에 적지 않음. 새 작업이면 `PROVIDER`·`SETTINGS` 둘 다.

**⑤ 시험** — 임시 작업 폴더에서 돌리고 지운다(메인 폴더 브랜치를 바꾸지 않는다):
```
git worktree add -q --detach ../VCC-review-tmp pr<n>
cd ../VCC-review-tmp/functions && for t in test_*.py; do echo "$t FAIL=$(python -X utf8 $t 2>&1 | grep -c '^FAIL')"; done
git worktree remove --force ../VCC-review-tmp
```
`tools/` 변경은 `--help`가 뜨는지 + 바뀐 판정 함수를 작은 입력으로 직접 불러 본다. **AI를 실제로 부르는 측정(run_eval 실행 등)은 비용이 드니 돌리지 않는다**(미리 승인 시에만).

**⑥ 화면 눈 확인** — 필요하면 `run` 스킬로 390px mock을 띄워 본다. 본문의 「확인 전」 항목은 그대로 「남은 확인」으로 옮긴다.

## 3. 보고 (짧게, PR당 3~6줄)
맨 위에 **병합 순서 한 줄**. 그다음 PR마다:
- **판정**: 병합 가능 / 고친 뒤 병합 / 미리가 정할 것 있음
- 확인한 것 한 줄(시험 결과 숫자 포함)
- 고칠 것(파일:줄 + 왜) — 꼭 고칠 것과 다듬을 것(nit)을 나눈다
- 미리가 정할 것(선택지 + 추천)
- 팀원 메시지는 **여기서 쓰지 않는다** — 병합한 뒤 4단계에서 한 번만 쓴다. 보고에는 「병합 뒤 ○○에게 알림 있음/없음」 한 줄만

## 4. 그다음
- 병합은 미리가 "병합해"라고 할 때만: `gh pr merge <n> --merge --admin` (hufsiei 계정, 순서대로). 병합 뒤 `git -C C:/dev/VCC pull`.
- **팀원 메시지는 병합한 뒤 여기서만 쓴다**(작업 대화창은 쓰지 않는다, 11/23 미리 결정). 재료: PR 본문 「## 팀원에게」, 상태판 `--handoff` 줄, 검토에서 나온 고칠 것·다듬을 것. 팀원이 직접 올린 PR이면 diff·본문에서 뽑는다. CLAUDE.md 「팀원에게 보내는 메시지」 형식으로, 머리 줄은 `[to받는 사람] PR #n merged`(예: `[to민지]`). 같은 사람에게 갈 PR 여러 개는 한 메시지로 묶는다(머리 줄에 번호 나열). 맨 위에 「Written for: ○○」. 미리가 다른 창에서 이미 보낸 메시지를 붙여 넣으면 빠진 것만 짚는다.
- 미리가 "보냈어"라고 하면 그 PR의 상태판 줄을 `board.py set <폴더> --sent`(줄이 없으면 생략).
- PR 댓글을 달아 달라고 하면 보고의 「고칠 것」을 그대로 `gh pr comment <n>`로 단다(달기 전에 문구를 보여 준다).
