<div align="center">

# 🍬 Sweet Journaler（work-journaler）

**把你的 AI 编程会话，熬成领导爱看的日报与 OKR 月报。**

[English](README.md) ｜ 简体中文

![Sweet Journaler — 由技能生成的中英文日报/月报示例，扇形铺开](example/promo-fan.webp)

</div>

> 你搬砖的每一天，Claude Code、Cursor、Copilot 们全程围观。
> 既然它们都看完了整场直播，凭什么日报还要你自己写？

## 这是什么

一个 Agent Skill（SKILL.md 开放标准——生于 Claude Code，也能入住 Codex、Cursor、Gemini CLI 等）。每天下班前丢一句「写日报」，它就会：

1. **翻旧账** —— 扫描本机 8 家 AI 编程工具的会话记录（Claude Code、Qoder、Cursor、GitHub Copilot、Aone Copilot、Codex、Cline、OpenCode）。你和 AI 的每一次深夜拉扯，都是今天的素材。
2. **去油提纯** —— 站在领导视角回答三个问题：核心工作动没动、落了什么价值、有什么风险。至于改名、重构、修 lint 这些「努力过的痕迹」？无情丢弃。
3. **先草稿，后出片** —— Markdown 草稿经你确认后，才渲染成设计感拉满的 HTML 报告：渐变 hero、进度卡片、OKR 对齐胸针、KR 进度条，还有「复制文本 / 复制为图片」两颗按钮，粘进任何汇报工具都体面。

日报落在 `~/work_journals/daily/`，OKR 月报落在 `~/work_journals/monthly_okr/`。
所有扒拉都只发生在本地——你的秘密不出家门，出门的只有精修过的你。

## 糖度说明（本技能的灵魂）

点单方式和奶茶店一致：「无糖日报」「月报，三分糖」「今天双份糖」。不备注默认**半糖**。

| 糖度 | 服务对象 | 口感 |
|---|---|---|
| **无糖 0%** | 未来的自己 | 美式直给。当天真实工作全记录，重命名也记、学习也记——毕竟未来的你，什么都会忘 |
| **三分糖 30%** | 技术型领导 | 微糖。保留技术术语与实现要点，懂行的人自然品得出层次 |
| **半糖 50%**（默认） | 一般领导 | 标准配方。一句结论 + 一句量化收益，术语翻译成人话 |
| **七分糖 70%** | 完全不懂技术的领导 | 丝滑厚乳。只讲「做成了什么、对业务意味着什么」，"P95 340→180ms" 自动化为「下单更快更稳了」 |
| **双份糖 200%** | 摸鱼的一天 | 体面模式。**不编造事实**，只是给小事穿上礼服：赋能、抓手、闭环、拉通、沉淀、组合拳，任君调味 |

三条铁律，加多少糖都不变：

1. **事实与数字绝不编造**——糖是修辞，不是造假；
2. 报告结构一分不少，卡片、进度条、OKR 对齐照常营业；
3. **糖度本身绝不写进报告**——一份双份糖日报被领导尝出配方，就不甜了。

## 快速上手

**推荐：一键安装。** [skills CLI](https://github.com/vercel-labs/skills) 会自动探测你本机装了哪些 AI 编程工具（Claude Code、Codex、Cursor、OpenCode……35+ 家），一条命令全部装齐：

```bash
npx skills add unpluggedcoder/sweet-journaler
```

**手动安装**：克隆进对应工具的技能目录即可，例如 Claude Code：

```bash
git clone https://github.com/unpluggedcoder/sweet-journaler.git ~/.claude/skills/work-journaler
```

| 工具 | 个人级目录 | 项目级目录 |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex CLI | `~/.codex/skills/` | `.codex/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.gemini/skills/` |
| Cursor | — | `.cursor/skills/` |
| 跨工具共享目录 | `~/.agents/skills/` | `.agents/skills/` |

还没原生支持技能的工具（Cline、Qoder、Aone Copilot……）也有兜底吃法：仓库克隆到任意位置，在该工具的指令文件（`AGENTS.md`、`.clinerules` 等）里加一句「当用户要求生成工作日报/月报时，读取并遵循 `<克隆路径>/SKILL.md`」。

> 依赖只有 `python3`。技能会读取各 AI 工具的本地会话存储，沙箱较严的工具（如 Codex 默认沙箱）首次运行时请批准相应目录的读取。

然后像在奶茶店点单一样：

```text
写日报               # 今天的日报
补一下周二的日报      # 指定日期也行
月报                 # 本月 OKR 月报
无糖日报             # 给未来的自己留档
月报，双份糖         # 你懂的
```

首次运行只问两个问题：**日报署名**（作者名），以及**输出语言**（中文 / English——默认跟你触发技能时用的语言走，用中文喊「写日报」默认就是中文）。答案存进 `~/work_journals/config.json`，之后不再啰嗦；某天想临时换语言，说一句「这份用英文写」即可。

## 示例（虚构数据）

`example/` 里有四份由本技能生成的演示报告，也就是上面宣传图里扇形铺开的那四张：

| | 中文 | English |
|---|---|---|
| 工作日报 | [daily-2026-07-16.zh.md](example/daily-2026-07-16.zh.md) | [daily-2026-07-16.en.md](example/daily-2026-07-16.en.md) |
| OKR 月报 | [monthly-okr-2026-07.zh.md](example/monthly-okr-2026-07.zh.md) | [monthly-okr-2026-07.en.md](example/monthly-okr-2026-07.en.md) |

作者「唐糖」与「NectarSearch 检索服务」纯属虚构；如有雷同，说明你们组也该装这个技能了。想亲手把玩渲染效果：

```bash
python3 scripts/md_to_html.py example/daily-2026-07-16.zh.md -o /tmp/demo.html
```

## 免责声明

- 本 README 供娱乐性质阅读，技能本身倒是真的很好用；
- 因日报过于好看，被领导要求「以后都按这个标准写」，后果自负；
- 双份糖模式产出的「抓手」与「闭环」如引起同事生理不适，请酌情减糖；
- 无糖模式可能含有真实工作量，令人清醒，慎用。
