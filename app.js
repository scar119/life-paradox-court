const issueInput = document.querySelector("#issueInput");
const oathInput = document.querySelector("#oathInput");
const fileCaseBtn = document.querySelector("#fileCaseBtn");
const runTrialBtn = document.querySelector("#runTrialBtn");
const resetTrialBtn = document.querySelector("#resetTrialBtn");
const filingBox = document.querySelector("#filingBox");
const oathQuestions = document.querySelector("#oathQuestions");
const verdictBox = document.querySelector("#verdictBox");
const trialProgress = document.querySelector("#trialProgress");
const progressTitle = document.querySelector("#progressTitle");
const progressPercent = document.querySelector("#progressPercent");
const progressFill = document.querySelector("#progressFill");
const progressSteps = document.querySelector("#progressSteps");
const trialStage = document.querySelector("#trialStage");
const cardProgress = document.querySelector("#cardProgress");
const cardProgressTitle = document.querySelector("#cardProgressTitle");
const cardProgressPercent = document.querySelector("#cardProgressPercent");
const cardProgressFill = document.querySelector("#cardProgressFill");
const cardProgressSteps = document.querySelector("#cardProgressSteps");
const shareBox = document.querySelector("#shareBox");
const shareImageWrap = document.querySelector("#shareImageWrap");
const shareImage = document.querySelector("#shareImage");
const downloadSvgLink = document.querySelector("#downloadSvgLink");
const downloadPngBtn = document.querySelector("#downloadPngBtn");
const logBox = document.querySelector("#logBox");
const modePill = document.querySelector("#modePill");
const demoButtons = document.querySelector("#demoButtons");

let currentIssue = "";
let progressTimer = null;
let progressIndex = 0;
let progressValue = 0;
let currentTrial = null;
let trialStages = [];
let currentStageIndex = 0;
let cardProgressTimer = null;
let cardProgressIndex = 0;
let cardProgressValue = 0;
let shareReady = false;
const stageAnswers = {};

const TRIAL_STEPS = [
  { label: "物理真相层 + Cynefin 分类", detail: "第一性原理剥洋葱，判断决策类型。", percent: 12 },
  { label: "删除检查 + 选项裂变", detail: "先删不该存在的选项，再打破二元框架生成 5+ 路径。", percent: 26 },
  { label: "贝叶斯概率校准 + 时间成本", detail: "拆解信心构成，把拖延换算成真金白银。", percent: 40 },
  { label: "权衡矩阵（7维）+ 敏感性分析", detail: "含时间窗口维度，找出翻转变量和今天决定。", percent: 54 },
  { label: "悖论关卡 + 后果推演 + 使命检查 + 预验尸", detail: "11位角色交叉审问，推三阶后果，使命校验，写事故报告。", percent: 72 },
  { label: "DeepSeek 生成判决书", detail: "整合全部增强阶段分析，生成判决书和含实验纪律的行动实验。", percent: 88 },
  { label: "渲染可分享判决卡", detail: "生成 1080×1440 判决卡 SVG，提供 PNG 下载。", percent: 96 }
];

const CARD_STEPS = [
  { label: "整理判词", detail: "提取标题、真正争议、判词、人格和行动实验。", percent: 24 },
  { label: "排版信息图", detail: "根据文字长度调整字号、行数和留白。", percent: 52 },
  { label: "渲染判决卡", detail: "加载 1080x1440 同源 SVG 信息图。", percent: 78 },
  { label: "准备下载", detail: "激活 PNG 和 SVG 两种下载入口。", percent: 96 }
];

async function api(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {})
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

async function getState() {
  const response = await fetch("/api/state");
  const data = await response.json().catch(() => ({}));
  renderState(data);
}

function setBusy(isBusy, text) {
  fileCaseBtn.disabled = isBusy;
  runTrialBtn.disabled = isBusy || !currentIssue;
  resetTrialBtn.disabled = isBusy;
  issueInput.disabled = isBusy;
  oathInput.disabled = isBusy || !currentIssue;
  if (isBusy) {
    modePill.textContent = text;
  } else if (!currentIssue) {
    modePill.textContent = "待立案";
  }
}

function clearStageAnswers() {
  Object.keys(stageAnswers).forEach((key) => delete stageAnswers[key]);
}

function resetLocalUi() {
  clearInterval(progressTimer);
  clearInterval(cardProgressTimer);
  currentIssue = "";
  progressIndex = 0;
  progressValue = 0;
  currentTrial = null;
  trialStages = [];
  currentStageIndex = 0;
  shareReady = false;
  clearStageAnswers();
  issueInput.value = "";
  oathInput.value = "";
  oathInput.disabled = true;
  fileCaseBtn.disabled = false;
  runTrialBtn.disabled = true;
  resetTrialBtn.disabled = false;
  issueInput.disabled = false;
  filingBox.textContent = "尚未立案。";
  document.querySelector(".cynefin-pill").innerHTML = "";
  const optArea = document.querySelector("#optionsArea");
  if (optArea) { optArea.innerHTML = ""; optArea.hidden = true; }
  oathQuestions.innerHTML = "";
  hideTrialProgress();
  trialStage.hidden = true;
  trialStage.innerHTML = "";
  verdictBox.hidden = false;
  verdictBox.textContent = "开庭后，这里会生成完整判决书。";
  shareBox.textContent = "暂无。";
  hideCardProgress();
  renderShareImage("");
  renderLog([]);
  modePill.textContent = "待立案";
}

function renderProgress(index, percent, title) {
  trialProgress.hidden = false;
  progressIndex = Math.max(0, Math.min(index, TRIAL_STEPS.length - 1));
  progressValue = Math.max(0, Math.min(percent, 100));
  progressTitle.textContent = title || TRIAL_STEPS[progressIndex].label;
  progressPercent.textContent = `${Math.round(progressValue)}%`;
  progressFill.style.width = `${progressValue}%`;
  progressSteps.innerHTML = TRIAL_STEPS.map((step, stepIndex) => {
    const state = stepIndex < progressIndex ? "done" : (stepIndex === progressIndex ? "active" : "pending");
    return `
      <li class="${state}">
        <span>${stepIndex + 1}</span>
        <div>
          <strong>${escapeHtml(step.label)}</strong>
          <p>${escapeHtml(step.detail)}</p>
        </div>
      </li>`;
  }).join("");
}

function startTrialProgress() {
  clearInterval(progressTimer);
  progressIndex = 0;
  progressValue = 6;
  renderProgress(0, progressValue, "审判庭正在开门");
  progressTimer = setInterval(() => {
    const current = TRIAL_STEPS[progressIndex];
    const next = TRIAL_STEPS[progressIndex + 1];
    if (next && progressValue >= current.percent) {
      progressIndex += 1;
    }
    const ceiling = next ? TRIAL_STEPS[progressIndex].percent : 88;
    const speed = progressIndex >= 4 ? 1.4 : 4.5;
    progressValue = Math.min(ceiling, progressValue + speed);
    renderProgress(progressIndex, progressValue);
  }, 900);
}

function completeTrialProgress(source) {
  clearInterval(progressTimer);
  const label = source === "model" ? "DeepSeek 审判完成" : "AI 暂不可用，规则兜底";
  renderProgress(TRIAL_STEPS.length - 1, 100, label);
}

function failTrialProgress(message) {
  clearInterval(progressTimer);
  renderProgress(progressIndex, progressValue, "开庭失败");
  progressSteps.insertAdjacentHTML("beforeend", `
    <li class="failed">
      <span>!</span>
      <div>
        <strong>错误信息</strong>
        <p>${escapeHtml(message)}</p>
      </div>
    </li>`);
}

function hideTrialProgress() {
  clearInterval(progressTimer);
  trialProgress.hidden = true;
}

function renderCardProgress(index, percent, title) {
  cardProgress.hidden = false;
  cardProgressIndex = Math.max(0, Math.min(index, CARD_STEPS.length - 1));
  cardProgressValue = Math.max(0, Math.min(percent, 100));
  cardProgressTitle.textContent = title || CARD_STEPS[cardProgressIndex].label;
  cardProgressPercent.textContent = `${Math.round(cardProgressValue)}%`;
  cardProgressFill.style.width = `${cardProgressValue}%`;
  cardProgressSteps.innerHTML = CARD_STEPS.map((step, stepIndex) => {
    const state = stepIndex < cardProgressIndex ? "done" : (stepIndex === cardProgressIndex ? "active" : "pending");
    return `
      <li class="${state}">
        <span>${stepIndex + 1}</span>
        <div>
          <strong>${escapeHtml(step.label)}</strong>
          <p>${escapeHtml(step.detail)}</p>
        </div>
      </li>`;
  }).join("");
}

function hideCardProgress() {
  clearInterval(cardProgressTimer);
  cardProgress.hidden = true;
}

function startCardProgress() {
  clearInterval(cardProgressTimer);
  shareReady = false;
  renderShareImage("");
  shareBox.textContent = "正在生成信息图判决卡。";
  cardProgressIndex = 0;
  cardProgressValue = 8;
  renderCardProgress(0, cardProgressValue, "启动信息图生成");
  cardProgressTimer = setInterval(() => {
    const current = CARD_STEPS[cardProgressIndex];
    const next = CARD_STEPS[cardProgressIndex + 1];
    if (next && cardProgressValue >= current.percent) {
      cardProgressIndex += 1;
    }
    const ceiling = next ? CARD_STEPS[cardProgressIndex].percent : 92;
    cardProgressValue = Math.min(ceiling, cardProgressValue + 12);
    renderCardProgress(cardProgressIndex, cardProgressValue);
  }, 260);
}

function completeCardProgress() {
  clearInterval(cardProgressTimer);
  renderCardProgress(CARD_STEPS.length - 1, 100, "信息图判决卡已生成");
  setTimeout(() => { cardProgress.hidden = true; }, 600);
}

function stripMarkdown(text) {
  return String(text || "")
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/^#+\s*/gm, "")
    .trim();
}

function extractSection(markdown, heading) {
  const text = String(markdown || "");
  const start = text.indexOf(`## ${heading}`);
  if (start === -1) return "";
  const bodyStart = text.indexOf("\n", start);
  const next = text.indexOf("\n## ", bodyStart + 1);
  return text.slice(bodyStart + 1, next === -1 ? text.length : next).trim();
}

function renderTextBlock(text) {
  const cleaned = stripMarkdown(text);
  if (!cleaned) return "";
  return `<div class="stage-text">${escapeHtml(cleaned).replace(/\n/g, "<br>")}</div>`;
}

function defaultFutureWitness() {
  return {
    three_months: "三个月后，你最可能后悔的是低估现实摩擦，而不是低估自己的热情。",
    one_year: "一年后，如果你做了小实验，你至少会拥有证据；如果你只在脑内反复模拟，你会继续把恐惧误认为理性。",
    three_years: "三年后，最大的后悔未必是失败，而是从没让真实世界审过一次你的愿望。"
  };
}

function buildTrialStages(trial) {
  const filing = trial.filing || {};
  const oath = trial.oath_answers || "用户尚未提交完整宣誓。";
  const cynefin = trial.cynefin || {};
  const prob = trial.probability_calibration || {};
  const matrix = trial.tradeoff_matrix || {};
  const sens = trial.sensitivity_analysis || {};
  const ladder = trial.consequence_ladder || {};
  const premortem = trial.premortem || {};
  const future = trial.future_witness || defaultFutureWitness();

  const stages = [
    // === Phase 1: Cynefin + Filing ===
    {
      kind: "info",
      eyebrow: "Phase 1",
      title: "立案分类与案件档案",
      lead: "先别急着选。本庭先判断你陷入的是哪种决策困境。",
      body: `
        <div class="cynefin-badge cynefin-${escapeHtml(cynefin.decision_type || "complex")}">
          <span>${escapeHtml(cynefin.decision_type === "simple" ? "简单决策" : cynefin.decision_type === "complicated" ? "复合决策" : cynefin.decision_type === "chaotic" ? "混乱决策" : "复杂/模糊决策")}</span>
          <small>${escapeHtml(cynefin.strategy || "调查-感知-响应")}</small>
        </div>
        <p class="cynefin-explain">${escapeHtml(cynefin.explanation || "这是复杂决策——一开始你不知道哪些变量最重要，需要先调查、先试探，再形成判断。" )}</p>
        <dl class="stage-docket">
          <div><dt>案件</dt><dd>${escapeHtml(filing.case_name || trial.issue || "-")}</dd></div>
          <div><dt>原告</dt><dd>${escapeHtml(filing.plaintiff || "现在的我")}</dd></div>
          <div><dt>被告</dt><dd>${escapeHtml(filing.defendant || "-")}</dd></div>
          <div><dt>真正争议</dt><dd>${escapeHtml(filing.focus || "-")}</dd></div>
        </dl>`
    },
    // === Phase 2: Options ===
    {
      kind: "info",
      eyebrow: "Phase 2",
      title: "选项裂变：打破二元思维",
      lead: "你带着二选一进来。本庭帮你看看：你还有哪些选项没想过？",
      body: buildOptionsDisplay(trial.options || trial.options_summary || "")
    },
    // === Phase 3: Oath + Calibration ===
    {
      kind: "info",
      eyebrow: "Phase 3",
      title: "直觉宣誓与概率校准",
      lead: "贝叶斯分析师出庭：你的信心有多少是证据，多少是直觉？",
      body: `
        <div class="stage-quote"><strong>你的宣誓</strong><p>${escapeHtml(oath)}</p></div>
        <div class="calib-box">
          <div class="calib-row"><label>基线率</label><span>${escapeHtml(prob.baseline_rate || "未校准")}</span></div>
          <div class="calib-row"><label>个人因子</label><span>${escapeHtml(prob.personal_factors || "未分析")}</span></div>
          <div class="calib-row"><label>校准估计</label><span>${escapeHtml(prob.calibrated_estimate || "待确认")}</span></div>
          <div class="calib-row"><label>沉没成本</label><span>${escapeHtml(prob.sunk_cost_check || "未检查")}</span></div>
        </div>`
    },
    // === Phase 4: Tradeoff Matrix + Sensitivity ===
    {
      kind: "info",
      eyebrow: "Phase 4",
      title: "权衡矩阵与敏感性分析",
      lead: "不是在脑子里比。是把每个选项在关键维度上排开，看看你真正在乎什么。",
      body: `
        <div class="matrix-narrative">${renderTextBlock(matrix.narrative || "权衡分析见完整判决书。")}</div>
        <div class="sens-box">
          <div class="sens-row"><label>翻转变量</label><span>${escapeHtml(sens.flip_variable || "未识别")}</span></div>
          <div class="sens-row"><label>信息价值</label><span>${escapeHtml(sens.value_of_information || "待评估")}</span></div>
          <div class="sens-row"><label>最稳健选项</label><span>${escapeHtml(sens.robust_choice || "待判断")}</span></div>
        </div>`
    },
    // === Phase 5: Paradoxes + Consequence Ladder + Premortem ===
    {
      kind: "info",
      eyebrow: "Phase 5",
      title: "悖论关卡：思想实验审问",
      lead: "在极端条件下，你的判断还成立吗？",
      body: buildParadoxesHtml(trial.paradoxes || [])
    },
    {
      kind: "consequence",
      eyebrow: "Phase 5 续",
      title: "后果阶梯推演",
      lead: "系统建模师出庭：你只看到了第一步。后面还有两层连锁反应。",
      body: buildConsequenceLadder(ladder)
    },
    {
      kind: "premortem",
      eyebrow: "Phase 5 续",
      title: "预验尸事故报告",
      lead: "预验尸警官出庭：假设你选了最优路径但三年后彻底失败。死因是什么？",
      body: buildPremortemReport(premortem)
    },
    // === Cross-examination ===
    {
      kind: "cross",
      eyebrow: "Cross",
      title: "哲学与分析角色当庭交锋",
      lead: "哲学型的审你的底线，分析型的审你的证据。",
      body: buildCrossExamination(trial.cross_examination || [])
    },
    // === Phase 6: Future Witness ===
    {
      kind: "future",
      eyebrow: "Phase 6",
      title: "未来证人出庭：三种时间尺度的后悔",
      lead: "同一个选择，放到不同时间尺度里，后悔的形状会变。",
      body: `
        <div class="future-grid">
          <div><strong>三个月后</strong><p>${escapeHtml(future.three_months || defaultFutureWitness().three_months)}</p></div>
          <div><strong>一年后</strong><p>${escapeHtml(future.one_year || defaultFutureWitness().one_year)}</p></div>
          <div><strong>三年后</strong><p>${escapeHtml(future.three_years || defaultFutureWitness().three_years)}</p></div>
        </div>`
    },
    // === Verdict ===
    {
      kind: "verdict",
      eyebrow: "判决",
      title: "最终判决：进入行动程序",
      lead: "本庭不替你做决定，只判你进入一个能产生证据的行动程序。",
      body: renderTextBlock(trial.verdict || "判决书已生成。")
    },
    // === Share ===
    {
      kind: "share",
      eyebrow: "卡片",
      title: "下载可分享判决卡",
      lead: "审判结束。带走这张卡，或者展开完整判决书复盘。",
      body: ""
    }
  ];

  return stages;
}

function buildOptionsDisplay(optionsOrSummary) {
  if (!optionsOrSummary) return "<p>选项裂变未生成。</p>";
  if (typeof optionsOrSummary === "string") return renderTextBlock(optionsOrSummary);
  if (!Array.isArray(optionsOrSummary) || optionsOrSummary.length === 0) return renderTextBlock(optionsOrSummary);
  const valid = optionsOrSummary.filter(o => o);
  if (valid.length === 0) return "<p>选项裂变未生成。</p>";
  return `<ol class="options-list">${valid.map((o, i) => `<li><span class="opt-num">${i + 1}</span>${escapeHtml(o)}</li>`).join("")}</ol>`;
}

function buildParadoxesHtml(paradoxes) {
  if (!paradoxes || paradoxes.length === 0) return "<p>无悖论关卡。</p>";
  return paradoxes.map((p, i) => `
    <div class="paradox-card">
      <div class="paradox-num">关卡 ${i + 1}</div>
      <h4>${escapeHtml(p.name || "思想实验")}</h4>
      <p class="paradox-purpose">${escapeHtml(p.purpose || "")}</p>
      <div class="paradox-question">${escapeHtml(p.question || "")}</div>
      <p class="paradox-expose">${escapeHtml(p.exposes || "")}</p>
    </div>
  `).join("");
}

function buildConsequenceLadder(ladder) {
  if (!ladder) return "<p>后果推演未生成。</p>";
  const paths = [];
  if (ladder.path_a) paths.push({label: "路径A", data: ladder.path_a});
  if (ladder.path_b) paths.push({label: "路径B", data: ladder.path_b});
  if (paths.length === 0) return renderTextBlock(ladder);
  return paths.map(p => `
    <div class="ladder-path">
      <h4>${escapeHtml(p.label)}</h4>
      <div class="ladder-step"><strong>一阶（3个月内）</strong><p>${escapeHtml(p.data.stage1 || "-")}</p></div>
      <div class="ladder-step"><strong>二阶（6-12个月）</strong><p>${escapeHtml(p.data.stage2 || "-")}</p></div>
      <div class="ladder-step"><strong>三阶（1-3年）</strong><p>${escapeHtml(p.data.stage3 || "-")}</p></div>
    </div>
  `).join('<div class="stage-divider"></div>');
}

function buildPremortemReport(premortem) {
  if (!premortem) return "<p>预验尸报告未生成。</p>";
  const causes = premortem.top_causes || [];
  const prevents = premortem.preventions || [];
  const warnings = premortem.early_warnings || [];
  let html = '<div class="premortem-box">';
  html += '<h4>最可能失败原因 TOP3</h4>';
  html += '<ol>';
  for (let i = 0; i < Math.max(causes.length, 3); i++) {
    const cause = causes[i] || "-";
    const prevent = prevents[i] || "-";
    html += `<li><strong>${escapeHtml(cause)}</strong><br><span class="prevent">预防：${escapeHtml(prevent)}</span></li>`;
  }
  html += '</ol>';
  if (warnings.length > 0) {
    html += '<h4>早期预警信号</h4><ul>';
    warnings.forEach(w => { html += `<li>${escapeHtml(w)}</li>`; });
    html += '</ul>';
  }
  html += '</div>';
  return html;
}

function buildCrossExamination(cross) {
  if (!cross || cross.length === 0) return "<p>角色交锋未生成。</p>";
  return cross.map(c => {
    const badge = c.type === "analyst" ? '<span class="role-badge analyst">分析型</span>' : '<span class="role-badge philosophy">哲学型</span>';
    return `
      <div class="cross-card">
        <div class="cross-head">${badge} <strong>${escapeHtml(c.role || "出庭角色")}</strong></div>
        <p class="cross-view">${escapeHtml(c.view || "")}</p>
        <div class="cross-question">${escapeHtml(c.question || "")}</div>
      </div>`;
  }).join("");
}

function renderTrialStage(index) {
  if (!currentTrial || trialStages.length === 0) return;
  currentStageIndex = Math.max(0, Math.min(index, trialStages.length - 1));
  const stage = trialStages[currentStageIndex];
  const isFirst = currentStageIndex === 0;
  const isLast = currentStageIndex === trialStages.length - 1;
  const canOpenFullVerdict = isLast;
  const answer = stageAnswers[currentStageIndex] || "";

  trialStage.hidden = false;
  verdictBox.hidden = true;
  if (isLast && shareReady) {
    shareBox.textContent = currentTrial.share_card || "";
    renderShareImage(currentTrial.share_card_image || "");
  } else if (isLast) {
    shareBox.textContent = "点击“审判完成”后，系统会生成信息图判决卡。";
    renderShareImage("");
  } else {
    shareBox.textContent = "审判完成后解锁。";
    renderShareImage("");
  }

  trialStage.innerHTML = `
    <div class="stage-meter">
      <span>${currentStageIndex + 1} / ${trialStages.length}</span>
      <div><i style="width:${((currentStageIndex + 1) / trialStages.length) * 100}%"></i></div>
    </div>
    <p class="eyebrow">${escapeHtml(stage.eyebrow)}</p>
    <h3>${escapeHtml(stage.title)}</h3>
    <p class="stage-lead">${escapeHtml(stage.lead || "")}</p>
    ${stage.body || ""}
    ${stage.kind === "answer" ? `
      <label class="stage-answer">
        <span>你的证词</span>
        <textarea id="stageAnswerInput" rows="4" placeholder="${escapeHtml(stage.placeholder || "写下你的当庭回应。")}">${escapeHtml(answer)}</textarea>
      </label>` : ""}
    <div class="stage-actions">
      <button id="prevStageBtn" ${isFirst ? "disabled" : ""}>上一步</button>
      <button id="toggleFullVerdictBtn" ${canOpenFullVerdict ? "" : "disabled"}>完整判决书</button>
      <button id="nextStageBtn" class="primary">${isLast ? "审判完成" : (stage.kind === "answer" ? "提交证词，进入下一环节" : "进入下一环节")}</button>
    </div>`;
}

function persistStageAnswer() {
  const input = document.querySelector("#stageAnswerInput");
  if (input) stageAnswers[currentStageIndex] = input.value.trim();
}

function startInteractiveTrial(trial, startIndex = 0) {
  currentTrial = trial;
  trialStages = buildTrialStages(trial);
  currentStageIndex = startIndex;
  shareReady = false;
  hideTrialProgress();
  hideCardProgress();
  renderTrialStage(startIndex);
}

function renderFiling(filing, physicalTruth, deletionCheck) {
  if (!filing) {
    filingBox.textContent = "尚未立案。";
  document.querySelector(".cynefin-pill").innerHTML = "";
  const optArea = document.querySelector("#optionsArea");
  if (optArea) { optArea.innerHTML = ""; optArea.hidden = true; }
  document.querySelector(".physical-truth-box")?.remove();
  document.querySelector(".deletion-check-box")?.remove();
    return;
  }
  let extra = "";
  if (physicalTruth) {
    extra += `<div class="physical-truth-box"><span class="pt-label">⚡ 物理真相层</span><p>${escapeHtml(physicalTruth)}</p></div>`;
  }
  if (deletionCheck) {
    extra += `<div class="deletion-check-box"><span class="dc-label">🗑️ 删除检查</span><p>${escapeHtml(deletionCheck)}</p></div>`;
  }
  filingBox.innerHTML = `
    <dl class="filing-list">
      <div><dt>案件</dt><dd>${escapeHtml(filing.case_name || "-")}</dd></div>
      <div><dt>原告</dt><dd>${escapeHtml(filing.plaintiff || "-")}</dd></div>
      <div><dt>被告</dt><dd>${escapeHtml(filing.defendant || "-")}</dd></div>
      <div><dt>焦点</dt><dd>${escapeHtml(filing.focus || "-")}</dd></div>
      <div><dt>提醒</dt><dd>${escapeHtml(filing.reminder || "-")}</dd></div>
    </dl>
    ${extra}`;
}

function renderQuestions(questions) {
  oathQuestions.innerHTML = "";
  (questions || []).forEach((question) => {
    const li = document.createElement("li");
    li.textContent = question;
    oathQuestions.appendChild(li);
  });
}

function renderLog(log) {
  if (!log || log.length === 0) {
    logBox.textContent = "暂无。";
    return;
  }
  logBox.textContent = log.map((item) => `${item.time}  ${item.event}\n${JSON.stringify(item.data, null, 2)}`).join("\n\n");
}

function renderShareImage(url) {
  if (!url) {
    shareImageWrap.hidden = true;
    shareImage.removeAttribute("src");
    downloadSvgLink.removeAttribute("href");
    downloadPngBtn.disabled = true;
    return;
  }
  shareImageWrap.hidden = false;
  shareImage.src = url;
  downloadSvgLink.href = url;
  downloadPngBtn.disabled = false;
}

function revealShareCard() {
  if (!currentTrial) return;
  shareReady = true;
  completeCardProgress();
  shareBox.textContent = currentTrial.share_card || "";
  renderShareImage(currentTrial.share_card_image || "");
  // Re-render the last stage to update the share card display
  if (trialStages.length > 0) {
    renderTrialStage(trialStages.length - 1);
  }
}

function generateShareCardAfterVerdict() {
  if (!currentTrial) return;
  startCardProgress();
  window.setTimeout(revealShareCard, 1250);
}

function renderState(data) {
  if (!data || !data.started) {
    resetLocalUi();
    return;
  }
  const state = data.state || {};
  currentIssue = state.issue || currentIssue;
  if (currentIssue && !issueInput.value.trim()) issueInput.value = currentIssue;
  renderFiling(state.filing || state.trial?.filing, state.physical_truth || state.trial?.physical_truth, state.deletion_check || state.trial?.deletion_check);
  if (state.cynefin) renderCynefinBadge(state.cynefin);
  if (state.options && state.options.length > 0) renderOptionsBox(state.options);
  if (state.cynefin) {
    renderCynefinBadge(state.cynefin);
  }
  if (state.options && state.options.length > 0) {
    renderOptionsBox(state.options);
  }
  renderQuestions(state.preview?.oath_questions || state.trial?.oath_questions || []);
  if (state.trial) {
    state.trial.share_card_image = data.share_card_image || state.trial.share_card_image || "";
    verdictBox.textContent = state.trial.verdict || data.verdict || "";
    startInteractiveTrial(state.trial, 0);
  } else {
    trialStage.hidden = true;
    verdictBox.hidden = false;
    verdictBox.textContent = data.verdict || "开庭后，这里会生成完整判决书。";
    shareBox.textContent = "暂无。";
    renderShareImage("");
  }
  oathInput.disabled = !currentIssue;
  runTrialBtn.disabled = !currentIssue;
  modePill.textContent = state.status === "verdict" ? "判决已生成" : "案件已立案";
  renderLog(data.log || []);
}

function renderCynefinBadge(cynefin) {
  if (!cynefin) return;
  const label = cynefin.decision_type === "simple" ? "简单决策" :
                cynefin.decision_type === "complicated" ? "复合决策" :
                cynefin.decision_type === "chaotic" ? "混乱决策" : "复杂/模糊决策";
  const badge = document.querySelector(".cynefin-pill");
  if (!badge) return;
  badge.innerHTML = `<span class="cynefin-badge cynefin-${escapeHtml(cynefin.decision_type || "complex")}">
    ${escapeHtml(label)} · ${escapeHtml(cynefin.strategy || "")}
  </span>`;
}

function renderOptionsBox(options) {
  if (!options || options.length === 0) return;
  const box = document.querySelector("#optionsArea");
  if (!box) return;
  const valid = options.filter(o => o);
  box.innerHTML = `<ol class="options-list">${valid.map((o, i) =>
    `<li><span class="opt-num">${i + 1}</span>${escapeHtml(o)}</li>`
  ).join("")}</ol>`;
  box.hidden = false;
}

async function fileCase() {
  const issue = issueInput.value.trim();
  if (!issue) return;
  setBusy(true, "正在立案");
  try {
    const data = await api("/api/trial/start", { issue });
    currentIssue = issue;
    renderFiling(data.preview.filing, data.preview.physical_truth, data.preview.deletion_check);
    if (data.preview.cynefin) renderCynefinBadge(data.preview.cynefin);
    if (data.preview.options && data.preview.options.length > 0) renderOptionsBox(data.preview.options);
    renderQuestions(data.preview.oath_questions);
    oathInput.disabled = false;
    oathInput.value = "";
    runTrialBtn.disabled = false;
    currentTrial = null;
    trialStages = [];
    shareReady = false;
    clearStageAnswers();
    hideTrialProgress();
    trialStage.hidden = true;
    verdictBox.hidden = false;
    verdictBox.textContent = "案件已立案。填写直觉宣誓后点击“开庭审判”。";
    shareBox.textContent = "等待判决。";
    renderShareImage("");
    modePill.textContent = "案件已立案";
    await getState();
  } catch (error) {
    verdictBox.textContent = `立案失败：${error.message}`;
  } finally {
    setBusy(false);
  }
}

async function runTrial() {
  const issue = issueInput.value.trim() || currentIssue;
  if (!issue) return;
  setBusy(true, "正在开庭");
  startTrialProgress();
  verdictBox.textContent = "开庭中。判决书生成后会自动显示在这里。";
  try {
    const data = await api("/api/trial/run", { issue, oath_answers: oathInput.value.trim() });
    const trial = data.trial || {};
    completeTrialProgress(trial.source);
    trial.share_card_image = trial.share_card_image || data.state?.trial?.share_card_image || "";
    renderFiling(trial.filing, trial.physical_truth, trial.deletion_check);
    renderQuestions(trial.oath_questions);
    verdictBox.textContent = trial.verdict || "没有生成判决书。";
    shareReady = false;
    startInteractiveTrial(trial, 0);
    modePill.textContent = trial.source === "model" ? "DeepSeek 审判完成" : "规则兜底完成";
    const stateResponse = await fetch("/api/state");
    const stateData = await stateResponse.json().catch(() => ({}));
    renderLog(stateData.log || []);
  } catch (error) {
    failTrialProgress(error.message);
    verdictBox.textContent = `开庭失败：${error.message}`;
  } finally {
    setBusy(false);
  }
}

async function resetTrial() {
  setBusy(true, "正在清空");
  try {
    await api("/api/trial/reset", {});
    resetLocalUi();
  } catch (error) {
    verdictBox.hidden = false;
    verdictBox.textContent = `清空失败：${error.message}`;
  } finally {
    if (!currentIssue) {
      issueInput.disabled = false;
      fileCaseBtn.disabled = false;
      runTrialBtn.disabled = true;
      resetTrialBtn.disabled = false;
      modePill.textContent = "待立案";
    } else {
      setBusy(false);
    }
  }
}

async function downloadPngFromSvg() {
  const svgUrl = shareImage.getAttribute("src");
  if (!svgUrl) return;
  downloadPngBtn.disabled = true;
  try {
    const response = await fetch(svgUrl, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const svgText = await response.text();
    const blob = new Blob([svgText], { type: "image/svg+xml;charset=utf-8" });
    const objectUrl = URL.createObjectURL(blob);
    const image = new Image();
    const loaded = new Promise((resolve, reject) => {
      image.onload = resolve;
      image.onerror = () => reject(new Error("SVG 渲染失败"));
    });
    image.src = objectUrl;
    await loaded;
    const canvas = document.createElement("canvas");
    canvas.width = 1080;
    canvas.height = 1440;
    const context = canvas.getContext("2d");
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    URL.revokeObjectURL(objectUrl);
    const pngBlob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png", 0.96));
    if (!pngBlob) throw new Error("PNG 生成失败");
    const pngUrl = URL.createObjectURL(pngBlob);
    const link = document.createElement("a");
    link.href = pngUrl;
    link.download = "人生悖论审判庭-判决卡.png";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(pngUrl), 1200);
  } catch (error) {
    shareBox.textContent = `PNG 下载失败：${error.message}`;
  } finally {
    downloadPngBtn.disabled = !shareImage.getAttribute("src");
  }
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

fileCaseBtn.addEventListener("click", fileCase);
runTrialBtn.addEventListener("click", runTrial);
resetTrialBtn.addEventListener("click", resetTrial);
downloadPngBtn.addEventListener("click", downloadPngFromSvg);

trialStage.addEventListener("input", (event) => {
  if (event.target.id === "stageAnswerInput") {
    stageAnswers[currentStageIndex] = event.target.value;
  }
});

trialStage.addEventListener("click", (event) => {
  const target = event.target.closest("button");
  if (!target || !currentTrial) return;
  persistStageAnswer();
  if (target.id === "prevStageBtn") {
    renderTrialStage(currentStageIndex - 1);
  }
  if (target.id === "nextStageBtn") {
    if (currentStageIndex >= trialStages.length - 1) {
      verdictBox.hidden = false;
      verdictBox.textContent = currentTrial.verdict || "";
      modePill.textContent = "审判完成";
      generateShareCardAfterVerdict();
      return;
    }
    renderTrialStage(currentStageIndex + 1);
  }
  if (target.id === "toggleFullVerdictBtn" && currentStageIndex >= trialStages.length - 1) {
    verdictBox.hidden = !verdictBox.hidden;
    verdictBox.textContent = currentTrial.verdict || "";
  }
});

demoButtons.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  issueInput.value = button.dataset.issue;
  issueInput.focus();
});

getState().catch(() => {});
