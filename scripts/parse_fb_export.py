# -*- coding: utf-8 -*-
"""Parse Facebook page export (profile_posts_1.html) -> data/posts.json + data/AUDIT.md
Usage: python parse_fb_export.py [export_root]
"""
import sys, os, re, json, html
from collections import Counter
from datetime import datetime

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"D:\Fb_AllRecord"
SRC = os.path.join(ROOT, "this_profile's_activity_across_facebook", "posts", "profile_posts_1.html")
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PAGE_NAME = "曼絨縣南華獨立中學 Nan Hwa High School"

MEDIA_RE = re.compile(r'href="([^"]+\.(?:jpg|png|gif|mp4))"', re.I)
TS_RE = re.compile(r'<div class="_a72d">([^<]+)</div>')
H2_RE = re.compile(r'<h2[^>]*>([^<]+)</h2>')
PIN_RE = re.compile(r'<div class="_2pin">(.*?)</div></div>', re.S)  # ponytail: greedy-enough for flat export markup
TAG_RE = re.compile(r'<[^>]+>')
URL_RE = re.compile(r'https?://[^\s<"]+')


def strip_tags(fragment):
    text = re.sub(r'<br\s*/?>', '\n', fragment)
    text = TAG_RE.sub('', text)
    return html.unescape(text).strip()


def classify(h2):
    if 'photo' in h2: return 'photo'
    if 'video' in h2: return 'video'
    if 'status' in h2: return 'status'
    if 'shared a link' in h2: return 'shared_link'
    if 'shared a post' in h2: return 'shared_post'
    if 'shared an album' in h2: return 'shared_album'
    return 'other'


def main():
    raw = open(SRC, encoding='utf-8').read()
    sections = raw.split('<section class="_a6-g"')[1:]
    posts = []
    for i, sec in enumerate(sections):
        h2_m = H2_RE.search(sec)
        ts_m = TS_RE.search(sec)
        assert ts_m, f"section {i} missing timestamp"
        ts = datetime.strptime(ts_m.group(1), "%b %d, %Y %I:%M:%S %p")
        h2 = html.unescape(h2_m.group(1)).replace(PAGE_NAME, '').strip() if h2_m else ''

        media = []
        for m in MEDIA_RE.finditer(sec):
            path = html.unescape(m.group(1))
            if path not in media:
                media.append(path)

        # text: from _2pin blocks that contain no media markup and aren't "Updated ..." stamps
        texts = []
        for pin in PIN_RE.finditer(sec):
            frag = pin.group(1)
            if '<img' in frag or '<video' in frag:
                continue
            t = strip_tags(frag)
            if not t or t.startswith('Updated '):
                continue
            texts.append(t)
        text = max(texts, key=len) if texts else ''
        # fallback: photo caption when no standalone text block
        if not text:
            cap = re.search(r'<div class="_3-95">(.*?)</div>', sec, re.S)
            if cap:
                text = strip_tags(cap.group(1))

        ptype = classify(h2)
        links = [u for u in URL_RE.findall(text)]
        is_filler = ptype in ('shared_link', 'shared_post') and len(re.sub(URL_RE, '', text).strip()) == 0

        posts.append({
            'id': i,
            'date': ts.strftime('%Y-%m-%d'),
            'time': ts.strftime('%H:%M:%S'),
            'year': ts.year,
            'type': ptype,
            'action': h2,
            'text': text,
            'media': media,
            'links': links,
            'is_filler': is_filler,
        })

    posts.sort(key=lambda p: (p['date'], p['time']))
    assert len(posts) == 1241, f"expected 1241 posts, got {len(posts)}"

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, 'posts.json'), 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=1)

    # audit
    media_root = ROOT
    referenced = {m for p in posts for m in p['media']}
    missing = [m for m in sorted(referenced) if not os.path.exists(os.path.join(media_root, m.replace('/', os.sep)))]
    on_disk = 8484  # from survey 2026-07-06
    years = Counter(p['year'] for p in posts)
    types = Counter(p['type'] for p in posts)
    fillers = sum(p['is_filler'] for p in posts)
    no_text = sum(1 for p in posts if not p['text'] and not p['is_filler'])
    long_posts = sum(1 for p in posts if len(p['text']) >= 300)

    lines = [
        '# FB 全档内容普查报告（P1 · 自动生成）', '',
        f'来源：`{SRC}`', f'生成：{datetime.now():%Y-%m-%d %H:%M}', '',
        f'- 帖子总数：**{len(posts)}**（校验通过 =1241）',
        f'- 水贴（纯转发无正文，将不入站）：**{fillers}**',
        f'- 有媒体的帖子引用媒体文件：**{len(referenced)}** 个（磁盘媒体总数 {on_disk}，差额为相册未挂帖/头像封面类）',
        f'- 引用但磁盘缺失：**{len(missing)}** 个',
        f'- 无正文且非水贴（生成页面时需占位标题）：**{no_text}**',
        f'- 长文帖（>=300字，新闻报道主力）：**{long_posts}**', '',
        '## 按年分布', '',
        '| 年份 | 帖数 | 水贴 | 长文帖 |', '|---|---|---|---|',
    ]
    for y in sorted(years):
        yf = sum(1 for p in posts if p['year'] == y and p['is_filler'])
        yl = sum(1 for p in posts if p['year'] == y and len(p['text']) >= 300)
        lines.append(f'| {y} | {years[y]} | {yf} | {yl} |')
    lines += ['', '## 按类型', '', '| 类型 | 数量 |', '|---|---|']
    for t, c in types.most_common():
        lines.append(f'| {t} | {c} |')
    if missing:
        lines += ['', '## 缺失媒体（引用了但磁盘没有）', ''] + [f'- `{m}`' for m in missing[:50]]
    with open(os.path.join(OUT_DIR, 'AUDIT.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    print(f'OK posts={len(posts)} fillers={fillers} referenced_media={len(referenced)} missing={len(missing)}')


if __name__ == '__main__':
    main()
