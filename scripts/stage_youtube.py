# -*- coding: utf-8 -*-
"""把 data/videos_for_youtube.md 里的 163 个 mp4 备料成一个可直接拖进 YouTube Studio 的文件夹，
上传后再从频道反查视频 ID，自动生成 data/youtube_map.json。

用法：
  python stage_youtube.py stage
      硬链接（不占额外空间）到 D:\\YouTube上传_官网141篇\\，文件名 = 上传后的默认标题，
      开头带 slug，供上传后机器反查。

  yt-dlp --flat-playlist --print "%(id)s %(title)s" <频道uploads网址> > ids.txt
  python stage_youtube.py map ids.txt
      按标题开头的 slug 反查，写出 data/youtube_map.json（一篇多视频自动写成列表）。

  python stage_youtube.py selftest
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')  # ponytail: 控制台默认 cp1252，中文 print 会炸

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD = os.path.join(SITE, 'data', 'videos_for_youtube.md')
OUT_MAP = os.path.join(SITE, 'data', 'youtube_map.json')
STAGE_DIR = r'D:\YouTube上传_官网141篇'

# ponytail: YouTube 标题禁 < >，Windows 文件名再禁一批；其余原样保留
BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def parse_md():
    """-> [(slug, date, title, [path, ...]), ...]"""
    items, cur = [], None
    for ln in open(MD, encoding='utf-8'):
        m = re.match(r'^- `(\S+)` (\S+) (.*)$', ln.rstrip('\n'))
        if m:
            cur = (m.group(1), m.group(2), m.group(3), [])
            items.append(cur)
            continue
        m = re.match(r'^  - `(.+)`$', ln.rstrip('\n'))
        if m and cur:
            cur[3].append(m.group(1))
    return items


def stage_name(slug, idx, n, title):
    """上传后的默认标题 = 这个文件名（去扩展名）。slug 前缀是反查的唯一键。"""
    # ponytail: 分隔符不能用 "/"，会被当成路径分隔（WinError 3）
    suffix = f' ({idx + 1}-{n})' if n > 1 else ''
    t = BAD.sub(' ', title).strip()
    name = f'{slug} {t}{suffix}'
    return name[:90].strip() + '.mp4'   # YouTube 标题上限 100，留余量


def do_stage():
    os.makedirs(STAGE_DIR, exist_ok=True)
    linked = copied = existed = 0
    for slug, _date, title, paths in parse_md():
        for i, src in enumerate(paths):
            dst = os.path.join(STAGE_DIR, stage_name(slug, i, len(paths), title))
            if os.path.exists(dst):
                existed += 1
                continue
            try:
                os.link(src, dst)          # 同一 NTFS 卷，零额外空间
                linked += 1
            except OSError:
                import shutil
                shutil.copy2(src, dst)
                copied += 1
    print(f'stage_dir={STAGE_DIR}')
    print(f'linked={linked} copied={copied} existed={existed} total={linked + copied + existed}')


def do_map(ids_file):
    """ids.txt 每行：<videoId> <title>；title 开头是 slug。"""
    known = {slug for slug, _d, _t, _p in parse_md()}
    ymap, unmatched = {}, []
    for ln in open(ids_file, encoding='utf-8'):
        ln = ln.strip()
        if not ln:
            continue
        vid, _, title = ln.partition(' ')
        slug = title.split(' ', 1)[0]
        if slug in known:
            ymap.setdefault(slug, []).append(vid)
        else:
            unmatched.append(ln[:80])
    # 单视频的写成字符串，读起来干净；build_news.py 两种都吃
    ymap = {k: (v[0] if len(v) == 1 else v) for k, v in sorted(ymap.items())}
    with open(OUT_MAP, 'w', encoding='utf-8') as f:
        json.dump(ymap, f, ensure_ascii=False, indent=2)
    n_vids = sum(1 if isinstance(v, str) else len(v) for v in ymap.values())
    print(f'wrote {OUT_MAP}: posts={len(ymap)}/{len(known)} videos={n_vids}')
    if unmatched:
        print(f'unmatched={len(unmatched)}（频道上非本批的视频，正常）:')
        for u in unmatched[:5]:
            print('  ', u)


def selftest():
    assert stage_name('20191123-2', 0, 1, '营歌：我要飞') == '20191123-2 营歌：我要飞.mp4'
    assert stage_name('20180712-1', 1, 3, 'A/B 测试') == '20180712-1 A B 测试 (2-3).mp4'
    # 文件名里绝不能出现路径分隔符，否则 os.path.join 会拐进子目录
    for slug, i, n, t in (('s', 1, 3, 'x'), ('s', 0, 1, 'a/b\\c')):
        assert not (set(stage_name(slug, i, n, t)) & set('/\\')), stage_name(slug, i, n, t)
    # 反查：文件名去扩展名 = 标题，首个空格前是 slug
    for slug, n in (('20191123-2', 1), ('20180712-1', 3)):
        title = stage_name(slug, 0, n, '园游会')[:-4]
        assert title.split(' ', 1)[0] == slug, title
    items = parse_md()
    assert len(items) == 141, len(items)
    assert sum(len(p) for _s, _d, _t, p in items) == 163
    assert len({s for s, *_ in items}) == 141, 'slug 必须唯一，否则反查会串'
    print('selftest ok: 141 posts / 163 files, slug 唯一, 命名可逆')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'selftest'
    if cmd == 'stage':
        do_stage()
    elif cmd == 'map':
        do_map(sys.argv[2])
    else:
        selftest()
