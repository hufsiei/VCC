# 미리 PC 설정 (집 노트북 · 사무실 데스크탑, PC마다 한 번)

저장소에는 스크립트와 스킬 원본만 있다. 아래 세 가지는 PC마다 따로 걸어야 한다. 팀원은 하지 않아도 된다(이 파일들은 팀원 Claude Code에서 자동으로 돌지 않는다).

## 1. SessionStart hook (자동 pull + 하루 한 번 상태 한 줄)
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
- 세션을 열 때마다 `C:\dev\VCC`가 main이고 고친 파일이 없을 때만 pull한다.
- 그날 첫 세션에만 `[VCC] main 최신 · 남은 작업 폴더 0 · 열린 PR 2 · .env 키 3/3`을 보여 준다(`~\.claude\vcc-status-day.txt`에 날짜 기록).
- 끄려면 `/hooks`에서 끄거나 위 블록을 지운다.

## 2. 스킬 milstart · milend 연결
Claude Code를 `C:\dev`에서 열기 때문에 저장소 안의 `.claude\skills`를 직접 찾지 못한다. 사용자 스킬 폴더에 연결(junction)한다. PowerShell:
```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills" | Out-Null
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\milstart" -Target "C:\dev\VCC\.claude\skills\milstart"
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\milend"   -Target "C:\dev\VCC\.claude\skills\milend"
```
스킬 내용은 git pull로 두 PC에 같이 갱신된다. 쓰는 법: `/milstart`, `/milend`, 또는 "밀시작", "밀종료".

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
