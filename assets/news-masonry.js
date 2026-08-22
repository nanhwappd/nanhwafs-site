/* 卡片补位：把每张卡的实际高度换算成 grid 行数，下一则新闻就能贴着上一则的底部往上补，
   不再等同排最高的那张。列数仍由 news.css 的断点决定，这里只负责算数字。
   渐进增强：没有 JS 就退回 align-items:start（参差但完全可用），所以 grid-auto-rows
   只在本脚本加上 .js-masonry 之后才生效——否则卡片会被压成 1px 高。 */
(function () {
  var grid = document.querySelector('.cards');
  if (!grid || !('gridRowEnd' in grid.style)) return;
  var ROW = 1;   // 1px 行高：span 数字大但无成本，4px 时量化误差会累成 20px 的洞（实测）

  // row-gap 归零、卡间距改用 margin-bottom，步长才真的是 ROW。
  // 留着 gap 的话有效步长 = ROW + gap = 17px，ceil 每张平均虚占 8.5px，实测累成 33px 的洞。
  function fit() {
    var gap = parseFloat(getComputedStyle(grid).rowGap) || 0;
    for (var i = 0; i < grid.children.length; i++) {
      var c = grid.children[i];
      var mb = parseFloat(getComputedStyle(c).marginBottom) || 0;
      c.style.gridRowEnd = 'auto';
      c.style.gridRowEnd = 'span ' +
        Math.ceil((c.getBoundingClientRect().height + mb + gap) / (ROW + gap));
    }
  }

  grid.classList.add('js-masonry');
  fit();

  // 图片是 lazy 的，落位后高度才准；字体加载同理。resize 用 rAF 收敛，别每帧重算。
  var pending = false;
  function schedule() {
    if (pending) return;
    pending = true;
    requestAnimationFrame(function () { pending = false; fit(); });
  }
  addEventListener('resize', schedule);
  addEventListener('load', schedule);
  if (window.ResizeObserver) new ResizeObserver(schedule).observe(grid);
  grid.addEventListener('load', schedule, true);   // 每张图载入即重算（捕获阶段才收得到 img.load）
})();
