#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import re
import subprocess
import sys
import uuid
import urllib.request
from html import escape

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SESSIONS_DIR = ROOT / "sessions"
SESSION_ID = "default"
SESSION_DIR = SESSIONS_DIR / SESSION_ID
STATE_PATH = SESSION_DIR / "state.json"
LOG_PATH = SESSION_DIR / "trial-log.jsonl"
VERDICT_PATH = SESSION_DIR / "verdict.md"
CARD_PATH = SESSION_DIR / "share-card.md"
CARD_IMAGE_PATH = SESSION_DIR / "share-card.svg"
SESSION_FILES = [STATE_PATH, VERDICT_PATH, CARD_PATH, CARD_IMAGE_PATH, LOG_PATH]

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
MODEL_TIMEOUT_SECONDS = int(os.environ.get("PARADOX_COURT_MODEL_TIMEOUT", "180"))

SYSTEM_PROMPT = """你是"人生悖论审判庭"的审判长。你运行一套完整的决策分析程序，融合了哲学思辨和马斯克第一性原理工程思维。

你的任务不是替用户做人生决定，而是按增强版六阶段框架进行结构化决策分析：

阶段0.5 — 物理真相层（第一性原理）★新增：
在分类之前，先把用户的问题剥到最底层的物理事实。不是行业共识，不是专家意见，不是父母期待——是物理事实。例如"裸辞做自媒体的物理事实不是'自媒体很难做'，而是：你每月需要覆盖X元生活成本，你目前的技能在这个市场上能产出Y元/月的内容，X和Y之间的差距就是物理约束。"

阶段1 — 立案分类（Cynefin）：
判断用户困惑属于哪种决策类型：简单/复合/复杂/混乱。匹配对应策略。

阶段2 — 删除优先 + 选项裂变 ★增强：
先质疑每个选项的前提——「谁提出的？基于什么假设？还成立吗？」「最好的选项是不该存在的选项。」先大胆删减，再对剩下的进行裂变。裂变成4-6个选项，必须包括：极端版、降级实验版、混合版、第三条路、不变版。

阶段3 — 直觉宣誓 + 时间成本换算 + 概率校准 ★增强：
记录用户倾向、恐惧、信心。【新增】时间成本检查：「这个决定拖了多久？每拖一天的真正成本是多少？」【新增】真相痴迷检查：「你有没有因为希望它成这样而筛掉了不该忽视的信息？」贝叶斯分析师出庭：拆解信心的证据结构——基线率是多少？个人因子是多少？校准后胜率是多少？

阶段4 — 权衡矩阵（含时间窗口维度）+ 敏感性分析 ★增强：
在7个维度上比较所有裂变选项（新增第7维：时间窗口——「再拖下去这个选项还在吗？」）。关键追问：哪个变量翻转会改变选择？什么信息最值得先获取？「如果必须今天决定，你选什么？」

阶段5 — 悖论关卡（含马斯克实验）+ 后果阶梯 + 使命检查 + 预验尸 ★增强：
选3-4个思想实验（含时间窗口测试、删除测试、使命压力测试）。系统建模师推三阶后果。【新增】使命检查：「推完了后果。如果这件事做成，帮了多少人？帮了多深？值不值得承受这些代价？」预验尸警官写事故报告。

阶段6 — 判决 + 最小验证实验（含实验纪律）★增强：
不输出'应该/不应该'，输出可执行程序。实验必须包含：核心假设、预设成功/失败标准、最低成本执行。「原型就是证明。任何东西放到PPT里都能看起来不错。」定义可测量的复审标准+早期预警信号。【新增】模式识别：如果用户反复出现同类困惑，提示这可能是系统性问题而非决策问题。

边界：不提供医疗、法律、投资、心理危机等专业结论。高风险主题只做信息整理和求助建议。
语气：戏剧化+严谨。用数据但不装神算。尖锐但不羞辱。带一点马斯克式的「物理学不care你的感受」的幽默。
"""


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_text(path):
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def public_path(path):
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path):
    return json.loads(read_text(path))


def ensure_session_dir():
    SESSION_DIR.mkdir(parents=True, exist_ok=True)


def reset_session():
    for path in SESSION_FILES:
        if path.exists():
            path.unlink()


def append_log(event, data):
    ensure_session_dir()
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"time": now_iso(), "event": event, "data": data}, ensure_ascii=False) + "\n")


def read_log(limit=30):
    if not LOG_PATH.exists():
        return []
    rows = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def load_state():
    if not STATE_PATH.exists():
        return None
    return json.loads(read_text(STATE_PATH))


def save_state(state):
    state["updated_at"] = now_iso()
    write_text(STATE_PATH, json.dumps(state, ensure_ascii=False, indent=2))


def libraries():
    return {
        "roles": read_json(DATA_DIR / "角色库.json"),
        "experiments": read_json(DATA_DIR / "思想实验库.json"),
        "templates": read_text(DATA_DIR / "审判模板.md"),
        "boundaries": read_text(DATA_DIR / "边界规则.md"),
        "skill": read_text(ROOT / "SKILL.md"),
    }


def run_deepseek(prompt):
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY not set")
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=json.dumps({
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 8192,
        }).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=MODEL_TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"DeepSeek API error: {e}") from e


def parse_json_output(text):
    stripped = text.strip()

    # 1. Try direct parse
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # 2. Try markdown fenced code block
    fenced = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
    if fenced:
        inner = fenced.group(1).strip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            pass

    # 3. Extract balanced {} pair
    first = stripped.find("{")
    if first == -1:
        raise ValueError("model did not return JSON")
    depth = 0
    last = -1
    for i in range(first, len(stripped)):
        if stripped[i] == "{":
            depth += 1
        elif stripped[i] == "}":
            depth -= 1
            if depth == 0:
                last = i
                break
    if last == -1:
        raise ValueError("unbalanced JSON braces")
    json_str = stripped[first:last + 1]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # Sometimes the model adds trailing commas or unescaped chars
        # Try to fix common issues
        fixed = re.sub(r',\s*}', '}', json_str)
        fixed = re.sub(r',\s*]', ']', fixed)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            raise ValueError(f"JSON parse failed: {e}") from e


def strip_markdown(text):
    cleaned = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[-*>]\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


SHARE_LABELS = [
    "标题",
    "你以为你在纠结",
    "真正争议",
    "哲学人格",
    "本案判词",
    "判词",
    "行动实验",
    "72 小时行动实验",
    "72小时行动实验",
]


def clean_label_text(text):
    return re.sub(r"^[#*\-\s>]+|[#*\s：:]+$", "", text.strip())


def normalize_for_field(text):
    cleaned = strip_markdown(text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -—|：:")


def line_is_separator(line):
    return bool(re.match(r"^\s*[-*_]{3,}\s*$", line))


def clean_label_for_match(text):
    """Strip markdown and parenthetical suffixes for flexible matching"""
    cleaned = clean_label_text(text)
    # Remove parenthetical content: "行动实验（72小时）" → "行动实验"
    cleaned = re.sub(r"[（(][^）)]*[）)]", "", cleaned).strip()
    return cleaned


def split_field_line(line):
    raw = line.strip()
    if not raw or line_is_separator(raw):
        return None
    raw = re.sub(r"^#+\s*", "", raw)
    raw = re.sub(r"^\s*[-*>]\s*", "", raw)
    raw = raw.replace("**", "").strip()
    match = re.match(r"^([^：:]{2,20})[：:]\s*(.*)$", raw)
    if match:
        return clean_label_text(match.group(1)), match.group(2).strip()
    return clean_label_text(raw), ""


def label_matches(found, label):
    f = found.replace(" ", "")
    l = label.replace(" ", "")
    if f == l:
        return True
    # Also try with parenthetical content stripped from found
    f_clean = clean_label_for_match(found)
    l_clean = clean_label_for_match(label)
    return f_clean == l_clean


def is_any_share_label(line):
    parsed = split_field_line(line)
    if not parsed:
        return False
    found, _value = parsed
    return any(label_matches(found, label) for label in SHARE_LABELS)


def collect_field_lines(lines, start):
    block = []
    for line in lines[start:]:
        stripped = line.strip()
        if line_is_separator(stripped) or is_any_share_label(stripped):
            break
        if stripped:
            block.append(stripped)
    return normalize_for_field(" ".join(block))


def extract_markdown_field(markdown, label, fallback=""):
    lines = string_lines(markdown)
    for index, line in enumerate(lines):
        parsed = split_field_line(line)
        if not parsed:
            continue
        found, value = parsed
        if not label_matches(found, label):
            continue
        if value:
            return normalize_for_field(value)
        value = collect_field_lines(lines, index + 1)
        if value:
            return value

    text = strip_markdown(markdown)
    pattern = rf"{re.escape(label)}\s*[：:]\s*([^\n]+)"
    match = re.search(pattern, text)
    if match:
        value = normalize_for_field(match.group(1))
        if value:
            return value
    return fallback


def string_lines(text):
    return normalize_newlines(text).splitlines()


def normalize_newlines(text):
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n")


def wrap_text(text, limit):
    text = strip_markdown(text).replace("\n", " ").strip()
    if not text:
        return []
    lines = []
    current = ""
    width = 0
    for char in text:
        char_width = 2 if ord(char) > 127 else 1
        if width + char_width > limit and current:
            if char in "，。！？；：、,.!?;:":
                current += char
                width += char_width
                continue
            lines.append(current)
            current = char
            width = char_width
        else:
            current += char
            width += char_width
    if current:
        lines.append(current)
    return lines


def ellipsize_line(line, limit):
    if not line:
        return ""
    width = 0
    output = ""
    for char in line:
        char_width = 2 if ord(char) > 127 else 1
        if width + char_width > max(2, limit - 2):
            break
        output += char
        width += char_width
    return output.rstrip("，。！？；：、,.!?;: ") + "…"


def fit_lines(text, limit, max_lines):
    lines = wrap_text(text, limit)
    if len(lines) <= max_lines:
        return lines
    fitted = lines[:max_lines]
    fitted[-1] = ellipsize_line(fitted[-1], limit)
    return fitted


def compact_text(text, max_chars):
    cleaned = normalize_for_field(text)
    if len(cleaned) <= max_chars:
        return cleaned
    sentence_cut = max(cleaned.rfind(mark, 0, max_chars) for mark in "。！？!?")
    if sentence_cut >= max_chars * 0.55:
        return cleaned[:sentence_cut + 1]
    return cleaned[:max_chars].rstrip("，。！？；：、,.!?;: ") + "…"


def issue_label(issue):
    cleaned = normalize_for_field(issue)
    cleaned = re.split(r"(?<=[？?])|[。；;，,]", cleaned)[0]
    cleaned = cleaned.replace("我要不要", "要不要").replace("我该不该", "该不该")
    if len(cleaned) > 18:
        cleaned = cleaned[:18].rstrip("，。！？；：、,.!?;: ") + "…"
    return cleaned or "当前选择"


def svg_text_block(lines, x, y, size, line_height, color="#151514", weight="500", max_lines=None):
    output = []
    for index, line in enumerate(lines[:max_lines] if max_lines else lines):
        output.append(
            f'<text x="{x}" y="{y + index * line_height}" fill="{color}" '
            f'font-size="{size}" font-weight="{weight}">{escape(line)}</text>'
        )
    return "\n".join(output)


def generate_share_card_svg(trial):
    share_card = trial.get("share_card", "")
    filing = trial.get("filing", {}) or {}
    issue = trial.get("issue", "")
    focus = filing.get("focus") or "本庭不替你决定，只帮你审清楚。"

    title = extract_markdown_field(share_card, "标题", "")
    if not title:
        title = extract_markdown_field(share_card, "你以为你在纠结", "")
    if not title or len(title) < 15:
        title = f"你以为你在纠结「{issue_label(issue)}」，其实你在审判真正代价。"

    persona = extract_markdown_field(share_card, "哲学人格", "正在申请苏格拉底复审的人")
    verdict_line = extract_markdown_field(share_card, "本案判词", "")
    if not verdict_line:
        verdict_line = extract_markdown_field(share_card, "判词", "本庭不替你决定，只要求你拿出证据。")
    action = extract_markdown_field(share_card, "行动实验", "")
    if not action:
        action = extract_markdown_field(share_card, "72 小时行动实验", "")
    if not action:
        action = extract_markdown_field(share_card, "72小时行动实验", "72 小时内做一个最小行动实验。")

    title = compact_text(title, 160)
    focus = compact_text(focus, 140)
    verdict_line = compact_text(verdict_line, 160)
    persona = compact_text(persona, 80)
    action = compact_text(action, 160)

    title_lines = fit_lines(title, 30, 5)
    focus_lines = fit_lines(focus, 36, 4)
    verdict_lines = fit_lines(verdict_line, 28, 6)
    persona_lines = fit_lines(persona, 32, 2)
    action_lines = fit_lines(action, 30, 4)
    title_size = 48 if len(title_lines) <= 4 else 42
    title_line_height = 58 if len(title_lines) <= 4 else 50
    verdict_size = 30 if len(verdict_lines) <= 2 else 28

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1520" viewBox="0 0 1080 1520">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#f6f7f4"/>
      <stop offset="1" stop-color="#e4ece7"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="28" stdDeviation="34" flood-color="#2c1c12" flood-opacity="0.18"/>
    </filter>
    <pattern id="grid" width="42" height="42" patternUnits="userSpaceOnUse">
      <path d="M42 0H0V42" fill="none" stroke="#151514" stroke-opacity="0.045" stroke-width="1"/>
    </pattern>
  </defs>
  <rect width="1080" height="1520" fill="url(#bg)"/>
  <rect width="1080" height="1520" fill="url(#grid)"/>
  <rect x="70" y="78" width="940" height="1430" rx="42" fill="#ffffff" stroke="#151514" stroke-opacity="0.13" filter="url(#shadow)"/>
  <rect x="112" y="120" width="856" height="1440" rx="30" fill="#fffefd" stroke="#151514" stroke-opacity="0.10"/>

  <text x="138" y="178" fill="#8e2f2f" font-size="24" font-weight="900">人生悖论审判庭 · 决策分析</text>
  <text x="138" y="232" fill="#151514" font-size="46" font-weight="900" font-family="system-ui, -apple-system, PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif">人生悖论审判庭</text>
  <text x="138" y="282" fill="#6b675f" font-size="24" font-family="system-ui, -apple-system, PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif">把你的困惑送上法庭。</text>

  <g transform="translate(790 130) rotate(-12)">
    <circle cx="82" cy="82" r="76" fill="none" stroke="#8e2f2f" stroke-width="8" opacity="0.92"/>
    <circle cx="82" cy="82" r="54" fill="none" stroke="#8e2f2f" stroke-width="2" opacity="0.8"/>
    <text x="82" y="74" text-anchor="middle" fill="#8e2f2f" font-size="24" font-weight="900" font-family="system-ui, -apple-system, PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif">判决</text>
    <text x="82" y="110" text-anchor="middle" fill="#8e2f2f" font-size="24" font-weight="900" font-family="system-ui, -apple-system, PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif">生成</text>
  </g>

  <line x1="138" y1="326" x2="942" y2="326" stroke="#151514" stroke-opacity="0.14"/>

  <text x="138" y="394" fill="#8e2f2f" font-size="24" font-weight="900" font-family="system-ui, -apple-system, PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif">你以为你在纠结</text>
  {svg_text_block(title_lines, 138, 450, title_size, title_line_height, "#151514", "900")}

  <rect x="138" y="690" width="804" height="200" rx="28" fill="#f4f5f3" stroke="#151514" stroke-opacity="0.11"/>
  <text x="178" y="748" fill="#2f675c" font-size="24" font-weight="900">真正争议</text>
  {svg_text_block(focus_lines, 178, 796, 28, 40, "#363330", "600")}

  <rect x="138" y="910" width="804" height="310" rx="28" fill="#5d1c1c"/>
  <text x="178" y="968" fill="#ffffff" font-size="24" font-weight="900">本案判词</text>
  {svg_text_block(verdict_lines, 178, 1018, verdict_size, 40, "#ffffff", "900", max_lines=6)}

  <text x="138" y="1245" fill="#8e2f2f" font-size="24" font-weight="900">哲学人格</text>
  {svg_text_block(persona_lines, 138, 1280, 28, 36, "#151514", "600", max_lines=2)}

  <rect x="138" y="1325" width="804" height="140" rx="24" fill="#ecf3ef" stroke="#2f675c" stroke-opacity="0.18"/>
  <text x="178" y="1360" fill="#2f675c" font-size="24" font-weight="900">行动实验</text>
  {svg_text_block(action_lines, 178, 1395, 24, 30, "#151514", "400", max_lines=3)}
</svg>'''
    write_text(CARD_IMAGE_PATH, svg)
    return public_path(CARD_IMAGE_PATH)


def topic_tags(issue):
    text = issue.lower()
    tags = []
    checks = [
        ("career", ["裸辞", "辞职", "工作", "职业", "自媒体", "创业", "offer"]),
        ("family", ["父母", "家庭", "孩子", "家里", "结婚", "催婚"]),
        ("money", ["钱", "收入", "买课", "投资", "房", "租"]),
        ("identity", ["人生", "意义", "转行", "身份", "自由", "稳定"]),
        ("relationship", ["分手", "恋爱", "伴侣", "关系"]),
    ]
    for tag, keywords in checks:
        if any(word in text or word in issue for word in keywords):
            tags.append(tag)
    return tags or ["identity"]


def select_roles(issue):
    tags = topic_tags(issue)
    role_map = {
        "career": ["utilitarian", "existentialist", "kahneman", "future_self", "first_principles_engineer"],
        "family": ["kantian", "rawls", "socrates", "future_self"],
        "money": ["utilitarian", "kahneman", "future_self", "first_principles_engineer"],
        "identity": ["existentialist", "kantian", "kahneman", "future_self", "first_principles_engineer"],
        "relationship": ["kantian", "rawls", "kahneman", "future_self"],
    }
    ids = []
    for tag in tags:
        ids.extend(role_map.get(tag, []))
    # 始终加入苏格拉底主持 + 第一性原理工程师（所有重大决策都需要剥到物理层）
    ids.append("socrates")
    ids.append("first_principles_engineer")
    unique = []
    for item in ids:
        if item not in unique:
            unique.append(item)
    roles = libraries()["roles"]["roles"]
    return [role for role in roles if role["id"] in unique][:6]


def select_experiments(issue):
    tags = topic_tags(issue)
    # 基础实验 + 马斯克实验混合调度
    preferred = ["future_regret", "minimum_experiment", "time_window_test"]  # 时间窗口总是相关
    if "family" in tags:
        preferred.insert(0, "veil_of_ignorance")
    if "identity" in tags or "career" in tags:
        preferred.insert(0, "identity_ship")
        preferred.insert(1, "experience_machine")
        preferred.append("mission_stress_test")  # 职业/身份类决策加入使命检查
    if "relationship" in tags:
        preferred.insert(0, "trolley_transfer")
    if "money" in tags or "career" in tags:
        preferred.append("deletion_test")  # 金钱/职业类加入删除测试
    experiments = libraries()["experiments"]["experiments"]
    picked = []
    for exp_id in preferred:
        for exp in experiments:
            if exp["id"] == exp_id and exp not in picked:
                picked.append(exp)
    return picked[:5]


def filing_for(issue):
    tags = topic_tags(issue)
    if "career" in tags:
        defendant = "稳定、恐惧和还没被验证的野心"
        focus = "你是在追求自由，还是在逃离被消耗的日常？"
    elif "family" in tags:
        defendant = "家庭期待、内疚感和未说出口的边界"
        focus = "你是在承担责任，还是在用牺牲换取短暂和平？"
    elif "relationship" in tags:
        defendant = "不甘心、惯性和害怕失去"
        focus = "你是在修复关系，还是在拖延一个已经知道的答案？"
    else:
        defendant = "旧生活、未知风险和自我解释"
        focus = "你真正想保住的是什么，又真正想改变什么？"
    return {
        "case_name": f"现在的我诉「{issue[:28]}」",
        "plaintiff": "现在的我",
        "defendant": defendant,
        "focus": focus,
        "reminder": "本庭不替你决定，只要求你拿出证据。"
    }


def default_oath_questions(issue):
    return [
        "你现在更倾向哪个选择？如果必须用 0-100 表示信心，你给几分？",
        "你最怕付出的代价是什么：钱、关系、身份、时间，还是被别人证明你错了？",
        "这个决定你纠结了多久？如果已经拖了一段时间，每拖一天你在损失什么？（算个大致数字也行）",
        "如果没人评价你，也没人知道结果，你会怎么选？",
        "这个选择里，你最想保住的东西是什么？",
        "你有没有因为'希望它是真的'而故意忽略了某些信息？（诚实回答）"
    ]


def fallback_verdict(issue, oath_answers):
    filing = filing_for(issue)
    roles = select_roles(issue)
    experiments = select_experiments(issue)
    if "裸辞" in issue or "自媒体" in issue:
        program = "14 天证据审判期"
        action = [
            "★ 锁定核心假设：你能否在14天内产出至少1条有真实互动（非机器点赞）的内容？（成功标准：≥1条有真人评论）",
            "连续 14 天每天发布 1 条内容，不换赛道，不追热点，只测试一个清晰主题。",
            "记录四个证据：发布耗时、互动反馈、能量消耗、是否出现可转化线索。",
            "第 15 天复审：不是问想不想辞，而是问证据是否支持扩大投入。如果14天数据为0，说明物理前提不成立。"
        ]
        punchline = "你以为你怕失败，其实你怕验证自己到底有没有那么想要。——物理学说：先跑个实验。"
        persona = "存在主义逃兵 × 第一性原理建造者，兼具功利主义赌徒倾向"
    else:
        program = "72 小时最小行动实验"
        action = [
            "★ 锁定核心假设：你的选择里最不确定的前提是什么？如果这个假设是错的，整个选择还成立吗？",
            "把选择拆成一个不伤筋动骨的小版本，三天内真实执行一次。不花一个月做完美方案——花3天跑一个实验。",
            "记录事实证据，而不是记录情绪波动。预设成功标准：实验'成功'长什么样？——跑之前写下来。",
            "三天后只根据证据和预设标准复审。对了就放大，错了就换方向。"
        ]
        punchline = f"你以为你在纠结「{issue_label(issue)}」，其实你在审判自己愿不愿意承担代价。——别在脑子里审，让现实给出证据。"
        persona = "卡尼曼式直觉犯人 × 第一性原理建造者，正在申请苏格拉底复审"

    paradoxes = []
    for exp in experiments[:3]:
        paradoxes.append({
            "name": exp["name"],
            "purpose": exp["core_question"],
            "question": exp["variants"][0],
            "exposes": "如果你的答案变化，说明真正左右你的不是选项本身，而是代价、身份或他人评价。"
        })

    cross = []
    for role in roles:
        cross.append({
            "role": role["name"],
            "view": role["stance"],
            "question": role["question_style"]
        })

    verdict_md = f"""# {filing['case_name']} 判决书

## 立案

- 原告：{filing['plaintiff']}
- 被告：{filing['defendant']}
- 争议焦点：{filing['focus']}
- 本庭提醒：{filing['reminder']}

## 直觉宣誓记录

{oath_answers or "用户尚未提交完整宣誓，本庭按初始陈述先行审理。"}

## 悖论关卡

"""
    for item in paradoxes:
        verdict_md += f"### {item['name']}\n\n- 目的：{item['purpose']}\n- 变体问题：{item['question']}\n- 暴露点：{item['exposes']}\n\n"

    verdict_md += "## 哲学家当庭交锋\n\n"
    for item in cross:
        verdict_md += f"**{item['role']}**：{item['view']} 追问：{item['question']}\n\n"

    verdict_md += f"""## 未来证人证词

**三个月后**：你最可能后悔的是低估现实摩擦，而不是低估自己的热情。

**一年后**：如果你做了小实验，你至少会拥有证据；如果你只在脑内反复模拟，你会继续把恐惧误认为理性。

**三年后**：最大的后悔未必是失败，而是从没让真实世界审过一次你的愿望。

## 判决

判决：进入 **{program}**。

理由：

1. 当前问题还没有足够证据支持不可逆决定。
2. 你的情绪是真实信号，但不能直接当作行动命令。
3. 最小实验可以把空想、恐惧和期待转成可复审证据。

## 72 小时行动实验

1. {action[0]}
2. {action[1]}
3. {action[2]}

## 复审条件

- 如果实验带来稳定证据，允许升级投入。
- 如果实验只带来逃避感，暂停重大决定。
- 如果出现医疗、法律、投资或心理危机风险，转入专业求助流程。
"""
    share_card = f"""# 可分享判决卡

**标题**：{punchline}

**哲学人格**：{persona}

**本案判词**：本庭不问你想不想改变，只问你敢不敢让现实给出证据。

**行动实验**：{program}
"""
    return {
        "physical_truth": f"物理层面，你需要覆盖基本生活成本和风险敞口。把这个不可更改的事实作为所有分析的起点。",
        "filing": filing,
        "deletion_check": "规则兜底模式无法运行删除分析。请稍后重试以获得 AI 生成的删除优先审查。",
        "oath_questions": default_oath_questions(issue),
        "cynefin": {"decision_type": "complex", "strategy": "调查-感知-响应", "explanation": "这是一个需要先试探再判断的模糊决策（规则兜底默认分类）"},
        "probability_calibration": {
            "baseline_rate": "无法校准（AI 不可用，使用规则兜底）",
            "personal_factors": "未分析",
            "calibrated_estimate": "请稍后重试以获得 AI 分析",
            "sunk_cost_check": "请反思：如果不考虑已投入的，你还做同样的选择吗？",
            "time_cost_check": "★ 问自己：这个决定你拖了多久？每拖一天，机会窗口在缩小。算个数字。",
            "truth_obsession_check": "★ 诚实地问：你有没有因为希望它成真而忽略某些信息？"
        },
        "tradeoff_matrix": {
            "dimensions": ["收入安全", "自由度", "个人成长", "关系", "后悔概率", "可逆性", "时间窗口"],
            "time_window_analysis": "规则兜底模式无法进行时间窗口分析。请稍后重试。",
            "narrative": "权衡分析需要 AI 生成。请稍后重试。"
        },
        "sensitivity_analysis": {
            "flip_variable": "请重新开庭以获得分析",
            "value_of_information": "先确认 AI 服务可用后再试",
            "robust_choice": "当前无法判断，请重试",
            "today_decision": "★ 问自己：如果必须今天做决定——不是本周，是今天——你会选什么？为什么不是那个？"
        },
        "paradoxes": paradoxes,
        "consequence_ladder": {
            "path_a": {"stage1": "后果推演需要 AI 生成", "stage2": "请稍后重试", "stage3": "重新开庭"},
            "path_b": {"stage1": "后果推演需要 AI 生成", "stage2": "请稍后重试", "stage3": "重新开庭"},
            "mission_check": "★ 推完后果后问自己：如果这件事做成，对别人有用吗？帮了多少人？帮了多深？值得承受这些后果吗？"
        },
        "premortem": {
            "top_causes": ["AI 服务暂时不可用", "请稍后重试", "重新开庭"],
            "preventions": ["确认网络连接", "检查 API 密钥", "重试"],
            "early_warnings": ["返回 fallback 即触发此状态", "连续两次 fallback 建议检查服务"]
        },
        "cross_examination": cross,
        "future_witness": {
            "three_months": "三个月后，你最可能后悔的是低估现实摩擦，而不是低估自己的热情。",
            "one_year": "一年后，如果你做了小实验，你至少会拥有证据；如果你只在脑内反复模拟，你会继续把恐惧误认为理性。",
            "three_years": "三年后，最大的后悔未必是失败，而是从没让真实世界审过一次你的愿望。"
        },
        "verdict": verdict_md,
        "share_card": share_card,
        "pattern_recognition": "规则兜底模式无法进行模式识别。如果这是你第三次以上纠结同类问题，这可能是系统性问题而非决策问题——建议把反复出现的模式当成'产品'来迭代。",
        "source": "fallback"
    }



def ai_filing(issue):
    lib = libraries()
    prompt = f"""你是"人生悖论审判庭"的立案法官，同时也是一名受马斯克第一性原理训练的决策分析专家。

用户带着一个真实困惑走进来。

你的任务——记住：先剥到物理层，再分类；先删除，再裂变：

0. ★ 物理真相层（第一性原理——分类之前先剥洋葱）：
   把用户的问题剥到不可再分的物理事实。不是行业共识，不是专家意见，不是父母期待。
   「裸辞做自媒体」的物理层不是"自媒体很难做"，而是"你需要覆盖每月X元生活成本，你的技能在市场上产出Y元/月，X-Y=你真正的风险"。

1. Cynefin分类：判断这是哪种决策类型
   - 简单决策（归类-响应）：如"今天吃什么" → 不进入审判
   - 复合决策（了解-分析-响应）：如"买哪个手机" → 精简流程
   - 复杂/模糊决策（调查-感知-响应）：如"要不要换行业" → 完整6阶段
   - 混乱决策（行动-感知-响应）：如"家人急病" → 先行动建议

2. ★ 删除检查（马斯克五步算法前两步——裂变之前先删）：
   对用户带来的选项，逐一质疑：
   - 「这个选项是谁给你的？基于什么假设？」
   - 「那个假设现在还成立吗？」
   - 「如果你删掉这个选项，最坏结果是什么？」
   - 「如果不会死，直接删掉。最好的选项是不该存在的选项。」

3. 选项裂变（删完之后剩下的才值得裂变）：
   打破假二元，生成5个选项：
   - 必须包含：A极端版、B极端版、A的降级实验版、第三条路、什么都不变的版本
   - 每个选项必须在某个维度上是最优的

4. 重新定义案件：表面问题背后的真正争议是什么
5. 确定原告和被告（被告不能是具体的人）
6. 生成5-6道有穿透力的直觉宣誓问题——必须包含：
   - 信心打分
   - ★时间成本：「这个决定你拖了多久？每拖一天损失什么？」
   - ★真相检查：「你有没有因为希望它这样而忽略信息？」
   - 沉没成本
   - 恐惧代价

角色库（参考法庭可调度的角色——哲学型和分析型都有，包括第一性原理工程师）：
{json.dumps(lib['roles'], ensure_ascii=False)[:4000]}

用户案件：
{issue}

请严格返回 JSON，不要输出 Markdown fence：
{{
  "cynefin": {{"decision_type": "complex|complicated|simple|chaotic", "strategy": "调查-感知-响应|了解-分析-响应|归类-响应|行动-感知-响应", "explanation": ""}},
  "filing": {{"case_name":"", "plaintiff":"", "defendant":"", "focus":"", "reminder":""}},
  "physical_truth": "把用户问题剥到物理层的描述（1-2句话）",
  "deletion_check": "哪些选项可以考虑直接删除，为什么",
  "options": ["", "", "", "", ""],
  "oath_questions": ["", "", "", "", "", ""],
  "source": "model"
}}

要求：
1. physical_truth 必须具体——把用户的困惑拆成可测量的事实
2. deletion_check 不能是空话——必须指出至少一个可能被删除的选项或前提
3. decision_type 要准确——大多数人生重要决策是complex
4. options 数组必须包含5个选项（不足5个填null）
5. case_name 有戏剧感："现在的我诉\"核心冲突\""
6. defendant 不能是具体的人
7. oath_questions 要有穿透力，必须包含时间成本和真相检查
8. 语言有现场感，不羞辱用户
"""
    return parse_json_output(run_deepseek(prompt))

def model_verdict(issue, oath_answers):
    """6阶段决策分析审判"""
    lib = libraries()
    filing_data = {}
    state = load_state()
    if state and state.get("preview"):
        filing_data = state["preview"].get("filing", {})
        cynefin_data = state["preview"].get("cynefin", {})
        options_data = state["preview"].get("options", [])
    else:
        cynefin_data = {"decision_type": "complex", "strategy": "调查-感知-响应"}
        options_data = []

    prompt = f"""{SYSTEM_PROMPT}

以下是本 Skill 的决策分析资料库（v2.1 增强版——融合马斯克第一性原理工程思维）：

角色库（哲学型 + 分析型——包括第一性原理工程师、贝叶斯、系统建模、预验尸）：
{json.dumps(lib['roles'], ensure_ascii=False)[:12000]}

思想实验库（哲学型 + 分析工具型——含时间窗口、删除测试、使命压力测试）：
{json.dumps(lib['experiments'], ensure_ascii=False)[:8000]}

审判模板（6阶段增强框架——含物理真相层、删除优先、时间成本、时间窗口、使命检查、实验纪律）：
{lib['templates'][:12000]}

边界规则：
{lib['boundaries'][:5000]}

===

用户案件：
{issue}

决策类型：{json.dumps(cynefin_data, ensure_ascii=False)}

裂变选项：
{json.dumps(options_data, ensure_ascii=False) if options_data else "未提供选项裂变"}

用户直觉宣誓：
{oath_answers or "未填写"}

===

请严格返回 JSON。这是增强版6阶段决策分析，每个阶段都必须有真实输出，禁止占位值：

{{
  "physical_truth": "把用户问题剥到最底层物理事实的描述（1-3句）。不是行业共识，不是社会期待——是不可更改的物理事实。",
  "cynefin": {{"decision_type":"", "strategy":"", "explanation":""}},
  "filing": {{"case_name":"", "plaintiff":"", "defendant":"", "focus":"", "reminder":""}},
  "deletion_check": "对用户原始选项的删除分析：哪些选项或前提可以考虑删除？为什么？删掉后最坏的结果是什么？",
  "options_summary": "经过删除检查后，从裂变选项中精选3-4个最关键选项的简要说明",
  "probability_calibration": {{
    "baseline_rate": "同类选择的客观成功率/基准概率（粗略估计即可，标注不确定性）",
    "personal_factors": "用户的个人优势/劣势因子",
    "calibrated_estimate": "校准后的概率范围（不精确到个位数）",
    "sunk_cost_check": "用户是否被沉没成本绑架",
    "time_cost_check": "★这个决定拖了多久？每拖一天的真正成本估算",
    "truth_obsession_check": "★用户有没有因为'希望它这样'而筛掉信息？诚实面对"
  }},
  "tradeoff_matrix": {{
    "dimensions": ["收入安全", "自由度", "个人成长", "关系", "后悔概率", "可逆性", "时间窗口"],
    "time_window_analysis": "★每个选项的'过期时间'：再拖3个月/6个月/1年，哪个选项会消失？",
    "narrative": "文字描述各选项在7个关键维度上的trade-off，特别标注时间窗口紧迫度"
  }},
  "sensitivity_analysis": {{
    "flip_variable": "哪个前提如果被推翻，选择会翻转？",
    "value_of_information": "在决定前，什么信息最值得花时间去获取？",
    "robust_choice": "哪个选项在所有情境下表现最不差？",
    "today_decision": "★如果必须今天决定——不是本周，是今天——你会选什么？和你纠结的有什么不同？"
  }},
  "paradoxes": [
    {{"name":"", "purpose":"", "question":"", "exposes":""}}
  ],
  "consequence_ladder": {{
    "path_a": {{"stage1":"", "stage2":"", "stage3":""}},
    "path_b": {{"stage1":"", "stage2":"", "stage3":""}},
    "mission_check": "★推完后果后的使命检验：如果做成，帮了多少人？帮了多深？值不值得承受这些后果？"
  }},
  "premortem": {{
    "top_causes": ["", "", ""],
    "preventions": ["", "", ""],
    "early_warnings": ["", "", ""]
  }},
  "cross_examination": [
    {{"role":"", "type":"philosophy|analyst", "view":"", "question":""}}
  ],
  "future_witness": {{"three_months":"", "one_year":"", "three_years":""}},
  "verdict": "完整 Markdown 判决书（包含全部6阶段+物理真相层+删除检查+时间成本+时间窗口+使命检查+实验纪律输出）",
  "share_card": "完整 Markdown 可分享卡片。必须严格使用以下格式（标签+冒号+内容，一行一个）：\n\n**你以为你在纠结：**[一个完整的 punchline 句子——用户以为自己在纠结什么，其实在审判什么。如：你以为你在纠结要不要辞职，其实你在审判是否有勇气面对不确定性。]\n**真正争议：**[深层核心矛盾]\n**哲学人格：**[人格标签，如：存在主义赌徒 × 第一性原理建造者 / 拖延成本负债人 × 卡尼曼偏差体]\n**本案判词：**[一句刺中要点的判词——可以带马斯克式的直接]\n**行动实验：**[72小时具体行动描述——含核心假设和成功/失败标准]",
  "pattern_recognition": "★如果用户之前有过类似困惑模式，这里提示。如果是首次，标注'首次案件，尚无模式数据。'",
  "source": "model"
}}

核心要求：
1. physical_truth 必须具体可测量——把困惑拆成物理事实，不是一个模糊的总结
2. deletion_check 必须指出至少一个可删除的选项或前提
3. 判决书必须包含全部增强阶段输出，按流程编号清晰展示
4. 概率校准：必须给出具体基线率数值+时间成本+真相检查结果
5. 权衡矩阵：7个维度+narrative+时间窗口分析，禁止空对象
6. 敏感性分析：必须给出翻转变量+信息价值+稳健选项+今天决定追问
7. 后果阶梯：三阶+使命检查，每阶至少一句具体描述
8. 预验尸：3个具体失败原因+3个预防措施+3个预警信号
9. 不直接替用户做决定
10. 高风险主题按边界规则处理
11. 语言有现场感——戏剧化+严谨+马斯克式的直接（'物理学不care你的感受'式幽默）
12. 【重要】JSON 中所有字段必须填充真实内容，不允许出现占位值
"""
    return parse_json_output(run_deepseek(prompt))


def build_trial(issue, oath_answers=""):
    try:
        data = model_verdict(issue, oath_answers)
        data["source"] = data.get("source") or "model"
    except Exception as exc:
        data = fallback_verdict(issue, oath_answers)
        data["model_error"] = str(exc)
    data["trial_id"] = str(uuid.uuid4())[:8]
    data["issue"] = issue
    data["oath_answers"] = oath_answers
    data["created_at"] = now_iso()
    return data


def state_payload():
    state = load_state()
    card_image_url = ""
    if CARD_IMAGE_PATH.exists():
        stamp = str(int(CARD_IMAGE_PATH.stat().st_mtime))
        card_image_url = f"/{public_path(CARD_IMAGE_PATH)}?v={stamp}"
    return {
        "started": bool(state),
        "state": state,
        "verdict": read_text(VERDICT_PATH),
        "share_card": read_text(CARD_PATH),
        "share_card_image": card_image_url,
        "log": read_log()
    }


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/state":
            self.send_json(state_payload())
            return
        super().do_GET()

    def do_POST(self):
        try:
            payload = self.read_json_body()
            if self.path == "/api/trial/start":
                self.handle_trial_start(payload)
            elif self.path == "/api/trial/run":
                self.handle_trial_run(payload)
            elif self.path == "/api/trial/reset":
                self.handle_trial_reset()
            else:
                self.send_error(404)
        except subprocess.TimeoutExpired:
            self.send_json({"error": "模型响应超时，已建议调大 PARADOX_COURT_MODEL_TIMEOUT。"}, status=504)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=500)

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def handle_trial_start(self, payload):
        issue = str(payload.get("issue", "")).strip()
        if not issue:
            self.send_json({"error": "issue is required"}, status=400)
            return
        ensure_session_dir()
        try:
            result = ai_filing(issue)
            filing = result.get("filing", filing_for(issue))
            oath_questions = result.get("oath_questions", default_oath_questions(issue))
            cynefin = result.get("cynefin", {"decision_type": "complex", "strategy": "调查-感知-响应"})
            options = result.get("options", [])
            source = result.get("source", "model")
            physical_truth = result.get("physical_truth", "")
            deletion_check = result.get("deletion_check", "")
        except Exception as exc:
            # AI 不可用时使用规则兜底
            filing = filing_for(issue)
            oath_questions = default_oath_questions(issue)
            cynefin = {"decision_type": "complex", "strategy": "调查-感知-响应", "explanation": "AI 暂不可用，使用规则兜底分类"}
            options = [
                f"极端版：直接{issue.replace('我要不要', '').replace('该不该', '')}，不设退路",
                "降级实验版：保留现有路径，但每周投入固定时间试新方向",
                "第三条路：不二选一，改变约束条件——比如换岗而非辞职",
                "不变版：继续现状，但重新定义成功的标准"
            ]
            physical_truth = f"物理层：你需要覆盖每月基本生活成本，你目前的技能和经验在市场上的可变现能力，以及两者之间的差距——这是不可更改的事实。"
            deletion_check = "规则兜底模式下无法运行完整删除分析。建议：问自己「如果我删掉其中一个选项，最坏的结果是什么？」如果不会死，直接删掉。"
            source = "fallback"
        data = {
            "issue": issue,
            "physical_truth": physical_truth,
            "deletion_check": deletion_check,
            "cynefin": cynefin,
            "filing": filing,
            "options": options,
            "oath_questions": oath_questions,
            "roles": select_roles(issue),
            "experiments": select_experiments(issue),
            "created_at": now_iso()
        }
        state = {"status": "oath", "issue": issue, "physical_truth": physical_truth, "deletion_check": deletion_check, "cynefin": cynefin, "filing": filing, "options": options, "preview": data, "created_at": now_iso(), "filing_source": source}
        save_state(state)
        append_log("start", {"issue": issue, "filing": filing, "cynefin": cynefin, "physical_truth": physical_truth, "deletion_check": deletion_check, "filing_source": source})
        self.send_json({"preview": data, "state": state})

    def handle_trial_reset(self):
        reset_session()
        self.send_json(state_payload())

    def handle_trial_run(self, payload):
        issue = str(payload.get("issue", "")).strip()
        oath_answers = str(payload.get("oath_answers", "")).strip()
        if not issue:
            state = load_state() or {}
            issue = state.get("issue", "")
        if not issue:
            self.send_json({"error": "issue is required"}, status=400)
            return
        trial = build_trial(issue, oath_answers)
        ensure_session_dir()
        write_text(VERDICT_PATH, trial.get("verdict", ""))
        write_text(CARD_PATH, trial.get("share_card", ""))
        card_image = generate_share_card_svg(trial)
        trial["share_card_image"] = f"/{card_image}"
        state = {"status": "verdict", "issue": issue, "trial": trial, "created_at": trial["created_at"]}
        save_state(state)
        append_log("verdict", {"issue": issue, "source": trial.get("source"), "trial_id": trial.get("trial_id"), "share_card_image": card_image})
        self.send_json({"trial": trial, "state": state})

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    port = int(os.environ.get("PARADOX_COURT_PORT", "8777"))
    os.chdir(ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Paradox Court UI: http://127.0.0.1:{port}/index.html", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
