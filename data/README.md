# 데이터 약속표

원본: docs/spec-v1.md (4장 함수, 9장 데이터 파일). 이 표와 명세가 다르면 명세가 맞습니다. 바꿔야 하면 명세를 먼저 고치고 팀에 알립니다.
모든 데이터는 가상입니다. 실제 학생 정보와 후기 원문은 올리지 않습니다.

## 데이터 파일

구글 시트 "가상프로필_보고서"의 시트 하나가 파일 하나입니다. **JSON 키는 시트 헤더를 글자 그대로** 씁니다(띄어쓰기·마침표 포함). 시트에 없는 값만 영어 이름을 붙입니다.

| 시트 | 파일 | 키 |
|---|---|---|
| 가상 학생 프로필 | `students.json` | 아래 표 |
| 가상 비교과이수내역 | `extracurricular.json` | `학번` `학년도` `학기` `프로그램명` `캠퍼스` `대학` `학과` `운영부서` `프로그램구분` `프로그램구분 소분류` `만족도` `한줄후기` |
| 가상 귀국보고서 | `reports.json` | `학번` `학년도` `학기` `국가` `대학명` + 문항 14개(아래) |
| 가상 인턴십후기 | `internships.json` | `학번` `학년도` `학기` `업체명` `직군` `지원동기` `업무내용` `배운점` |
| 프로그램 목록(새 시트) | `programs.json` | 시트를 만들 때 정한 헤더 그대로 |
| 예상질문 | `eval-questions.csv` | 시트를 만들 때 정한 헤더 그대로 |

### students.json (학생 프로필은 시스템 코드 행을 키로)

| 키 | 시트 헤더 | 뜻 |
|---|---|---|
| status | 구분 | `학생` 또는 `직원` |
| campus | 캠퍼스 | |
| univ_cd | 단과대 코드 | 단과대 (예: `서양어대`) |
| crs_nm | 소속학과명 | 학과 (예: `스페인어과`). 직원은 소속 부서 |
| colreg_no | 학번 | 다른 시트의 `학번`과 같은 값. 학생을 잇는 열쇠 |
| pw | 비번 | 응답에는 넣지 않음 |
| regst_grad | 학년 | |
| buj_mjr_nm | 부전공명 | 없으면 빈 글자 |
| dbl_mjr_nm | 이중전공명 | 예: `경영학`. 없으면 빈 글자 |

선배·후배를 나누는 열은 두지 않습니다. 같은 사람이 이수한 프로그램에서는 답하고, 이수하지 않은 프로그램에서는 묻습니다.

### reports.json 문항 헤더와 노트 칸

| 칸 (`frames.json`) | 문항 헤더 |
|---|---|
| 지원 | `1-1. 입학허가서 신청시 유의사항` `1-2. 비자 취득, 항공권 및 유학생 보험 구입` `1-3. 기타 유의사항` |
| 학점 | `2-2. 수강신청` `2-3. 수업내용 및 프로그램 과정` `3. 파견대학 취득 성적 본교 학점 인정 관련` |
| 비용 | `2-6. 소요 비용` |
| 생활 | `2-1. 공항에서 학교까지 교통편` `2-4. 기숙사 정보` `2-5. 교내 활동` `2-7. 기타 사항` |
| 팁 | `4. 후배들에게 남기고픈 한마디` |
| (제목 칸) | `1. 출국 전 준비사항` `2. 파견대학 관련` |

인턴십후기는 열 이름이 곧 칸 이름입니다(`지원동기` `업무내용` `배운점`). `지원·선발`, `근무조건` 칸은 선배 인터뷰로만 채웁니다.

### evidence.json (시트에서 만드는 근거 문단)

`reports.json`·`internships.json`의 칸 하나가 문단 하나입니다.

| 키 | 뜻 |
|---|---|
| id | 근거 번호(예: `R03-1-1`). 함수 응답의 `sourceId` |
| docType | `귀국보고서` · `인턴십후기` · `인터뷰` · `비교과후기` |
| 학번 · 학년도 · 학기 | 원래 시트 값 그대로 |
| 프로그램명 | `programs.json`의 이름 |
| 문항 | 원래 시트 헤더 글자 그대로(예: `2-4. 기숙사 정보`, `업무내용`) |
| 칸 | `frames.json`의 칸 이름 |
| text | 문단 내용 |

함수 응답의 `studentId`, `withId`, `to`는 모두 `colreg_no` 값입니다.

## 공통 규칙

| 규칙 | 내용 |
|---|---|
| 함수 | 모두 `async`이고 JSON 객체를 돌려준다 |
| 실패 | `{ "error": "사람이 읽을 메시지" }`. 화면은 `res.error`가 있으면 안내 문구를 보여 준다 |
| 학기 표기 | `2025-1`, `2025-2`, `2025-여름`, `2025-겨울` |
| 사람 표시 | 학번은 화면에 보이지 않는다. 다른 사람은 서버가 자동 생성한 `nickname`으로만 표시한다(닮은 선배 카드, 익명 쪽지창). 시트·프로필에는 닉네임이 없다 |
| 로그인 정보 | 화면이 `sessionStorage`의 `"me"`에 저장한다. 함수는 따로 받지 않는다 |
| docType | `귀국보고서` · `인턴십후기` · `인터뷰` · `비교과후기` |

## 함수 15개

| 함수 | 보내는 값 |
|---|---|
| login(id, pw) | `{id, pw}` |
| getMe() | 없음 |
| askBoo(question) | `{question}` |
| interviewNext(program, answers) | `{program, answers:[{section, question, answer}]}` |
| summarizeInterview(program, transcript) | `{program, transcript:[{section, question, answer}]}` |
| saveConsent(draftId, edits) | `{draftId, edits:{removed:[lineId], changed:[{lineId, text}]}, consent:true}` |
| listNotes(filter) | `{filter:{type?, q?}}` (type: 교환·파견·인턴·비교과) |
| getNote(id) | `{id}` |
| recommendSeniors(noteId) | `{noteId}` |
| checkMessage(text) | `{text}` |
| sendMessage(to, text) | `{to, text}` (to는 상대 studentId) |
| getMessages() | 없음 |
| getInbox() | 없음 |
| reportStatement(lineId, reason) | `{lineId, reason?}` |
| getDeptReport(dept) | `{dept}` (직원 전용) |

## 응답 모양

### login

| 필드 | 형식 | 뜻 |
|---|---|---|
| ok | 참/거짓 | 로그인 성공 여부 |
| user.colreg_no | 글자 | 학번(직원은 아이디) |
| user.status | 글자 | `학생` 또는 `직원` (시트 값 그대로) |
| user.crs_nm | 글자 | 직원만. 소속 부서 |
| reason | 글자 | 실패일 때만. 안내 문구 |

### getMe

학생 프로필 한 줄(아래 "데이터 파일"의 `students.json` 키 그대로, `pw` 제외)에 아래를 더합니다.

| 필드 | 형식 | 뜻 |
|---|---|---|
| 비교과이수내역 | 목록 | `extracurricular.json`의 내 행들(키 그대로, `학번` 제외) |
| 귀국보고서 | 목록 | 내 귀국보고서의 `학년도` `학기` `국가` `대학명` |
| 인턴십후기 | 목록 | 내 인턴십후기의 `학년도` `학기` `업체명` `직군` |

선배·후배 구분 필드는 없습니다. 어떤 프로그램에 답할 수 있는지는 위 이수 기록으로 정해집니다.

### askBoo

| 필드 | 형식 | 뜻 |
|---|---|---|
| status | 글자 | `ok`(근거 있음) 또는 `hold`(근거 없음) |
| lines[].text / sourceId / lineId | 글자 | 답변 문장과 출처, 문장 번호 |
| sources | 객체 | sourceId별 `{docType, program, semester}` |
| noteId | 글자 | `ok`일 때. 관련 노트 |
| suggestSenior | 참/거짓 | 닮은 선배 추천을 권할지 |
| questionId | 글자 | `hold`일 때. 질문함에 자동 저장된 질문 번호 |
| message | 글자 | `hold`일 때. 안내 문구 |

### interviewNext

| 필드 | 형식 | 뜻 |
|---|---|---|
| done | 참/거짓 | 인터뷰가 끝났는지 |
| section, question | 글자 | `done`이 false일 때. 다음 질문 한 개 |
| progress.filled / total | 숫자 | 채운 칸 수 / 전체 칸 수 |

### summarizeInterview

| 필드 | 형식 | 뜻 |
|---|---|---|
| draftId | 글자 | 초안 번호 |
| program | 글자 | 프로그램 이름 |
| myNote.sections[].name | 글자 | 내 경험 노트(1인칭, 나만 봄)의 칸 이름 |
| myNote.sections[].lines[].text | 글자 | 문장 |
| publicDraft.sections[].lines[].lineId / text | 글자 | 공개용 초안 문장. 선배가 고치고 동의해야 공개 |
| publicDraft.sections[].lines[].match | 참/거짓 | AI 원문 일치 검사. false면 "원문과 다를 수 있어요" 표시 |

### saveConsent

| 필드 | 형식 | 뜻 |
|---|---|---|
| ok | 참/거짓 | 저장 성공 여부 |
| noteId | 글자 | 반영된 노트 |
| added | 숫자 | 추가된 문장 수 |

### listNotes

| 필드 | 형식 | 뜻 |
|---|---|---|
| notes[].id / program / type | 글자 | 노트 번호, 프로그램, 종류 |
| notes[].oneLine / forWhom | 글자 | 한 줄 요약, 추천 대상 |
| notes[].evidenceCount | 숫자 | 근거 개수 |
| notes[].lastSemester | 글자 | 가장 최근 학기 |
| notes[].satisfaction | 숫자 | 만족도 |

### getNote

칸 순서와 이름은 `data/frames.json`을 따릅니다. 빈 칸도 `lines: []`로 보냅니다.

| 필드 | 형식 | 뜻 |
|---|---|---|
| id / program / type / oneLine / forWhom | 글자 | listNotes와 같음 |
| evidenceCount / lastSemester / satisfaction | 숫자·글자 | listNotes와 같음 |
| officialUrl | 글자 | 공식 안내 주소 |
| sections[].name | 글자 | 칸 이름 |
| sections[].interviewOnly | 참/거짓 | true면 선배 인터뷰로만 채워지는 칸 |
| sections[].lines[].text / sourceId / lineId | 글자 | 문장, 출처, 문장 번호 |
| sections[].lines[].official | 참/거짓 | true면 규정성 진술. "개인 경험이에요" 표시와 `officialUrl` 링크를 붙인다 |
| sources | 객체 | sourceId별 `{docType, program, semester}` |

### recommendSeniors

| 필드 | 형식 | 뜻 |
|---|---|---|
| seniors[].studentId | 글자 | 선배 학번(화면에 보이지 않음) |
| seniors[].nickname | 글자 | 자동 생성 닉네임 |
| seniors[].score | 숫자 | 닮은 정도 점수 |
| seniors[].reasons | 글자 목록 | 점수 이유 |

### checkMessage

| 필드 | 형식 | 뜻 |
|---|---|---|
| ok | 참/거짓 | 보내도 되는지 |
| reason | 글자 | 막힌 이유: `연락처` · `학번` · `비방` |
| message | 글자 | 막혔을 때 안내 문구 |

### sendMessage

| 필드 | 형식 | 뜻 |
|---|---|---|
| ok | 참/거짓 | 전송 성공 여부 |
| threadId | 글자 | 대화 번호. 첫 메시지는 쪽지 신청이 된다 |
| at | 글자 | 보낸 시각 |

### getMessages

| 필드 | 형식 | 뜻 |
|---|---|---|
| threads[].threadId / withId / nickname | 글자 | 대화 번호, 상대 학번, 상대의 자동 생성 닉네임 |
| threads[].accepted | 참/거짓 | 상대가 수락했는지 |
| threads[].unread | 숫자 | 안 읽은 메시지 수 |
| threads[].messages[].from | 글자 | `me` 또는 `them` |
| threads[].messages[].text / at | 글자 | 내용, 시각 |

### getInbox

| 필드 | 형식 | 뜻 |
|---|---|---|
| myNotes[].id / program | 글자 | 내 경험 노트 |
| questions[].questionId / text | 글자 | 질문 번호, 내용 |
| questions[].status | 글자 | `waiting` 또는 `answered` |
| questions[].askedAt / noteId | 글자 | 질문 시각(waiting) / 답이 된 노트(answered) |
| scraps[].noteId / program | 글자 | 스크랩한 노트 |
| alerts[].text / noteId / at | 글자 | 알림 문구, 관련 노트, 시각 |

### reportStatement

| 필드 | 형식 | 뜻 |
|---|---|---|
| ok | 참/거짓 | 신고 접수 여부 |
| hidden | 참/거짓 | 신고된 문장을 즉시 숨겼는지 |

### getDeptReport

| 필드 | 형식 | 뜻 |
|---|---|---|
| dept / period | 글자 | 부서, 기간(예: 2026-11) |
| programs[].program | 글자 | 프로그램 이름 |
| programs[].questions / unanswered / reports | 숫자 | 질문 수, 미해결 수, 신고 수 |
| unansweredQuestions[].text / count | 글자·숫자 | 미해결 질문과 횟수 |
| reportedStatements | 숫자 | 신고된 문장 수 |
| summary | 글자 | AI가 쓴 한 단락 요약 |
