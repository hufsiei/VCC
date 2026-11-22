// 해봤노트 화면 (작업 23 1단계) — 목록 + 노트 커버
// 기준: docs/design-rules.md 7-③·5-5·6-3~6-5, docs/spec-v1.md 4장 listNotes
// 규칙: 데이터는 common/data.js 함수로만, 화면 글은 textContent로만(innerHTML 금지), 색은 style.css 변수만.

import { currentUser, listNotes } from "../../common/data.js";

// ---------------------------------------------------------------------------
// 0. 로그인 확인
// ---------------------------------------------------------------------------

const me = currentUser();
if (!me) location.replace("../login/");
if (me && me.status === "직원") document.getElementById("consoleBtn").hidden = false;

// 노트 종류(type) → 분야(3-3). 교환·파견은 국제교류, 인턴은 현장실습
const CATEGORY = { 교환: "global", 파견: "global", 인턴: "practice", 비교과: "extra" };
const CATEGORY_NAME = { global: "국제교류", practice: "현장실습", extra: "비교과" };
// 띠의 세부 분류. listNotes에 국가·기관 유형이 없어서 종류만 쓴다(비교과는 분야 태그와 같아 비움)
const KIND_NAME = { 교환: "교환학생", 파견: "파견", 인턴: "인턴", 비교과: "" };
const DASH = "–";

// ---------------------------------------------------------------------------
// 확인용 예시(?demo=1일 때만). mock-data.json에 비교과·빈 요약 노트가 없어서 화면 폴더 안에만 둔다.
// mock에 비교과 노트가 들어오면 이 블록을 지운다.
// ---------------------------------------------------------------------------

const DEMO = new URLSearchParams(location.search).get("demo") === "1";
const DEMO_NOTES = [
  { id: "N-demo-extra", program: "HUFS 동문멘토링 데이", type: "비교과",
    oneLine: "", forWhom: "진로를 고민하는 1~2학년",
    evidenceCount: 0, lastSemester: "2026-1", satisfaction: 4.2, completedCount: 150 },
  { id: "N-demo-dispatch", program: "(예시) 파견 노트 — 값이 비어 있을 때", type: "파견",
    oneLine: "", forWhom: "", evidenceCount: 0, lastSemester: null, satisfaction: null, completedCount: null },
];

// ---------------------------------------------------------------------------
// 1. 작은 도우미 — 요소 만들기(글은 textContent로만), 아이콘
// ---------------------------------------------------------------------------

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  const { className, text, attrs } = props;
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (attrs) for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  for (const child of [].concat(children)) if (child) node.append(child);
  return node;
}
const icon = (name) => el("i", { className: "icon", attrs: { "data-lucide": name } });
const drawIcons = () => window.lucide && window.lucide.createIcons({ attrs: { "stroke-width": 1.75 } });

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

// ---------------------------------------------------------------------------
// 2. 노트 커버 — 공통 부품 .note-card(7-③ 커버 5항목)
// ---------------------------------------------------------------------------

function noteCover(note) {
  const cat = CATEGORY[note.type] || "global";

  const band = el("div", { className: "note-card__band" }, [
    el("span", { className: "category-tag", text: CATEGORY_NAME[cat] }),
    el("span", { className: "note-card__kind", text: KIND_NAME[note.type] ?? "" }),
  ]);

  // 메타 줄: 근거 N건 · 최근 학기 · ★ 만족도 (비교과는 · 이수 N명 추가)
  const count = Number.isFinite(note.evidenceCount) ? note.evidenceCount : 0;
  const star = el("span", { className: "note-card__star" }, [icon("star"), el("span", { text: orDash(note.satisfaction) })]);
  const meta = el("p", { className: "note-card__meta" }, [
    el("span", { text: `근거 ${count}건` }), el("span", { text: "·", attrs: { "aria-hidden": "true" } }),
    el("span", { text: `최근 ${semesterText(note.lastSemester)}` }), el("span", { text: "·", attrs: { "aria-hidden": "true" } }),
    star,
  ]);
  star.setAttribute("aria-label", `만족도 ${orDash(note.satisfaction)}`);
  if (note.type === "비교과") {
    const done = note.completedCount === null || note.completedCount === undefined ? DASH : `${note.completedCount}명`;
    meta.append(el("span", { text: "·", attrs: { "aria-hidden": "true" } }), el("span", { text: `이수 ${done}` }));
  }

  const body = el("div", { className: "note-card__body" }, [
    el("h3", { className: "note-card__title", text: orDash(note.program) }),
    el("p", { className: "note-card__summary", text: orDash(note.oneLine) }),
    el("p", { className: "note-card__target", text: orDash(note.forWhom) }),
    meta,
  ]);

  return el("article", { className: `note-card cat-${cat}` }, [band, body]);
}

// ---------------------------------------------------------------------------
// 3. 목록 그리기 — 로딩(6-3) · 빈 화면(6-4) · 오류(6-5)
// ---------------------------------------------------------------------------

const listEl = document.getElementById("noteList");
const countEl = document.getElementById("noteCount");
let allNotes = [];
let currentCat = "";
let loaded = false;

function showLoading() {
  loaded = false;
  listEl.setAttribute("aria-busy", "true");
  countEl.textContent = "";
  listEl.replaceChildren(...[0, 1, 2].map(() => el("div", { className: "skeleton note-skeleton", attrs: { "aria-hidden": "true" } })));
}

function showError() {
  listEl.setAttribute("aria-busy", "false");
  countEl.textContent = "";
  const retry = el("button", { className: "btn btn--outline", text: "다시 시도", attrs: { type: "button" } });
  retry.addEventListener("click", load);
  listEl.replaceChildren(el("div", { className: "state-box" }, [
    el("span", { className: "status-label status-label--error" }, [icon("circle-alert"), el("span", { text: "불러오지 못했어요" })]),
    el("p", { className: "sub", text: "잠시 뒤 다시 시도해 주세요." }),
    retry,
  ]));
  drawIcons();
}

function render() {
  listEl.setAttribute("aria-busy", "false");
  const notes = currentCat ? allNotes.filter((n) => CATEGORY[n.type] === currentCat) : allNotes;
  countEl.textContent = `노트 ${notes.length}개`;

  if (!notes.length) {
    const ask = el("a", { className: "btn btn--secondary", text: "BOO에게 물어보기", attrs: { href: "../talk/" } });
    listEl.replaceChildren(el("div", { className: "state-box" }, [
      el("img", { className: "boo-illust", attrs: { src: "../../assets/boo-portrait.png", alt: "BOO" } }),
      el("p", { className: "state-box__title", text: "아직 이 분야의 해봤노트가 없어요" }),
      el("p", { className: "sub", text: "궁금한 점은 BOO에게 먼저 물어보세요." }),
      ask,
    ]));
    return;
  }
  listEl.replaceChildren(...notes.map(noteCover));
  drawIcons();
}

// 국제교류 = 교환 + 파견이라 서버 type 하나로 거를 수 없어서, 전체를 한 번 받아 화면에서 거른다
async function load() {
  showLoading();
  try {
    const res = await listNotes({});
    allNotes = Array.isArray(res && res.notes) ? res.notes : [];
    if (DEMO) allNotes = allNotes.concat(DEMO_NOTES);
    loaded = true;
    render();
  } catch (err) {
    console.error(err);
    showError();
  }
}

// ---------------------------------------------------------------------------
// 4. 필터 칩 — 같은 화면 안 전환이라 하단 탭은 그대로(5-2)
// ---------------------------------------------------------------------------

document.getElementById("filters").addEventListener("click", (e) => {
  const chip = e.target.closest(".choice-chip");
  if (!chip) return;
  currentCat = chip.dataset.cat;
  for (const c of e.currentTarget.querySelectorAll(".choice-chip")) c.setAttribute("aria-pressed", String(c === chip));
  if (loaded) render(); // 불러오는 중이거나 오류면 그 화면을 그대로 둔다
});

if (DEMO) document.getElementById("demoNotice").hidden = false;
drawIcons();
if (me) load();
