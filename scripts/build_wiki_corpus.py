#!/usr/bin/env python3
"""posts.json -> nanhwa-wiki/corpus/fb-news/fb-posts_<year>.md（一年一档）

契约见 nanhwa-wiki/corpus/README.md：语料堆、一年一档、不炸成逐条图谱页、豁免 wiki 五铁律。
取代 2026-04 的后台 CSV 导出（fb-posts_2025-05_2026-04.md，仅 136 篇 / 11 个月 = 全档 11%）。

ponytail: 纯 stdlib，无模板引擎。水贴（is_filler）与空正文帖不入语料——语料是给炼指纹用的，
          没正文的帖子对指纹零贡献，留着只会稀释。媒体/链接只记数与档名，不搬 6GB。
"""
import json
import pathlib
import sys
from collections import Counter

SRC = pathlib.Path(r"C:\dev\nanhwafs-site\data\posts.json")
OUT = pathlib.Path(r"C:\Users\lee66\claude-workspace\nanhwa-wiki\corpus\fb-news")

HEADER = """# 南华独中脸书语料 · {year}

> 来源：Meta 全档导出 `D:\\Fb_AllRecord\\` → `nanhwafs-site/scripts/parse_fb_export.py`
> → `data/posts.json` → 本档（`build_wiki_corpus.py` 生成，勿手改）。
> 生成日：{gendate}｜本年入档 {kept} 篇（该年原始 {total} 篇，剔除水贴/无正文 {dropped} 篇）。
>
> ⚠️ **作者身份混合**：本页帖文由林子策撰写，但**内文常含校长陳麗冰、董事长颜登逸的引言**。
> 炼写作指纹（/kgs）时**必须先分离他人引言**，否则指纹池会混入三个人的笔迹。
> 见 memory `feedback_news_corpus_authorship`。
>
> 语料区豁免 wiki 五条铁律：无 `level:`、无 typed links、不计入孤立页/断链 lint。

---

"""


def render(post: dict) -> str:
    head = f"## {post['date']} {post['time']}　[{post['type']}]"
    meta = []
    if post.get("media"):
        meta.append(f"媒体 {len(post['media'])} 项")
    if post.get("links"):
        meta.append("链接 " + " ".join(post["links"][:3]))
    lines = [head]
    if meta:
        lines.append("> " + "｜".join(meta))
    lines.append("")
    lines.append(post["text"].strip())
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    posts = json.loads(SRC.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)

    by_year: dict[int, list[dict]] = {}
    total = Counter()
    dropped = Counter()
    for p in posts:
        y = p["year"]
        total[y] += 1
        if p.get("is_filler") or not p.get("text", "").strip():
            dropped[y] += 1
            continue
        by_year.setdefault(y, []).append(p)

    gendate = __import__("datetime").date.today().isoformat()
    summary = []
    for y in sorted(by_year):
        items = sorted(by_year[y], key=lambda x: (x["date"], x["time"]))
        body = HEADER.format(
            year=y, gendate=gendate, kept=len(items), total=total[y], dropped=dropped[y]
        ) + "\n".join(render(p) for p in items)
        f = OUT / f"fb-posts_{y}.md"
        f.write_text(body, encoding="utf-8", newline="\n")
        summary.append((y, len(items), total[y], dropped[y], f.stat().st_size))

    print(f"{'年':<6}{'入档':>6}{'原始':>6}{'剔除':>6}{'KB':>9}")
    for y, kept, tot, drop, size in summary:
        print(f"{y:<6}{kept:>6}{tot:>6}{drop:>6}{size/1024:>9.1f}")
    print(f"{'合计':<6}{sum(s[1] for s in summary):>6}{sum(s[2] for s in summary):>6}"
          f"{sum(s[3] for s in summary):>6}{sum(s[4] for s in summary)/1024:>9.1f}")

    # 自检：入档 + 剔除 必须等于原始总数，且不得有空档
    assert sum(s[1] + s[3] for s in summary) == len(posts), "计数对不上"
    assert all(s[1] > 0 for s in summary), "有年份产出 0 篇"
    print("self-check OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
