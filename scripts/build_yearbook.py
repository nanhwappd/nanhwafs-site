"""Turn a scanned yearbook PDF into a self-contained web reader.

Each page of these scans is exactly one embedded JPEG, so the images are pulled
out directly rather than re-rendered -- no poppler, no resampling of a resample.
Output is one folder: index.html + pages/ + thumbs/.

    python scripts/build_yearbook.py "D:/数码馆藏扫描档案/校刊/1979.pdf" \
        --out "D:/数码馆藏扫描档案/_原型/1979" --title "南华中学校刊 1979"

ponytail: no framework, no lazy-load library, no flipbook dependency. The reader
is one HTML file; paging is three lines of JS and the browser's own <img>
decoding. Page-turn animation is deliberately absent -- on the 85MB 1962 scan the
thing that matters on a phone is bytes, not curl.
"""
import argparse
import io
import os
import sys

import fitz
from PIL import Image

PAGE_LONG_EDGE = 1600   # readable when pinch-zoomed, ~250KB/page
THUMB_LONG_EDGE = 240
PAGE_QUALITY = 80
THUMB_QUALITY = 72


def extract(pdf_path, out_dir):
    """Pull one JPEG per page; return list of (index, w, h) for the full-size set."""
    doc = fitz.open(pdf_path)
    pages_dir = os.path.join(out_dir, "pages")
    thumbs_dir = os.path.join(out_dir, "thumbs")
    os.makedirs(pages_dir, exist_ok=True)
    os.makedirs(thumbs_dir, exist_ok=True)

    meta = []
    for i, page in enumerate(doc, start=1):
        images = page.get_images(full=True)
        if len(images) == 1:
            raw = doc.extract_image(images[0][0])["image"]
            im = Image.open(io.BytesIO(raw))
        else:
            # mixed-content page: fall back to rendering it, so we never silently
            # drop text or a second photo that the single-image assumption misses
            pix = page.get_pixmap(dpi=200)
            im = Image.open(io.BytesIO(pix.tobytes("png")))
        im = im.convert("RGB")

        full = _fit(im, PAGE_LONG_EDGE)
        full.save(os.path.join(pages_dir, "p%03d.jpg" % i), "JPEG",
                  quality=PAGE_QUALITY, optimize=True, progressive=True)
        _fit(im, THUMB_LONG_EDGE).save(os.path.join(thumbs_dir, "t%03d.jpg" % i),
                                       "JPEG", quality=THUMB_QUALITY, optimize=True)
        meta.append((i, full.width, full.height))
    doc.close()
    return meta


def _fit(im, long_edge):
    w, h = im.size
    if max(w, h) <= long_edge:
        return im.copy()
    scale = long_edge / float(max(w, h))
    return im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)


HTML = """<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>__TITLE__ · 南华独立中学数码馆藏</title>
<meta name="description" content="__TITLE__ 全本数码翻阅，共 __COUNT__ 页。">
<style>
:root { --green:#3EB370; --green-deep:#1E5C3A; --cream:#F5F1E8; --ink:#222; --gold:#E8B84B;
  --serif:"Noto Serif SC","Source Han Serif SC","STZhongsong","SimSun",serif;
  --bar:4.25rem; }
* { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
html,body { height:100%; }
body { margin:0; background:#171512; color:var(--cream);
  font-family:"Noto Sans SC","Microsoft YaHei",system-ui,sans-serif;
  overscroll-behavior:none; }

header { position:fixed; inset:0 0 auto 0; z-index:3; display:flex; align-items:center; gap:.75rem;
  padding:.7rem 1rem; background:linear-gradient(#171512ee,#17151200);
  transition:opacity .25s; }
header.hide { opacity:0; pointer-events:none; }
header a.back { color:var(--cream); text-decoration:none; font-size:1.4rem; line-height:1; opacity:.75; }
header h1 { margin:0; font-family:var(--serif); font-weight:700; font-size:1rem; letter-spacing:.02em; }

.stage { position:absolute; inset:0 0 var(--bar) 0; display:flex; align-items:center;
  justify-content:center; padding:.5rem; }
.stage img { max-width:100%; max-height:100%; object-fit:contain; display:block;
  box-shadow:0 2px 24px rgba(0,0,0,.6); background:#e8e4da; }

/* tap zones: outer thirds page, middle toggles chrome */
.zone { position:absolute; top:0; bottom:0; width:33%; z-index:2; border:0; background:transparent;
  cursor:pointer; }
.zone.prev { left:0; } .zone.next { right:0; }
.zone:focus-visible { outline:2px solid var(--gold); outline-offset:-4px; }

footer { position:fixed; inset:auto 0 0 0; z-index:3; height:var(--bar);
  display:flex; align-items:center; gap:.9rem; padding:0 1rem calc(env(safe-area-inset-bottom));
  background:linear-gradient(#17151200,#171512ee); transition:opacity .25s; }
footer.hide { opacity:0; pointer-events:none; }
#counter { font-family:var(--serif); font-size:.95rem; min-width:4.5rem; text-align:center;
  background:none; border:1px solid #ffffff2e; color:var(--cream); border-radius:2rem;
  padding:.35rem .7rem; cursor:pointer; }
#counter:hover, #counter:focus-visible { border-color:var(--gold); }
#slider { flex:1; -webkit-appearance:none; appearance:none; height:3px; border-radius:2px;
  background:#ffffff33; }
#slider::-webkit-slider-thumb { -webkit-appearance:none; width:16px; height:16px; border-radius:50%;
  background:var(--gold); cursor:pointer; }
#slider::-moz-range-thumb { width:16px; height:16px; border:0; border-radius:50%; background:var(--gold); }

/* jump grid */
#grid { position:fixed; inset:0; z-index:4; background:#171512f2; overflow:auto; padding:1rem;
  display:none; }
#grid.open { display:block; }
#grid .inner { display:grid; gap:.6rem; grid-template-columns:repeat(auto-fill,minmax(88px,1fr));
  max-width:70rem; margin:0 auto; }
#grid button { border:1px solid #ffffff1f; background:none; padding:0; border-radius:.25rem;
  cursor:pointer; overflow:hidden; line-height:0; }
#grid button.here { border-color:var(--gold); }
#grid img { width:100%; height:auto; display:block; }
#grid b { display:block; font:400 .72rem/1.9 system-ui; color:#cfc9bb; text-align:center; }
#gridClose { position:sticky; top:0; float:right; z-index:5; background:#2a2622; color:var(--cream);
  border:1px solid #ffffff2e; border-radius:2rem; padding:.4rem .95rem; font-size:.9rem; cursor:pointer; }
@media (min-width:900px) { header h1 { font-size:1.1rem; } }
</style>
</head>
<body>
<header id="chromeTop">
  <a class="back" href="../index.html" title="返回书架">&#8592;</a>
  <h1>__TITLE__</h1>
</header>

<div class="stage"><img id="page" alt="第 1 页" src="pages/p001.jpg"></div>
<button class="zone prev" id="zPrev" aria-label="上一页"></button>
<button class="zone next" id="zNext" aria-label="下一页"></button>

<footer id="chromeBot">
  <button id="counter" aria-haspopup="dialog">1 / __COUNT__</button>
  <input id="slider" type="range" min="1" max="__COUNT__" value="1" aria-label="跳到某页">
</footer>

<div id="grid" role="dialog" aria-label="页面总览">
  <button id="gridClose">关闭</button>
  <div class="inner" id="gridInner"></div>
</div>

<script>
const TOTAL = __COUNT__;
const img = document.getElementById('page');
const counter = document.getElementById('counter');
const slider = document.getElementById('slider');
const grid = document.getElementById('grid');
const gridInner = document.getElementById('gridInner');
const top_ = document.getElementById('chromeTop');
const bot = document.getElementById('chromeBot');
let cur = 1;
const pad = n => String(n).padStart(3, '0');
const src = n => 'pages/p' + pad(n) + '.jpg';

function preload(n) {
  [n + 1, n + 2, n - 1].filter(i => i >= 1 && i <= TOTAL)
    .forEach(i => { const p = new Image(); p.src = src(i); });
}
function go(n) {
  n = Math.min(TOTAL, Math.max(1, n));
  if (n === cur) return;
  cur = n;
  img.src = src(n);
  img.alt = '第 ' + n + ' 页';
  counter.textContent = n + ' / ' + TOTAL;
  slider.value = n;
  location.replace('#p=' + n);
  preload(n);
  [...gridInner.children].forEach((b, i) => b.classList.toggle('here', i + 1 === n));
}
document.getElementById('zPrev').onclick = () => go(cur - 1);
document.getElementById('zNext').onclick = () => go(cur + 1);
slider.oninput = e => go(+e.target.value);
addEventListener('keydown', e => {
  if (e.key === 'ArrowLeft' || e.key === 'PageUp') go(cur - 1);
  else if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') go(cur + 1);
  else if (e.key === 'Home') go(1);
  else if (e.key === 'End') go(TOTAL);
  else if (e.key === 'Escape') grid.classList.remove('open');
});
let x0 = null;
addEventListener('touchstart', e => { x0 = e.touches[0].clientX; }, {passive:true});
addEventListener('touchend', e => {
  if (x0 === null) return;
  const dx = e.changedTouches[0].clientX - x0;
  if (Math.abs(dx) > 45) go(cur + (dx < 0 ? 1 : -1));
  x0 = null;
}, {passive:true});

// build the jump grid once, lazily on first open
let built = false;
counter.onclick = () => {
  if (!built) {
    const frag = document.createDocumentFragment();
    for (let i = 1; i <= TOTAL; i++) {
      const b = document.createElement('button');
      b.innerHTML = '<img loading="lazy" src="thumbs/t' + pad(i) + '.jpg" alt=""><b>' + i + '</b>';
      b.onclick = () => { go(i); grid.classList.remove('open'); };
      if (i === cur) b.className = 'here';
      frag.appendChild(b);
    }
    gridInner.appendChild(frag);
    built = true;
  }
  grid.classList.add('open');
};
document.getElementById('gridClose').onclick = () => grid.classList.remove('open');

const start = parseInt((location.hash.match(/p=(\\d+)/) || [])[1], 10);
if (start) { cur = 0; go(start); } else { preload(1); }
</script>
</body>
</html>
"""


def write_html(out_dir, title, count):
    html = HTML.replace("__TITLE__", title).replace("__COUNT__", str(count))
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", required=True)
    args = ap.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    meta = extract(args.pdf, args.out)
    write_html(args.out, args.title, len(meta))

    total = sum(
        os.path.getsize(os.path.join(dp, f))
        for dp, _dn, fn in os.walk(args.out) for f in fn
    )
    print("%s -> %d pages, %.1f MB total" % (args.title, len(meta), total / 1024.0 / 1024))

    # self-check: every page the HTML can reach must exist at both sizes
    for i, _w, _h in meta:
        for sub, prefix in (("pages", "p"), ("thumbs", "t")):
            f = os.path.join(args.out, sub, "%s%03d.jpg" % (prefix, i))
            assert os.path.getsize(f) > 1024, "missing or truncated: " + f
    with open(os.path.join(args.out, "index.html"), encoding="utf-8") as fh:
        page = fh.read()
    assert "__" not in page.replace("__TITLE__x", ""), "unfilled placeholder left in HTML"
    assert str(len(meta)) in page, "page count not injected"
    print("check OK: %d pages x2 sizes on disk, no unfilled placeholders" % len(meta))
    return 0


if __name__ == "__main__":
    sys.exit(main())
