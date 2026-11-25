# 미리 PC 설정 (집 노트북 · 사무실 데스크탑, PC마다 한 번 — 원우·민지도 2절 junction은 같은 방식)

저장소에는 스크립트와 스킬 원본만 있다. 아래 세 가지는 PC마다 따로 걸어야 한다. 팀원은 하지 않아도 된다(이 파일들은 팀원 Claude Code에서 자동으로 돌지 않는다).

## 1. SessionStart hook (자동 pull + 실패 시 알림)
11/24부터 저장소 `.claude/settings.json`에 같은 hook이 등록돼 있어, 저장소 폴더(`C:\dev\VCC`나 `C:\dev\VCC-*`)에서 Claude Code를 열면 팀원 PC에서도 저절로 돈다. 미리처럼 `C:\dev`에서 여는 PC는 저장소 설정을 읽지 않으니 아래를 계속 둔다. 두 곳에 다 걸려도 같은 세션에서는 한 번만 돈다.
- 저장소 `.claude/settings.json`은 hook만 담는다. 이 PC 전용 권한 줄은 `.claude/settings.local.json`에 둔다(커밋 안 함). **병합 뒤 처음 pull하기 전에** 예전에 추적되지 않던 `C:\dev\VCC\.claude\settings.json`(권한 줄)을 `settings.local.json`으로 옮기고 지워야 pull이 된다.

`C:\Users\<사용자>\.claude\settings.json`에 아래를 **합쳐** 넣는다(기존 설정 유지).
```json
"hooks": {
  "SessionStart": [
    { "hooks": [ { "type": "command",
                   "command": "python -X utf8 C:/dev/VCC/.claude/hooks/session_start.py",
                   "timeout": 30 } ] }
  ]
}
```
- 세션을 열 때마다 `C:\dev\VCC`를 pull한다(main이고 고친 파일이 없을 때만, `--ff-only`). 성공·최신이면 **아무것도 띄우지 않는다**.
- 본 폴더의 추적 안 하는 파일(캡처 등)이 pull을 막으면 그 파일을 `~\.claude\vcc-pull-backup\<YYYYMMDD>\`로 옮기고 다시 pull한다(11/25: 이것 때문에 170커밋 밀린 일).
- 그 밖에 안 되면(다른 브랜치·고친 파일·네트워크) `[VCC] pull 안 됨 — <이유> · 직접 pull하세요: git -C C:/dev/VCC pull` 한 줄을 **Windows 알림(풍선)**으로 띄우고, Claude가 첫 답변 맨 위에 같은 줄을 보여 준다(VS Code 패널은 hook 출력을 띄우지 않는다, 11/21 확인). 알림이 안 보이면 Windows 「방해 금지/집중 지원」을 본다.
- 사용량은 `/token`, 팀원 메시지는 `/mchk`로 본다(11/25부터 hook이 띄우지 않는다).
- 시험: `python -X utf8 .claude/hooks/test_session_start.py`(임시 저장소에서).
- 끄려면 `/hooks`에서 끄거나 위 블록을 지운다.

## 2. 스킬 milstart · milend 연결
Claude Code를 `C:\dev`에서 열기 때문에 저장소 안의 `.claude\skills`를 직접 찾지 못한다. 사용자 스킬 폴더에 연결(junction)한다. PowerShell:
```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills" | Out-Null
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\milstart" -Target "C:\dev\VCC\.claude\skills\milstart"
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\milend"   -Target "C:\dev\VCC\.claude\skills\milend"
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\milreview" -Target "C:\dev\VCC\.claude\skills\milreview"
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\milwork"  -Target "C:\dev\VCC\.claude\skills\milwork"
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\milwatch" -Target "C:\dev\VCC\.claude\skills\milwatch"
```
스킬 내용은 git pull로 두 PC에 같이 갱신된다. 쓰는 법: `/milstart`, `/milend`, `/milreview`, `/milwork`, `/milwatch`(총괄창에서 `/loop 20m /milwatch`), 또는 "밀시작", "밀종료", "밀리뷰", "밀워크".

대화창 역할(11/23): VS Code 창은 `C:\dev\VCC` 하나만 열고 Claude 대화창을 여러 개 띄운다. **총괄 대화창** 하나(milstart·milreview·milend·milwatch), 저장소를 고치는 **작업 대화창**은 시작할 때 `milwork <요청자> <작업 제목>`(폴더·브랜치·상태판 줄이 생김), **상의 대화창**은 아무것도 치지 않고 결론만 작업 대화창에 넘긴다. 상태판은 사람별 `board-<이름>.md`(드라이브 `@VCC\총괄\`, 두 PC 공용. 드라이브 없으면 그 PC의 `C:\dev\VCC-board-<이름>.md`). worktree는 PC마다 따로. 커밋하지 않는다.

## 3. Claude 메모리를 드라이브와 공유
메모리 원본: `H:\내 드라이브\@VCC\미리 memory` (드라이브 동기화). 이 PC의 메모리 폴더를 그곳에 연결한다.
```powershell
$base = "$env:USERPROFILE\.claude\projects\c--dev"
# (1) 이 PC에만 있던 메모리를 먼저 합친다: 드라이브에 없는 파일은 복사, 같은 이름은 내용을 비교해 합친다(Claude에게 맡겨도 됨)
# (2) 원래 폴더는 지우지 말고 이름만 바꿔 둔다
Rename-Item "$base\memory" "memory.bak-<날짜>"
New-Item -ItemType Junction -Path "$base\memory" -Target "H:\내 드라이브\@VCC\미리 memory"
```
- 집 노트북: 11/21 연결 완료(백업 `memory.bak-20261121`).
- 사무실 데스크탑: 아직. 연결 전에 (1) 합치기를 꼭 한다 — `MEMORY.md`는 두 PC 줄을 합친 한 파일이어야 한다.
- 링크를 지울 때는 `cmd /c rmdir <링크>`(Remove-Item은 드라이브 쪽 내용까지 지울 수 있음).

## .env
값은 미리가 Bitwarden ↔ 각 PC `.env`로 직접 옮긴다. Claude는 키 이름이 있는지만 확인하고 값은 읽어서 보여 주지 않는다.
