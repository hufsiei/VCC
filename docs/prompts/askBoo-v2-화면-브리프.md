# 작업 87(화면) 브리프 — askBoo v2 인터BOO 물어보기·들려주기 화면 (민지)

새 Claude Code 세션이 이 파일만 읽고 시작한다. 작성 2026-11-24(미리). 서버 쪽(#161, 병합됨)에 맞춰 화면을 고치는 일이다.
기준: `docs/spec-v1.md` 4장 askBoo [v2]·interviewNext [v2], `docs/design-rules.md` 5-7·6-1·6-2·7-①, `docs/askBoo-v2 반영 검토안 (2026-11-23, 상의용).md` 2-3·3-1·3-4·3-6. 일정: A 단계 11/26.

## 시작 프롬프트(붙여넣기)

```
docs/prompts/askBoo-v2-화면-브리프.md를 읽고 그대로 구현해 줘. CLAUDE.md 규칙(worktree, 내 폴더 screens/만, PR)을 지킨다.
common/·functions/는 고치지 않는다(필요하면 미리에게 알린다). 화면 글은 textContent로만, 색은 style.css 변수만.
브리프에 없는 결정이 필요하면 먼저 물어보고, 있는 결정은 바꾸지 않는다.
```

## 1. 왜 하나(배경 3줄)

- 11/23 실사용에서 물어보기가 「독일에서 인턴 어디 있어요?」에 **빈 말풍선 + null**을 그렸다. 서버가 `status: "notes"`를 보냈는데 `talk.js`의 `renderAnswer`가 그 상태를 모른다.
- 서버(#161)가 바뀌었다: 답은 발췌 3줄이 아니라 **근거 번호가 달린 2~4문장**(`lines[].cites`)이고, 대화·메타 말에는 새 상태 **`chat`**(고정 문구 + 칩), 탐색 질문에는 `notes`(카드 `oneLine`, 현장실습은 `kinds`)가 온다. 맥락은 화면이 **`history`**(최근 4턴)로 보내야 한다 — 서버는 기억하지 않는다.
- 들려주기·물어보기 대화가 화면 메모리에만 있어 해봤노트를 다녀오면 사라지고, 진행률 「노트 틀 2/3」가 틀리고, 내 보관함 「경험 들려주기」가 물어보기로 열린다.

## 2. 범위 (파일 2개)

| 파일 | 고칠 것 |
|---|---|
| `screens/talk/talk.js` (+ 필요하면 `screens/talk/index.html`) | ① `notes`·`chat` 상태 그리기 ② `ok` 답의 인용 번호·「근거 원문 보기」·`singleSenior` 라벨 ③ `history` 전달 ④ 두 모드 대화 sessionStorage 보존 ⑤ 진행률 문구·`covered` 칩 ⑥ `?mode=tell&program=…` 진입 |
| `screens/questions/questions.js` | ⑦ 「경험 들려주기」 링크 `../talk/?mode=tell` (288행) |

하지 않는 것: `common/data.js`·`mock-data.json`·`functions/` 수정(미리), 「후배 질문」 칩 삭제(A′ #89에서 frames가 바뀐 뒤), 「더 들려주기」·질문 삭제(C 단계), 검색어 굵게·innerHTML.

## 3. 서버 응답 (spec 4장 [v2], mock은 `common/mock-data.json`의 `askBoo.*`)

`askBoo(question, history)` — `common/data.js`가 이미 `history`를 받는다(기본 `[]`).

```js
// ok — 답 문장마다 cites(인용한 sourceId 1개 이상). sourceId는 cites[0]과 같다. fallback 줄은 cites 1개 + fallback: true
{ status: "ok", lines: [ { text: "기숙사 월세는 270~380유로였어요.", cites: ["R149-2-4","R213-2-4"], sourceId: "R149-2-4", lineId: "L-A1-1" } ],
  sources: { "R149-2-4": { docType: "귀국보고서", program: "마르부르크필립스대학교", semester: "2025-1" } },
  noteId: "N-marburg", suggestSenior: false, singleSenior: false }
// chat — 질문이 아닌 말(「아까도 한 얘기잖아」). 질문함에 저장되지 않음(questionId 없음). message는 서버 고정 문구
{ status: "chat", lines: [], sources: {}, suggestSenior: false,
  message: "아까는 KOTRA 해외무역관(유럽 권역) 이야기였어요. 다른 현장실습 해봤노트를 찾아볼까요?",
  chips: [ { label: "다른 노트 보기", action: "notes", payload: { field: "현장실습", exclude: ["KOTRA 해외무역관(유럽 권역)"] } },
           { label: "질문함에 담기", action: "save", payload: { question: "코트라를 뺀 무역 인턴은 어떤가요?" } } ] }
// notes — 탐색·사람 찾기. 카드에 oneLine. 현장실습을 나라로 물으면 notes: [] + kinds(기관 유형 13개)
{ status: "notes", lines: [], sources: {}, suggestSenior: true, message: "관련 해봤노트가 3개 있어요. 궁금한 노트를 골라 보세요.",
  notes: [ { noteId: "N-kotra", program: "KOTRA 해외무역관(유럽 권역)", country: null, evidenceCount: 115, oneLine: "…" } ] }
{ status: "notes", lines: [], sources: {}, suggestSenior: true, message: "현장실습 노트는 나라가 아니라 기관 유형으로 나뉘어요. 궁금한 유형을 골라 보세요.",
  notes: [], kinds: ["KOTRA 해외무역관", "공공기관", "국제기구 한국사무소", "…"] }
```
`hold`·`official`은 그대로. mock에는 `askBoo.chat`·`exchange`(cites)·`notes`(oneLine)가 있고 `kinds` 예시는 없다(없으면 `notes`만 그리면 됨).

## 4. 화면 결정 (하나씩)

### ① `notes` 상태 (`renderAnswer`)
- BOO 말풍선 `message` + 노트 카드 목록. 카드는 해봤노트 커버(7-③)의 축소형: 분야 띠(`category-tag`, `note.js`의 `CATEGORY`·`CATEGORY_NAME`·`KIND_NAME` 표를 그대로 옮김) + 프로그램명(18px) + `oneLine`(없으면 「–」) + 메타 「근거 N건」. 누르면 `../note/?id=<noteId>`.
- `kinds`가 있으면 카드 대신 선택형 키워드 칩(5-6) 줄. 칩을 누르면 `../note/?type=인턴`(목록 화면의 필터는 분야 단위라 그대로 현장실습 목록으로 간다 — 유형별 필터는 만들지 않는다).
- 근거 블록은 두지 않는다(답이 아님). `suggestSenior`면 아래 Secondary 「닮은선배 보기」. 토스트 없음(질문함에 담기지 않았으므로).

### ② `chat` 상태
- BOO 말풍선 `message` + 칩 줄(Secondary 버튼, 5-7 예시답 칩과 같은 모양). 토스트·근거 블록 없음.
- 칩 동작: `action: "notes"` → `../note/`(payload.field가 있으면 `?type=` 그 분야의 type — 국제교류 `교환`, 현장실습 `인턴`, 비교과 `비교과`) / `"save"` → `askBoo(payload.question)`가 아니라 **`call`을 직접 쓰지 말고** `data.js`에 `saveToInbox(question)`가 없으므로 지금은 `askBoo(payload.question, [])`를 부르고 결과(`hold`)를 평소처럼 그린다(서버가 `force: "hold"`를 받지만 `data.js`가 아직 넘기지 않음 — 미리가 추가하면 그때 바꾼다) / `"ask"` → `../senior/`.
- 한 번 누른 칩 줄은 비활성(지나간 질문의 버튼과 같은 규칙).

### ③ `ok` 답의 인용 번호·근거 원문
- 문장 `p` 끝에 작은 위첨자 번호(`cites` 순서, HUFS GREEN 12px, `aria-label="근거 1"`). 번호는 **응답 안의 sourceId 등장 순서**로 매긴다(첫 문장이 인용한 R149가 1, 다음 새 sourceId가 2…).
- 근거 블록(6-1) 머리줄은 지금 `evidenceBlock(res.sources)` 그대로. 펼치면 지금의 출처 한 줄(종류 | 연도) 앞에 번호를 붙여 문장의 번호와 맞춘다. 원문 본문은 서버가 보내지 않으므로 「근거 원문 보기」는 **그 노트 링크**(`../note/?id=`)로 대신한다(원문 텍스트를 화면이 들고 있지 않다).
- `singleSenior: true`면 말풍선 아래 중립 라벨 「선배 1명의 경험이에요」(6-1 근거 적음 라벨과 같은 부품) + Outline 「질문함에 담기」(누르면 `askBoo(질문, [])`를 다시 부르지 말고 **토스트 「이 질문은 이미 답이 있어요 · 더 듣고 싶으면 닮은선배에게 물어보세요」 + 「닮은선배 보기」**로 — 서버에 같은 질문을 hold로 넣는 길이 아직 없다).
- `fallback` 줄의 「근거 원문」 라벨은 그대로.

### ④ `history` + 대화 보존 (sessionStorage, 탭별 — 두 창 시연)
- 물어보기: 턴마다 `{question, status, program}`을 배열에 쌓고(`program` = `res.sources` 첫 값의 `program`, 없으면 `""`), `askBoo(question, history.slice(-4))`로 보낸다. `chat`·`notes`·`hold`도 턴으로 쌓는다.
- 저장 키: `sessionStorage["talk:ask"]` = `{turns:[{question, status, program, lines?, message?}]}`(그릴 때 필요한 최소: 사용자 말 + BOO 응답 전체 `res`를 그대로 넣어도 된다 — 크기 걱정 없음, 최근 20턴만). `sessionStorage["talk:tell:<program>"]` = `tell` 객체 중 `program`·`answers`·`step`·`pending`·`extra`.
- 들어올 때 저장분이 있으면 그대로 다시 그리고, 들려주기는 BOO 말풍선 「아까 이야기를 이어서 할게요」 + 마지막 질문을 다시 보인 뒤 입력 가능. AI 요약·공유가 끝나면 `talk:tell:<program>`을 지운다. 로그아웃(`logout`) 때도 지운다(`data.js`가 `me`를 지우므로 화면이 `talk:*`를 함께 지운다).
- `?mode=tell&program=<이름>`로 들어오면 경험 선택 없이 그 프로그램으로 `chooseProgram`. `getMe`의 이수 목록에 없는 이름이면 평소처럼 선택 화면.

### ⑤ 진행률 (3-1)
- `renderChips`: `covered`(서버 응답 `res.covered`, 매 응답에 옴)를 `tell.covered`에 두고, 그 칸 칩은 세 번째 상태 **「보고서로 채워짐」**(중립색 `status-neutral-bg/fg` + `file-text` 아이콘). 내가 답한 칸은 지금처럼 MINT ✓.
- AI 요약 바 문구: 「노트 틀 N/M 채움」 → **「내 이야기 N칸 · 보고서 M칸」**(N = 답한 칸, M = covered 칸). 버튼 활성 조건은 그대로(N ≥ 1).
- `done` 말풍선: 「고마워요. 노트 틀을 모두 채웠어요. …」 → **「지금 물을 건 다 물었어요. 더 들려줄 칸을 고르거나 아래 「AI 요약」을 눌러 주세요.」**
- 「후배 질문」 칩과 분모는 **아직 그대로**(A′ #89에서 `frames.json`이 6칸이 되면 `FRAMES` 표를 맞춘다 — 그때 미리가 알린다).

### ⑥ 내 보관함 링크
- `questions.js` 288행 「경험 들려주기」 `href: "../talk/"` → `"../talk/?mode=tell"`.

## 5. 디자인 규칙 대조
- 색은 변수만(인용 번호 `--color-ai`, 칩 Secondary, 라벨 중립). 이모지·HEX 금지. 12px 미만 금지(인용 번호 12px).
- 글은 `textContent`(`message`·`chips[].label`·`oneLine`·`kinds[]` 전부 서버·AI 글).
- 상태는 색 + 아이콘 + 문구. 칩 누른 뒤 비활성.
- 터치 44px: 칩 높이 32px이면 줄 간격으로 44px 확보(5-6 키워드 칩과 같은 처리).

## 6. 확인 (끝나면 셀프 체크)
- mock(`USE_MOCK = true`): 「아까도 한 얘기잖아」 → chat 말풍선 + 칩 2개, 토스트 없음 / 「네덜란드 교환 다녀온 선배 있어요?」 → notes 카드 / 「마르부르크 생활비」 → 문장 3개 끝에 ¹²³, 근거 블록 번호 일치 / 「평점 몇 점」 → 공식 안내 그대로.
- 미리 서버(`USE_MOCK = false`, 미리 PC): 11/23 캡처 6건 순서대로 — 1 notes 3개 → 2 notes(KOTRA 제외) → 3 chat → 4 kinds 13개 → 5 기숙사 4문장 인용 → 6 식비 hold. 해봤노트 탭을 다녀와도 대화가 남는가.
- 들려주기: 마르부르크 선택 → 칩에 「보고서로 채워짐」 5개 + 현재 질문 NAVY, 바 문구 「내 이야기 0칸 · 보고서 5칸」 → 답 2개 뒤 「내 이야기 2칸 · 보고서 5칸」 → 해봤노트 갔다 와도 그대로.
- 내 보관함 빈 화면 「경험 들려주기」 → 들려주기 탭으로 열림.
- `<script>alert(1)</script>`를 질문으로 넣어 글자로만 보이는가(chat·notes 경로 포함).

## 7. 미리에게 알릴 것(화면에서 막히면)
- `data.js`에 `force: "hold"` 전달, `saveQuestion`을 노트 없이 부르는 길, `kinds` mock — 필요해지면 단톡에 적는다. 서버 응답 모양은 바꾸지 않는다.
