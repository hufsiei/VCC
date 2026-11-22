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
const QUESTION_SECTION = "후배 질문";
const LEARN_SECTION = "배운점";
// 출처 종류 표기(인터BOO와 같음). 근거 블록 머리줄의 보고서 이름은 노트 종류에 따라
const DOC_LABEL = { 귀국보고서: "결과보고서", 현장실습후기: "현장실습후기", 인터뷰: "선배 인터뷰" };
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

function renderList() {
  listEl.setAttribute("aria-busy", "false");
  const notes = currentCat ? allNotes.filter((n) => CATEGORY[n.type] === currentCat) : allNotes;
  countEl.textContent = `노트 ${notes.length}개`;

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
  for (const c of e.currentTarget.querySelectorAll(".choice-chip")) c.setAttribute("aria-pressed", String(c === chip));
  if (loaded) renderList(); // 불러오는 중이거나 오류면 그 화면을 그대로 둔다
});

// ---------------------------------------------------------------------------
// 4. 근거/출처 블록 — 6-1 · 6-2 (칸마다)
// ---------------------------------------------------------------------------

// button: 「질문함에 담기」 버튼(후배 질문 칸은 담을 수 없어 null)
function emptyEvidence(message, button) {
  return el("div", { className: "evidence evidence--empty" }, [
    el("div", { className: "evidence__head" }, [
      el("span", { className: "evidence__summary" }, [
        icon("sparkles"),
        el("span", {}, ["근거 ", el("span", { className: "evidence__num", text: "0" }), "건 · 결과보고서 – · 선배 인터뷰 – · 최근 –"]),
      ]),
    ]),
    el("div", { className: "evidence__empty-body" }, [el("p", { text: message }), button || null]),
  ]);
}

// lines: 칸 문장, sources: getNote.sources, reportName: 「결과보고서」 또는 「현장실습후기」
function evidenceBlock(lines, sources, reportName) {
  const items = lines.map((l) => ({ line: l, src: sources[l.sourceId] || {} }));
  const reports = items.filter((i) => i.src.docType && i.src.docType !== "인터뷰").length;
  const interviews = items.filter((i) => i.src.docType === "인터뷰").length;
  const latest = items.map((i) => i.src.semester).filter(Boolean).sort((a, b) => semesterKey(b) - semesterKey(a))[0];
  const num = (n) => (n > 0 ? el("span", { className: "evidence__num", text: n }) : DASH);

  // 근거 적음 라벨(6-1 v4.3): 1~2건이면 「선배 N명의 경험이에요」(lines.length로 판단, spec)
  const few = lines.length <= 2 ? statusLabel("neutral", "user", `선배 ${lines.length}명의 경험이에요`) : null;

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

// 후배 질문 칸: 같은 질문(answersQuestionId)에 답이 여럿이면 A가 아래로 쌓인다(8절 v4.3)
function questionCards(lines, sources) {
  const groups = new Map();
  for (const l of lines) {
    const key = l.answersQuestionId || l.asked || l.lineId;
    if (!groups.has(key)) groups.set(key, { asked: l.asked, answers: [] });
    groups.get(key).answers.push(l);
  }
  return [...groups.values()].map((g) => el("div", { className: "line qa" }, [
    el("div", { className: "qa__q" }, [
      el("span", { className: "qa__mark", text: "Q", attrs: { "aria-label": "후배 질문" } }),
      el("p", { text: orDash(g.asked) }),
    ]),
    ...g.answers.map((a) => el("div", { className: "qa__a" }, [
      el("span", { className: "qa__mark", text: "A", attrs: { "aria-label": "선배 답" } }),
      el("div", { className: "qa__a-body" }, [el("p", { text: a.text }), lineMeta(a, sources[a.sourceId] || {})]),
    ])),
  ]));
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
  const reportName = note.type === "인턴" ? "현장실습후기" : "결과보고서";

  const children = [];
  const isQuestion = section.name === QUESTION_SECTION;
  // 후배 질문 칸은 질문함에 담을 수 없다(spec saveQuestion: 오류)
  const askBtn = () => (isQuestion ? null : askBoxButton(note.id, section.name));
  if (!lines.length) {
    const msg = isQuestion
      ? "아직 후배 질문에 답한 선배가 없어요."
      : "아직 이 항목을 경험한 선배의 이야기가 없어요.";
    children.push(emptyEvidence(msg, askBtn()));
  } else {
    if (section.name === QUESTION_SECTION) children.push(...questionCards(lines, sources));
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

function route() {
  const id = new URLSearchParams(location.search).get("id");
  if (id) showDetail(id);
  else showList();
}

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
let reportTarget = null;
let reportChoice = null;
let lastFocus = null;

function openReportSheet(line) {
  reportTarget = line;
  reportChoice = null;
  lastFocus = document.activeElement;
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
    // 신고한 문장은 바로 숨긴다(spec: 즉시 숨김)
    for (const s of detailNote.sections) s.lines = (s.lines || []).filter((l) => l.lineId !== reportTarget.lineId);
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
// 9. 시작
// ---------------------------------------------------------------------------

drawIcons();
if (me) route();
