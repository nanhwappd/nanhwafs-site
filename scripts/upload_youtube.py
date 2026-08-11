# -*- coding: utf-8 -*-
"""用 playwright 接管已登入的 Chrome（CDP），把备料好的影片逐支传上 YouTube，
每支传完立刻把 slug -> videoId 追加进 uploaded.jsonl（断点续传靠它）。

前置：Chrome 必须用专用 profile + --remote-debugging-port 启动，并已登入学校账号。
      （Chrome 136+ 对默认 profile 封 CDP，见 memory reference_browser_upload_limits）

用法：
  python upload_youtube.py --limit 3        # 试跑前 3 支
  python upload_youtube.py                  # 跑完剩下全部
  python upload_youtube.py --map            # 把 uploaded.jsonl 写成 data/youtube_map.json
"""
import argparse
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage_youtube as S                                   # noqa: E402
from playwright.sync_api import sync_playwright              # noqa: E402

CDP = 'http://127.0.0.1:9333'
CHANNEL = 'UC956RAKqzdspLPeoXV9v6aQ'
UPLOAD_URL = f'https://studio.youtube.com/channel/{CHANNEL}/videos/upload?d=ud'
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'uploaded.jsonl')
LOG = os.path.abspath(LOG)
VISIBILITY = 'UNLISTED'          # 林子策 2026-08-11 定：不公开，官网 iframe 照样能嵌


def jobs():
    """-> [(slug, video_title, staged_path), ...]，顺序 = md 顺序"""
    out = []
    for slug, _date, title, paths in S.parse_md():
        n = len(paths)
        for i in range(n):
            fname = S.stage_name(slug, i, n, title)
            path = os.path.join(S.STAGE_DIR, fname)
            # 上传后的正式标题：干净标题，不带 slug 前缀
            vt = title if n == 1 else f'{title} ({i + 1}/{n})'
            out.append((slug, vt[:100], path))
    return out


def done_keys():
    if not os.path.exists(LOG):
        return set()
    return {json.loads(ln)['file'] for ln in open(LOG, encoding='utf-8') if ln.strip()}


def upload_one(ctx, slug, title, path):
    # 每支一个全新分页，用完关掉。跨影片复用同一个分页会带着上一次的对话框状态，
    # 实测症状五花八门：拿到 ID 但零字节、重传时挂死等不到链接、beforeunload 打崩连线。
    pg = ctx.new_page()
    pg.on('dialog', lambda dl: dl.accept())
    pg.set_viewport_size({'width': 1400, 'height': 950})
    try:
        return _upload_in_tab(pg, slug, title, path)
    finally:
        try:
            pg.close()
        except Exception:
            pass


def _upload_in_tab(pg, slug, title, path):
    pg.goto(UPLOAD_URL, wait_until='domcontentloaded', timeout=120000)
    pg.wait_for_selector('input[type="file"]', state='attached', timeout=60000)
    pg.locator('input[type="file"]').first.set_input_files(path)

    d = pg.locator('ytcp-uploads-dialog')
    # 视频链接一出现就代表 YouTube 已经分配 ID
    link = d.locator('a[href*="youtu.be/"]').first
    # 同一个档若在频道上留着废弃的上传 session，这个链接永远不会出现。别等太久。
    link.wait_for(state='attached', timeout=240000)
    vid = link.get_attribute('href').rsplit('/', 1)[-1]

    # ⚠️ youtu.be 链接一分配就出现，此时字节还没传完。不等完就走＝列表显示「上传已中断」。
    # 只认 ytcp-video-upload-progress 这个元素：上传中含「正在上传」，传完转「上传完毕」。
    # 之后的「处理中」是服务器端的事，不需要浏览器留着。
    deadline = time.time() + 3600
    while True:
        txt = pg.evaluate("""() => {const e = document.querySelector('ytcp-video-upload-progress');
                              return e ? e.innerText.replace(/\\s+/g, ' ').trim() : ''}""")
        if txt and '正在上传' not in txt and ('上传完毕' in txt or '处理' in txt):
            break
        if time.time() > deadline:
            raise TimeoutError(f'upload stalled: {txt[:120]}')
        pg.wait_for_timeout(2000)

    tb = d.locator('#textbox').first          # 第一个 textbox = 标题
    tb.click()
    pg.keyboard.press('Control+A')
    pg.keyboard.press('Delete')
    pg.keyboard.type(title)
    pg.wait_for_timeout(600)

    d.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').first.click()
    pg.wait_for_timeout(400)

    for _ in range(3):                        # 详细信息 → 视频元素 → 检查 → 公开范围
        d.locator('#next-button').first.click()
        pg.wait_for_timeout(1200)

    d.locator(f'tp-yt-paper-radio-button[name="{VISIBILITY}"]').first.click()
    pg.wait_for_timeout(600)

    # Studio 会边填边自动保存，标题栏出现「正在保存…」。此时点保存或关分页会整个作废，
    # 症状＝影片留成草稿、标题回退成原始档名。必须等它落定。
    for _ in range(60):
        if '正在保存' not in d.inner_text():
            break
        pg.wait_for_timeout(1000)

    d.locator('#done-button').first.click()

    # 点保存后会弹「我们仍在检查你的内容…」，按钮是「仍然发布 / 返回」。
    # ⚠️ 别盲点 #close-button —— 那等于按「返回」，影片就停在草稿（本脚本前几版全栽在这）。
    dismissed = False
    for _ in range(90):
        pg.wait_for_timeout(1000)
        gone = pg.evaluate("""() => {const d = document.querySelector('ytcp-uploads-dialog');
                                return !d || !d.offsetParent}""")
        if gone:
            break
        if not dismissed:
            pub = pg.get_by_role('button', name='仍然发布')
            if pub.count() and pub.first.is_visible():
                pub.first.click()
                dismissed = True
                continue
        # 不要再点任何其他按钮：「关闭」会匹配到禁用的「保存并关闭」，
        # 别的按钮又可能等于「返回」。点完「仍然发布」对话框会自己收。
    pg.wait_for_timeout(2000)
    return vid


VIS_TEXT = {'UNLISTED': '不公开', 'PUBLIC': '公开', 'PRIVATE': '私享'}


def probe(ctx, vid):
    """读影片编辑页的原始信号，供 verify 与人工排错共用。"""
    pg = ctx.new_page()
    pg.on('dialog', lambda dl: dl.accept())
    try:
        pg.goto(f'https://studio.youtube.com/video/{vid}/edit',
                wait_until='domcontentloaded', timeout=120000)
        pg.wait_for_timeout(6000)
        return pg.evaluate("""() => {
          const pick = s => {const e = document.querySelector(s);
                             return e ? e.innerText.replace(/\\s+/g, ' ').trim().slice(0, 60) : null};
          return {title: pick('#title-textarea #textbox') || pick('#textbox'),
                  vis: pick('ytcp-video-metadata-visibility') || pick('#visibility-container')
                       || pick('ytcp-video-visibility-select'),
                  banner: pick('ytcp-video-info-message') || pick('#error-message'),
                  bodyHas: ['草稿', '处理中断', '视频未能上传', '不公开', '私享']
                           .filter(w => document.body.innerText.includes(w))};
        }""")
    finally:
        try:
            pg.close()
        except Exception:
            pass


def verify(ctx, vid, title):
    """回 None = 通过；回字串 = 失败原因。写 log 前必须过这关。"""
    r = probe(ctx, vid)
    if any(w in (r.get('bodyHas') or []) for w in ('草稿', '处理中断', '视频未能上传')):
        return f'状态异常 {r["bodyHas"]} raw={r}'
    want = VIS_TEXT[VISIBILITY]
    if want not in (r.get('vis') or '') and want not in (r.get('bodyHas') or []):
        return f'可见性不是{want} raw={r}'
    if (r.get('title') or '').strip() != title.strip():
        return f'标题不符 got={r.get("title")!r} want={title!r}'
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--start', type=int, default=0, help='跳过前 N 支（试跑时避开被污染的档）')
    ap.add_argument('--skip-slug', default='', help='逗号分隔，跳过这些 slug（频道上留着废弃上传的档）')
    ap.add_argument('--map', action='store_true')
    a = ap.parse_args()

    if a.map:
        ymap = {}
        for ln in open(LOG, encoding='utf-8'):
            if ln.strip():
                r = json.loads(ln)
                ymap.setdefault(r['slug'], []).append(r['id'])
        ymap = {k: (v[0] if len(v) == 1 else v) for k, v in sorted(ymap.items())}
        with open(S.OUT_MAP, 'w', encoding='utf-8') as f:
            json.dump(ymap, f, ensure_ascii=False, indent=2)
        n = sum(1 if isinstance(v, str) else len(v) for v in ymap.values())
        print(f'wrote {S.OUT_MAP}: posts={len(ymap)} videos={n}')
        return

    skip = {s.strip() for s in a.skip_slug.split(',') if s.strip()}
    todo = [j for j in jobs() if j[2] not in done_keys() and j[0] not in skip][a.start:]
    if a.limit:
        todo = todo[:a.limit]
    print(f'todo={len(todo)}')

    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        failures, streak = [], 0
        for i, (slug, title, path) in enumerate(todo, 1):
            t0 = time.time()
            try:
                vid = upload_one(ctx, slug, title, path)
                bad = verify(ctx, vid, title)
                if bad:
                    raise RuntimeError(f'verify: {bad}')
            except Exception as e:
                msg = f'{type(e).__name__}: {e}'[:200].replace('\n', ' ')
                print(f'[{i}/{len(todo)}] FAIL {slug} {os.path.basename(path)}: {msg}', flush=True)
                failures.append((slug, path, msg))
                streak += 1
                # 单支坏档不该毁掉整场；连续坏才是系统性问题，停下来
                if streak >= 5:
                    print('连续 5 支失败，停止', flush=True)
                    break
                continue
            streak = 0
            with open(LOG, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'slug': slug, 'id': vid, 'title': title,
                                    'file': path}, ensure_ascii=False) + '\n')
            print(f'[{i}/{len(todo)}] {slug} -> {vid}  {time.time() - t0:.0f}s  {title[:30]}', flush=True)

        print(f'\n=== done. ok={len(todo) - len(failures)} failed={len(failures)}')
        for slug, path, msg in failures:
            print(f'  FAILED {slug}  {os.path.basename(path)}  {msg[:90]}')


if __name__ == '__main__':
    main()
