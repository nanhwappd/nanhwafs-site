# 南华独立中学 · 静态站骨架（GitHub Pages 候选版）

「两版竞标」中飞鑫这一版。纯 HTML，零构建，目标托管 GitHub Pages。

## 结构
- `index.html` — 首页（含校园动态列表）
- `news/2026-sample.html` — 一篇示范新闻（每条 FB 贴文 = 一个这样的页）
- `CNAME` — 自定义域名（**占位，需确认子域名后改**）

## 上线（最懒路径，零配置）
1. 新建 GitHub repo，把本目录 push 上去。
2. repo → Settings → Pages → Source 选 `main` 分支根目录。
3. 几分钟后得到 `https://<账号>.github.io/<repo>/`，可直接给延盛对比。
4. 绑自定义域名：把 `CNAME` 里的域名改成最终子域名（如 `new.nanhwafs.edu.my`），
   在 DNS 加一条 CNAME 指向 `<账号>.github.io` → GitHub 自动签 HTTPS 证书（免费，免管）。

> ponytail：先纯 HTML 验证。内容多到手改吃力，再上 Astro/Eleventy + GitHub Actions；
> 非技术同事要自助发帖，再加 Decap/Sveltia CMS。现在都不需要。
