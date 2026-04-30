"""
Minify index.html + styles.css for Webflow embed (50K char limit).
Rewrites local asset paths to jsDelivr URLs from the public GitHub repo.
No external deps — stdlib re only.
"""
import re
import sys
import json
from pathlib import Path

ROOT = Path(__file__).parent
CDN = "https://cdn.jsdelivr.net/gh/janabadilla-ux/ppc-credit-card@main"


# ----------------------------- CSS minify --------------------------------
def minify_css(src: str) -> str:
    # Strip /* ... */ comments
    out = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    # Collapse whitespace runs to single space
    out = re.sub(r"\s+", " ", out)
    # Drop whitespace around delimiters
    out = re.sub(r"\s*([{}:;,>+~])\s*", r"\1", out)
    # Drop trailing ; before }
    out = re.sub(r";}", "}", out)
    # Drop leading/trailing whitespace
    return out.strip()


# ----------------------------- HTML minify -------------------------------
PRESERVE_TAGS = ("pre", "textarea", "script", "style")


def rewrite_urls(html: str) -> str:
    repl = {
        'href="styles.css"': f'href="{CDN}/styles.min.css"',
        'src="assets/logo.png"': f'src="{CDN}/assets/logo.png"',
        'src="assets/image1.png"': f'src="{CDN}/assets/image1.png"',
        'src="assets/image2.jpg"': f'src="{CDN}/assets/image2.jpg"',
        'src="assets/image3.jpg"': f'src="{CDN}/assets/image3.jpg"',
        'content="assets/image1.png"': f'content="{CDN}/assets/image1.png"',
        '"image": "assets/image1.png"': f'"image": "{CDN}/assets/image1.png"',
    }
    for old, new in repl.items():
        if old in html:
            html = html.replace(old, new)
    return html


def minify_jsonld(content: str) -> str:
    """Compact JSON-LD payload to single line."""
    try:
        obj = json.loads(content)
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        return content  # fallback


def minify_inline_js(js: str) -> str:
    """Conservative JS minify: strip line comments, block comments, collapse ws."""
    # Strip /* ... */ block comments
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.DOTALL)
    # Strip // line comments (be careful with URLs — but our JS has none)
    js = re.sub(r"(?m)^\s*//.*$", "", js)
    js = re.sub(r"(?<=[;{}\s])//[^\n]*", "", js)
    # Collapse whitespace
    js = re.sub(r"[ \t]+", " ", js)
    js = re.sub(r"\s*\n\s*", "\n", js)
    js = re.sub(r"\n+", "\n", js)
    return js.strip()


def extract_and_protect(html: str):
    """Pull <script>, <style>, <pre>, <textarea> bodies out and replace with markers."""
    placeholders = {}

    def stash(tag, content):
        key = f"\x00{tag}{len(placeholders)}\x00"
        placeholders[key] = content
        return key

    def replace_block(match):
        tag = match.group(1).lower()
        full = match.group(0)
        body = match.group(2)
        attrs = match.group(0)[: match.group(0).find(">") + 1]

        if tag == "script":
            # JSON-LD
            if 'type="application/ld+json"' in attrs:
                body_min = minify_jsonld(body)
            else:
                body_min = minify_inline_js(body)
            return stash(tag, f"{attrs}{body_min}</{tag}>")
        elif tag == "style":
            return stash(tag, f"{attrs}{minify_css(body)}</{tag}>")
        else:
            return stash(tag, full)

    pattern = re.compile(
        r"<(script|style|pre|textarea)\b[^>]*>(.*?)</\1>",
        re.DOTALL | re.IGNORECASE,
    )
    protected = pattern.sub(replace_block, html)
    return protected, placeholders


def restore(html: str, placeholders: dict) -> str:
    for key, content in placeholders.items():
        html = html.replace(key, content)
    return html


def minify_html(src: str) -> str:
    src = rewrite_urls(src)

    # Protect tags whose interior should not be touched
    protected, ph = extract_and_protect(src)

    # Strip HTML comments (decorative section dividers)
    protected = re.sub(r"<!--[\s\S]*?-->", "", protected)

    # Collapse whitespace BETWEEN tags
    protected = re.sub(r">\s+<", "><", protected)
    # Collapse whitespace runs inside lines (but keep single spaces in text)
    protected = re.sub(r"[ \t]{2,}", " ", protected)
    # Collapse newlines
    protected = re.sub(r"\n\s*", "", protected)

    return restore(protected, ph).strip()


# ------------------------------ run --------------------------------------
def main():
    css_src = (ROOT / "styles.css").read_text(encoding="utf-8")
    css_min = minify_css(css_src)
    (ROOT / "styles.min.css").write_text(css_min, encoding="utf-8")

    html_src = (ROOT / "index.html").read_text(encoding="utf-8")
    html_min = minify_html(html_src)
    (ROOT / "index.min.html").write_text(html_min, encoding="utf-8")

    css_orig = len(css_src)
    css_after = len(css_min)
    html_orig = len(html_src)
    html_after = len(html_min)

    def pct(a, b):
        return f"{(1 - b / a) * 100:.1f}%"

    print(f"styles.css      {css_orig:>7} chars")
    print(f"styles.min.css  {css_after:>7} chars  (-{pct(css_orig, css_after)})")
    print(f"index.html      {html_orig:>7} chars")
    print(f"index.min.html  {html_after:>7} chars  (-{pct(html_orig, html_after)})")
    print()
    if html_after <= 50000:
        print(f"OK index.min.html fits Webflow embed ({html_after} <= 50000)")
    else:
        print(f"FAIL index.min.html is OVER 50K ({html_after})")
        sys.exit(1)


if __name__ == "__main__":
    main()
