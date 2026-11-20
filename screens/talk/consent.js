// 공개 동의 바텀시트 (작업 70) — AI 요약 미리보기의 「해봤노트에 공유」에서 열린다.
// 기준: docs/design-rules.md 7-② 공개 동의 바텀시트 · 8절 '공개 동의' · 5-10, docs/spec-v1.md 4장(summarizeInterview·saveConsent)
// 규칙: 데이터는 common/data.js 함수로만, 화면 글은 textContent로만(innerHTML 금지), 색은 style.css 변수만.
//
// 흐름: talk.js가 document에 "open-consent"(detail = summarizeInterview 응답)를 보낸다
//   → 시트를 연다 → 「동의하고 공유」 → saveConsent(draftId, {removed:[끈 lineId]})
//   → 성공하면 시트를 닫고 document에 "consent-saved"(detail = {draftId, result, shared, removed})를 보낸다(토스트는 talk.js가 띄움).
//   → 응답에 rejected(서버가 거절한 문장)가 있으면 시트를 닫지 않고 그 문장 아래에 message를 보여 준 뒤 「확인」으로 닫는다.
// 끈 문장은 removed로만 보낸다. 내 경험노트(myNote)는 서버가 이미 저장했으므로 끈 문장도 거기에는 남는다.

import { saveConsent, listNotes } from "../../common/data.js";

const CATEGORY = { 교환: "global", 파견: "global", 인턴: "practice", 비교과: "extra" };
const CATEGORY_NAME = { global: "국제교류", practice: "현장실습", extra: "비교과" };
const QUESTION_SECTION = "후배 질문";

// ---------------------------------------------------------------------------
// 도우미 — 요소 만들기(글은 textContent로만), 아이콘
// ---------------------------------------------------------------------------

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  const { className, text, attrs, on } = props;
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (attrs) for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null && v !== false) node.setAttribute(k, v === true ? "" : String(v));
  if (on) for (const [k, fn] of Object.entries(on)) node.addEventListener(k, fn);
  for (const child of [].concat(children)) if (child !== null && child !== undefined && child !== false) node.append(child);
  return node;
}
const icon = (name) => el("i", { className: "icon", attrs: { "data-lucide": name } });
const drawIcons = () => window.lucide && window.lucide.createIcons({ attrs: { "stroke-width": 1.75 } });
const statusLabel = (kind, iconName, text) =>
  el("span", { className: `status-label status-label--${kind}` }, [iconName ? icon(iconName) : null, text]);

// ---------------------------------------------------------------------------
// 시트 틀 (index.html의 #consentSheet)
// ---------------------------------------------------------------------------

const root = document.getElementById("consentSheet");
const panel = root.querySelector(".sheet");
const targetBox = document.getElementById("consentTarget");
const linesBox = document.getElementById("consentLines");
const scopeBox = document.getElementById("consentScope");
const agreeBox = document.getElementById("consentAgree");
const agreeError = document.getElementById("consentError");
const submitBtn = document.getElementById("consentSubmit");
const submitReason = document.getElementById("consentReason");
const cancelBtn = document.getElementById("consentCancel");
const resultBox = document.getElementById("consentResult");

const state = {
  draft: null,        // summarizeInterview 응답
  on: new Map(),      // lineId → 켬(true)/끔(false)
  lineCount: 0,
  note: undefined,    // 반영될 해봤노트(listNotes 한 줄) · null이면 새 노트 · undefined면 아직 모름
  busy: false,
  done: false,        // 공유는 됐지만 서버가 일부 문장을 거절해 결과를 보여 주는 중
  rejected: new Map(), // lineId → 서버가 준 message (saveConsent.rejected, spec 4장 [11/20])
  lastFocus: null,
};
// 같은 요약 초안을 다시 열면 고른 상태를 그대로 보여 준다(공유 범위 바꾸기)
const remembered = new Map(); // draftId → Map(lineId → bool)
const rememberedRejected = new Map(); // draftId → Map(lineId → message)

document.addEventListener("open-consent", (event) => openSheet(event.detail));

function openSheet(draft) {
  if (!draft || !draft.publicDraft) return;
  state.draft = draft;
  state.busy = false;
  state.done = false;
  state.lastFocus = document.activeElement;
  state.rejected = new Map(rememberedRejected.get(draft.draftId) || []);

  const prev = remembered.get(draft.draftId);
  state.on = new Map();
  for (const line of allLines(draft)) {
    // 기본 켬. 본인 식별 문장(identifying)은 기본 꺼짐 — 판단은 사용자가 한다(7-②)
    // 서버가 거절한 문장은 해봤노트에 들어가지 않았으므로 꺼짐
    const on = prev && prev.has(line.lineId) ? prev.get(line.lineId) : line.identifying !== true;
    state.on.set(line.lineId, state.rejected.has(line.lineId) ? false : on);
  }
  state.lineCount = state.on.size;

  agreeBox.checked = false;
  agreeBox.disabled = false;
  agreeError.replaceChildren();
  resultBox.replaceChildren();
  resultBox.hidden = true;
  submitBtn.textContent = "동의하고 공유";
  cancelBtn.hidden = false;
  renderLines();
  renderTarget();
  update();
  loadTarget(draft.program);

  root.hidden = false;
  document.body.classList.add("sheet-open");
  panel.querySelector(".sheet__body").scrollTop = 0;
  drawIcons();
  panel.focus();
}

function closeSheet() {
  if (state.busy) return;
  if (state.draft) remembered.set(state.draft.draftId, new Map(state.on));
  root.hidden = true;
  document.body.classList.remove("sheet-open");
  if (state.lastFocus && state.lastFocus.focus) state.lastFocus.focus();
}

function allLines(draft) {
  return ((draft.publicDraft && draft.publicDraft.sections) || [])
    .flatMap((s) => (s.lines || []).filter((l) => l && l.lineId));
}

// ---------------------------------------------------------------------------
// ① 반영될 해봤노트 (시트 맨 위)
// ---------------------------------------------------------------------------

async function loadTarget(program) {
  state.note = undefined;
  renderTarget();
  const res = await listNotes({ q: program });
  if (state.draft && state.draft.program !== program) return; // 그 사이 다른 초안이 열림
  const notes = (res && Array.isArray(res.notes)) ? res.notes : [];
  state.note = notes.find((n) => n.program === program) || null;
  renderTarget();
  drawIcons();
}

function onCount() {
  let n = 0;
  for (const v of state.on.values()) if (v) n += 1;
  return n;
}

function renderTarget() {
  const head = el("span", { className: "consent-target__label", text: "반영될 해봤노트" });

  if (state.note === undefined) {
    targetBox.replaceChildren(head, el("div", { className: "skeleton", attrs: { style: "height: 48px", "aria-label": "불러오는 중" } }));
    return;
  }

  if (state.note === null) {
    // 같은 프로그램 노트가 없을 때: 정보 라벨
    targetBox.replaceChildren(head, el("div", {}, [statusLabel("info", "info", "새 해봤노트로 만들어져요")]));
    return;
  }

  const note = state.note;
  const cat = CATEGORY[note.type];
  const before = Number(note.evidenceCount) || 0;
  // 켠 문장이 하나도 없으면 근거 수는 바뀌지 않는다(7-②). 이번 인터뷰 1건이 더해진다.
  const after = onCount() > 0 ? before + 1 : before;

  targetBox.replaceChildren(
    head,
    el("div", { className: "consent-target__title" }, [
      cat ? el("span", { className: `category-tag cat-${cat}`, text: CATEGORY_NAME[cat] }) : null,
      el("span", { className: "consent-target__name", text: note.program }),
    ]),
    el("p", { className: "consent-target__count num" }, [icon("sparkles"), `근거 ${before}건 → ${after}건`]),
    el("p", { className: "sub", text: "결과보고서·다른 선배 인터뷰와 함께 정리돼요" }),
  );
}

// ---------------------------------------------------------------------------
// ② 칸별 문장 + 문장마다 공개 스위치
// ---------------------------------------------------------------------------

function renderLines() {
  const sections = (state.draft.publicDraft.sections || []).filter((s) => (s.lines || []).some((l) => l && l.lineId));
  if (sections.length === 0) {
    linesBox.replaceChildren(el("p", { className: "sub", text: "공개할 수 있는 문장이 없어요." }));
    return;
  }
  linesBox.replaceChildren(...sections.map((section) => el("div", { className: "consent-section" }, [
    el("h3", { className: "consent-section__name", text: section.name }),
    ...section.lines.filter((l) => l && l.lineId).map((line) => lineRow(section.name, line)),
  ])));
}

let switchSeq = 0;
function lineRow(sectionName, line) {
  const id = `consent-sw-${++switchSeq}`;
  // 끈 문장: 진한 남색 + 자물쇠로 「내 경험노트에만 남아요」
  const offNote = el("span", { className: "consent-line__off" }, [icon("lock"), "내 경험노트에만 남아요"]);
  // 본인 식별 문장을 켰을 때 주의 문구 (임시 문장 — 민지 11/20, 문구 확정 시 교체)
  const riskNote = line.identifying === true
    ? el("span", { className: "consent-line__risk" }, [icon("triangle-alert"), "내 개인 정보가 유출될 수 있어요"])
    : null;
  // 서버가 거절한 문장(saveConsent.rejected): 문장 바로 아래에 서버 message를 그대로
  const rejectedMsg = state.rejected.get(line.lineId);
  const rejectNote = rejectedMsg !== undefined
    ? el("span", { className: "consent-line__rejected" }, [icon("circle-alert"), rejectedMsg || "이 문장은 해봤노트에 넣을 수 없어요."])
    : null;
  const showNotes = (on) => {
    offNote.hidden = on;
    if (riskNote) riskNote.hidden = !on;
  };

  const sw = el("input", {
    className: "switch",
    attrs: { type: "checkbox", role: "switch", id },
    on: {
      change: (e) => {
        state.on.set(line.lineId, e.currentTarget.checked);
        row.classList.toggle("consent-line--off", !e.currentTarget.checked);
        showNotes(e.currentTarget.checked);
        renderTarget();
        update();
        drawIcons();
      },
    },
  });
  sw.checked = state.on.get(line.lineId) === true;
  // 거절된 문장은 켤 수 없게, 결과를 보여 주는 동안은 모든 스위치를 잠근다
  sw.disabled = Boolean(rejectNote) || state.done;
  showNotes(sw.checked);

  const text = el("label", { className: "consent-line__text", attrs: { for: id } }, [
    // 후배 질문 칸: Q(후배 질문 원문, 인용) + A(내 답)
    sectionName === QUESTION_SECTION && line.asked ? el("span", { className: "msg__quote", text: `Q. ${line.asked}` }) : null,
    el("span", { text: sectionName === QUESTION_SECTION ? `A. ${line.text}` : line.text }),
  ]);

  const row = el("div", {
    className: `consent-line${sw.checked ? "" : " consent-line--off"}${rejectNote ? " consent-line--rejected" : ""}`,
  }, [
    el("div", { className: "consent-line__main" }, [
      line.identifying === true ? statusLabel("warning", "triangle-alert", "나를 알아볼 수 있는 내용이에요") : null,
      text,
      rejectNote,
      // AI 원문 일치 검사에 걸린 문장(spec summarizeInterview.match)
      line.match === false ? statusLabel("neutral", "info", "원문과 다를 수 있어요") : null,
      offNote,
      riskNote,
    ]),
    sw,
  ]);
  return row;
}

// ---------------------------------------------------------------------------
// ③ 공개되는 것 / 공개되지 않는 것 · ④ 동의 체크 + 「동의하고 공유」
// ---------------------------------------------------------------------------

function renderScope() {
  const on = onCount();
  const off = state.lineCount - on;
  const item = (iconName, text) => el("li", { className: "consent-scope__item" }, [icon(iconName), text]);
  scopeBox.replaceChildren(
    el("div", { className: "consent-scope__col" }, [
      el("h3", { className: "consent-scope__title", text: "공개되는 것" }),
      el("ul", {}, [item("check", `켠 문장 ${on}개`), item("check", "전공"), item("check", "이수 학기")]),
    ]),
    el("div", { className: "consent-scope__col" }, [
      el("h3", { className: "consent-scope__title", text: "공개되지 않는 것" }),
      el("ul", {}, [item("lock", "이름"), item("lock", "학번"), item("lock", "대화 원문"), item("lock", `끈 문장 ${off}개`)]),
    ]),
  );
}

function update() {
  renderScope();
  if (state.done) {
    // 결과를 보여 주는 중: 「확인」만 누를 수 있다
    submitBtn.disabled = false;
    submitReason.hidden = true;
    return;
  }
  const on = onCount();
  const ready = on > 0 && agreeBox.checked && !state.busy;
  submitBtn.disabled = !ready;
  // 비활성이면 이유를 버튼 아래 14px로(5-4)
  let reason = "";
  if (on === 0) reason = "공개할 문장을 하나 이상 켜 주세요";
  else if (!agreeBox.checked) reason = "동의에 체크하면 공유할 수 있어요";
  submitReason.hidden = !reason || state.busy;
  submitReason.lastChild.textContent = reason;
}

agreeBox.addEventListener("change", update);

submitBtn.addEventListener("click", async () => {
  if (state.done) {
    closeSheet(); // 결과 확인 뒤 「확인」
    return;
  }
  if (submitBtn.disabled || !state.draft) return;
  const removed = [...state.on].filter(([, v]) => !v).map(([id]) => id);

  state.busy = true;
  submitBtn.disabled = true;
  submitBtn.textContent = "공유하는 중…";
  agreeError.replaceChildren();

  const res = await saveConsent(state.draft.draftId, { removed });

  state.busy = false;
  submitBtn.textContent = "동의하고 공유";
  if (!res || res.error || res.ok === false) {
    // 화면 안 오류(6-5): 시트는 닫지 않고 고른 상태를 그대로 둔다.
    // 서버가 문장을 막으면(ok:false + message) 그 문구를 그대로 보여 준다
    // 예: "해봤노트에는 연락처·메일·링크·주소를 넣을 수 없어요."
    agreeError.replaceChildren(
      statusLabel("error", "circle-alert", "공유하지 못했어요"),
      el("p", { className: "sub", text: (res && (res.message || res.error)) || "잠시 뒤에 다시 시도해 주세요." }),
    );
    agreeError.scrollIntoView({ block: "nearest" });
    update();
    drawIcons();
    return;
  }

  const draftId = state.draft.draftId;
  // 서버가 고친 문장 중 일부를 거절한 경우(spec 4장 saveConsent [11/20]):
  // 그 문장만 해봤노트에서 빠지고 나머지는 저장됐다 → 시트를 닫지 않고 문장마다 message를 보여 준다
  const rejected = (Array.isArray(res.rejected) ? res.rejected : []).filter((r) => r && state.on.has(r.lineId));
  if (rejected.length === 0) {
    closeSheet();
    document.dispatchEvent(new CustomEvent("consent-saved", {
      detail: { draftId, result: res, shared: onCount(), removed },
    }));
    return;
  }

  for (const r of rejected) {
    state.rejected.set(r.lineId, typeof r.message === "string" ? r.message : "");
    state.on.set(r.lineId, false); // 해봤노트에 안 들어감
  }
  rememberedRejected.set(draftId, new Map(state.rejected));
  state.done = true;
  showResult(rejected.length);
  renderLines();
  renderTarget();
  update();
  drawIcons();
  linesBox.querySelector(".consent-line--rejected")?.scrollIntoView({ block: "center" });
  document.dispatchEvent(new CustomEvent("consent-saved", {
    detail: { draftId, result: res, shared: onCount(), removed: [...state.on].filter(([, v]) => !v).map(([id]) => id) },
  }));
});

// 일부 거절 결과(시트 맨 위): 반영 상태 + 「N문장은 해봤노트에 넣지 못했어요」
function showResult(rejectedCount) {
  const shared = onCount();
  resultBox.replaceChildren(
    shared > 0
      ? statusLabel("success", "check", "해봤노트에 반영하고 있어요")
      : statusLabel("warning", "triangle-alert", "해봤노트에 넣은 문장이 없어요"),
    el("p", { className: "sub", text: `${rejectedCount}문장은 해봤노트에 넣지 못했어요. 내 경험노트에는 남아 있어요.` }),
  );
  resultBox.hidden = false;
  agreeBox.disabled = true;
  cancelBtn.hidden = true;
  submitBtn.textContent = "확인";
}

// ---------------------------------------------------------------------------
// 닫기: 「취소」 · 바깥(어두운 면) · Esc. 시트 안에서 Tab이 밖으로 나가지 않게
// ---------------------------------------------------------------------------

cancelBtn.addEventListener("click", closeSheet);
root.querySelector(".sheet-scrim").addEventListener("click", closeSheet);
root.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    e.preventDefault();
    closeSheet();
    return;
  }
  if (e.key !== "Tab") return;
  const focusables = [...panel.querySelectorAll("button, input, a[href], [tabindex]:not([tabindex='-1'])")]
    .filter((n) => !n.disabled && n.offsetParent !== null);
  if (focusables.length === 0) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (e.shiftKey && (document.activeElement === first || document.activeElement === panel)) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
});
