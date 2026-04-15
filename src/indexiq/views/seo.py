"""
SEO helpers — config driven from config/seo.yml.

Streamlit controls the <head> tag, so tags injected via st.markdown() land in
<body>. The JS snippet below upserts every tag directly into <head> at page-load,
where crawlers and social parsers expect them.
"""
import json
from pathlib import Path

import streamlit as st
import yaml

# ── Load config ────────────────────────────────────────────────────────────────
_seo_path = Path(__file__).parent.parent.parent.parent / "config" / "seo.yml"
with open(_seo_path) as _f:
    _s: dict = yaml.safe_load(_f)

_site        = _s["site"]
_TITLE       = _site["title"]
_URL         = _site["url"]
_IMAGE       = _site["image"]
_DESCRIPTION = _s["description"].strip().replace("\n", " ")
_KEYWORDS    = ", ".join(_s["keywords"])

# ── JSON-LD ────────────────────────────────────────────────────────────────────
_json_ld = {
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "WebApplication",
            "name": _site["name"],
            "url": _URL,
            "description": _DESCRIPTION,
            "applicationCategory": "FinanceApplication",
            "operatingSystem": "Any (Web Browser)",
            "inLanguage": _site["locale"][:2],
            "isAccessibleForFree": True,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
            "image": _IMAGE,
            "featureList": [
                "Moving averages MA5, MA20, MA50, MA100, MA200",
                "200-week moving average overlay",
                "RSI-14 overbought and oversold indicator",
                "Fibonacci retracement levels",
                "Candlestick reversal pattern detection",
                "S&P 500 weekly and monthly candle screener",
                "Short squeeze scanner with squeeze score",
                "Bounce radar for stocks near 200-day MA",
                "Charlie Munger quality stock watchlist",
                "AI-powered SPY 5-day price forecast",
                "Golden Cross and Death Cross detection",
            ],
        },
        {
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": item["q"],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": item["a"].strip().replace("\n", " "),
                    },
                }
                for item in _s["faq"]
            ],
        },
    ],
}


def inject_seo() -> None:
    """
    Call once at the top of app.py.
    Injects meta tags into <head> via JS and emits JSON-LD structured data.
    """
    meta_rows = [
        # Standard
        ("name",     "description",        _DESCRIPTION),
        ("name",     "keywords",           _KEYWORDS),
        ("name",     "author",             _site["name"]),
        ("name",     "application-name",   _site["name"]),
        ("name",     "robots",             "index, follow, max-snippet:-1, max-image-preview:large"),
        ("name",     "theme-color",        "#0F172A"),
        # Open Graph
        ("property", "og:type",            "website"),
        ("property", "og:url",             _URL),
        ("property", "og:title",           _TITLE),
        ("property", "og:description",     _DESCRIPTION),
        ("property", "og:site_name",       _site["name"]),
        ("property", "og:locale",          _site["locale"]),
        ("property", "og:image",           _IMAGE),
        ("property", "og:image:width",     str(_site["image_width"])),
        ("property", "og:image:height",    str(_site["image_height"])),
        ("property", "og:image:alt",       f"{_site['name']} — {_TITLE}"),
        # Twitter Card
        ("name",     "twitter:card",       "summary_large_image"),
        ("name",     "twitter:title",      _TITLE),
        ("name",     "twitter:description", _DESCRIPTION),
        ("name",     "twitter:image",      _IMAGE),
    ]

    js_calls = []
    for attr, key, val in meta_rows:
        safe = val.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
        js_calls.append(f'  upsertMeta("{attr}", "{key}", "{safe}");')

    script = f"""
<script>
(function() {{
  function upsertMeta(attr, key, content) {{
    var sel = 'meta[' + attr + '="' + key + '"]';
    var el  = document.querySelector(sel);
    if (!el) {{
      el = document.createElement('meta');
      el.setAttribute(attr, key);
      document.head.appendChild(el);
    }}
    el.setAttribute('content', content);
  }}

  function upsertCanonical(url) {{
    var el = document.querySelector('link[rel="canonical"]');
    if (!el) {{
      el = document.createElement('link');
      el.rel = 'canonical';
      document.head.appendChild(el);
    }}
    el.href = url || (window.location.origin + window.location.pathname);
  }}

{chr(10).join(js_calls)}

  upsertCanonical("{_URL}");
  document.title = "{_TITLE}";
}})();
</script>
"""

    json_ld_tag = (
        '<script type="application/ld+json">'
        + json.dumps(_json_ld, ensure_ascii=False)
        + "</script>"
    )

    st.markdown(script + "\n" + json_ld_tag, unsafe_allow_html=True)
