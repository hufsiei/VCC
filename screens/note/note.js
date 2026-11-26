// 해봤노트 화면 (작업 23) — 목록 + 노트 커버(1단계) / 노트 상세(2단계, ?id=노트번호)
// 기준: docs/design-rules.md 7-③·5-2·5-5·6-1~6-5·8절(해봤노트 상세), docs/spec-v1.md 4장 listNotes·getNote·scrapNote·reportStatement
// 규칙: 데이터는 common/data.js 함수로만, 화면 글은 textContent로만(innerHTML 금지), 색은 style.css 변수만.

import { currentUser, listNotes, getNote, scrapNote, saveQuestion, reportStatement } from "../../common/data.js";

// ---------------------------------------------------------------------------
// 0. 로그인 확인
// ---------------------------------------------------------------------------

const me = currentUser();
if (!me) location.replace("../login/");
if (me && me.status === "직원") document.getElementById("consoleBtn").hidden = false;

// 노트 종류(type) → 분야(3-3). 교환·파견은 국제교류, 인턴은 현장실습
const CATEGORY = { 교환: "global", 파견: "global", 인턴: "practice", 비교과: "extra" };
const CATEGORY_NAME = { global: "국제교류", practice: "현장실습", extra: "비교과" };
// 띠의 세부 분류: 종류 + 국가(spec [11/22] country). country가 null이면 종류만(비교과는 분야 태그와 같아 비움)
const KIND_NAME = { 교환: "교환학생", 파견: "파견", 인턴: "인턴", 비교과: "" };
const DASH = "–";
const LEARN_SECTION = "배운점";
// 출처 종류 표기(인터BOO와 같음). 근거 블록 머리줄의 보고서 이름은 노트 종류에 따라
const DOC_LABEL = { 귀국보고서: "보고서", 현장실습후기: "현장실습후기", 인터뷰: "선배 인터뷰" };
// 오래된 근거(6-1 v4.3): 칸의 근거가 모두 2년 넘은 연도
const OLD_YEARS = 2;

// 「질문함에 담기」(spec [11/22] saveQuestion): 그 노트의 한 칸을 질문함에 넣는다.
// 성공하면 응답 message를 토스트로, 버튼은 「질문함에 담았어요」(비활성). 같은 칸은 서버가 하나만 만든다(멱등).
// 탭을 바꿨다 돌아와도 담은 상태가 남게 노트·칸별로 기억한다.
const savedSections = new Set();
const sectionKey = (noteId, section) => `${noteId}|${section}`;

function setSaved(btn) {
  btn.textContent = "질문함에 담았어요";
  btn.disabled = true;
}

function askBoxButton(noteId, section) {
  const btn = el("button", { className: "btn btn--outline", text: "질문함에 담기", attrs: { type: "button" } });
  if (savedSections.has(sectionKey(noteId, section))) {
    setSaved(btn);
    return btn;
  }
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try {
      const res = await saveQuestion(noteId, section);
      if (!res || !res.ok) throw new Error((res && res.error) || "질문함에 담지 못했어요");
      savedSections.add(sectionKey(noteId, section));
      setSaved(btn);
      toast(res.message || "질문함에 담았어요");
    } catch (err) {
      console.error(err);
      btn.disabled = false;
      toast(err.message || "질문함에 담지 못했어요", "circle-alert");
    }
  });
  return btn;
}

function kindText(note) {
  const kind = KIND_NAME[note.type] ?? "";
  return note.country ? [kind, note.country].filter(Boolean).join(" · ") : kind;
}

// ---------------------------------------------------------------------------
// 1. 작은 도우미 — 요소 만들기(글은 textContent로만), 아이콘, 토스트, 학기
// ---------------------------------------------------------------------------

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  const { className, text, attrs } = props;
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (attrs) for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  for (const child of [].concat(children)) if (child !== null && child !== undefined && child !== false) node.append(child);
  return node;
}
const icon = (name) => el("i", { className: "icon", attrs: { "data-lucide": name } });
const drawIcons = () => window.lucide && window.lucide.createIcons({ attrs: { "stroke-width": 1.75 } });
const statusLabel = (kind, iconName, text) =>
  el("span", { className: `status-label status-label--${kind}` }, [iconName ? icon(iconName) : null, el("span", { text })]);

// 토스트(5-10): 3초
function toast(text, iconName = "check") {
  const host = document.getElementById("toastHost");
  host.replaceChildren(el("span", { className: "toast" }, [icon(iconName), el("span", { text })]));
  drawIcons();
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => host.replaceChildren(), 3000);
}

// 빈 값(null·undefined·빈 문자열)은 "–"
const orDash = (v) => (v === null || v === undefined || String(v).trim() === "" ? DASH : String(v));

// 학기 표기(1-2절): "2026-1" → "2026-1학기", "2025-여름" → "2025 하계방학", "2025-겨울" → "2025 동계방학"
function semesterText(s) {
  if (!s) return DASH;
  const [year, term] = String(s).split("-");
  if (term === "1" || term === "2") return `${year}-${term}학기`;
  if (term === "여름") return `${year} 하계방학`;
  if (term === "겨울") return `${year} 동계방학`;
  return String(s);
}
const SEM_ORDER = { 1: 1, 여름: 2, 2: 3, 겨울: 4 };
const semesterKey = (sem) => {
  const [year, part] = String(sem || "").split("-");
  return Number(year || 0) * 10 + (SEM_ORDER[part] || 0);
};
const yearOf = (sem) => String(sem || DASH).split("-")[0]; // 출처 칩은 연도만(v4.3)

// 안전한 링크만(공식 안내 URL): http·https만
function safeUrl(url) {
  try {
    const u = new URL(String(url || ""), location.href);
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// 2. 노트 커버 — 공통 부품 .note-card(7-③ 커버 5항목). 목록은 본문이 상세 링크, 상세에서는 링크 없음
// ---------------------------------------------------------------------------

// 스크랩 버튼(5-5 띠 오른쪽). 상태는 서버 응답의 scrapped로만 바꾼다(spec [11/22] scrapNote)
function setScrapState(btn, on) {
  btn.setAttribute("aria-pressed", String(on));
  btn.setAttribute("aria-label", on ? "스크랩 취소" : "스크랩");
}

function scrapButton(note) {
  const btn = el("button", { className: "icon-btn", attrs: { type: "button" } }, [icon("bookmark")]);
  setScrapState(btn, note.scrapped === true);
  btn.addEventListener("click", async () => {
    const want = btn.getAttribute("aria-pressed") !== "true";
    btn.disabled = true;
    try {
      const res = await scrapNote(note.id, want);
      if (!res || !res.ok) throw new Error((res && res.error) || "스크랩 실패");
      note.scrapped = res.scrapped === true;
      // 목록과 상세가 같은 노트를 보고 있으면 둘 다 맞춘다
      const inList = allNotes.find((n) => n.id === note.id);
      if (inList) inList.scrapped = note.scrapped;
      setScrapState(btn, note.scrapped);
      toast(note.scrapped ? "내 보관함 스크랩에 담았어요" : "스크랩을 해제했어요");
    } catch (err) {
      console.error(err);
      toast("스크랩하지 못했어요. 다시 시도해 주세요", "circle-alert");
    } finally {
      btn.disabled = false;
    }
  });
  return btn;
}

function noteCover(note, { link = true } = {}) {
  const cat = CATEGORY[note.type] || "global";

  const band = el("div", { className: "note-card__band" }, [
    el("span", { className: "category-tag", text: CATEGORY_NAME[cat] }),
    el("span", { className: "note-card__kind", text: kindText(note) }),
    scrapButton(note),
  ]);

  // 메타 줄: 근거 N건 · 최근 학기 · ★ 만족도 (비교과는 · 이수 N명 추가)
  const count = Number.isFinite(note.evidenceCount) ? note.evidenceCount : 0;
  const dot = () => el("span", { text: "·", attrs: { "aria-hidden": "true" } });
  const star = el("span", { className: "note-card__star", attrs: { "aria-label": `만족도 ${orDash(note.satisfaction)}` } },
    [icon("star"), el("span", { text: orDash(note.satisfaction) })]);
  const meta = el("p", { className: "note-card__meta" }, [
    el("span", { text: `근거 ${count}건` }), dot(),
    el("span", { text: `최근 ${semesterText(note.lastSemester)}` }), dot(),
    star,
  ]);
  if (note.type === "비교과") {
    const done = note.completedCount === null || note.completedCount === undefined ? DASH : `${note.completedCount}명`;
    meta.append(dot(), el("span", { text: `이수 ${done}` }));
  }

  const bodyChildren = [
    el(link ? "h3" : "h1", { className: "note-card__title", text: orDash(note.program) }),
    el("p", { className: "note-card__summary", text: orDash(note.oneLine) }),
    el("p", { className: "note-card__target", text: orDash(note.forWhom) }),
    meta,
  ];
  let body;
  if (link) {
    body = el("a", { className: "note-card__body", attrs: { href: `?id=${encodeURIComponent(note.id)}` } }, bodyChildren);
    body.addEventListener("click", (e) => {
      e.preventDefault();
      openDetail(note.id);
    });
  } else {
    body = el("div", { className: "note-card__body" }, bodyChildren);
  }

  return el("article", { className: `note-card cat-${cat}` }, [band, body]);
}

// ---------------------------------------------------------------------------
// 3. 목록 — 로딩(6-3) · 빈 화면(6-4) · 오류(6-5)
// ---------------------------------------------------------------------------

const listEl = document.getElementById("noteList");
const countEl = document.getElementById("noteCount");
let allNotes = [];
let currentCat = "";
let currentQuery = ""; // 검색창 글자(그대로) — 거를 때는 norm()으로
let loaded = false;
let listRequested = false;

function errorBox(onRetry) {
  const retry = el("button", { className: "btn btn--outline", text: "다시 시도", attrs: { type: "button" } });
  retry.addEventListener("click", onRetry);
  return el("div", { className: "state-box" }, [
    statusLabel("error", "circle-alert", "불러오지 못했어요"),
    el("p", { className: "sub", text: "잠시 뒤 다시 시도해 주세요." }),
    retry,
  ]);
}

// 검색(7-③, 11/24): 띄어쓰기·대소문자 무시하고 프로그램명·한 줄 요약·추천 대상·나라·기관유형·종류·분야 글자에 들어 있으면 남긴다.
// 서버 listNotes q와 같은 방식이지만, 분야 필터처럼 전체를 한 번 받아 화면에서 거른다(글자마다 서버를 부르지 않음, mock에서도 동작).
// 검색어를 굵게·밑줄로 강조하지 않는다(디자인 규칙 12절).
const norm = (s) => String(s || "").replace(/\s+/g, "").toLowerCase();
function matchesQuery(n, q) {
  if (!q) return true;
  const words = [n.program, n.oneLine, n.forWhom, n.country, n.kind, n.type, KIND_NAME[n.type], CATEGORY_NAME[CATEGORY[n.type]]];
  return words.some((w) => norm(w).includes(q));
}

// [11/23 주제별 묶기] spec listNotes groups: 분야·검색으로 거른 뒤, 나라·기관 유형으로 거르기 전 카드로 센다
// (칩 하나를 눌러도 다른 칩이 그대로 보이게). 많은 순, 같으면 가나다순. 값이 null인 카드는 세지 않는다.
// 목록을 화면에서 거르므로(국제교류 = 교환 + 파견) 칩 수도 지금 받은 카드로 센다 — 보이는 카드 수와 늘 맞는다(9절)
const GROUP_BY_CAT = { global: { key: "country", label: "나라" }, practice: { key: "kind", label: "기관 유형" } };
const groupEl = document.getElementById("groupChips");
let currentGroup = ""; // 고른 나라·기관 유형(없으면 "")

function renderGroupChips(base) {
  const g = GROUP_BY_CAT[currentCat];
  if (!g) {
    currentGroup = "";
    groupEl.hidden = true;
    groupEl.replaceChildren();
    return;
  }
  const counts = new Map();
  for (const n of base) if (n[g.key]) counts.set(n[g.key], (counts.get(n[g.key]) || 0) + 1);
  const groups = [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ko"));
  if (currentGroup && !counts.has(currentGroup)) currentGroup = ""; // 검색으로 사라진 칩은 풀어 준다
  groupEl.hidden = groups.length === 0;
  groupEl.setAttribute("aria-label", `${g.label} 필터`);
  const chip = (value, text) => {
    const b = el("button", { className: "choice-chip", text, attrs: { type: "button", "aria-pressed": String(currentGroup === value) } });
    b.addEventListener("click", () => {
      currentGroup = value;
      renderList();
    });
    return b;
  };
  groupEl.replaceChildren(chip("", `${g.label} 전체`), ...groups.map(([name, count]) => chip(name, `${name} ${count}`)));
}

function renderList() {
  listEl.setAttribute("aria-busy", "false");
  const q = norm(currentQuery);
  const base = allNotes.filter((n) => (!currentCat || CATEGORY[n.type] === currentCat) && matchesQuery(n, q));
  renderGroupChips(base);
  const g = GROUP_BY_CAT[currentCat];
  const notes = g && currentGroup ? base.filter((n) => n[g.key] === currentGroup) : base;
  countEl.textContent = `노트 ${notes.length}개`;

  if (!notes.length && q) {
    // 검색 결과 없음(6-4): 이름을 바꿔 찾거나, 노트에 없는 것은 BOO에게 묻도록
    listEl.replaceChildren(el("div", { className: "state-box" }, [
      el("img", { className: "boo-illust", attrs: { src: "../../assets/boo-portrait.png", alt: "BOO" } }),
      el("p", { className: "state-box__title", text: `「${currentQuery.trim()}」에 맞는 해봤노트가 없어요` }),
      el("p", { className: "sub", text: "다른 이름으로 찾아보거나, BOO에게 물어보세요." }),
      el("a", { className: "btn btn--secondary", text: "BOO에게 물어보기", attrs: { href: "../talk/?mode=ask" } }),
    ]));
    return;
  }
  if (!notes.length) {
    listEl.replaceChildren(el("div", { className: "state-box" }, [
      el("img", { className: "boo-illust", attrs: { src: "../../assets/boo-portrait.png", alt: "BOO" } }),
      el("p", { className: "state-box__title", text: "아직 이 분야의 해봤노트가 없어요" }),
      el("p", { className: "sub", text: "궁금한 점은 BOO에게 먼저 물어보세요." }),
      el("a", { className: "btn btn--secondary", text: "BOO에게 물어보기", attrs: { href: "../talk/" } }),
    ]));
    return;
  }
  listEl.replaceChildren(...notes.map((n) => noteCover(n)));
  drawIcons();
}

// 국제교류 = 교환 + 파견이라 서버 type 하나로 거를 수 없어서, 전체를 한 번 받아 화면에서 거른다
async function loadList() {
  listRequested = true;
  loaded = false;
  listEl.setAttribute("aria-busy", "true");
  countEl.textContent = "";
  listEl.replaceChildren(...[0, 1, 2].map(() => el("div", { className: "skeleton note-skeleton", attrs: { "aria-hidden": "true" } })));
  try {
    const res = await listNotes({});
    allNotes = Array.isArray(res && res.notes) ? res.notes : [];
    loaded = true;
    renderList();
  } catch (err) {
    console.error(err);
    listEl.setAttribute("aria-busy", "false");
    listEl.replaceChildren(errorBox(loadList));
    drawIcons();
  }
}

// 필터 칩 — 같은 화면 안 전환이라 하단 탭은 그대로(5-2)
document.getElementById("filters").addEventListener("click", (e) => {
  const chip = e.target.closest(".choice-chip");
  if (!chip) return;
  currentCat = chip.dataset.cat;
  currentGroup = ""; // 분야를 바꾸면 나라·기관 유형 칩은 처음부터
  for (const c of e.currentTarget.querySelectorAll(".choice-chip")) c.setAttribute("aria-pressed", String(c === chip));
  if (loaded) renderList(); // 불러오는 중이거나 오류면 그 화면을 그대로 둔다
});

// 검색창 — 칠 때마다 바로 거른다(같은 화면 안 전환). Enter는 휴대폰 키보드만 내린다
const queryInput = document.getElementById("noteQuery");
const queryClear = document.getElementById("noteQueryClear");
function setQuery(value) {
  currentQuery = value;
  queryClear.hidden = value === "";
  if (loaded) renderList();
}
queryInput.addEventListener("input", () => setQuery(queryInput.value));
document.getElementById("noteSearch").addEventListener("submit", (e) => {
  e.preventDefault();
  queryInput.blur();
});
queryClear.addEventListener("click", () => {
  queryInput.value = "";
  setQuery("");
  queryInput.focus();
});

// ---------------------------------------------------------------------------
// 4. 근거/출처 블록 — 6-1 · 6-2 (칸마다)
// ---------------------------------------------------------------------------

// button: 「질문함에 담기」 버튼
function emptyEvidence(message, button, reportName = "보고서") {
  return el("div", { className: "evidence evidence--empty" }, [
    el("div", { className: "evidence__head" }, [
      el("span", { className: "evidence__summary" }, [
        icon("sparkles"),
        el("span", {}, ["근거 ", el("span", { className: "evidence__num", text: "0" }), `건 · ${reportName} – · 선배 인터뷰 – · 최근 –`]),
      ]),
    ]),
    el("div", { className: "evidence__empty-body" }, [el("p", { text: message }), button || null]),
  ]);
}

// lines: 칸 문장, sources: getNote.sources, reportName: 「보고서」 또는 「현장실습후기」
function evidenceBlock(lines, sources, reportName) {
  const items = lines.map((l) => ({ line: l, src: sources[l.sourceId] || {} }));
  const reports = items.filter((i) => i.src.docType && i.src.docType !== "인터뷰").length;
  const interviews = items.filter((i) => i.src.docType === "인터뷰").length;
  const latest = items.map((i) => i.src.semester).filter(Boolean).sort((a, b) => semesterKey(b) - semesterKey(a))[0];
  const num = (n) => (n > 0 ? el("span", { className: "evidence__num", text: n }) : DASH);

  // 근거 적음 라벨(6-1 v4.3): 1~2건이면 고정 문구 「선배 1명의 경험이에요」(lines.length로 판단, spec)
  // [11/26 #295] 문장 수 ≠ 선배 수(서버에 사람 수 없음)라 「선배 2명」으로 세지 않는다
  const few = lines.length <= 2 ? statusLabel("neutral", "user", "선배 1명의 경험이에요") : null;

  return el("details", { className: "evidence" }, [
    el("summary", { className: "evidence__head" }, [
      el("span", { className: "evidence__summary" }, [
        icon("sparkles"),
        el("span", {}, ["근거 ", num(lines.length), `건 · ${reportName} `, num(reports), " · 선배 인터뷰 ", num(interviews), ` · 최근 ${semesterText(latest)}`]),
      ]),
      el("span", { className: "evidence__side" }, [
        few,
        el("span", { className: "evidence__toggle" }, [
          el("span", { className: "evidence__toggle-closed", text: "펼치기" }),
          el("span", { className: "evidence__toggle-open", text: "접기" }),
          icon("chevron-down"),
        ]),
      ]),
    ]),
    // 출처 한 줄: 종류 | 연도만(v4.3). 자동 분류 문장은 끝에 「자동 분류」
    el("ul", { className: "evidence__list" }, items
      .slice()
      .sort((a, b) => semesterKey(b.src.semester) - semesterKey(a.src.semester))
      .map((i) => el("li", { className: "evidence__item" }, [
        DOC_LABEL[i.src.docType] || orDash(i.src.docType),
        " ", el("span", { className: "evidence__sep", text: "|" }), " ",
        yearOf(i.src.semester),
        i.line.autoClassified ? statusLabel("neutral", null, "자동 분류") : null,
      ]))),
  ]);
}

// ---------------------------------------------------------------------------
// 5. 칸 문장 — 원문 인용, 신고 버튼, 「개인 경험」·「자동 분류」 라벨
// ---------------------------------------------------------------------------

// 출처 칩: 「선배 인터뷰 · 2025」(연도만, v4.3).
// 배운점 문장에 senior가 있으면 「선배 A · 2025」(spec [11/22], 노트 안에서만 쓰는 글자, 학과 없음 — PRD 9-1)
function sourceChip(line, src) {
  const who = line.senior || DOC_LABEL[src.docType] || orDash(src.docType);
  return el("span", { text: `${who} · ${yearOf(src.semester)}` });
}

function reportButton(line) {
  const btn = el("button", { className: "icon-btn", attrs: { type: "button", "aria-label": "이 문장 신고" } }, [icon("flag")]);
  btn.addEventListener("click", () => openReportSheet(line));
  return btn;
}

function lineMeta(line, src) {
  return el("div", { className: "line__meta" }, [
    sourceChip(line, src),
    line.official ? statusLabel("neutral", "user", "개인 경험") : null,
    line.autoClassified ? statusLabel("neutral", null, "자동 분류") : null,
    // 후배 질문에 답한 문장(spec getNote [v2]): 질문의 칸에 일반 문장으로 들어오고 라벨만 붙인다. Q 원문은 보이지 않음
    line.answersQuestionId ? statusLabel("neutral", "message-circle", "후배 질문에 답한 문장") : null,
    reportButton(line),
  ]);
}

function lineCard(line, src, { quote = false } = {}) {
  // 배운점은 선배별 원문 인용 — 출처 칩이 「선배 A · 2025」(sourceChip)
  return el("div", { className: `line${quote ? " line--quote" : ""}` }, [
    el("p", { className: "line__text", text: line.text }),
    lineMeta(line, src),
  ]);
}

// ---------------------------------------------------------------------------
// 5-1. 칸별 요약(작업 78, spec getNote [v2] summary·[11/23] newLines·[11/26 칸유형])
//   소제목 → (비용 칸 stats 한 줄 + 분포 띠) → 요약 개조식(문장마다 한 줄 + 출처 연도 + 「보고서 N건」, official이면 「개인 경험」)
//   → 「새로 더해진 선배 이야기 N건」. 생활·지원 칸은 summary[].topic이 있으면 소주제 라벨로 묶는다.
//   [11/26 #321] 한 문단으로 이어 쓰던 것을 개조식으로 바꿈(국제처 피드백 「그래서 얼마인거지?」).
//   [11/25 #266] 「원문 N건 보기」 접기는 없앴다 — 근거는 요약 문장 끝 출처, 신고는 요약 문장에(5-2 신고 풍선).
//   summary가 없으면 이 부분을 안 쓰고 원문 목록 그대로. 배운점은 서버가 summary를 보내지 않는다.
// ---------------------------------------------------------------------------

const hasSummary = (section) =>
  section.name !== LEARN_SECTION && Array.isArray(section.summary) && section.summary.length > 0;

// lines 끝 newLines개가 요약 뒤 인터뷰로 붙은 문장. 0~lines.length 안으로만
function newLineCount(section) {
  const n = Number(section.newLines);
  const total = (section.lines || []).length;
  return Number.isFinite(n) && n > 0 ? Math.min(Math.floor(n), total) : 0;
}

// 문장 끝 출처: 「보고서 2025, 2026」, 인터뷰가 섞이면 「보고서 2025 · 선배 인터뷰 2026」
function summarySourceText(item, sources, reportName) {
  const byKind = new Map();
  for (const id of item.sources || []) {
    const src = sources[id];
    if (!src) continue;
    const kind = src.docType === "인터뷰" ? DOC_LABEL.인터뷰 : reportName;
    const year = Number(yearOf(src.semester));
    if (!byKind.has(kind)) byKind.set(kind, new Set());
    if (Number.isFinite(year)) byKind.get(kind).add(year);
  }
  // sources에서 학기를 못 찾으면 서버가 준 years로
  if (![...byKind.values()].some((s) => s.size) && Array.isArray(item.years) && item.years.length) {
    byKind.clear();
    byKind.set(reportName, new Set(item.years.map(Number).filter(Number.isFinite)));
  }
  return [...byKind.entries()]
    .map(([kind, years]) => [kind, ...(years.size ? [[...years].sort((a, b) => a - b).join(", ")] : [])].join(" "))
    .join(" · ");
}

// [11/26 칸유형] 생활 칸 소주제 순서(디자인 규칙 1-2, 민지 결정 5종). 다른 칸은 처음 나온 순서
const TOPIC_ORDER = { 생활: ["주거", "교통", "음식", "행정", "사람"] };

// 그 요약 문장 sources의 서로 다른 문서 수(spec getNote [11/26 칸유형], Q-38) — sourceId 앞부분(R149·I12)이 문서.
// R149-1-1·R149-1-3은 1명. 한 선배의 보고서와 인터뷰는 이을 칸이 없어 따로 센다
const docCount = (ids) => new Set((ids || []).map((id) => String(id).split("-")[0]).filter(Boolean)).size;

// 요약 문장 한 줄: 문장 + (출처 연도 · 「선배 N명」 · 「개인 경험」)
function summaryItem(item, sources, reportName) {
  const from = summarySourceText(item, sources, reportName);
  const count = docCount(item.sources);
  return el("li", { className: "summary__item" }, [
    summarySentence(item),
    el("span", { className: "summary__meta" }, [
      from ? el("span", { className: "summary__from", text: from }) : null,
      // 이 문장을 받치는 선배(문서) 수 — 코드 집계라 AI 표시색이 아닌 중립색. [11/26 #324] 「보고서 N건」 → 「선배 N명」
      count ? el("span", { className: "summary__count", text: `선배 ${count}명` }) : null,
      // 규정에 닿는 요약 문장(official) — 칸 문장과 같은 중립 라벨 「개인 경험」(디자인 규칙 8-1)
      item.official ? statusLabel("neutral", "user", "개인 경험") : null,
    ]),
  ]);
}

// 요약 개조식. topic이 하나라도 있으면 소주제별로 묶고, topic 없는 문장은 라벨 없이 맨 뒤
function summaryList(section, sources, reportName) {
  const items = section.summary;
  const list = (arr, extra = "") => el("ul", { className: `summary__list${extra}` }, arr.map((it) => summaryItem(it, sources, reportName)));
  const topicOf = (it) => (typeof it.topic === "string" && it.topic.trim() ? it.topic.trim() : null);
  if (!items.some(topicOf)) return [list(items)];

  const order = TOPIC_ORDER[section.name] || [];
  const groups = new Map();
  for (const it of items) {
    const t = topicOf(it);
    if (!t) continue;
    if (!groups.has(t)) groups.set(t, []);
    groups.get(t).push(it);
  }
  const rank = (t) => (order.includes(t) ? order.indexOf(t) : order.length);
  const names = [...groups.keys()].sort((a, b) => rank(a) - rank(b)); // 정렬은 안정적이라 목록 밖 라벨은 처음 나온 순서
  const out = names.map((t) =>
    el("div", { className: "summary__group" }, [el("h4", { className: "summary__topic", text: t }), list(groups.get(t))]));
  const rest = items.filter((it) => !topicOf(it));
  if (rest.length) out.push(list(rest, " summary__list--rest"));
  return out;
}

// [11/26 칸유형] 비용 칸 stats {min, max, median, n, years}(만 원, 코드 집계). 값이 이상하면 null → 표시 안 함
function validStats(stats) {
  if (!stats || typeof stats !== "object") return null;
  const { min, max, median, n } = stats;
  const nums = [min, max, median, n].map(Number);
  if (!nums.every(Number.isFinite) || nums[3] < 1 || nums[0] > nums[1] || nums[2] < nums[0] || nums[2] > nums[1]) return null;
  const years = (Array.isArray(stats.years) ? stats.years : []).map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  const values = (Array.isArray(stats.values) ? stats.values : []).map(Number).filter((v) => Number.isFinite(v) && v >= nums[0] && v <= nums[1]);
  return { min: nums[0], max: nums[1], median: nums[2], n: nums[3], years, values };
}

const manwon = (v) => `${Math.round(v).toLocaleString("ko-KR")}만 원`;

// 비용 한 줄 + 분포 띠(SVG, createElementNS — innerHTML 금지). AI가 만든 것이 아니므로 중립색만
function statsBlock(stats, reportName) {
  const range = stats.min === stats.max ? manwon(stats.min) : `${manwon(stats.min)} ~ ${manwon(stats.max)}`;
  const years = stats.years.length ? ` · ${[...new Set([stats.years[0], stats.years[stats.years.length - 1]])].join("–")}` : "";
  const line = el("p", { className: "stats__line" }, [
    el("span", { className: "stats__range num", text: `한 달 ${range}` }),
    el("span", { className: "stats__sub", text: `가운데 ${manwon(stats.median)} · ${reportName} ${stats.n}건${years}` }),
  ]);

  const NS = "http://www.w3.org/2000/svg";
  const svgEl = (tag, attrs) => {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
    return node;
  };
  // 가로로 늘어나도(preserveAspectRatio none) 점·선 굵기는 그대로(CSS vector-effect), 점은 길이 0인 둥근 선
  const W = 300, H = 28, PAD = 8, Y = 14;
  const x = (v) => (stats.max === stats.min ? W / 2 : PAD + ((v - stats.min) / (stats.max - stats.min)) * (W - PAD * 2));
  const svg = svgEl("svg", { class: "stats__strip", viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", role: "img",
    "aria-label": `한 달 비용 ${range}, 가운데 ${manwon(stats.median)}, ${reportName} ${stats.n}건` });
  svg.append(svgEl("line", { class: "stats__axis", x1: PAD, y1: Y, x2: W - PAD, y2: Y }));
  // 보고서별 금액(values)이 오면 점으로, 없으면 최소·최대 눈금만
  if (stats.values.length) stats.values.forEach((v) => svg.append(svgEl("line", { class: "stats__dot", x1: x(v), y1: Y, x2: x(v), y2: Y })));
  else [stats.min, stats.max].forEach((v) => svg.append(svgEl("line", { class: "stats__tick", x1: x(v), y1: Y - 6, x2: x(v), y2: Y + 6 })));
  svg.append(svgEl("line", { class: "stats__median", x1: x(stats.median), y1: Y - 9, x2: x(stats.median), y2: Y + 9 }));

  return el("div", { className: "stats" }, [
    line,
    svg,
    el("p", { className: "stats__ends num" }, [el("span", { text: manwon(stats.min) }), el("span", { text: manwon(stats.max) })]),
  ]);
}

// 요약 문장 하나. lineId(「S-…」)가 있으면 신고할 수 있다 — 선택하면 풍선(5-2), 키보드는 Tab → Enter
const sentenceItem = new WeakMap(); // 문장 span → summary 항목
function summarySentence(item) {
  const span = el("span", { className: "summary__sentence", text: item.text });
  if (item.lineId) {
    sentenceItem.set(span, item);
    span.tabIndex = 0;
    span.setAttribute("aria-label", `${item.text} — Enter를 누르면 이 문장을 신고할 수 있어요`);
    span.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); openReportSheet({ ...item, kind: "summary" }); }
    });
  }
  return span;
}

function summaryBlock(section, sources, reportName) {
  const lines = section.lines || [];
  const fresh = newLineCount(section);
  const added = lines.slice(lines.length - fresh);
  const stats = validStats(section.stats);
  const out = [
    el("div", { className: "summary" }, [
      el("h3", { className: "summary__title", text: section.name }),
      stats ? statsBlock(stats, reportName) : null,
      ...summaryList(section, sources, reportName),
      el("p", { className: "summary__hint" }, [icon("flag"), el("span", { text: "틀린 문장은 길게 누르거나 드래그해서 신고할 수 있어요" })]),
    ]),
  ];
  if (added.length) {
    out.push(el("h4", { className: "summary-new__title" }, [icon("message-circle-plus"), el("span", { text: `새로 더해진 선배 이야기 ${added.length}건` })]));
    out.push(...added.map((l) => lineCard(l, sources[l.sourceId] || {})));
  }
  return out;
}

// 신고한 요약 문장만 뺀다(원문 lines는 그대로, spec reportStatement). 하나도 안 남으면 그 칸은 원문 목록으로
function hideSummaryInSection(section, lineId) {
  if (!Array.isArray(section.summary)) return;
  section.summary = section.summary.filter((s) => s.lineId !== lineId);
  if (!section.summary.length) {
    delete section.summary;
    delete section.newLines;
  }
}

// 신고로 숨긴 문장을 요약·newLines에도 맞춘다(서버 규칙과 같게: 그 문장을 sources에 든 요약 문장은 뺀다)
function hideLineInSection(section, line) {
  const lines = section.lines || [];
  const idx = lines.findIndex((l) => l.lineId === line.lineId);
  if (idx < 0) return;
  const fresh = newLineCount(section);
  section.lines = lines.filter((l) => l.lineId !== line.lineId);
  if (!Array.isArray(section.summary)) return;
  if (idx >= lines.length - fresh) section.newLines = fresh - 1;
  section.summary = section.summary.filter((s) => !(s.sources || []).includes(line.sourceId));
  if (!section.summary.length) {
    delete section.summary;
    delete section.newLines;
  }
}

// ---------------------------------------------------------------------------
// 6. 상세 화면 — 커버 → 노트 틀 탭 → 칸 문장 + 근거 블록 → 닮은선배
// ---------------------------------------------------------------------------

const viewList = document.getElementById("viewList");
const viewDetail = document.getElementById("viewDetail");
const detailBody = document.getElementById("detailBody");
const detailTitle = document.getElementById("detailTitle");
let detailNote = null;
let currentSection = 0;
let listScrollY = 0;
let cameFromList = false; // 목록에서 눌러 들어왔으면 ←는 브라우저 뒤로(스크롤·필터 유지)

function renderSection(panel) {
  const note = detailNote;
  const section = note.sections[currentSection];
  const sources = note.sources || {};
  const lines = section.lines || [];
  const reportName = note.type === "인턴" ? "현장실습후기" : "보고서"; // [11/25 #274] 화면 용어 「결과보고서」 → 「보고서」

  const children = [];
  const askBtn = () => askBoxButton(note.id, section.name);
  if (!lines.length) {
    children.push(emptyEvidence("아직 이 항목을 경험한 선배의 이야기가 없어요.", askBtn(), reportName));
  } else {
    if (hasSummary(section)) children.push(...summaryBlock(section, sources, reportName));
    else children.push(...lines.map((l) => lineCard(l, sources[l.sourceId] || {}, { quote: section.name === LEARN_SECTION })));
    children.push(evidenceBlock(lines, sources, reportName));

    // 블록 아래 줄: 오래된 근거 · 공식 안내(6-1)
    const after = [];
    const years = lines.map((l) => Number(yearOf((sources[l.sourceId] || {}).semester))).filter(Number.isFinite);
    const thisYear = new Date().getFullYear();
    if (years.length && years.every((y) => thisYear - y > OLD_YEARS)) {
      after.push(statusLabel("info", "info", "최근 경험이 없어요"), askBtn());
    }
    const url = safeUrl(note.officialUrl);
    if (lines.some((l) => l.official) && url) {
      after.push(el("a", { className: "link-more", text: "공식 안내 보기 ›", attrs: { href: url, target: "_blank", rel: "noopener" } }));
    }
    if (after.length) children.push(el("div", { className: "evidence-after" }, after));
  }
  panel.replaceChildren(...children);
  drawIcons();
}

// 고른 탭이 화면 밖으로 잘려 있으면 탭 줄을 밀어 다 보이게 한다(다음 탭도 살짝 보이도록 한 칸 여유).
// 탭 줄만 옆으로 움직이고 화면 전체는 위아래로 움직이지 않게 scrollTo를 쓴다.
function revealTab(tabs, tab) {
  const pad = 48;
  const left = tab.offsetLeft; // .section-tabs가 position: relative라 탭 줄 기준 위치
  const right = left + tab.offsetWidth;
  let target = null;
  if (right + pad > tabs.scrollLeft + tabs.clientWidth) target = right + pad - tabs.clientWidth;
  else if (left - pad < tabs.scrollLeft) target = left - pad;
  if (target === null) return;
  const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  tabs.scrollTo({ left: Math.max(0, target), behavior: smooth ? "smooth" : "auto" });
}

function renderDetail() {
  const note = detailNote;
  detailTitle.textContent = orDash(note.program);
  document.title = `${orDash(note.program)} · 해봤노트`;
  if (currentSection >= note.sections.length) currentSection = 0;

  // 노트 틀 탭: 칸 순서는 getNote가 준 순서 그대로(data/frames.json)
  const tabs = el("div", { className: "section-tabs", attrs: { role: "tablist", "aria-label": "노트 틀" } });
  const panel = el("div", { className: "section-panel", attrs: { role: "tabpanel", id: "sectionPanel" } });
  note.sections.forEach((s, i) => {
    const tab = el("button", {
      className: "choice-chip",
      text: s.name,
      attrs: { type: "button", role: "tab", "aria-selected": String(i === currentSection), "aria-controls": "sectionPanel" },
    });
    tab.addEventListener("click", () => {
      currentSection = i;
      for (const t of tabs.children) t.setAttribute("aria-selected", String(t === tab));
      revealTab(tabs, tab);
      renderSection(panel);
    });
    tabs.append(tab);
  });

  const seniors = el("a", {
    className: "btn btn--secondary btn--block",
    text: "이 노트를 경험한 닮은선배 보기",
    attrs: { href: `../senior/?noteId=${encodeURIComponent(note.id)}` },
  });

  detailBody.setAttribute("aria-busy", "false");
  detailBody.replaceChildren(noteCover(note, { link: false }), tabs, panel, seniors);
  renderSection(panel);
}

// 최근에 본 노트(PR #232 원우 요청): 닮은선배 탭이 추천 기준 노트로 쓴다(senior.js pickBaseNotes).
// 이 탭의 sessionStorage에만, 사람별, 최근이 앞, 5개까지(두 창 시연이 섞이지 않게)
function rememberViewed(id) {
  if (!me || !id) return;
  const key = `viewedNotes:${me.colreg_no}`;
  try {
    const old = JSON.parse(sessionStorage.getItem(key) || "[]");
    const list = [id, ...(Array.isArray(old) ? old : []).filter((x) => x !== id)].slice(0, 5);
    sessionStorage.setItem(key, JSON.stringify(list));
  } catch {
    // 저장 공간이 막혀 있으면 기억하지 않는다
  }
}

async function loadDetail(id) {
  detailNote = null;
  currentSection = 0;
  detailTitle.textContent = "해봤노트";
  detailBody.setAttribute("aria-busy", "true");
  detailBody.replaceChildren(...[0, 1, 2].map(() => el("div", { className: "skeleton detail-skeleton", attrs: { "aria-hidden": "true" } })));
  try {
    const res = await getNote(id);
    if (!res || res.error || !Array.isArray(res.sections)) throw new Error((res && res.error) || "노트 없음");
    detailNote = res;
    rememberViewed(id);
    renderDetail();
  } catch (err) {
    console.error(err);
    detailBody.setAttribute("aria-busy", "false");
    detailBody.replaceChildren(errorBox(() => loadDetail(id)));
    drawIcons();
  }
}

// ---------------------------------------------------------------------------
// 7. 화면 전환 — 주소 ?id=노트번호 이면 상세. 브라우저 뒤로가기도 같이 동작
// ---------------------------------------------------------------------------

function showList() {
  viewDetail.hidden = true;
  viewList.hidden = false;
  document.title = "해봤노트 · 외대人사이드";
  if (!listRequested) loadList();
  window.scrollTo(0, listScrollY);
}

function showDetail(id) {
  viewList.hidden = true;
  viewDetail.hidden = false;
  window.scrollTo(0, 0);
  loadDetail(id);
}

function openDetail(id) {
  listScrollY = window.scrollY;
  cameFromList = true;
  history.pushState({ noteId: id }, "", `?id=${encodeURIComponent(id)}`);
  showDetail(id);
}

// ?type=인턴처럼 들어오면(인터BOO chat 칩 「다른 노트 보기」) 그 분야 필터를 켜고 목록을 연다
function applyTypeFilter(type) {
  const cat = CATEGORY[type];
  if (!cat) return;
  currentCat = cat;
  for (const c of document.querySelectorAll("#filters .choice-chip")) c.setAttribute("aria-pressed", String(c.dataset.cat === cat));
  if (loaded) renderList();
}

function route() {
  const params = new URLSearchParams(location.search);
  const id = params.get("id");
  if (id) showDetail(id);
  else showList();
}

// ?type= 필터는 처음 들어올 때 한 번만 — 뒤로가기(popstate)로 목록에 오면 사용자가 고른 필터를 그대로 둔다
applyTypeFilter(new URLSearchParams(location.search).get("type"));

document.getElementById("detailBack").addEventListener("click", () => {
  if (cameFromList) {
    cameFromList = false;
    history.back(); // popstate → route() → 목록(필터·스크롤 그대로)
  } else {
    // 인터BOO 링크 등으로 바로 들어온 경우: 목록으로
    history.replaceState(null, "", location.pathname);
    showList();
  }
});
window.addEventListener("popstate", () => {
  cameFromList = false;
  route();
});

// ---------------------------------------------------------------------------
// 8. 신고 바텀시트 — 사유 고르기 → reportStatement → 그 문장 숨김
// ---------------------------------------------------------------------------

const REPORT_REASONS = ["사실과 달라요", "개인 정보가 보여요", "불쾌한 표현이 있어요", "기타"];
const sheet = document.getElementById("reportSheet");
const reasonsEl = document.getElementById("reportReasons");
const submitBtn = document.getElementById("reportSubmit");
const reasonHint = document.getElementById("reportReason");
const reportQuote = document.getElementById("reportQuote");
let reportTarget = null;
let reportChoice = null;
let lastFocus = null;

// target: 원문 문장(line, lineId 「L-…」) 또는 요약 문장({ lineId 「S-…」, text, kind: "summary" })
function openReportSheet(line) {
  hideReportBubble();
  reportTarget = line;
  reportChoice = null;
  lastFocus = document.activeElement;
  reportQuote.textContent = line.text || "";
  reportQuote.hidden = !line.text;
  reasonsEl.replaceChildren(...REPORT_REASONS.map((r) => {
    const chip = el("button", { className: "choice-chip", text: r, attrs: { type: "button", "aria-pressed": "false" } });
    chip.addEventListener("click", () => {
      reportChoice = r;
      for (const c of reasonsEl.children) c.setAttribute("aria-pressed", String(c === chip));
      submitBtn.disabled = false;
      reasonHint.hidden = true;
    });
    return chip;
  }));
  submitBtn.disabled = true;
  reasonHint.hidden = false;
  sheet.hidden = false;
  document.body.classList.add("sheet-open");
  sheet.querySelector(".sheet").focus();
}

function closeReportSheet() {
  sheet.hidden = true;
  document.body.classList.remove("sheet-open");
  reportTarget = null;
  if (lastFocus && lastFocus.isConnected) lastFocus.focus();
}

submitBtn.addEventListener("click", async () => {
  if (!reportTarget || !reportChoice || !detailNote) return;
  submitBtn.disabled = true;
  try {
    const res = await reportStatement(reportTarget.lineId, reportChoice);
    if (!res || !res.ok) throw new Error((res && res.error) || "신고 실패");
    // 신고한 문장은 바로 숨긴다(spec: 즉시 숨김). 요약 문장이면 그 요약 문장만
    for (const s of detailNote.sections) {
      if (reportTarget.kind === "summary") hideSummaryInSection(s, reportTarget.lineId);
      else hideLineInSection(s, reportTarget);
    }
    closeReportSheet();
    renderSection(document.getElementById("sectionPanel"));
    toast("신고했어요. 이 문장은 숨겼어요");
  } catch (err) {
    console.error(err);
    submitBtn.disabled = false;
    toast("신고하지 못했어요. 다시 시도해 주세요", "circle-alert");
  }
});
document.getElementById("reportCancel").addEventListener("click", closeReportSheet);
sheet.querySelector(".sheet-scrim").addEventListener("click", closeReportSheet);
sheet.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeReportSheet();
});

// ---------------------------------------------------------------------------
// 8-1. 요약 문장 신고 풍선(spec reportStatement 화면, 디자인 규칙 8-1 ③) — 11/25 #266
//   요약 문장을 길게 누르거나(모바일: 글자 선택) 드래그하면(PC) 선택 끝에 「신고하기」 풍선 → 위 신고 시트.
//   선택이 여러 문장에 걸치면 선택이 끝난 문장을 신고한다.
// ---------------------------------------------------------------------------

const bubble = el("button", { className: "report-bubble", attrs: { type: "button" } }, [icon("flag"), el("span", { text: "신고하기" })]);
bubble.hidden = true;
document.body.append(bubble);
let bubbleItem = null;

function sentenceOf(node) {
  const elNode = node && (node.nodeType === 1 ? node : node.parentElement);
  const span = elNode && elNode.closest(".summary__sentence");
  return span && sentenceItem.has(span) ? span : null;
}

function hideReportBubble() {
  bubble.hidden = true;
  bubbleItem = null;
}

function placeReportBubble() {
  const sel = window.getSelection();
  if (!sel || sel.isCollapsed || !sel.rangeCount || viewDetail.hidden) return hideReportBubble();
  const span = sentenceOf(sel.focusNode) || sentenceOf(sel.anchorNode);
  if (!span) return hideReportBubble();
  const rects = sel.getRangeAt(0).getClientRects();
  const last = rects[rects.length - 1] || span.getBoundingClientRect();
  bubbleItem = sentenceItem.get(span);
  bubble.hidden = false;
  drawIcons();
  // 선택 블록 오른쪽 끝 아래. 화면 밖으로 나가지 않게 좌우 16px 안으로
  const w = bubble.offsetWidth;
  const left = Math.min(Math.max(16, last.right - w), document.documentElement.clientWidth - w - 16);
  bubble.style.left = `${left + window.scrollX}px`;
  bubble.style.top = `${last.bottom + window.scrollY + 8}px`;
}

let bubbleTick = 0;
document.addEventListener("selectionchange", () => {
  cancelAnimationFrame(bubbleTick);
  bubbleTick = requestAnimationFrame(placeReportBubble);
});
// 풍선을 누를 때 선택이 풀려 풍선이 먼저 사라지지 않게 mousedown 기본 동작을 막는다
bubble.addEventListener("mousedown", (e) => e.preventDefault());
bubble.addEventListener("click", () => {
  if (!bubbleItem) return;
  const item = bubbleItem;
  window.getSelection().removeAllRanges();
  openReportSheet({ ...item, kind: "summary" });
});
window.addEventListener("resize", hideReportBubble);

// ---------------------------------------------------------------------------
// 9. 시작
// ---------------------------------------------------------------------------

drawIcons();
if (me) route();
