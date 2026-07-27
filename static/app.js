const API = "";

const els = {
  statusPill: document.getElementById("statusPill"),
  statusDot: document.getElementById("statusDot"),
  statusText: document.getElementById("statusText"),
  requestInput: document.getElementById("requestInput"),
  emailToggle: document.getElementById("emailToggle"),
  emailRecipient: document.getElementById("emailRecipient"),
  generateBtn: document.getElementById("generateBtn"),
  generateBtnText: document.getElementById("generateBtnText"),
  btnSpinner: document.getElementById("btnSpinner"),
  modeNote: document.getElementById("modeNote"),
  historyList: document.getElementById("historyList"),
  historyCount: document.getElementById("historyCount"),
  emptyState: document.getElementById("emptyState"),
  runState: document.getElementById("runState"),
  docTypeLabel: document.getElementById("docTypeLabel"),
  modeBadge: document.getElementById("modeBadge"),
  confidenceBadge: document.getElementById("confidenceBadge"),
  reasoningLine: document.getElementById("reasoningLine"),
  summaryCard: document.getElementById("summaryCard"),
  sumIntent: document.getElementById("sumIntent"),
  sumType: document.getElementById("sumType"),
  sumClassConf: document.getElementById("sumClassConf"),
  sumReflConf: document.getElementById("sumReflConf"),
  sumAssumptions: document.getElementById("sumAssumptions"),
  sumIssues: document.getElementById("sumIssues"),
  sumSections: document.getElementById("sumSections"),
  sumRegenerated: document.getElementById("sumRegenerated"),
  sumTime: document.getElementById("sumTime"),
  emailRow: document.getElementById("emailRow"),
  emailBadge: document.getElementById("emailBadge"),
  emailDetail: document.getElementById("emailDetail"),
  checklist: document.getElementById("checklist"),
  assumptionsBlock: document.getElementById("assumptionsBlock"),
  assumptionsList: document.getElementById("assumptionsList"),
  reflectionBlock: document.getElementById("reflectionBlock"),
  reflectionList: document.getElementById("reflectionList"),
  timingBlock: document.getElementById("timingBlock"),
  timingPlanning: document.getElementById("timingPlanning"),
  timingDrafting: document.getElementById("timingDrafting"),
  timingReflection: document.getElementById("timingReflection"),
  timingDocx: document.getElementById("timingDocx"),
  timingTotal: document.getElementById("timingTotal"),
  logDetails: document.getElementById("logDetails"),
  logCount: document.getElementById("logCount"),
  logTimeline: document.getElementById("logTimeline"),
  documentCard: document.getElementById("documentCard"),
  documentTitle: document.getElementById("documentTitle"),
  downloadBtn: document.getElementById("downloadBtn"),
  sectionsPreview: document.getElementById("sectionsPreview"),
};

// ---------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------
async function checkHealth() {
  try {
    const res = await fetch(`${API}/health`);
    const data = await res.json();
    els.statusDot.classList.add("live");
    const mode = data.has_groq_key ? "live LLM configured" : "offline fallback mode";
    els.statusText.textContent = `connected · ${mode} · ${data.total_documents} generated`;
  } catch (e) {
    els.statusDot.classList.add("down");
    els.statusText.textContent = "backend unreachable";
  }
}

// ---------------------------------------------------------------------
// History
// ---------------------------------------------------------------------
async function loadHistory() {
  try {
    const res = await fetch(`${API}/documents`);
    const items = await res.json();
    renderHistory(items);
  } catch (e) {
    // silent — history is a nice-to-have, not core to the flow
  }
}

function renderHistory(items) {
  els.historyCount.textContent = items.length ? `${items.length}` : "";
  if (!items.length) {
    els.historyList.innerHTML = `<p class="history-empty">Nothing generated yet — your first document will appear here.</p>`;
    return;
  }
  els.historyList.innerHTML = "";
  for (const item of items) {
    const btn = document.createElement("button");
    btn.className = "history-item";
    btn.innerHTML = `
      <span class="history-item-icon">§</span>
      <span class="history-item-body">
        <span class="history-item-title">${escapeHtml(item.title)}</span>
        <span class="history-item-meta">${item.document_type.replace(/_/g, " ")} · ${formatDate(item.created_at)}</span>
      </span>
    `;
    btn.addEventListener("click", () => loadDocumentDetail(item.id));
    els.historyList.appendChild(btn);
  }
}

async function loadDocumentDetail(id) {
  try {
    const res = await fetch(`${API}/documents/${id}`);
    if (!res.ok) return;
    const data = await res.json();
    renderResult(data, { instant: true });
  } catch (e) {
    /* ignore */
  }
}

// ---------------------------------------------------------------------
// Generate
// ---------------------------------------------------------------------
els.generateBtn.addEventListener("click", handleGenerate);
document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    els.requestInput.value = chip.dataset.example;
    els.requestInput.focus();
  });
});

// Ctrl+Enter to submit from the textarea
els.requestInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    if (!els.generateBtn.disabled) {
      handleGenerate();
    }
  }
});

els.emailToggle.addEventListener("change", () => {
  els.emailRecipient.classList.toggle("hidden", !els.emailToggle.checked);
  if (els.emailToggle.checked) els.emailRecipient.focus();
});

async function handleGenerate() {
  let request = els.requestInput.value.trim();
  if (!request) {
    setNote("Type a request first.", true);
    return;
  }
  if (els.emailToggle.checked) {
    const recipient = els.emailRecipient.value.trim();
    if (!recipient || !recipient.includes("@")) {
      setNote("Enter a valid recipient email address, or uncheck the email option.", true);
      return;
    }
    // The backend detects email intent from the request TEXT itself
    // (agent/email_intent.py) -- this checkbox is a convenience that
    // appends an explicit instruction rather than a separate API field,
    // so detection stays natural-language-driven either way.
    request += ` Please email the finished document to ${recipient}.`;
  }
  setNote("", false);
  els.generateBtn.disabled = true;
  els.generateBtnText.textContent = "Generating…";
  els.btnSpinner.classList.remove("hidden");

  // Show progress bar and animate it
  const progressEl = document.getElementById("generationProgress");
  const progressFill = document.getElementById("progressFill");
  progressEl.classList.remove("hidden");
  progressFill.classList.remove("done");
  let pct = 0;
  const progressInterval = setInterval(() => {
    // Slow ramp: fast early, slower later (generation takes time)
    if (pct < 40) pct += 4;
    else if (pct < 70) pct += 1.5;
    else if (pct < 88) pct += 0.5;
    progressFill.style.width = pct + "%";
  }, 400);
  // Store interval id so we can clear it later

  try {
    const res = await fetch(`${API}/agent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed (${res.status})`);
    }
    const data = await res.json();
    renderResult(data, { instant: false });
    loadHistory();
    checkHealth();
    
    // Progress bar: fill to done then hide
    clearInterval(progressInterval);
    progressFill.style.width = "100%";
    progressFill.classList.add("done");
    setTimeout(() => {
      progressEl.classList.add("hidden");
      progressFill.style.width = "0%";
      progressFill.classList.remove("done");
    }, 600);
  } catch (e) {
    // On error, clear progress bar and show error
    clearInterval(progressInterval);
    progressEl.classList.add("hidden");
    progressFill.style.width = "0%";
    progressFill.classList.remove("done");
    setNote(e.message || "Something went wrong.", true);
  } finally {
    els.btnSpinner.classList.add("hidden");
    els.generateBtn.disabled = false;
    els.generateBtnText.textContent = "Generate document";
  }
}

function setNote(text, isError) {
  els.modeNote.textContent = text;
  els.modeNote.classList.toggle("error", !!isError);
}

// ---------------------------------------------------------------------
// Render the run: checklist animation -> assumptions -> document card
// ---------------------------------------------------------------------
function renderResult(data, { instant }) {
  els.emptyState.classList.add("hidden");
  els.runState.classList.remove("hidden");

  els.docTypeLabel.textContent = data.document_type.replace(/_/g, " ");
  els.modeBadge.textContent = data.llm_mode;
  els.modeBadge.className = `mode-badge ${data.llm_mode}`;

  // Confidence badge (classification confidence)
  const pct = Math.round((data.classification_confidence ?? 0) * 100);
  els.confidenceBadge.textContent = `${pct}% classification confidence`;
  els.confidenceBadge.className = "confidence-badge " + (pct >= 80 ? "high" : pct >= 55 ? "mid" : "low");
  els.confidenceBadge.title = data.classification_reasoning || "";
  els.reasoningLine.textContent = data.classification_reasoning || "";

  // Agent Decision Summary -- compact one-glance synthesis
  if (data.summary) {
    const s = data.summary;
    els.sumIntent.textContent = s.intent;
    els.sumType.textContent = s.detected_type.replace(/_/g, " ");
    els.sumClassConf.textContent = `${Math.round(s.classification_confidence * 100)}%`;
    els.sumReflConf.textContent = `${Math.round(s.reflection_confidence * 100)}%`;
    els.sumAssumptions.textContent = s.assumptions_count;
    els.sumIssues.textContent = s.reflection_issues;
    els.sumSections.textContent = s.sections_generated;
    els.sumRegenerated.textContent = s.sections_regenerated;
    els.sumTime.textContent = fmtMs(s.execution_time_ms);
    els.summaryCard.classList.remove("hidden");

    // Email delivery -- only shown when it was actually requested
    if (s.email_requested) {
      const badgeClass = s.email_status === "sent" ? "sent" : s.email_status === "pending" ? "pending" : "failed";
      const badgeText = { sent: "✓ Email sent", failed: "✗ Email failed", pending: "… Email pending" }[badgeClass] || s.email_status;
      els.emailBadge.textContent = badgeText;
      els.emailBadge.className = `email-badge ${badgeClass}`;
      const durText = s.email_duration_ms != null ? ` (${fmtMs(s.email_duration_ms)})` : "";
      els.emailDetail.textContent = `to ${s.email_recipient}${durText}`;
      els.emailRow.classList.remove("hidden");
    } else {
      els.emailRow.classList.add("hidden");
    }
  } else {
    els.summaryCard.classList.add("hidden");
  }

  // Checklist
  els.checklist.innerHTML = "";
  const steps = data.plan || [];
  steps.forEach((step, idx) => {
    const li = document.createElement("li");
    li.style.animationDelay = instant ? "0s" : `${idx * 0.12}s`;
    li.innerHTML = `
      <span class="step-mark">${idx + 1}</span>
      <span><span class="step-name">${escapeHtml(step.name)}</span>${escapeHtml(step.description)}</span>
    `;
    els.checklist.appendChild(li);
    const revealDelay = instant ? 0 : idx * 220 + 180;
    setTimeout(() => li.classList.add("done"), revealDelay);
  });

  const totalChecklistTime = instant ? 0 : steps.length * 220 + 300;

  // Assumptions
  if (data.assumptions && data.assumptions.length) {
    els.assumptionsList.innerHTML = data.assumptions.map((a) => `<li>${escapeHtml(a)}</li>`).join("");
    els.assumptionsBlock.classList.remove("hidden");
  } else {
    els.assumptionsBlock.classList.add("hidden");
  }

  // Reflection -- evaluate/repair status, not a plain pass/fail
  if (data.reflection && data.reflection.length) {
    const statusIcon = { strong: "✓", regenerated: "↻", strengthened: "↗", unresolved: "✗" };
    els.reflectionList.innerHTML = data.reflection
      .map((c) => {
        const icon = statusIcon[c.status] || "•";
        return `<li><span class="reflection-mark ${c.status}">${icon}</span><span>${escapeHtml(capitalize(c.label))}<span class="reflection-status-tag">${escapeHtml(c.status)}</span> <span class="reflection-note">— ${escapeHtml(c.note)}</span></span></li>`;
      })
      .join("");
    els.reflectionBlock.classList.remove("hidden");
  } else {
    els.reflectionBlock.classList.add("hidden");
  }

  // Timing
  if (data.timing) {
    els.timingPlanning.textContent = fmtMs(data.timing.planning_ms);
    els.timingDrafting.textContent = fmtMs(data.timing.drafting_ms);
    els.timingReflection.textContent = fmtMs(data.timing.reflection_ms);
    els.timingDocx.textContent = fmtMs(data.timing.docx_ms);
    els.timingTotal.textContent = fmtMs(data.timing.total_ms);
    els.timingBlock.classList.remove("hidden");
  } else {
    els.timingBlock.classList.add("hidden");
  }

  // Full execution log timeline (collapsible, grouped by phase, event-structured)
  if (data.execution_log && data.execution_log.length) {
    els.logCount.textContent = data.execution_log.length;
    let html = "";
    let lastPhase = null;
    for (const e of data.execution_log) {
      if (e.phase !== lastPhase) {
        html += `<div class="log-phase-divider">${escapeHtml(e.phase)}</div>`;
        lastPhase = e.phase;
      }
      const time = e.timestamp ? e.timestamp.split("T")[1]?.split(".")[0] || e.timestamp : "";
      const dur = e.duration_ms != null ? ` <span class="log-dur">(${e.duration_ms}ms)</span>` : "";
      const statusClass = e.status === "error" ? "log-status-error" : "";
      html += `<div class="log-line ${statusClass}"><span class="log-time">${escapeHtml(time)}</span><span><span class="log-action">${escapeHtml(e.action)}</span>${escapeHtml(e.message)}${dur}</span></div>`;
    }
    els.logTimeline.innerHTML = html;
    els.logDetails.classList.remove("hidden");
  } else {
    els.logDetails.classList.add("hidden");
  }

  // Document card (revealed after the checklist finishes, for the "it just finished" feel)
  els.documentCard.classList.add("hidden");
  setTimeout(() => {
    els.documentTitle.textContent = data.title || data.document_type;
    els.downloadBtn.href = data.download_url;
    els.downloadBtn.setAttribute("download", data.file_name);

    els.sectionsPreview.innerHTML = "";
    for (const section of data.sections || []) {
      const block = document.createElement("div");
      block.className = "section-block";
      block.innerHTML = `<h3>${escapeHtml(section.title)}</h3><p>${escapeHtml(truncate(section.content, 480))}</p>`;
      els.sectionsPreview.appendChild(block);
    }
    els.documentCard.classList.remove("hidden");
  }, totalChecklistTime);
}

// ---------------------------------------------------------------------
// utils
// ---------------------------------------------------------------------
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function truncate(str, n) {
  if (!str) return "";
  return str.length > n ? str.slice(0, n).trim() + "…" : str;
}

function fmtMs(ms) {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

function capitalize(str) {
  if (!str) return "";
  return str.charAt(0).toUpperCase() + str.slice(1);
}

function formatDate(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch (e) {
    return iso;
  }
}

// ---------------------------------------------------------------------
// init
// ---------------------------------------------------------------------
checkHealth();
loadHistory();
