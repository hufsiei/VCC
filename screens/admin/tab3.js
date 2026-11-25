// 탭3 리포트 발행(PRD 5-4, 작업 69) — 발행 설정 · 다음 발행 예정 · 지금 발행 · 미리보기 · 발행 이력.
// 부서 담당자(권한: 부서)는 설정·발행 없이 「받은 리포트」 목록과 열기만(PRD 7장 권한, 11/19 보강).
// 리포트 HTML은 서버가 만든 메일 본문이라 iframe srcdoc + sandbox(스크립트 없음)로만 보여 준다 — innerHTML 금지(spec 551행).
import { getReportSettings, saveReportSettings, issueReport, listIssuedReports, getIssuedReport } from "../../common/data.js";
import { el, icon, statusLabel, fmt, toast, drawIcons, errorBox } from "./ui.js";

const SECTIONS = ["지표", "프로그램 순위", "미답변 질문", "개선 제안", "신고 진술"]; // functions/admin.py SECTIONS
const PERIOD_NAME = { monthly: "월간", semester: "학기당" };
const DAY_RANGE = { monthly: [1, 28], semester: [0, 60] }; // 서버 saveReportSettings와 같은 범위
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/; // 서버 EMAIL과 같은 규칙
const MAX_RECIPIENTS = 10;
// 미리보기 iframe 안에서 읽을 스타일: 토큰(style.css) + 리포트 모양(report.css)
const REPORT_CSS = [new URL("../../common/style.css", import.meta.url).href, new URL("./report.css", import.meta.url).href];

// ---------------------------------------------------------------------------
// 로딩(6-3)
// ---------------------------------------------------------------------------
export function renderReportLoading(panel) {
  const sk = (cls) => el("div", { className: `skeleton ${cls}`, attrs: { "aria-hidden": "true" } });
  panel.setAttribute("aria-busy", "true");
  panel.replaceChildren(el("div", { className: "pc-only report-tab" }, [sk("block--skeleton"), sk("report--skeleton")]));
}

// ---------------------------------------------------------------------------
// 불러오기 + 그리기
// ctx: { dept, deptName, period, periodLabel, isDept }
// isCurrent(): 부서·기간을 그새 바꿨으면 false → 그리지 않는다
// ---------------------------------------------------------------------------
export async function loadReport(panel, ctx, isCurrent) {
  const retry = () => loadReport(panel, ctx, isCurrent);
  renderReportLoading(panel);
  // 설정을 먼저 부른다 — 서버가 이때 예정일이 지난 자동 발행을 하므로, 이력은 그 뒤에 읽어야 새 줄이 보인다
  const settings = ctx.isDept ? null : await getReportSettings(ctx.dept);
  const list = await listIssuedReports(ctx.dept);
  if (!isCurrent()) return;
  const bad = (!ctx.isDept && (!settings || settings.error)) || !list || list.error || !Array.isArray(list.reports);
  if (bad) {
    panel.removeAttribute("aria-busy");
    panel.replaceChildren(errorBox((settings && settings.error) || (list && list.error), retry));
    drawIcons();
    return;
  }

  const preview = previewBlock(ctx);
  const history = historyBlock(list.reports, ctx, preview);
  const reloadHistory = async () => {
    const res = await listIssuedReports(ctx.dept);
    if (isCurrent() && res && Array.isArray(res.reports)) history.update(res.reports);
  };
  const parts = ctx.isDept
    ? [history.block, preview.block]
    : [settingsBlock(settings, ctx, preview, reloadHistory), preview.block, history.block];
  panel.replaceChildren(el("div", { className: "pc-only report-tab" }, parts));
  panel.removeAttribute("aria-busy");
  drawIcons();
}

// ---------------------------------------------------------------------------
// 1. 발행 설정(총괄 관리자만) + 다음 발행 예정 + 지금 발행
// ---------------------------------------------------------------------------
function settingsBlock(s, ctx, preview, reloadHistory) {
  // 화면에서 고치는 값. 저장한 값(saved)과 다르면 「지금 발행」을 막는다(발행은 서버에 저장된 설정을 쓰므로)
  const form = {
    period: s.period === "semester" ? "semester" : "monthly",
    day: Number.isFinite(s.day) ? s.day : 1,
    recipients: Array.isArray(s.recipients) ? [...s.recipients] : [],
    sections: Array.isArray(s.sections) ? SECTIONS.filter((x) => s.sections.includes(x)) : [...SECTIONS],
  };
  let saved = JSON.stringify(form);
  let everSaved = !!s.nextIssueAt; // 서버는 저장한 적 있는 설정에만 nextIssueAt을 준다
  const dirty = () => JSON.stringify(form) !== saved;

  // 주기: 세그먼트(7-①과 같은 부품)
  const periodBtns = ["monthly", "semester"].map((p) => {
    const b = el("button", { className: "segment__btn", text: PERIOD_NAME[p], attrs: { type: "button", role: "radio", "data-period": p } });
    b.addEventListener("click", () => {
      if (form.period === p) return;
      form.period = p;
      const [lo, hi] = DAY_RANGE[p];
      form.day = Math.min(Math.max(form.day, lo), hi);
      dayInput.value = form.day;
      paint();
    });
    return b;
  });
  const periodField = el("div", { className: "field" }, [
    el("p", { className: "field__label", text: "주기", attrs: { id: "rptPeriodLabel" } }),
    el("div", { className: "segment report-segment", attrs: { role: "radiogroup", "aria-labelledby": "rptPeriodLabel" } }, periodBtns),
  ]);

  // 발행일: 월간 = 매월 n일(1~28) / 학기당 = 학기 종료 후 n일(0~60)
  const dayInput = el("input", { className: "input report-day", attrs: { id: "rptDay", type: "number", inputmode: "numeric", value: form.day } });
  const dayBefore = el("span", { className: "report-day__text" });
  const dayAfter = el("span", { className: "report-day__text" });
  const dayHint = el("p", { className: "block__note" });
  const dayError = fieldError();
  dayInput.addEventListener("input", () => { form.day = Number(dayInput.value); setError(dayInput, dayError, ""); paint(); });
  const dayField = el("div", { className: "field" }, [
    el("label", { className: "field__label", text: "발행일", attrs: { for: "rptDay" } }),
    el("div", { className: "report-day__row" }, [dayBefore, dayInput, dayAfter]),
    dayHint,
    dayError.node,
  ]);

  // 받는 사람: 목록 + 이메일 추가(형식 검사, 10명까지)
  const recList = el("ul", { className: "report-recipients" });
  const recCount = el("span", { className: "block__note" });
  const recInput = el("input", { className: "input", attrs: { id: "rptMail", type: "email", placeholder: "name@example.com", autocomplete: "off" } });
  const recAdd = el("button", { className: "btn btn--outline", text: "추가", attrs: { type: "button" } });
  const recError = fieldError();
  const addRecipient = () => {
    const v = recInput.value.trim();
    if (!v) return setError(recInput, recError, "이메일을 입력해 주세요");
    if (!EMAIL.test(v)) return setError(recInput, recError, "이메일 형식을 확인해 주세요");
    if (form.recipients.some((r) => r.toLowerCase() === v.toLowerCase())) return setError(recInput, recError, "이미 넣은 이메일이에요");
    if (form.recipients.length >= MAX_RECIPIENTS) return setError(recInput, recError, `받는 사람은 ${MAX_RECIPIENTS}명까지예요`);
    form.recipients.push(v);
    recInput.value = "";
    setError(recInput, recError, "");
    paint();
    recInput.focus();
  };
  recAdd.addEventListener("click", addRecipient);
  recInput.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); addRecipient(); } });
  recInput.addEventListener("input", () => setError(recInput, recError, ""));
  const recField = el("div", { className: "field" }, [
    el("div", { className: "report-field-head" }, [el("label", { className: "field__label", text: "받는 사람", attrs: { for: "rptMail" } }), recCount]),
    recList,
    el("div", { className: "report-add" }, [recInput, recAdd]),
    el("p", { className: "block__note", text: "부서 대표메일(가상)이 기본으로 들어가 있어요." }),
    recError.node,
  ]);

  // 포함 항목 체크
  const secError = fieldError();
  const checks = SECTIONS.map((name) => {
    const box = el("input", { className: "checkbox", attrs: { type: "checkbox", value: name } });
    box.checked = form.sections.includes(name);
    box.addEventListener("change", () => {
      form.sections = SECTIONS.filter((x) => (x === name ? box.checked : form.sections.includes(x)));
      setError(null, secError, "");
      paint();
    });
    return el("label", { className: "check-row report-check" }, [box, el("span", { text: name })]);
  });
  const secField = el("fieldset", { className: "field report-fieldset" }, [
    el("legend", { className: "field__label", text: "포함 항목" }),
    el("div", { className: "report-checks" }, checks),
    secError.node,
  ]);

  // 다음 발행 예정 · 마지막 발행
  const nextLine = el("div", { className: "report-next" });
  let nextShown = null;
  const showNext = (nextIssueAt, lastIssuedAt) => {
    nextShown = nextIssueAt;
    nextLine.replaceChildren(...[
      nextIssueAt
        ? statusLabel("info", "calendar", `다음 발행 예정: ${nextIssueAt} (${PERIOD_NAME[savedPeriod()]})`)
        : statusLabel("neutral", "calendar", "설정을 저장하면 다음 발행 예정일이 정해져요"),
      lastIssuedAt ? el("span", { className: "block__note", text: `마지막 발행 ${timeText(lastIssuedAt)}` }) : null,
    ].filter(Boolean));
    drawIcons();
  };
  const savedPeriod = () => JSON.parse(saved).period;
  let lastIssuedAt = s.lastIssuedAt;
  showNext(s.nextIssueAt, lastIssuedAt);

  // 저장(Primary) · 지금 발행(Secondary)
  const saveBtn = el("button", { className: "btn btn--primary", text: "저장", attrs: { type: "button" } });
  const issueBtn = el("button", { className: "btn btn--secondary", attrs: { type: "button" } }, [icon("send"), el("span", { text: "지금 발행" })]);
  const issueReason = el("p", { className: "btn-reason" });
  const formError = el("div", { className: "report-form-error", attrs: { "aria-live": "polite" } });

  saveBtn.addEventListener("click", async () => {
    formError.replaceChildren();
    if (!validate()) return;
    saveBtn.disabled = true;
    const res = await saveReportSettings(ctx.dept, { ...form, day: Number(form.day) });
    saveBtn.disabled = false;
    if (res && res.ok) {
      saved = JSON.stringify(form);
      everSaved = true;
      toast("발행 설정을 저장했어요");
      showNext(res.nextIssueAt, lastIssuedAt);
      paint();
    } else {
      formError.replaceChildren(statusLabel("error", "circle-alert", (res && res.error) || "저장하지 못했어요. 다시 시도해 주세요"));
      drawIcons();
    }
  });

  issueBtn.addEventListener("click", async () => {
    issueBtn.disabled = true;
    issueBtn.replaceChildren(el("span", { text: "발행하는 중…" }));
    const res = await issueReport(ctx.dept, ctx.period);
    issueBtn.replaceChildren(icon("send"), el("span", { text: "지금 발행" }));
    paint();
    if (res && res.reportId && typeof res.html === "string") {
      // 다음 발행 예정일은 서버가 마지막 발행 기준으로 다시 계산한다 → 탭을 다시 열 때 갱신. 지금은 마지막 발행만 바꾼다
      lastIssuedAt = res.issuedAt;
      showNext(nextShown, lastIssuedAt);
      toast("리포트를 발행했어요");
      preview.show(res);
      reloadHistory();
    } else {
      toast((res && res.error) || "발행하지 못했어요. 다시 시도해 주세요", "circle-alert");
    }
    drawIcons();
  });
  function validate() {
    let ok = true;
    const [lo, hi] = DAY_RANGE[form.period];
    if (!Number.isInteger(Number(form.day)) || form.day < lo || form.day > hi || dayInput.value === "") {
      setError(dayInput, dayError, `발행일은 ${lo}~${hi} 사이 숫자로 적어 주세요`);
      ok = false;
    }
    if (!form.recipients.length) {
      setError(recInput, recError, "받는 사람을 1명 이상 넣어 주세요");
      ok = false;
    }
    if (!form.sections.length) {
      setError(null, secError, "포함 항목을 하나 이상 골라 주세요");
      ok = false;
    }
    return ok;
  }

  // 화면 다시 칠하기(값 → 표시)
  function paint() {
    for (const b of periodBtns) {
      const on = b.dataset.period === form.period;
      b.setAttribute("aria-checked", String(on));
      b.setAttribute("aria-selected", String(on)); // .segment__btn 모양은 aria-selected로 칠한다
    }
    const [lo, hi] = DAY_RANGE[form.period];
    dayInput.min = lo;
    dayInput.max = hi;
    dayBefore.textContent = form.period === "monthly" ? "매월" : "학기 종료 후";
    dayAfter.textContent = "일";
    dayHint.textContent = form.period === "monthly"
      ? `${lo}~${hi}일 중에서 골라요. 지난달 집계를 보내요.`
      : `학기 종료일(2월 말·8월 말)에서 ${lo}~${hi}일 뒤. 지난 학기 집계를 보내요.`;

    recList.replaceChildren(...form.recipients.map((r, i) => {
      const del = el("button", { className: "btn btn--text", text: "빼기", attrs: { type: "button", "aria-label": `${r} 빼기` } });
      del.addEventListener("click", () => { form.recipients.splice(i, 1); paint(); recInput.focus(); });
      return el("li", { className: "report-recipient" }, [icon("mail"), el("span", { className: "report-recipient__mail", text: r }), del]);
    }));
    if (!form.recipients.length) recList.append(el("li", { className: "report-recipient report-recipient--empty", text: "아직 받는 사람이 없어요" }));
    recCount.textContent = `${form.recipients.length}/${MAX_RECIPIENTS}명`;
    recAdd.disabled = form.recipients.length >= MAX_RECIPIENTS;

    // 바뀐 설정이 있으면 지금 발행을 막고 이유를 보인다(5-4)
    const changed = dirty();
    issueBtn.disabled = changed;
    issueReason.hidden = !changed;
    issueReason.replaceChildren(icon("info"), el("span", { text: "바꾼 설정을 저장한 뒤 발행할 수 있어요" }));
    // 한 번도 저장하지 않은 부서(nextIssueAt 없음)는 기본값 그대로도 저장할 수 있다
    const canSave = changed || !everSaved;
    saveBtn.textContent = canSave ? "저장" : "저장됨";
    saveBtn.disabled = !canSave;
    drawIcons();
  }
  paint();

  return el("section", { className: "card block", attrs: { "aria-labelledby": "rptSettingsTitle" } }, [
    el("div", { className: "block__head" }, [
      el("h2", { className: "section-title", text: `발행 설정 · ${ctx.deptName}`, attrs: { id: "rptSettingsTitle" } }),
      el("p", { className: "block__note", text: "부서마다 따로 저장돼요" }),
    ]),
    el("div", { className: "report-form" }, [
      el("div", { className: "report-form__col" }, [periodField, dayField, secField]),
      el("div", { className: "report-form__col" }, [recField]),
    ]),
    formError,
    nextLine,
    el("div", { className: "report-actions" }, [
      saveBtn,
      el("div", { className: "report-issue" }, [
        issueBtn,
        el("p", { className: "block__note", text: `지금 선택한 기간(${ctx.periodLabel})으로 발행해요` }),
        issueReason,
      ]),
    ]),
  ]);
}

// ---------------------------------------------------------------------------
// 2. 미리보기 — 메일 본문과 같은 HTML(7-⑤). 처음엔 숨김, 발행하거나 「열기」를 누르면 보인다
// ---------------------------------------------------------------------------
function previewBlock(ctx) {
  const meta = el("p", { className: "block__note" });
  const source = el("span");
  const frame = el("iframe", {
    className: "report-frame",
    // 스크립트·같은 출처 권한 없음. 「공식 안내 보기」 링크만 새 탭으로 열 수 있게 팝업 허용
    attrs: { sandbox: "allow-popups allow-popups-to-escape-sandbox", title: "리포트 미리보기", referrerpolicy: "no-referrer" },
  });
  const close = el("button", { className: "btn btn--text", attrs: { type: "button" } }, [icon("x"), el("span", { text: "닫기" })]);
  // 메일 발송은 P2 — 비활성 + 이유(5-4). 부서 담당자 화면에는 두지 않는다
  const send = ctx.isDept ? null : el("div", { className: "report-send" }, [
    el("button", { className: "btn btn--primary", text: "메일 발송", attrs: { type: "button", disabled: "" } }),
    el("p", { className: "btn-reason" }, [icon("info"), el("span", { text: "메일 발송은 운영 연계 시 활성화돼요" })]),
  ]);
  const block = el("section", { className: "card block report-preview", attrs: { "aria-labelledby": "rptPreviewTitle" } }, [
    el("div", { className: "block__head" }, [
      el("h2", { className: "section-title", text: "리포트 미리보기", attrs: { id: "rptPreviewTitle" } }),
      close,
    ]),
    el("div", { className: "report-preview__meta" }, [meta, source]),
    frame,
    send,
  ]);
  block.hidden = true;
  close.addEventListener("click", () => { block.hidden = true; });

  return {
    block,
    show(r) {
      meta.textContent = `${r.reportId || "–"} · 발행 ${timeText(r.issuedAt)}`;
      // 요약이 AI 문장인지 기본 문장인지(issueReport만 알려 줌)
      source.replaceChildren(
        r.summarySource === "ai" ? statusLabel("ai", "sparkles", "AI 요약")
          : r.summarySource === "template" ? statusLabel("neutral", "file-text", "요약: 기본 문장")
            : "",
      );
      frame.srcdoc = reportDoc(r.html || "");
      block.hidden = false;
      drawIcons();
      block.scrollIntoView({ behavior: "smooth", block: "start" });
    },
  };
}

// 서버 HTML을 iframe 문서로 감싼다(글자는 서버가 escape, 여기서는 스타일 링크만 더함)
function reportDoc(body) {
  const links = REPORT_CSS.map((h) => `<link rel="stylesheet" href="${h}">`).join("");
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><base target="_blank">${links}</head><body class="rpt-body">${body}</body></html>`;
}

// ---------------------------------------------------------------------------
// 3. 발행 이력(총괄) / 받은 리포트(부서 담당자)
// ---------------------------------------------------------------------------
function historyBlock(reports, ctx, preview) {
  const title = ctx.isDept ? "받은 리포트" : "발행 이력";
  const count = el("p", { className: "block__note" });
  const body = el("div");
  const block = el("section", { className: "card block", attrs: { "aria-labelledby": "rptHistoryTitle" } }, [
    el("div", { className: "block__head" }, [el("h2", { className: "section-title", text: title, attrs: { id: "rptHistoryTitle" } }), count]),
    body,
  ]);

  const open = async (r, btn) => {
    btn.disabled = true;
    const res = await getIssuedReport(r.reportId);
    btn.disabled = false;
    if (res && typeof res.html === "string" && !res.error) preview.show(res);
    else toast((res && res.error) || "리포트를 열지 못했어요", "circle-alert");
  };

  function update(list) {
    count.textContent = `${fmt(list.length)}건`;
    if (!list.length) {
      body.replaceChildren(el("div", { className: "empty" }, [
        icon("file-text"),
        el("p", { className: "empty__title", text: ctx.isDept ? "아직 받은 리포트가 없어요" : "아직 발행한 리포트가 없어요" }),
        el("p", { className: "sub", text: ctx.isDept ? "총괄 관리자가 발행하면 여기에 쌓여요." : "「지금 발행」을 누르면 여기에 쌓여요." }),
      ]));
      drawIcons();
      return;
    }
    const rows = list.map((r) => {
      const btn = el("button", { className: "btn btn--text", text: "열기", attrs: { type: "button", "aria-label": `${timeText(r.issuedAt)} 리포트 열기` } });
      btn.addEventListener("click", () => open(r, btn));
      return el("tr", {}, [
        el("td", { className: "is-time", text: timeText(r.issuedAt) }),
        el("td", { text: r.dept === "ALL" ? "전체" : (ctx.deptNames[r.dept] || r.dept || "–") }),
        el("td", { text: r.label || periodText(r.period) }),
        el("td", {}, r.mode === "auto" ? statusLabel("info", "clock", "자동") : statusLabel("neutral", "hand", "수동")),
        el("td", { className: "is-num", text: `${fmt(r.recipients)}명` }),
        el("td", { className: "is-action" }, btn),
      ]);
    });
    body.replaceChildren(el("table", { className: "dept-table report-table" }, [
      el("thead", {}, el("tr", {}, ["발행 일시", "부서", "기간", "방식", "받는 사람", "미리보기"].map((h, i) =>
        el("th", { className: i === 4 ? "is-num" : i === 5 ? "is-action" : "", text: h, attrs: { scope: "col" } })))),
      el("tbody", {}, rows),
    ]));
    drawIcons();
  }
  update(reports);
  return { block, update };
}

// 도우미 ------------------------------------------------------------------------
function fieldError() {
  const text = el("span");
  const node = el("p", { className: "field__error", attrs: { role: "alert" } }, [icon("circle-alert"), text]);
  node.hidden = true;
  return { node, text };
}

function setError(input, err, message) {
  err.text.textContent = message;
  err.node.hidden = !message;
  if (input) {
    if (message) input.setAttribute("aria-invalid", "true");
    else input.removeAttribute("aria-invalid");
  }
  drawIcons();
}

// "2026-11-21T10:00:00+09:00" → "2026-11-21 10:00"
function timeText(iso) {
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(String(iso || ""));
  return m ? `${m[1]} ${m[2]}` : (iso ? String(iso) : "–");
}

// {type:"semester", value:"2026-2"} → "2026년 2학기", {type:"month", value:"2026-11"} → "2026년 11월"
function periodText(p) {
  if (!p || !p.value) return "–";
  const [y, n] = String(p.value).split("-");
  return p.type === "semester" ? `${y}년 ${Number(n)}학기` : `${y}년 ${Number(n)}월`;
}
