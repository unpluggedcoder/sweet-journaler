#!/usr/bin/env python3
"""Convert a work-journal markdown file into a styled, self-contained HTML report.

- Light theme, gradient hero header, card-based progress items.
- Two toolbar buttons: 复制文本 / 复制为图片 (html2canvas is inlined — fully offline).
- Local images referenced from the markdown are inlined as data URIs, so the
  resulting .html is a single portable file.

Journal-aware rendering conventions (see SKILL.md):
- First H1 + following non-heading lines  -> hero header (title, meta, stat chips)
- [[label]]                               -> colored chip (OKR/已完成/承接/风险/学习…)
- ordered-list items starting with **粗体** -> numbered cards (body = indented lines,
  a chips-only body line becomes the card footer)
- - [ ] / - [x]                           -> real styled checkboxes
- 进度[**45%**]                            -> visual progress bar

Usage: md_to_html.py input.md [-o output.html] [--title "..."]
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import mimetypes
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
RAW_TAGS = r"span|font|mark|b|strong|i|em|u|sub|sup|br|img"
CHIP_ONLY = re.compile(r"^\s*(\[\[[^\[\]]+\]\]\s*)+$")
HEADING = re.compile(r"^#{1,4}\s")
LIST_ITEM = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)")

# --------------------------------------------------------------- image inline


def inline_image(src: str, base_dir: Path) -> str:
    """Return a data URI for a local image; pass remote/missing srcs through."""
    if src.startswith(("data:", "http://", "https://")):
        return src
    path = (base_dir / src).resolve() if not src.startswith(("/", "~")) else Path(src).expanduser()
    if not path.is_file():
        print(f"[md_to_html] warn: image not found, kept as-is: {src}", file=sys.stderr)
        return src
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


# --------------------------------------------------------------------- chips


def chip_html(label: str) -> str:
    label = label.strip()
    if re.match(r"OKR\b", label, re.I):
        body = re.sub(r"^OKR\s*[:：]\s*", "", label, flags=re.I)
        return f'<span class="tag okr">对应 OKR：{body}</span>'
    if re.search(r"已完成|完成 ?✓|达成|已上线|全绿", label):
        cls = "tag ok"
    elif re.search(r"风险|阻塞|延期|未达|blocked", label, re.I):
        cls = "tag warn"
    elif re.search(r"承接|顺延|carry", label, re.I):
        cls = "tag carry"
    else:
        cls = "tag"
    return f'<span class="{cls}">{label}</span>'


# ------------------------------------------------------------- inline parsing


def render_inline(text: str, base_dir: Path) -> str:
    """Escape text, then apply markdown inline syntax; whitelisted raw HTML survives."""
    raws: list[str] = []

    def stash(match: re.Match) -> str:
        tag = match.group(0)
        if re.search(r"on\w+\s*=", tag, re.I):  # never allow event handlers
            return ""
        src = re.search(r'src="([^"]+)"', tag)
        if src:
            tag = tag.replace(src.group(1), inline_image(src.group(1), base_dir))
        raws.append(tag)
        return f"\x00R{len(raws) - 1}\x00"

    text = re.sub(rf"</?(?:{RAW_TAGS})\b[^>]*>", stash, text)
    text = html.escape(text, quote=False)

    # images before links (shared bracket syntax)
    text = re.sub(
        r"!\[([^\]]*)\]\(([^)\s]+)\)",
        lambda m: f'<img src="{inline_image(m.group(2), base_dir)}" alt="{m.group(1)}">',
        text,
    )
    # chips before links so [[..]] never half-matches link syntax
    text = re.sub(r"\[\[([^\[\]]+)\]\]", lambda m: chip_html(m.group(1)), text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*\*([^*]+)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"(?<![\w_])_([^_\s][^_]*?)_(?![\w_])", r"<em>\1</em>", text)
    text = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", text)

    # 进度[**45%**] or 进度[60% → **90%**] -> progress bar; the two-value form
    # renders month-over-month segments: amber = last month's base, green =
    # this month's gain (red = regression), gray = remaining, plus a delta badge.
    def bar(m: re.Match) -> str:
        inner = re.sub(r"</?strong>", "", m.group(1))
        nums = [max(0, min(100, int(n))) for n in re.findall(r"(\d{1,3})\s*%", inner)]
        if not nums:
            return m.group(0)
        cur = nums[-1]
        prev = nums[0] if len(nums) > 1 else None
        if prev is None or prev == cur:
            segs = f'<span class="kr-fill" style="width:{cur}%"></span>'
            badge = '<span class="kr-delta flat">持平</span>' if prev is not None else ""
        elif cur > prev:
            segs = (f'<span class="kr-seg base" style="width:{prev}%"></span>'
                    f'<span class="kr-seg gain" style="left:{prev}%;width:{cur - prev}%"></span>')
            badge = f'<span class="kr-delta up">↑ +{cur - prev}</span>'
        else:
            segs = (f'<span class="kr-seg base" style="width:{cur}%"></span>'
                    f'<span class="kr-seg loss" style="left:{cur}%;width:{prev - cur}%"></span>')
            badge = f'<span class="kr-delta down">↓ -{prev - cur}</span>'
        return (f'<span class="kr-progress"><span class="kr-bar">{segs}</span>'
                f'<span class="kr-pct">{cur}%</span>{badge}</span>')

    text = re.sub(r"(?:\s*[—–-]+\s*)?进度\s*[\[［]([^\]］]*%[^\]］]*)[\]］]", bar, text)

    for i, raw in enumerate(raws):
        text = text.replace(f"\x00R{i}\x00", raw)
    return text


# ---------------------------------------------------------------- list model


def collect_list(lines: list[str], i: int) -> tuple[list[dict], int]:
    """Collect consecutive list items (with indented continuation lines) from lines[i:].

    Returns (items, next_index). Each item: {"marker", "head", "body": [lines]}.
    A continuation line is any non-empty line indented ≥2 spaces that is not
    itself a top-level list item; indented list markers become sub-bullets.
    """
    items: list[dict] = []
    while i < len(lines):
        if items and not lines[i].strip():
            # blank line(s) between items: keep the same list going if the next
            # non-blank line is another top-level item of the same kind —
            # otherwise each card would start its own <ol> and reset numbering
            k = i
            while k < len(lines) and not lines[k].strip():
                k += 1
            nxt = LIST_ITEM.match(lines[k]) if k < len(lines) else None
            if nxt and not nxt.group(1) and \
               nxt.group(2)[0].isdigit() == items[-1]["marker"][0].isdigit():
                i = k
                continue
            break
        m = LIST_ITEM.match(lines[i])
        if not m or len(m.group(1)) >= 2:
            break
        item = {"marker": m.group(2), "head": m.group(3).strip(), "body": []}
        i += 1
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                # blank line ends the item unless the next line is still indented
                if i + 1 < len(lines) and re.match(r"^\s{2,}\S", lines[i + 1]):
                    i += 1
                    continue
                break
            if re.match(r"^\s{2,}\S", line):  # continuation text or indented sub-bullet
                item["body"].append(line.strip())
                i += 1
                continue
            break
        items.append(item)
    return items, i


def render_task_li(head: str, base_dir: Path) -> str | None:
    """GFM task syntax -> one unified plan-row style.

    Plan items are to-dos by nature; completion is expressed in 今日进展 (chips)
    and the hero stats, so every plan row renders identically — checked state
    in legacy files is deliberately ignored.
    """
    task = re.match(r"\[( |x|X)\]\s+(.*)", head)
    if not task:
        return None
    return (f'<li class="plan"><span class="plan-ico">→</span>'
            f'<span class="plan-text">{render_inline(task.group(2), base_dir)}</span></li>')


def render_list(items: list[dict], base_dir: Path) -> str:
    ordered = items[0]["marker"][0].isdigit()
    as_cards = ordered and any(it["head"].startswith("**") for it in items)
    out: list[str] = []

    if as_cards:
        out.append('<ol class="cards">')
        for it in items:
            out.append('<li class="card">')
            out.append(f'<div class="card-title">{render_inline(it["head"], base_dir)}</div>')
            foot: list[str] = []
            body: list[str] = []
            subs: list[str] = []
            for ln in it["body"]:
                if CHIP_ONLY.match(ln):
                    foot.append(render_inline(ln, base_dir))
                elif re.match(r"^[-*]\s+", ln):
                    subs.append(f"<li>{render_inline(ln[2:], base_dir)}</li>")
                else:
                    body.append(f"<p>{render_inline(ln, base_dir)}</p>")
            if body or subs:
                out.append('<div class="card-body">' + "".join(body)
                           + (f"<ul>{''.join(subs)}</ul>" if subs else "") + "</div>")
            for f in foot:
                out.append(f'<div class="card-foot">{f}</div>')
            out.append("</li>")
        out.append("</ol>")
        return "\n".join(out)

    tag = "ol" if ordered else "ul"
    out.append(f"<{tag}>")
    for it in items:
        task_li = render_task_li(it["head"], base_dir)
        extra = ""
        if it["body"]:
            subs = [f"<li>{render_inline(b[2:], base_dir)}</li>" for b in it["body"]
                    if re.match(r"^[-*]\s+", b)]
            paras = [render_inline(b, base_dir) for b in it["body"] if not re.match(r"^[-*]\s+", b)]
            extra = ("<br>" + "<br>".join(paras) if paras else "") + \
                    (f"<ul>{''.join(subs)}</ul>" if subs else "")
        if task_li:
            out.append(task_li[:-5] + extra + "</li>")
        else:
            out.append(f"<li>{render_inline(it['head'], base_dir)}{extra}</li>")
    out.append(f"</{tag}>")
    return "\n".join(out)


# -------------------------------------------------------------- block parsing


def render_blocks(md: str, base_dir: Path) -> str:
    out: list[str] = []
    lines = md.splitlines()
    i = 0
    open_kr = False

    def close_kr() -> None:
        nonlocal open_kr
        if open_kr:
            out.append("</section>")
            open_kr = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            code: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            out.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
            i += 1
            continue

        if not stripped:
            i += 1
            continue

        m = re.match(r"(#{1,4})\s+(.*)", stripped)
        if m:
            level = len(m.group(1))
            if level <= 2:
                close_kr()
            kr = re.match(r"(K\d+)\s*[:：]\s*(.*)", m.group(2)) if level == 2 else None
            obj = re.match(r"(O\d+)\s*[:：]\s*(.*)", m.group(2)) if level == 1 else None
            if kr:  # ## K*: sections render as cards, echoing the daily card style
                out.append('<section class="kr-card">')
                out.append(f'<div class="kr-head"><span class="kr-badge">{kr.group(1)}</span>'
                           f'<span class="kr-title">{render_inline(kr.group(2), base_dir)}</span></div>')
                open_kr = True
            elif obj:  # # O*: objectives render as gradient bands echoing the hero
                out.append(f'<div class="obj-band"><span class="obj-badge">{obj.group(1)}</span>'
                           f'<span class="obj-title">{render_inline(obj.group(2), base_dir)}</span></div>')
            else:
                out.append(f"<h{level}>{render_inline(m.group(2), base_dir)}</h{level}>")
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,})$", stripped):
            out.append("<hr>")
            i += 1
            continue

        if stripped.startswith(">"):
            quote: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>" + render_inline(" ".join(quote), base_dir) + "</blockquote>")
            continue

        if "|" in stripped and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]):
            header = [c.strip() for c in stripped.strip("|").split("|")]
            out.append("<table><thead><tr>" +
                       "".join(f"<th>{render_inline(c, base_dir)}</th>" for c in header) +
                       "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>" + "".join(f"<td>{render_inline(c, base_dir)}</td>" for c in cells) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue

        if LIST_ITEM.match(line) and not line.startswith(("  ", "\t")):
            items, i = collect_list(lines, i)
            out.append(render_list(items, base_dir))
            continue

        if CHIP_ONLY.match(stripped):
            out.append(f'<div class="chip-row">{render_inline(stripped, base_dir)}</div>')
            i += 1
            continue

        key = re.match(r"^关键进展\s*[:：]\s*(.*)", stripped)
        if key:  # standalone highlight for the KR's core progress event
            out.append(f'<div class="kr-key"><span class="kr-key-badge">关键进展</span>'
                       f'<span>{render_inline(key.group(1), base_dir)}</span></div>')
            i += 1
            continue

        para = [stripped]
        while (i + 1 < len(lines) and lines[i + 1].strip()
               and not re.match(r"^(\s*([-*]|\d+\.)\s|#{1,4}\s|>|```|(-{3,})$|关键进展\s*[:：])", lines[i + 1].strip())
               and "|" not in lines[i + 1]
               and not CHIP_ONLY.match(lines[i + 1].strip())):
            i += 1
            para.append(lines[i].strip())
        out.append(f"<p>{render_inline(' '.join(para), base_dir)}</p>")
        i += 1

    close_kr()
    return "\n".join(out)


# ----------------------------------------------------------------- hero split


def split_hero(md: str, base_dir: Path, fallback_title: str) -> tuple[str, str, str]:
    """Extract (hero_html, page_title, rest_md) from the journal markdown.

    Hero = first H1 plus everything until the next heading: plain lines become
    the meta row, chips-only lines the stat-chip row.
    """
    lines = md.splitlines()
    h1_idx = next((i for i, ln in enumerate(lines) if re.match(r"^#\s+\S", ln)), None)
    if h1_idx is None:
        title = fallback_title
        hero = f'<h1 class="hero-title">{html.escape(title)}</h1>'
        return hero, title, md

    title_md = re.sub(r"^#\s+", "", lines[h1_idx]).strip()
    title = re.sub(r"[*_`]|\[\[[^\]]*\]\]", "", title_md).strip()
    owner_html = ""
    parts = [f'<h1 class="hero-title">{render_inline(title_md, base_dir)}</h1>']
    j = h1_idx + 1
    while j < len(lines) and not HEADING.match(lines[j]):
        s = lines[j].strip()
        if s:
            owner = re.match(r"(?:作者|署名|Owner|Author)\s*[:：]\s*(.+)", s, re.I)
            if owner:  # journal owner renders top-left, above the title
                name = owner.group(1).strip()
                owner_html = (f'<div class="hero-owner"><span class="hero-avatar">'
                              f'{html.escape(name[:1].upper())}</span>'
                              f'{render_inline(name, base_dir)}</div>')
            elif CHIP_ONLY.match(s):
                parts.append(f'<div class="hero-chips">{render_inline(s, base_dir)}</div>')
            else:
                parts.append(f'<p class="hero-meta">{render_inline(s, base_dir)}</p>')
        j += 1
    if owner_html:
        parts.insert(0, owner_html)
    rest = "\n".join(lines[:h1_idx] + lines[j:])
    return "\n".join(parts), title, rest


# ------------------------------------------------------------------------ main


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", help="markdown file to convert")
    ap.add_argument("-o", "--output", help="output html path (default: input with .html)")
    ap.add_argument("--title", help="page title (default: first H1 of the markdown)")
    args = ap.parse_args()

    src = Path(args.input).expanduser()
    if not src.is_file():
        print(f"[md_to_html] error: no such file: {src}", file=sys.stderr)
        return 1
    md = src.read_text(encoding="utf-8")

    hero, title, rest = split_hero(md, src.parent, args.title or src.stem)
    if args.title:
        title = args.title

    template = (SKILL_ROOT / "assets/template.html").read_text(encoding="utf-8")
    h2c = (SKILL_ROOT / "assets/html2canvas.min.js").read_text(encoding="utf-8")
    content = render_blocks(rest, src.parent)

    page = (template
            .replace("{{TITLE}}", html.escape(title))
            .replace("{{HTML2CANVAS}}", h2c)
            .replace("{{GENERATED_AT}}", dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
            .replace("{{HERO}}", hero)
            .replace("{{CONTENT}}", content))

    dest = Path(args.output).expanduser() if args.output else src.with_suffix(".html")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(page, encoding="utf-8")
    print(f"[md_to_html] wrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
