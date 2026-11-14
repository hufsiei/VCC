# 외대人사이드 함수·응답 명세 v1 (2026-11-14)

이 문서대로 `common/data.js`, `common/mock-data.json`, `data/README.md`를 채운다.
화면은 `common/data.js`의 함수만 부르고, 응답 모양은 이 문서를 따른다.
명세를 바꿔야 하면 코드보다 이 문서를 먼저 고치고 팀에 알린다.

## 0. 공통 규칙

- 모든 함수는 `async`이고 JSON 객체를 돌려준다.
- 실패 시 공통 모양: `{ "error": "사람이 읽을 메시지" }`. 화면은 `res.error`가 있으면 안내 문구를 보여 준다.
- 학기 표기는 `"2025-1"`, `"2025-2"`, `"2025-여름"`, `"2025-겨울"`.
- 화면에는 학번을 보여 주지 않는다. 사람은 `nickname`(별칭)으로만 표시한다.
- 로그인한 사용자 정보는 화면이 `sessionStorage`의 `"me"`에 저장한다. 함수는 이를 따로 받지 않는다(서버 연결 후 미리가 처리).

## 1. 시연 인물과 가상 계정 (README.md에도 적을 것)

| 역할 | 아이디 | 비밀번호 | 별칭 | 설명 |
|---|---|---|---|---|
| 학생 A | 202530101 | 1 | 독일어과 새내기 | 서양어대학 독일어과 1학년, 이중전공 경영학부, 비교과 외대쌤 이수. 질문하는 사람 |
| 선배 B | 202130012 | 1 | 뮌헨 다녀온 독일어과 4학년 | 독일어과 4학년, 이중전공 경영학부, 외대쌤 이수, 2025-1 독일 뮌헨대 교환 |
| 선배 C | 202130045 | 1 | 뮌헨 다녀온 스페인어과 4학년 | 스페인어과 4학년, 2025-1 독일 뮌헨대 교환. 비교 대상(공통점 적음) |
| 직원 | staff01 | 1 | 국제교류팀 | 부서 리포트용 직원 계정 |

실제 학생 데이터(`data/students.json`)는 원우가 구글 시트에서 변환해 채운다. mock은 위 인물로 만든다.

## 2. 접속 주소 (README.md)

- 로컬: 저장소 폴더에서 `python -m http.server 8000` → `http://localhost:8000/screens/login/`
- 미리 개발 서버(미리 PC만): `functions/local_fn.py` → `http://localhost:8787`
- 공개 주소(GitHub Pages 등): 미정. 정해지면 추가.

## 3. data.js 동작

```js
export const USE_MOCK = true;
const FN_BASE = "http://localhost:8787";
// call(name, payload): USE_MOCK이면 pickMock, 아니면 POST `${FN_BASE}/${name}` (JSON body)
// mock-data.json은 import.meta.url 기준 상대경로로 한 번만 fetch해서 캐시
```

### pickMock 규칙 (입력에 따라 다른 mock을 고르는 곳은 여기 한 곳)

| 함수 | 규칙 |
|---|---|
| login | `id`가 `"staff"`로 시작하면 `login.staff`, 그 외 비밀번호가 `"1"`이면 `login.student`, 아니면 `login.fail` |
| askBoo | 질문에 `교환|파견|독일|뮌헨`이 있으면 `askBoo.exchange`, 그 외 `askBoo.hold` |
| interviewNext | `answers.length`가 0~2면 `interviewNext.steps[answers.length]`, 3 이상이면 `interviewNext.done` |
| getNote | `getNote[id]`가 있으면 그것, 없으면 `getNote["N-munich"]` |
| checkMessage | 숫자가 8자리 이상 연속(전화·학번)이면 `checkMessage.blocked`, 그 외 `checkMessage.ok` |
| 나머지 | `m[name]` 그대로 |

## 4. 함수 15개

### login(id, pw)
payload `{id, pw}`
```json
{ "ok": true, "user": { "id": "202530101", "nickname": "독일어과 새내기", "role": "student" } }
{ "ok": true, "user": { "id": "staff01", "nickname": "국제교류팀", "role": "staff", "dept": "국제교류팀" } }
{ "ok": false, "reason": "아이디 또는 비밀번호가 맞지 않아요." }
```

### getMe()
```json
{ "id": "202530101", "nickname": "독일어과 새내기", "layer": "후배", "role": "student",
  "college": "서양어대학", "major": "독일어과", "doubleMajor": "경영학부", "grade": 1,
  "programs": [ { "name": "외대쌤", "type": "비교과", "semester": "2025-2" } ] }
```

### askBoo(question)
payload `{question}`. 근거가 있으면 `ok`, 없으면 `hold`(질문은 자동으로 질문함에 저장되고 `questionId`가 옴).
```json
{ "status": "ok",
  "lines": [ { "text": "...", "sourceId": "R03-1-1", "lineId": "L-R03-1-1" } ],
  "sources": { "R03-1-1": { "docType": "귀국보고서", "program": "독일 뮌헨대 교환", "semester": "2025-1" } },
  "noteId": "N-munich", "suggestSenior": false }
{ "status": "hold", "lines": [], "sources": {}, "questionId": "Q-0001", "suggestSenior": true,
  "message": "이 부분은 아직 들은 선배가 없어요. 질문함에 담아 두었어요. 닮은 선배에게 물어볼까요?" }
```
docType: `귀국보고서` | `인턴십후기` | `인터뷰` | `비교과후기`

### interviewNext(program, answers)
선배 인터뷰에서 다음 질문 하나. payload `{program, answers:[{section, question, answer}]}`
```json
{ "done": false, "section": "지원", "question": "뮌헨대 교환은 언제부터 준비하셨어요?", "progress": { "filled": 0, "total": 5 } }
{ "done": true, "progress": { "filled": 5, "total": 5 } }
```

### summarizeInterview(program, transcript)
payload `{program, transcript:[{section, question, answer}]}`. 두 장을 돌려준다: 내 경험 노트(1인칭, 나만 봄)와 공개용 초안(선배가 고치고 동의해야 공개).
`match`는 AI 원문 일치 검사 결과. `false`면 화면이 "원문과 다를 수 있어요" 표시.
```json
{ "draftId": "D-0001", "program": "독일 뮌헨대 교환",
  "myNote": { "sections": [ { "name": "지원", "lines": [ { "text": "나는 출국 3학기 전부터 TestDaF를 준비했다." } ] } ] },
  "publicDraft": { "sections": [ { "name": "지원", "lines": [ { "lineId": "L-D1-1", "text": "출국 3학기 전부터 TestDaF를 준비했어요.", "match": true } ] } ] } }
```

### saveConsent(draftId, edits)
payload `{draftId, edits:{removed:[lineId], changed:[{lineId, text}]}, consent:true}`
```json
{ "ok": true, "noteId": "N-munich", "added": 3 }
```

### listNotes(filter)
payload `{filter:{type?: "교환"|"파견"|"인턴"|"비교과", q?: "검색어"}}`
```json
{ "notes": [ { "id": "N-munich", "program": "독일 뮌헨대 교환", "type": "교환",
  "oneLine": "TestDaF는 3학기 전부터, 기숙사는 합격 직후 신청", "forWhom": "독일어권 교환을 생각하는 1~2학년",
  "evidenceCount": 7, "lastSemester": "2025-1", "satisfaction": 4.5 } ] }
```

### getNote(id)
칸 순서와 이름은 `data/frames.json`을 따른다. 빈 칸도 `lines: []`로 보낸다. `interviewOnly`가 true인 칸은 선배 인터뷰로만 채워진다.
```json
{ "id": "N-munich", "program": "독일 뮌헨대 교환", "type": "교환",
  "oneLine": "...", "forWhom": "...", "evidenceCount": 7, "lastSemester": "2025-1", "satisfaction": 4.5,
  "officialUrl": "https://...",
  "sections": [ { "name": "지원", "interviewOnly": false,
                  "lines": [ { "text": "...", "sourceId": "R03-1-1", "lineId": "L-R03-1-1", "official": false } ] } ],
  "sources": { "R03-1-1": { "docType": "귀국보고서", "program": "독일 뮌헨대 교환", "semester": "2025-1" } } }
```
`official: true`인 문장(학점 인정·장학금·자격 요건·선발 기준 같은 규정성 진술)은 화면이 "개인 경험이에요" 표시 + `officialUrl` 링크를 붙인다.

### recommendSeniors(noteId)
payload `{noteId}`. 점수 계산은 `common/score.js`(원우). AI 없음.
```json
{ "seniors": [ { "studentId": "202130012", "nickname": "뮌헨 다녀온 독일어과 4학년", "score": 14,
                 "reasons": ["같은 서양어대학", "같은 독일어과", "이중전공 경영학부 같음", "외대쌤 함께 이수"] } ] }
```

### checkMessage(text)
payload `{text}`. 연락처·학번은 코드(정규식), 비방은 AI 판정.
```json
{ "ok": true }
{ "ok": false, "reason": "연락처", "message": "전화번호나 학번은 보낼 수 없어요. 이메일은 괜찮아요." }
```
reason: `연락처` | `학번` | `비방`

### sendMessage(to, text)
payload `{to, text}`. `to`는 상대 studentId. 첫 메시지는 쪽지 신청이 된다.
```json
{ "ok": true, "threadId": "T-0001", "at": "2026-11-20T10:00:00+09:00" }
```

### getMessages()
```json
{ "threads": [ { "threadId": "T-0001", "withId": "202130012", "nickname": "뮌헨 다녀온 독일어과 4학년",
  "accepted": true, "unread": 1,
  "messages": [ { "from": "me", "text": "...", "at": "..." }, { "from": "them", "text": "...", "at": "..." } ] } ] }
```

### getInbox()
```json
{ "myNotes": [ { "id": "N-munich", "program": "독일 뮌헨대 교환" } ],
  "questions": [ { "questionId": "Q-0001", "text": "...", "status": "waiting", "askedAt": "..." },
                 { "questionId": "Q-0002", "text": "...", "status": "answered", "noteId": "N-munich" } ],
  "scraps": [ { "noteId": "N-munich", "program": "독일 뮌헨대 교환" } ],
  "alerts": [ { "text": "기다리던 질문에 새 노트가 생겼어요.", "noteId": "N-munich", "at": "..." } ] }
```

### reportStatement(lineId, reason)
payload `{lineId, reason?}`. 신고된 문장은 즉시 숨김, 부서 리포트에 집계.
```json
{ "ok": true, "hidden": true }
```

### getDeptReport(dept)
직원 전용. AI는 `summary` 한 단락만.
```json
{ "dept": "국제교류팀", "period": "2026-11",
  "programs": [ { "program": "독일 뮌헨대 교환", "questions": 12, "unanswered": 3, "reports": 1 } ],
  "unansweredQuestions": [ { "text": "...", "count": 4 } ],
  "reportedStatements": 1,
  "summary": "..." }
```

## 5. data.js에 둘 export (시그니처)

```js
login(id, pw) · getMe() · askBoo(question)
interviewNext(program, answers) · summarizeInterview(program, transcript) · saveConsent(draftId, edits)
listNotes(filter) · getNote(id) · reportStatement(lineId, reason)
recommendSeniors(noteId) · checkMessage(text) · sendMessage(to, text) · getMessages()
getInbox() · getDeptReport(dept)
```

## 6. mock-data.json 작성 지시

- 최상위 키는 함수 이름. 3장 pickMock 규칙에 나오는 하위 키(`login.student/staff/fail`, `askBoo.exchange/hold`, `interviewNext.steps/done`, `getNote["N-munich"]`, `checkMessage.ok/blocked`)를 만든다.
- 내용은 1장 시연 인물 기준. askBoo.exchange 문장 3개, getNote["N-munich"]는 교환 5칸(지원·학점·비용·생활·팁) 중 4칸 채우고 1칸(비용)은 빈 칸.
- `getNote["N-trade-intern"]`도 하나: 인턴 노트(무역협회 인턴십), 칸은 지원동기·업무내용·배운점·지원·선발·근무조건, 마지막 두 칸은 `interviewOnly: true`이고 비어 있음.
- recommendSeniors는 B(14점), C(5점) 두 명. 가상 문장만 쓰고 실제 후기 원문을 옮기지 않는다.

## 7. data/frames.json (이번에 함께 생성)

```json
{
  "교환": { "칸": ["지원", "학점", "비용", "생활", "팁"] },
  "파견": { "칸": ["지원", "학점", "비용", "생활", "팁"] },
  "인턴": { "칸": ["지원동기", "업무내용", "배운점", "지원·선발", "근무조건"], "인터뷰로만": ["지원·선발", "근무조건"] },
  "비교과": { "칸": ["활동내용", "배운점"] }
}
```

## 8. 완료 확인

- `screens/talk/index.html`에 askBoo를 부르는 임시 화면(입력창+버튼+결과)을 두고, "독일 교환 준비 언제부터?"는 출처 달린 문장 3개, "HUFS특강 어때요?"는 보류 안내가 나온다.
- data/README.md에는 이 문서 4장의 응답 모양을 표로 옮기고 "원본: docs/spec-v1.md"라고 적는다.
