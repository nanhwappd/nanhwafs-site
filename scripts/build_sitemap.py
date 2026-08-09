"""Generate sitemap.xml for the whole static site.

Base URL matches the canonical already baked into the 1198 news pages
(https://nanhwappd.github.io/nanhwafs-site/). If the site ever moves to
nanhwafs.edu.my, the page canonicals must be rewritten first -- this script
follows them, it does not lead.

ponytail: stdlib only, idempotent, no config file. Run from repo root:
    python scripts/build_sitemap.py
"""
import os
import re
from datetime import date

BASE = "https://nanhwappd.github.io/nanhwafs-site/"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "scripts", "templates", "reference", ".impeccable", ".claude", "assets", "data"}
# news post filenames carry their own date: 20260628-1.html
DATED = re.compile(r"(\d{4})(\d{2})(\d{2})-\d+\.html$")

# crawl priority: homepage first, then the parent-facing funnel, news last
PRIORITY = [
    ("index.html", "1.0", "weekly"),
    ("admission/", "0.9", "monthly"),
    ("about/", "0.8", "monthly"),
    ("academic/", "0.8", "monthly"),
    ("cocurricular/", "0.7", "monthly"),
    ("facilities/", "0.7", "monthly"),
    ("faculty/", "0.7", "monthly"),
    ("history/", "0.7", "yearly"),
    ("90/", "0.9", "weekly"),
    ("news/index.html", "0.8", "daily"),
]


def rank(rel):
    for i, (prefix, prio, freq) in enumerate(PRIORITY):
        if rel == prefix or rel.startswith(prefix):
            return i, prio, freq
    # year indexes rank above individual posts
    if re.fullmatch(r"news/\d{4}/index\.html", rel):
        return len(PRIORITY), "0.6", "monthly"
    return len(PRIORITY) + 1, "0.5", "yearly"


def lastmod(path, rel):
    m = DATED.search(rel)
    if m:
        return "-".join(m.groups())
    ts = date.fromtimestamp(os.path.getmtime(path))
    return ts.isoformat()


def collect():
    rows = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if not name.endswith(".html"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            if rel == "404.html" or "preview-sample" in rel:
                continue
            order, prio, freq = rank(rel)
            rows.append((order, rel, lastmod(full, rel), prio, freq))
    # stable: by rank, then newest news first, then path
    rows.sort(key=lambda r: (r[0], r[2] if r[0] > len(PRIORITY) else "", r[1]), reverse=False)
    tail = [r for r in rows if r[0] > len(PRIORITY)]
    head = [r for r in rows if r[0] <= len(PRIORITY)]
    tail.sort(key=lambda r: (r[2], r[1]), reverse=True)
    return head + tail


def main():
    rows = collect()
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for _order, rel, mod, prio, freq in rows:
        loc = BASE + ("" if rel == "index.html" else rel)
        out.append("  <url>")
        out.append("    <loc>%s</loc>" % loc)
        out.append("    <lastmod>%s</lastmod>" % mod)
        out.append("    <changefreq>%s</changefreq>" % freq)
        out.append("    <priority>%s</priority>" % prio)
        out.append("  </url>")
    out.append("</urlset>")
    path = os.path.join(ROOT, "sitemap.xml")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")
    print("wrote %s with %d urls" % (path, len(rows)))
    return rows


def demo():
    """Self-check: the numbers the sitemap claims must match what is on disk."""
    rows = main()
    urls = [r[1] for r in rows]
    assert len(urls) == len(set(urls)), "duplicate <loc> entries"
    on_disk = sum(
        1
        for dp, dn, fn in os.walk(ROOT)
        if not any(s in os.path.relpath(dp, ROOT).split(os.sep) for s in SKIP_DIRS)
        for f in fn
        if f.endswith(".html") and f != "404.html" and "preview-sample" not in f
    )
    assert len(urls) == on_disk, "sitemap %d != html on disk %d" % (len(urls), on_disk)
    assert urls[0] == "index.html", "homepage must be first, got %s" % urls[0]
    for _o, rel, mod, _p, _f in rows:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", mod), "bad lastmod %r on %s" % (mod, rel)
    print("demo OK: %d urls, no dupes, lastmod well-formed" % len(urls))


if __name__ == "__main__":
    demo()
