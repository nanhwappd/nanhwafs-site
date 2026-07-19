# 站点地图 v1.0（P2 定稿 · 2026-07-06）

> 原则：URL 一旦上线永不改（SEO 命脉）。栏目可以先空着，URL 结构必须现在锁死。

## URL 结构

```
/                               首页
/news/                          新闻动态总入口（按年新闻馆索引）
/news/2026/                     年度索引页（P4 生成，2018–2026 共 9 个）
/news/2026/20260628-1.html      新闻内页：YYYYMMDD-当日序号（同日多帖递增）
/history/                       数字校史馆（90 周年主打；时光隧道相册为底料）
/about/                         关于南华（校史沿革/办学理念/行政团队）
/admission/                     招生资讯
/academic/                      学术课程
/cocurricular/                  联课活动
/facilities/                    硬体设施（新增，未在v1.0原始规划中，2026-07-19随about家族一并建成）
/alumni/                        校友
/donate/                        捐助支持
/contact/                       联系我们
/sitemap.xml                    P5 生成
```

## 建设优先级

| 栏目 | 期数 | 内容来源 |
|---|---|---|
| /news/（1198 页） | **P4 主战场** | posts.json 全量生成，倒序 2026→2018 |
| / 首页 | P4 收尾时重做 | 最新 6 条新闻卡片 + 栏目入口；版面设计届时另议（motionsites 灵感用在这里） |
| /history/ | P4 之后、8 月中前 | 「南华时光隧道」相册 + 按年大事记（从 posts.json 提炼） |
| /about/ /admission/ /contact/ | P5 前补上 | 向校方/冠铭要现成文案，一页一档 |
| /about/ /academic/ /cocurricular/ /facilities/ | ✅ 2026-07-19 四页均已建成 | 2027简介手册文案+真实照片，套用同一「四style骨干」设计 |
| /alumni/ /donate/ | 上线后迭代 | 先放占位页 + noindex，有内容再开 |

## 新闻内页模板锁定（1198 页共用，改版只动 CSS）

- 骨架：`templates/news-post.html`（生成器填占位符）＋ `assets/news.css`（全站唯一样式文件）
- 结构：面包屑 → h1 标题 → time 日期 → 正文（p 段落）→ figure 图组 → 上一篇/下一篇 → 返回年度索引
- SEO：每页 title/description/canonical/OG + NewsArticle JSON-LD
- 标题规则（P4 生成器实现）：取正文首行（≤40 字截断）；无正文的 81 篇用「YYYY 年 M 月校园剪影」
- 手机优先：375px 视口先行，正文 18px 起跳（用户桌面大屏 + 家长手机双场景）
