# -*- coding: utf-8 -*-
"""P3+P4: posts.json -> news/YYYY/*.html + compressed images + year indexes.
Idempotent: re-run safe (skips already-compressed images). Usage: python build_news.py
"""
import json, os, re, html, shutil
from collections import defaultdict
from PIL import Image
from opencc import OpenCC

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FB_ROOT = r'D:\Fb_AllRecord'
BASE_URL = 'https://nanhwappd.github.io/nanhwafs-site'  # swap when custom domain lands (P5)
MAX_SIDE, QUALITY, MAX_IMGS = 1280, 78, 8

cc = OpenCC('t2s')
URL_RE = re.compile(r'https?://[^\s<]+')


def esc_autolink(line):
    out, last = [], 0
    for m in URL_RE.finditer(line):
        out.append(html.escape(line[last:m.start()]))
        u = m.group(0)
        out.append(f'<a href="{html.escape(u)}" rel="nofollow">{html.escape(u)}</a>')
        last = m.end()
    out.append(html.escape(line[last:]))
    return ''.join(out)


def make_title(p, s_text):
    for line in s_text.split('\n'):
        line = line.strip()
        if line and not URL_RE.fullmatch(line):
            return line[:40]
    return f"{p['year']} 年 {int(p['date'][5:7])} 月校园动态"


def main():
    posts = json.load(open(os.path.join(SITE, 'data', 'posts.json'), encoding='utf-8'))
    live = [p for p in posts if not p['is_filler']]
    live.sort(key=lambda p: (p['date'], p['time']))

    ymap = json.load(open(os.path.join(SITE, 'data', 'youtube_map.json'), encoding='utf-8')) \
        if os.path.exists(os.path.join(SITE, 'data', 'youtube_map.json')) else {}
    tpl = open(os.path.join(SITE, 'templates', 'news-post.html'), encoding='utf-8').read()

    # slugs: YYYYMMDD-N
    day_counter = defaultdict(int)
    for p in live:
        d = p['date'].replace('-', '')
        day_counter[d] += 1
        p['slug'] = f'{d}-{day_counter[d]}'

    # drop P2 preview sample
    for f in ('preview-sample.html', 'preview-img-0.jpg', 'preview-img-1.jpg', 'preview-img-2.jpg'):
        fp = os.path.join(SITE, 'news', '2026', f)
        if os.path.exists(fp):
            os.remove(fp)

    videos_md = ['# 视频上传清单（交冠铭 · YouTube 学校频道）', '',
                 '上传后把「slug: YouTube视频ID」填进 `data/youtube_map.json`，重跑 build_news.py 即自动内嵌。', '']
    compressed = skipped = 0
    by_year = defaultdict(list)

    for p in live:
        year = str(p['year'])
        ydir = os.path.join(SITE, 'news', year)
        os.makedirs(os.path.join(ydir, 'img'), exist_ok=True)

        s_text = cc.convert(p['text'])
        title = make_title(p, s_text)
        desc = ' '.join(s_text.split())[:80] or title

        body = ''.join(f'      <p>{esc_autolink(ln.strip())}</p>\n'
                       for ln in s_text.split('\n') if ln.strip())

        figs, og_img = [], ''
        imgs = [m for m in p['media'][:MAX_IMGS] if not m.lower().endswith('.mp4')]
        for i, rel in enumerate(imgs):
            src = os.path.join(FB_ROOT, rel.replace('/', os.sep))
            name = f"{p['slug']}-{i}.jpg"
            dst = os.path.join(ydir, 'img', name)
            if os.path.exists(dst):
                skipped += 1
            else:
                im = Image.open(src).convert('RGB')
                im.thumbnail((MAX_SIDE, MAX_SIDE))
                im.save(dst, 'JPEG', quality=QUALITY, optimize=True)
                compressed += 1
            figs.append(f'      <figure><img src="img/{name}" loading="lazy" alt="{html.escape(title)}"></figure>\n')
            if not og_img:
                og_img = f'{BASE_URL}/news/{year}/img/{name}'

        mp4s = [m for m in p['media'] if m.lower().endswith('.mp4')]
        if mp4s:
            if p['slug'] in ymap:
                figs.insert(0, f'      <div class="video-embed"><iframe src="https://www.youtube.com/embed/{ymap[p["slug"]]}" '
                                f'allowfullscreen loading="lazy" title="{html.escape(title)}"></iframe></div>\n')
            else:
                figs.append('      <p class="video-note">📹 本篇含视频，收录于学校官方脸书。</p>\n')
                videos_md.append(f"- `{p['slug']}` {p['date']} {title}")
                videos_md += [f'  - `{os.path.join(FB_ROOT, m.replace("/", os.sep))}`' for m in mp4s]

        p['_title'], p['_desc'], p['_figs'], p['_body'], p['_og'] = title, desc, figs, body, og_img
        by_year[year].append(p)

    # write pages with prev/next within year
    total_pages = 0
    for year, plist in by_year.items():
        for i, p in enumerate(plist):
            prev_a = f'<a href="{plist[i-1]["slug"]}.html">← {html.escape(plist[i-1]["_title"][:18])}</a>' if i > 0 else '<span></span>'
            next_a = f'<a href="{plist[i+1]["slug"]}.html">{html.escape(plist[i+1]["_title"][:18])} →</a>' if i < len(plist) - 1 else '<span></span>'
            url = f'{BASE_URL}/news/{year}/{p["slug"]}.html'
            page = (tpl.replace('{{TITLE}}', html.escape(p['_title']))
                    .replace('{{DESCRIPTION}}', html.escape(p['_desc']))
                    .replace('{{URL}}', url).replace('{{OG_IMAGE}}', p['_og'])
                    .replace('{{DATE_ISO}}', p['date']).replace('{{DATE_HUMAN}}', p['date'])
                    .replace('{{YEAR}}', year)
                    .replace('{{BODY}}', p['_body']).replace('{{FIGURES}}', ''.join(p['_figs']))
                    .replace('{{PREV}}', prev_a).replace('{{NEXT}}', next_a))
            assert '{{' not in page, f'unfilled placeholder in {p["slug"]}'
            with open(os.path.join(SITE, 'news', year, f'{p["slug"]}.html'), 'w', encoding='utf-8') as f:
                f.write(page)
            total_pages += 1

    # year indexes + news root index
    years = sorted(by_year, reverse=True)
    def year_nav(cur):
        pills = ''.join(f'<a href="../{y}/index.html" class="{"on" if y == cur else ""}">{y}</a>' for y in years)
        return f'<nav class="year-nav">{pills}</nav>'

    def card(p, href_prefix=''):
        return (f'<div class="post-card"><time datetime="{p["date"]}">{p["date"]}</time>'
                f'<a href="{href_prefix}{p["slug"]}.html">{html.escape(p["_title"])}</a></div>')

    head = ('<!DOCTYPE html><html lang="zh-Hans"><head><meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>{t} · 南华独立中学</title><meta name="description" content="{d}">'
            '<link rel="stylesheet" href="{css}"></head><body>'
            '<header class="site-header"><a class="logo" href="{home}">南华独立中学</a>'
            '<nav><a href="{newsroot}">新闻动态</a></nav></header><main class="year-list">')
    foot = '</main><footer class="site-footer">© 曼绒县南华独立中学</footer></body></html>'

    for year in years:
        plist = sorted(by_year[year], key=lambda p: p['date'], reverse=True)
        cards = '\n'.join(card(p) for p in plist)
        page = (head.format(t=f'{year} 年新闻动态', d=f'曼绒县南华独立中学 {year} 年校园新闻档案，共 {len(plist)} 篇。',
                            css='../../assets/news.css', home='../../index.html', newsroot='../index.html')
                + f'<h1>{year} 年新闻动态（{len(plist)} 篇）</h1>' + year_nav(year) + cards + foot)
        with open(os.path.join(SITE, 'news', year, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(page)

    latest = sorted(live, key=lambda p: (p['date'], p['time']), reverse=True)[:12]
    cards = '\n'.join(card(p, f'{p["year"]}/') for p in latest)
    pills = ''.join(f'<a href="{y}/index.html">{y}</a>' for y in years)
    page = (head.format(t='新闻动态', d='曼绒县南华独立中学新闻档案（2018–2026），按年归档。',
                        css='../assets/news.css', home='../index.html', newsroot='index.html')
            + f'<h1>新闻动态</h1><nav class="year-nav">{pills}</nav><h2>最新</h2>' + cards + foot)
    with open(os.path.join(SITE, 'news', 'index.html'), 'w', encoding='utf-8') as f:
        f.write(page)

    with open(os.path.join(SITE, 'data', 'videos_for_youtube.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(videos_md) + '\n')

    assert total_pages == len(live), f'{total_pages} pages != {len(live)} posts'
    print(f'OK pages={total_pages} years={len(years)} img_compressed={compressed} img_skipped={skipped} '
          f'videos_pending={len([l for l in videos_md if l.startswith("- ")])}')


if __name__ == '__main__':
    main()
