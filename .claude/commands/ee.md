---
description: 이 창(세션)을 닫아도 되는지 점검 — 안 올린 작업·돌아가는 것·미완 PR 확인
allowed-tools: Bash(git:*), Bash(gh:*), PowerShell
---

사용자가 "이 창 닫아도 되지?"라고 물은 것이다. **읽기 전용**으로 점검하고(파일·브랜치·PR을 바꾸지 않는다), 아래를 현재 작업 폴더 기준으로 확인한다.

1. `git rev-parse --show-toplevel`, `git branch --show-current`, `git worktree list` — 지금 폴더가 본 저장소(main)인지 작업 폴더(VCC-*)인지.
2. `git status --short` — 커밋 안 한 변경(`.vscode/` 같은 추적 안 하는 폴더는 따로 구분해 말한다).
3. `git log @{u}..HEAD --oneline` (upstream 없으면 `git log origin/main..HEAD --oneline`) — push 안 한 커밋.
4. `gh pr list -R hufsiei/VCC --head <현재 브랜치> --state all --json number,state,isDraft,mergedAt,title` — 이 브랜치의 PR 상태(없음 / open / draft / merged).
5. 이 대화에서 백그라운드로 돌린 명령·에이전트가 있으면 아직 도는지(없으면 「없음」).
6. 이 대화에서 내가 하겠다고 하고 아직 안 끝낸 일, 사용자 답을 기다리는 질문이 있는지.

답은 맨 위에 한 줄 결론:
- **닫아도 됨** — 위 항목에 걸리는 게 없음(또는 PR 병합까지 끝났고 작업 폴더만 남음 → 그 폴더를 지울지 한 줄로 묻기. 지우지는 말 것).
- **닫기 전에 할 것 있음** — 걸리는 항목을 개조식으로 (커밋 안 함 / push 안 함 / PR 없음 / 병합 대기 / 돌아가는 작업 / 대답 대기), 각각 무엇을 하면 되는지 한 줄.

판단이 애매하면(예: PR은 열렸지만 병합 전) 「닫아도 작업은 안 사라지지만, 병합은 아직」처럼 사실만 말한다. 길게 설명하지 않는다.
