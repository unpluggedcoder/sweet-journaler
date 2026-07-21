---
name: work-journaler
description: Generate or update work journals (工作日报 / 月度 OKR 月报) by mining the user's local AI-coding conversation histories (Claude Code, Qoder, Cursor, Copilot, Aone Copilot, Codex, Cline, OpenCode) and producing confirmed Markdown + styled HTML reports under ~/work_journals. Supports a 甜度/含糖量 (sweetness) knob — 无糖/三分糖/半糖/七分糖/双份糖 — controlling how abstract vs. detailed the reporting reads. Use this skill whenever the user asks to generate, write, or update a work journal, daily report, work log, monthly report, or OKR progress — including phrases like 生成日报 / 写日报 / 更新工作日志 / 月报 / OKR 月报 / 无糖日报 / work journal / daily journal / monthly OKR, even if they don't mention files or formats.
---

# Work Journaler

Turn the user's AI-assistant conversation history into two kinds of work
reports, written in Chinese (technical terms stay in English):

| Type | Output paths |
|------|--------------|
| 工作日报 (daily) | `~/work_journals/daily/YYYY-MM-DD.md` + `.html` |
| 月度 OKR 月报 (monthly) | `~/work_journals/monthly_okr/YYYY-MM.md` + `.html` |

The invariant that matters most: **markdown first, user confirms, HTML last.**
The journal is an outward-facing artifact the user pastes into review tools —
never publish (write the HTML for) content the user hasn't approved.

## Step 0 — Confirm output language and journal owner (first run only)

Read `~/work_journals/config.json` (create the directory if needed). On the
**first skill invocation**, determine the language of the user's triggering
message and use it as the default output language. Ask the user to explicitly
confirm it before scraping or drafting — for example, `I detected English;
shall I generate the journal in English?` or `检测到中文，日报将使用中文输出，是否确认？`.
The user may choose another language. Do not infer a later language switch
from an ordinary conversational reply: use the confirmed setting until the
user asks to change it.

Persist the confirmed `output_language` alongside `author`. If either key is
missing, ask only for that missing value; when both are missing, combine the
two questions in one concise first-run message:

```json
{"author": "****", "output_language": "zh-CN"}
```

Use the selected language for all report prose, headings, chips, metadata and
chat confirmation prompts. Keep source names, repository names, filenames and
technical identifiers unchanged. The Chinese structures below are the canonical
examples for `zh-CN`; for English use their direct equivalents (for example
`# Daily Work Journal YYYY-MM-DD`, `## Highlights`, `## Next Steps`, and
`# Monthly OKR Review · YYYY-MM`). Preserve the same information hierarchy and
Markdown-first confirmation flow in every language.

Every journal carries a localized author line as the first line under the H1 —
`作者：{author}` in Chinese and `Author: {author}` in English. The renderer
shows it top-left in the hero band with an avatar. When testing with
a sandboxed journal root, the config lives in that sandbox root instead.

## Step 1 — Establish the period

Never trust your internal sense of "today". Get it from the system:

```bash
date +%F          # daily default
date +%Y-%m       # monthly default
date -v-1d +%F    # "昨天" on macOS
```

The user may name an explicit date/month ("补一下周二的日报") — that wins.

## Step 2 — Scrape the conversation digest

```bash
python3 <skill>/scripts/scrape_conversations.py --date 2026-07-03 --out /tmp/digest.md
python3 <skill>/scripts/scrape_conversations.py --month 2026-07 --out /tmp/digest.md
```

The script reads every supported tool's local storage and emits a compact
digest: per session — project, time span, the user's prompts, and the final
assistant note. stderr shows per-source session counts; if a tool the user
actively uses shows 0, consult `references/sources.md` before assuming there
was no activity. `--home <dir>` redirects all storage lookups (sandbox/testing
only). For very busy months the caps are already tighter; `--json` gives
machine-readable output if you need to post-process.

Read the digest, then delete it if it was written to /tmp.

## 甜度（含糖量）— 汇报模糊度旋钮

用户触发时可以带一个"甜度/含糖量"备注（"来份无糖日报"、"月报，三分糖"、
"今天双份糖"）。甜度控制进展表述的抽象程度与修辞浓度——糖越多，越宏观、
越模糊、越"好入口"；糖越少，越接近工作的真实颗粒。**未指定时默认五分糖**，
即 Step 3 / Step 5 描述的现行标准；其他甜度在该基线上调整：

| 甜度 | 读者 | 写法调整 |
|---|---|---|
| 无糖 / 零糖 | 自己（全量工作留档，供未来抽样回顾） | 不受 1-2 句限制，呈现当天真实工作细节：重构/重命名等杂务也记（可多件合并一行），学习会话照记。仍要总结提炼、忌流水账；关键缩写仍须中英文全称说明——未来的自己也会忘 |
| 三分糖 / 少糖 | 技术型领导（熟悉技术细节） | 领导视角过滤照旧，但可适当保留技术术语与实现要点，常见技术缩写不必展开，每项可放宽到 2-3 句 |
| 五分糖 / 半糖（默认） | 一般领导 | 现行标准：关键进展 + 量化价值，每项 1-2 句，避免技术细节，复杂缩写替换或注释 |
| 七分糖 ~ 正常糖 | 完全不懂技术的领导 | 高度概括、宏观说大白话：只讲"做成了什么、对业务意味着什么"，不用任何术语与缩写，量化数字翻译成业务影响（"下单更快更稳"而非 "P95 340→180ms"） |
| 双份糖（>100%） | 摸鱼的一天 | 今日产出太少或没有核心进展时的体面模式：**不编造事实**，但用互联网黑话把小事讲出声势——赋能、抓手、闭环、拉通、对齐、沉淀、组合拳、颗粒度、心智、反哺，任君调味 |

无论甜度多少，三条不变：**事实与数字不可编造**；报告结构（hero/卡片/计划行/
OKR 对齐）不变；**甜度本身绝不写进报告**——一份"双份糖"日报被领导看出配方
就不甜了。

## Step 3 — Distill for the leader's view

The journal's reader is the user's **leader**, not a teammate. A leader reads
it to answer three questions: is the core work moving, what value landed, and
what's at risk. Every line must pass the test *"does my leader need this to
see progress and value?"* — activity that only demonstrates effort buries the
signal and makes the report read like busywork.

（本节与 Step 5 的写法规则描述的是默认甜度=五分糖；用户指定了其他甜度时，
先按上文「甜度」一节调整读者画像与详略度，再应用这里的原则。）

- **Keep**: progress on core initiatives, shipped capabilities, evaluations
  with conclusions, deployments, direction-changing decisions, risks/blockers —
  each stated as **outcome + value**, with the quantified benefit whenever the
  digest offers numbers (成功率、延迟、覆盖率、吞吐、耗时). Numbers are what
  make a leader-facing report credible; never invent ones the digest doesn't
  contain.
- **Drop (leader-irrelevant detail)**: renames, refactors, lint/style cleanups,
  config tweaks, and code-level implementation detail. These are *how* the
  work got done, not *what* it achieved — fold them into their parent outcome
  or omit them entirely. A session whose only product is such chores yields no
  journal item at all.
- **Summarize outcomes, never narrate chronology.** One item = one
  initiative's result（“完成 X 能力：支持 …，收益 …”）, not the sequence of
  sessions or attempts that produced it. If the work was building a
  tool/skill/feature, describe its **capabilities and the value it delivers**
  — not the iterations, style passes, or technical minutiae along the way.
- **Learning-only sessions** ("X 是什么原理", "explain this error" with no work
  product) must never appear as work progress. They may appear as at most one
  short line each at the end of 今日进展, tagged `[[学习]]` — e.g.
  `- 学习 asyncio event loop 原理 [[学习]]`. Include them when they round out
  the picture of the day; drop them when the day is already full.
- **Merge duplicates**: the same task often spans several sessions and tools
  (debug in Qoder, finish in Claude Code) — report the outcome once.
- **Thin periods still deserve a full report.** If only one work item exists,
  go deeper on it instead of shipping a three-line stub — deeper meaning more
  about impact, value and follow-through, not more implementation detail.
  The reader should never be able to tell the day was quiet from the report's
  effort level.

## Step 4a — Daily journal (工作日报)

Exact top-level structure:

```markdown
# 工作日报 YYYY-MM-DD

作者：{config.json 里的 author}

星期X ｜ 项目：{当日主要项目} ｜ 数据来源：{参与的工具，如 Claude Code / Qoder}

[[今日进展 N 项]] [[昨日计划完成 X/Y]] [[顺延 N 项]]

## 今日进展

1. **{成果标题，一句话结论}** [[承接 MM-DD 计划]] [[已完成]]
   {1-2 句概括：交付了什么能力、它的价值/量化收益}
   [[OKR: O1-K3 核心链路 CI 全绿率 95%]]

## 下一步计划

- [ ] 计划项（只列未完成/新增的计划）
```

How the converter turns this into the designed report — rely on it instead of
writing HTML yourself:

- The **H1 + the lines under it** (meta row, then a chips-only line) become a
  gradient hero header with stat chips. Always include the meta row and the
  stat-chips line — they are what makes the report look designed.
- **Ordered items whose first line starts with bold** become numbered cards:
  first line = card title (+ status chips), indented lines = card body, an
  indented chips-only line = card footer. Status chips: [[已完成]] renders
  green, [[承接 …]] blue, [[风险]]/[[阻塞]] red, [[学习]] gray, [[OKR: …]]
  accent.
- `- [ ]` items in 下一步计划 render as unified accent → arrow rows. List only
  open/new plans there — completion is already expressed by the 已完成 chips in
  今日进展 and the 昨日计划完成 X/Y hero stat, never by the plan list itself.
  Never leave literal `[ ]` brackets outside a task list.

Daily reports may carry more detail than monthly ones, but detail means
**summary statements of what landed and why it matters** — never a
chronological or technical account. Card bodies stay at the capability/value
altitude; the leader can ask for implementation detail if they want it.

For 下一步计划, look at two inputs before drafting:

1. The **previous daily journal** (latest file in `~/work_journals/daily/`
   before this date) — if it has a 下一步计划, carry it forward: items done
   today become 今日进展 cards with a [[承接 MM-DD 计划]] chip (and feed the
   昨日计划完成 X/Y hero stat); still-open items stay in 下一步计划.
2. The **current month's OKR file** (`~/work_journals/monthly_okr/YYYY-MM.md`),
   falling back to the most recent month available — next steps should push
   some KR forward, and progress items get their `[[OKR: …]]` chip from it.

Then present 2–4 candidate next-step items and ask the user to pick or edit
them (a short numbered list in chat is enough). If the user already told you
what's next, or asked you not to prompt, skip the question and use that.

## Step 4b — Monthly OKR journal (月度 OKR 月报)

First resolve the OKR themselves:

- If `~/work_journals/monthly_okr/` has a previous month's file, **carry its
  O/KR structure forward by default** (tell the user you did).
- If the user supplies O/KR in the request, use those.
- If neither exists (first run), ask the user for their Objectives and Key
  Results before writing anything.

Exact structure — one H1 per objective, one H2 per key result with a progress
percentage, work items aligned under the KR they advance:

```markdown
# OKR 月报 · YYYY-MM

作者：{config.json 里的 author}

{一句话月度总结} ｜ 数据来源：{参与的工具}

[[KR 达标 X/Y]] [[平均进度 Z%]] [[风险 N 项]]

# O1: {objective}

## K1: {key result} — 进度[20% → **45%**]

（一行进度解读，然后列本月相关进展条目）

## K2: {key result} — 进度[**80%**]

# O2: {objective}
…
```

The first H1 + owner + meta + chips lines become the hero header (same as the
daily); each `# O*:` heading renders as a gradient objective band with an O
badge, and each `## K*:` section as a card — hero → O band → K card is the
visual hierarchy, all driven by the exact `O*:`/`K*:` heading prefixes.

Inside each KR card, two tiers of content — and only two:

- `关键进展：{一句话，含数字}` — reserved for updates that **directly moved
  the KR** (target crossed, large quantified jump). The converter renders it
  as a green highlight strip. At most one per KR; ordinary months have none.
- Everything else KR-related goes in the plain unordered list, still filtered
  to leader altitude: aggregate small related items into one line, keep each
  line outcome-shaped.

The 月报 is one level coarser than the 日报 — it exists to show KR movement,
not to inventory the month. Minor bug fixes (unless the bug was a major
user-affecting incident), refactors, renames and similar chores do **not**
appear in a monthly report at all, even under 其他进展.

Keep the 进度 pattern exact in every KR heading — the converter renders it as
a segmented progress bar. Use the two-value form `进度[上月% → **本月%**]`
whenever last month's number is known: it draws last month's base in amber,
this month's gain in green (a drop in red) plus a ↑/↓/持平 delta badge —
managers read 月报 for the delta, not the absolute number. The single-value
form `进度[**45%**]` is for first-month OKR only.

Estimate each 进度 percentage from the month's evidence and the KR's target;
present your estimates as proposals — the user corrects them at confirmation.
Work that advances no KR goes under a final `# 其他进展` section rather than
being force-fitted or dropped.

## Step 5 — Content style

- Write in the confirmed `output_language`; keep technical terms verbatim (`vLLM`, `structured decoding`,
  repo/file/model names).
- **每一项 1-2 句话说完。** 领导是扫读的：一句结论 + 一句量化收益/价值即可；
  需要第三句时，它多半是不该出现的实现细节。宁可少写一句，不要多写一行。
- **少用缩写术语，尤其是复杂统计/算法类专业缩写。** 标准是"领导不用检索也能
  看懂"：能替换就用通俗说法（如写"滑动平均"而不是 EWMA）；确实无法替换的
  缩写，首次出现必须括号标注中英文全称，如 `EWMA（指数加权移动平均，
  Exponentially Weighted Moving Average）`。已经出现在用户 OKR/KR 原文中的
  术语（如 P95）属于共同语言，无需解释。
- **Bold** key results and project names; *italic* for emphasis; color
  sparingly via inline HTML for signal, e.g.
  `<span style="color:#2da44e">已完成</span>`,
  `<span style="color:#d73a49">风险/阻塞</span>` — the HTML converter
  whitelists span/font/mark with style attributes.
- **Chips**: `[[学习]]` renders as a neutral pill, `[[OKR: K 描述]]` as an
  accent pill — use them for per-item metadata instead of parentheses so the
  报告 stays scannable.
- Numbers, tables and short bullets over long paragraphs — the reader is a
  manager skimming.
- **Images/charts**: if the period's work produced meaningful visuals (eval
  charts, dashboards) or clearly chartable data, and they strengthen the
  report, save them to `~/work_journals/assets/<YYYY-MM-DD|YYYY-MM>/` and
  embed with `![desc](../assets/…/x.png)`. The converter inlines local images
  into the HTML as data URIs, so the .html stays a single portable file.
  Importance decides: one strong chart beats three decorative ones.

## Step 6 — Confirm, then render HTML

1. Write the markdown to its final path (create dirs as needed).
2. Show the user the draft (inline for short reports, or tell them the path)
   and ask for confirmation or edits. Iterate in markdown until they approve.
   If the user pre-approved in their request ("直接生成，不用确认"), proceed.
3. On approval:

```bash
python3 <skill>/scripts/md_to_html.py ~/work_journals/daily/YYYY-MM-DD.md
open ~/work_journals/daily/YYYY-MM-DD.html   # let the user see the result
```

The HTML is light-themed, self-contained (html2canvas inlined), and carries
two toolbar buttons: 复制文本 (plain text to clipboard) and 复制为图片
(renders a compact 800px capture, shows a preview popup, user confirms → PNG
lands on the clipboard, with a download fallback).

If the user later edits the markdown, just re-run `md_to_html.py` — it
overwrites the .html idempotently.

## Updating an existing journal

"更新日报" means: re-scrape the period, read the existing .md, merge new
progress into it (don't clobber user hand-edits — treat their text as source
of truth and add/adjust around it), reconfirm, re-render HTML.
