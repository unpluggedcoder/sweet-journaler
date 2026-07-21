# Work Journaler

> Turn local AI-coding conversations into leader-ready daily journals and monthly OKR reviews — Markdown first, confirmation second, polished HTML last.

![Bilingual daily-report and monthly-OKR examples fanned into one promotional image](assets/examples/report-examples-fan.svg)

## What it does

Work Journaler mines local conversations from Claude Code, Qoder, Cursor, Copilot, Aone Copilot, Codex, Cline, and OpenCode, then distills verified work into reports under `~/work_journals`.

| Report | Markdown | HTML |
| --- | --- | --- |
| Daily work journal | `~/work_journals/daily/YYYY-MM-DD.md` | `~/work_journals/daily/YYYY-MM-DD.html` |
| Monthly OKR review | `~/work_journals/monthly_okr/YYYY-MM.md` | `~/work_journals/monthly_okr/YYYY-MM.html` |

### First-run language confirmation

On the first invocation, the skill detects the language of the triggering request and asks you to confirm it before doing any work. That detected language is the default, but you can select another one. The confirmed preference is saved as `output_language` in `~/work_journals/config.json` and is used for report prose, headings, metadata, chips, and confirmation messages.

```json
{"author":"Alex Lin","output_language":"en"}
```

## Examples

The `example/` directory includes fictional, complete Markdown reports that can be rendered with the bundled converter:

```bash
python3 scripts/md_to_html.py example/daily-report-demo.md
python3 scripts/md_to_html.py example/monthly-okr-demo.md
```

| Daily journal | Monthly OKR review |
| --- | --- |
| ![Chinese daily report preview](assets/examples/daily-cn.svg) | ![Chinese monthly OKR preview](assets/examples/monthly-cn.svg) |
| ![English daily report preview](assets/examples/daily-en.svg) | ![English monthly OKR preview](assets/examples/monthly-en.svg) |

These images are illustrative previews of the two report types in Chinese and English; the Markdown examples themselves are fictional.

## Workflow guarantees

1. **Evidence first.** The skill reads local conversation history and never invents facts or metrics.
2. **Markdown first.** It writes a draft, shows it to you, and waits for approval.
3. **HTML only after approval.** The self-contained HTML version is generated only after you confirm the Markdown.
4. **Leader-focused.** It reports outcomes, value, progress, and risks—not a chronological activity dump.

## Sweetness level

Add a sweetness level to control abstraction: `sugar-free`, `light sugar`, `half sugar` (default), `regular sugar`, or `double sugar`. More sweetness means a more executive-friendly, high-level presentation; it never permits fabricated facts.

See [SKILL.md](SKILL.md) for the complete invocation guidance, report structures, source handling, and rendering conventions.
