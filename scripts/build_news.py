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
MAX_SIDE, QUALITY, MAX_IMGS = 1600, 82, 8   # 08-23 他批准 1280/q78 → 1600/q82（+180MB，仍在 GH Pages 1GB 内）
THUMB_SIDE, THUMB_Q = 480, 72          # 索引卡片缩图：从 repo 内 1280 图再缩，不回头读 D:\Fb_AllRecord
YT_THUMB = 'https://i.ytimg.com/vi/{}/hqdefault.jpg'   # 480x360，mqdefault 在 2x 手机屏会糊
MIN_CARD_AR = 2 / 3          # 长过 2:3 的图，卡片按 2:3 收住（Pinterest 同样的下限）

cc = OpenCC('t2s')
URL_RE = re.compile(r'https?://[^\s<]+')

# 全站简体，但人名用字不随简繁走（校方定名）。t2s 之后按此表改回。
NAME_KEEP = {'陈丽冰': '陳麗冰'}
# 2022 起脸书发布转密集、图文品质稳定 → 照片卡；2021 及之前走紧凑列表（他 08-23 定的分水岭）
PHOTO_CARD_FROM = 2022
FB_PAGE = 'https://www.facebook.com/sekolahtingginanhwa'   # 导出档无单篇 permalink，只能链专页


def fix_names(s):
    for simp, keep in NAME_KEEP.items():
        s = s.replace(simp, keep)
    return s


def esc_autolink(line):
    out, last = [], 0
    for m in URL_RE.finditer(line):
        out.append(html.escape(line[last:m.start()]))
        u = m.group(0)
        out.append(f'<a href="{html.escape(u)}" rel="nofollow">{html.escape(u)}</a>')
        last = m.end()
    out.append(html.escape(line[last:]))
    return ''.join(out)


# FB 贴文第一行中位数只有 11 字（常是装饰性短句、日期戳或断句），单取第一行 = 标题像被截断。
# 规则：去掉首尾装饰 → 跳过纯日期行 → 首行没写完就接下一行 → 句末标点处停。
EMOJI = '\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍〰〽←-⇿'
LEAD_RE = re.compile(f'^[{EMOJI}\\s]+')
TAIL_RE = re.compile(f'[{EMOJI}\\s]+$')
DATE_LINE_RE = re.compile(r'^\d{1,2}\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*\d{2,4}$')
DANGLING = '之：:，,、·|-—～~…'      # 行尾出现即视为没写完，可接下一行
TERMINAL = '。！？!?」』）)'           # 行尾出现即视为写完，不再接
JOIN_MIN, JOIN_MAX, TITLE_MAX, CUT_MAX, SENT_MIN = 12, 30, 48, 40, 8


def strip_decor(line):
    line = TAIL_RE.sub('', LEAD_RE.sub('', line))     # 只削首尾，行内 emoji 是作者的分隔符，留着
    while len(line) > 2 and line[0] in '【[' and line[-1] in '】]':
        line = TAIL_RE.sub('', LEAD_RE.sub('', line[1:-1]))
    return line.strip('　 ')


def make_title(p, s_text):
    lines = [strip_decor(l) for l in s_text.split('\n')
             if l.strip() and not URL_RE.fullmatch(l.strip())]
    lines = [l for l in lines if l and not DATE_LINE_RE.match(l)]   # 日期戳不是标题
    if not lines:
        return f"{p['year']} 年 {int(p['date'][5:7])} 月校园动态"
    t, i = lines[0], 1
    while i < len(lines) and t[-1] not in TERMINAL and (len(t) < JOIN_MIN or t[-1] in DANGLING):
        if len(t) + len(lines[i]) > JOIN_MAX:
            break
        t = t + ('' if t[-1] in DANGLING else '·') + lines[i]
        i += 1
    m = re.search(r'[。！？]', t)          # 行内出现句号 = 这是正文段落不是标题，取第一句
    if m and SENT_MIN <= m.start() < len(t) - 1:   # 门槛比 JOIN_MIN 低：8 字的完整短句也是好标题
        t = t[:m.start()]
    if len(t) > TITLE_MAX:      # 整篇挤成一行的贴文：切在句读处，别硬切在词中间
        head = t[:CUT_MAX]
        cut = max(head.rfind(c) for c in '。！？；')
        if cut < JOIN_MIN:
            cut = max(head.rfind(c) for c in '，、：')
        return head[:cut] if cut >= JOIN_MIN else head.rstrip('　 ') + '…'
    return t.rstrip('。！？!?' + DANGLING + ' 　')


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
                 '上传后把「slug: YouTube视频ID」填进 `data/youtube_map.json`，重跑 build_news.py 即自动内嵌。',
                 '一篇多个视频时值写成列表：`"20191123-2": ["ID1", "ID2"]`。',
                 '流程见 `scripts/stage_youtube.py`（备料 → 拖拽上传 → 反查生成 map）。', '']
    compressed = skipped = thumbed = 0
    by_year = defaultdict(list)

    for p in live:
        year = str(p['year'])
        ydir = os.path.join(SITE, 'news', year)
        os.makedirs(os.path.join(ydir, 'img'), exist_ok=True)

        s_text = fix_names(cc.convert(p['text']))
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
            # 幂等＋可升级：已存在但边长小于当前上限、而原档还更大时，重压一遍（不删档，直接覆写）
            stale = os.path.exists(dst) and max(Image.open(dst).size) < MAX_SIDE \
                and max(Image.open(src).size) > max(Image.open(dst).size)
            if os.path.exists(dst) and not stale:
                skipped += 1
            else:
                im = Image.open(src).convert('RGB')
                im.thumbnail((MAX_SIDE, MAX_SIDE))
                im.save(dst, 'JPEG', quality=QUALITY, optimize=True)
                compressed += 1
                if stale:                       # 主图换了，卡片缩图跟着重出
                    old_t = os.path.join(ydir, 'img', f"{p['slug']}-t.jpg")
                    if i == 0 and os.path.exists(old_t):
                        os.remove(old_t)
            # 包一层链接＝原生看大图。正文里图只渲染 682px(桌面)/337px(手机)，剪报内文非放大不可读
            figs.append(f'      <figure><a href="img/{name}" target="_blank" rel="noopener" '
                        f'title="点开看原图"><img src="img/{name}" loading="lazy" '
                        f'alt="{html.escape(title)}"></a></figure>\n')
            if not og_img:
                og_img = f'{BASE_URL}/news/{year}/img/{name}'
            if i == 0:                      # 首图再出一张 480px 缩图给索引卡片用
                tname = f"{p['slug']}-t.jpg"
                tdst = os.path.join(ydir, 'img', tname)
                if not os.path.exists(tdst):
                    tim = Image.open(dst)
                    tim.thumbnail((THUMB_SIDE, THUMB_SIDE))
                    tim.save(tdst, 'JPEG', quality=THUMB_Q, optimize=True)
                    thumbed += 1
                p['_thumb'] = f'img/{tname}'
                # 卡片按图片自己的比例长，不裁（他 08-23 定：不裁图源）。
                # 只对极端长图设下限 2:3——Pinterest 的推荐比例，再长下去一张卡就吃掉整个手机屏。
                tw, th = Image.open(tdst).size
                p['_ar'] = f'{tw}/{th}' if tw / th >= MIN_CARD_AR else '2/3'

        mp4s = [m for m in p['media'] if m.lower().endswith('.mp4')]
        if mp4s:
            if p['slug'] in ymap:
                # ponytail: value may be one id or a list of ids (22 posts have 2+ videos)
                vids = ymap[p['slug']]
                vids = [vids] if isinstance(vids, str) else vids
                p['_yt'] = vids[0]          # 索引卡片用 YouTube 封面当预览
                figs[0:0] = [f'      <div class="video-embed"><iframe src="https://www.youtube.com/embed/{v}" '
                             f'allowfullscreen loading="lazy" title="{html.escape(title)}"></iframe></div>\n'
                             for v in vids]
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
                    .replace('{{YEAR}}', year).replace('{{FB_PAGE}}', FB_PAGE)
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

    def compact_row(p, href_prefix=''):
        # 深档年份（≤2021）：一行一条，日期＋标题，有图/有片只给一个小记号
        mark = '▶' if p.get('_yt') else ('◻' if p.get('_thumb') else '')
        return (f'<a class="post-row" href="{href_prefix}{p["slug"]}.html">'
                f'<time datetime="{p["date"]}">{p["date"]}</time>'
                f'<span class="t">{html.escape(p["_title"])}</span>'
                f'<span class="mark" aria-hidden="true">{mark}</span></a>')

    def card(p, href_prefix=''):
        # 整张卡是入口（照片/视频封面当钩子），无媒体的贴文走纯文字变体，不留空图框
        if p.get('_yt'):
            # YouTube hqdefault 一律 480x360
            media = (f'<span class="thumb is-video" style="--card-ar:4/3"><img '
                     f'src="{YT_THUMB.format(p["_yt"])}" loading="lazy" alt=""></span>')
        elif p.get('_thumb'):
            media = (f'<span class="thumb" style="--card-ar:{p["_ar"]}"><img '
                     f'src="{href_prefix}{p["_thumb"]}" loading="lazy" alt=""></span>')
        else:
            media = ''
        return (f'<a class="post-card{"" if media else " is-text"}" href="{href_prefix}{p["slug"]}.html">'
                f'{media}<span class="txt"><time datetime="{p["date"]}">{p["date"]}</time>'
                f'<span class="t">{html.escape(p["_title"])}</span></span></a>')

    head = ('<!DOCTYPE html><html lang="zh-Hans"><head><meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>{t} · 南华独立中学</title><meta name="description" content="{d}">'
            '<link rel="stylesheet" href="{css}"></head><body>'
            '<header class="site-header"><a class="logo" href="{home}">南华独立中学</a>'
            '<nav><a href="{newsroot}">新闻动态</a></nav></header><main class="year-list">')
    foot = '</main><footer class="site-footer">© 曼绒县南华独立中学</footer></body></html>'

    for year in years:
        plist = sorted(by_year[year], key=lambda p: p['date'], reverse=True)
        if int(year) >= PHOTO_CARD_FROM:
            cards = '<div class="cards">' + '\n'.join(card(p) for p in plist) + '</div>'
        else:
            cards = '<div class="rows">' + '\n'.join(compact_row(p) for p in plist) + '</div>'
        page = (head.format(t=f'{year} 年新闻动态', d=f'曼绒县南华独立中学 {year} 年校园新闻档案，共 {len(plist)} 篇。',
                            css='../../assets/news.css', home='../../index.html', newsroot='../index.html')
                + f'<h1>{year} 年新闻动态（{len(plist)} 篇）</h1>' + year_nav(year) + cards + foot)
        with open(os.path.join(SITE, 'news', year, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(page)

    latest = sorted(live, key=lambda p: (p['date'], p['time']), reverse=True)[:12]
    cards = '<div class="cards">' + '\n'.join(card(p, f'{p["year"]}/') for p in latest) + '</div>'
    pills = ''.join(f'<a href="{y}/index.html">{y}</a>' for y in years)
    page = (head.format(t='新闻动态', d='曼绒县南华独立中学新闻档案（2018–2026），按年归档。',
                        css='../assets/news.css', home='../index.html', newsroot='index.html')
            + f'<h1>新闻动态</h1><nav class="year-nav">{pills}</nav><h2>最新</h2>' + cards + foot)
    with open(os.path.join(SITE, 'news', 'index.html'), 'w', encoding='utf-8') as f:
        f.write(page)

    with open(os.path.join(SITE, 'data', 'videos_for_youtube.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(videos_md) + '\n')

    assert total_pages == len(live), f'{total_pages} pages != {len(live)} posts'
    n_yt = sum(1 for p in live if p.get('_yt'))                                 # 与 card() 的取用顺序一致
    n_thumb = sum(1 for p in live if not p.get('_yt') and p.get('_thumb'))
    n_text = sum(1 for p in live if not p.get('_yt') and not p.get('_thumb'))
    assert n_thumb + n_yt + n_text == len(live), 'card variants must partition all posts'
    print(f'OK pages={total_pages} years={len(years)} img_compressed={compressed} img_skipped={skipped} '
          f'thumbs_new={thumbed} cards_photo={n_thumb} cards_video={n_yt} cards_text={n_text} '
          f'videos_pending={len([l for l in videos_md if l.startswith("- ")])}')


if __name__ == '__main__':
    main()
