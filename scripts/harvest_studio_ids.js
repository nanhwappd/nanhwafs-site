// 在 YouTube Studio「频道内容 → 视频」页的控制台跑，翻页收集全部 <videoId> <标题>。
// 输出直接喂：python scripts\stage_youtube.py map ids.txt
// 不限可见性——Unlisted / Private 一样抓得到（读的是 Studio 自己的列表）。
(async () => {
  const map = new Map();

  // 优先取 /video/<id>/ 链接；未水合的行退回缩图 URL 里的 /vi/<id>/
  const idOf = (r) => {
    const a = r.querySelector('a[href*="/video/"]');
    const m = a && (a.getAttribute('href') || '').match(/\/video\/([\w-]{11})\//);
    if (m) return m[1];
    const im = [...r.querySelectorAll('img')].map(i => i.src)
      .find(s => /\/vi\/[\w-]{11}\//.test(s || ''));
    return im ? im.match(/\/vi\/([\w-]{11})\//)[1] : null;
  };

  const grab = () => {
    for (const r of document.querySelectorAll('ytcp-video-row')) {
      const id = idOf(r);
      const t = r.querySelector('#video-title');
      const title = t ? t.textContent.trim() : '';
      if (id && title) map.set(id, title);
    }
  };

  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const scroller = document.querySelector('#main') || document.scrollingElement;

  for (let page = 0; page < 40; page++) {
    // 滚到底把本页所有行渲染出来
    let stall = 0, last = -1;
    for (let i = 0; i < 40; i++) {
      grab();
      scroller.scrollTop = scroller.scrollHeight;
      await sleep(600);
      grab();
      stall = (map.size === last) ? stall + 1 : 0;
      last = map.size;
      if (stall >= 3) break;
    }
    const next = document.querySelector('ytcp-icon-button#navigate-after:not([disabled])');
    if (!next || next.hasAttribute('disabled')) break;
    next.click();
    await sleep(2500);
    scroller.scrollTop = 0;
  }

  const lines = [...map].map(([id, t]) => `${id} ${t}`).join('\n');
  console.log(`harvested=${map.size}`);
  try { await navigator.clipboard.writeText(lines); console.log('已复制到剪贴板'); } catch (e) { }
  return lines;
})();
