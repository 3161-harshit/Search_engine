"""
HFS Search Engine
Google Custom Search + FastText search-history suggestions, with a
modern UI (search form, Web/Images views, pagination, highlighting, sidebar).

Run:
    streamlit run search.py

Credentials (pick one, don't hard-code them):
    .streamlit/secrets.toml
        GOOGLE_SEARCH_API_KEY = "your_key"
        SEARCH_ENGINE_ID      = "your_cx_id"
    or environment variables with the same names.
"""

import html
import os
import re

import requests
import streamlit as st

import train_search_history as search_history

# ----------------------------------------------------------------------------
# Constants / credentials
# ----------------------------------------------------------------------------
IMAGE_PATH = "L:\\search_engine\\image.png"
API_URL = "https://www.googleapis.com/customsearch/v1"
MAX_API_RESULTS = 100  # Google CSE only serves the first 100 results per query


def get_secret(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)


GOOGLE_SEARCH_API_KEY = get_secret("GOOGLE_SEARCH_API_KEY")
SEARCH_ENGINE_ID = get_secret("SEARCH_ENGINE_ID")

# ----------------------------------------------------------------------------
# Page config & styling (your orange / red theme)
# ----------------------------------------------------------------------------
st.set_page_config(page_title="HFS Search Engine", page_icon="🔍", layout="wide")

st.markdown(
    """
    <style>
#MainMenu, footer {visibility:hidden;}
.stApp {background:linear-gradient(135deg,#fff7ed 0%,#fff 48%,#fff1f2 100%);}
.block-container {max-width:1080px;padding-top:2rem;padding-bottom:3rem;}
html,body,[class*="css"] {font-family:Inter,Arial,sans-serif;}
h1 {text-align:center;font-weight:750;letter-spacing:-1px;color:#222;}
[data-testid="stSidebar"] {background:#fff7ed;}
[data-testid="stForm"] {background:rgba(255,255,255,.9);padding:1rem 1.2rem;border:1px solid #fed7aa;border-radius:18px;box-shadow:0 8px 28px rgba(124,45,18,.07);}
.stButton>button,.stFormSubmitButton>button {background:linear-gradient(90deg,#ea580c,#dc2626)!important;color:white!important;font-size:16px;font-weight:650;border-radius:12px;border:none;min-height:42px;}
.stButton>button:disabled {opacity:.4;}
.stTextInput>div>div>input {font-size:17px;padding:12px;border-radius:12px;font-family:Inter,Arial,sans-serif;border:1px solid #e5e7eb;}
.meta {opacity:.7;font-size:.85rem;margin:.5rem 0 1rem 0;}
.search-result {margin:12px 0;padding:14px 18px;border:1px solid #e5e7eb;border-radius:12px;background:#fff;box-shadow:0 3px 12px rgba(15,23,42,.06);}
.search-result .url {font-size:.8rem;color:#188038;word-break:break-all;}
.search-result h3 {margin:.15rem 0 .3rem 0;font-size:1.15rem;color:#1a0dab;}
.search-result a {text-decoration:none;}
.search-result a:hover h3 {text-decoration:underline;}
.search-result p {margin:0;color:#333;line-height:1.55;}
mark {background:rgba(234,21,21,.18);color:inherit;padding:0 2px;border-radius:3px;}
</style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Google Custom Search
# ----------------------------------------------------------------------------
class SearchError(Exception):
    """Raised for any API/network problem (never cached by st.cache_data)."""


@st.cache_data(ttl=600, show_spinner=False)
def google_search(query: str, kind: str, page: int, per_page: int,
                  safe: bool, date_restrict: str):
    params = {
        "q": query,
        "key": GOOGLE_SEARCH_API_KEY,
        "cx": SEARCH_ENGINE_ID,
        "num": per_page,
        "start": (page - 1) * per_page + 1,
        "safe": "active" if safe else "off",
    }
    if kind == "images":
        params["searchType"] = "image"
    if date_restrict:
        params["dateRestrict"] = date_restrict

    try:
        resp = requests.get(API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        raise SearchError("Search request timed out. Please try again.")
    except requests.exceptions.HTTPError as e:
        raise SearchError(f"Google API returned an HTTP error: {e}")
    except ValueError:
        raise SearchError("Google API returned an invalid response.")
    except requests.exceptions.RequestException as e:
        raise SearchError(f"Network error: {e}")

    total = int(data.get("searchInformation", {}).get("totalResults", 0) or 0)
    items = []
    for it in data.get("items", []):
        if kind == "images":
            img = it.get("image", {})
            items.append({
                "title": it.get("title", "No Title"),
                "link": it.get("link", "#"),
                "thumb": img.get("thumbnailLink") or it.get("link", ""),
                "page": img.get("contextLink", "#"),
            })
        else:
            items.append({
                "title": it.get("title", "No Title"),
                "link": it.get("link", "#"),
                "display": it.get("displayLink", ""),
                "snippet": it.get("snippet", "No description available."),
            })
    return {"items": items, "total": total}


# ----------------------------------------------------------------------------
# Session state & callbacks
# ----------------------------------------------------------------------------
ss = st.session_state
ss.setdefault("query", "")
ss.setdefault("page", 1)
ss.setdefault("history", [])          # searches made in this session
ss.setdefault("search_history", None)  # persisted history used by FastText

if ss.search_history is None:
    try:
        ss.search_history = search_history.load_search_history()
    except Exception as e:
        ss.search_history = []
        st.sidebar.warning(f"Could not load search history: {e}")


def reset_page():
    ss.page = 1


def goto_page(p: int):
    ss.page = p


def run_search(q: str):
    """Start a new search: update state, save it to search history."""
    q = (q or "").strip()
    if not q:
        return
    ss.query = q
    ss.page = 1
    if q in ss.history:
        ss.history.remove(q)
    ss.history.insert(0, q)
    try:
        search_history.process_search(q)  # save the query and update history
        ss.search_history = search_history.load_search_history()
    except Exception as e:
        st.toast(f"Search history not updated: {e}", icon="⚠️")


def related_searches(q: str):
    key = f"rel::{q}"
    if key not in ss:
        try:
            sugg = search_history.get_related_searches(q, ss.search_history, search_history.fasttext_model) or []
            ss[key] = [s for s in list(sugg) if str(s).strip().lower() != q.lower()][:6]
        except Exception:
            ss[key] = []
    return ss[key]


def highlight(text: str, q: str) -> str:
    safe = html.escape(text)
    for term in sorted(set(re.findall(r"\w+", q)), key=len, reverse=True):
        safe = re.sub(f"(?i)({re.escape(term)})", r"<mark>\1</mark>", safe)
    return safe


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Settings")
    safe_search = st.checkbox("SafeSearch", value=True, on_change=reset_page)
    time_label = st.selectbox(
        "Time range",
        ["Any time", "Past day", "Past week", "Past month", "Past year"],
        on_change=reset_page,
    )
    date_restrict = {"Any time": "", "Past day": "d1", "Past week": "w1",
                     "Past month": "m1", "Past year": "y1"}[time_label]

    st.divider()
    st.subheader("🕘 Recent searches")
    if ss.history:
        for i, h in enumerate(ss.history[:8]):
            st.button(h, key=f"hist_{i}", use_container_width=True,
                      on_click=run_search, args=(h,))
        if st.button("Clear recent", key="clear_hist"):
            ss.history = []
            st.rerun()
    else:
        st.caption("Nothing yet.")

# ----------------------------------------------------------------------------
# Header + search bar
# ----------------------------------------------------------------------------
if os.path.exists(IMAGE_PATH):
    mid = st.columns([2, 1, 2])[1]
    mid.image(IMAGE_PATH, use_container_width=True)

st.markdown("<h1>HFS Search Engine</h1>", unsafe_allow_html=True)

with st.form("search_form"):
    c1, c2 = st.columns([5, 1])
    q_input = c1.text_input("🔍 Search here...", value=ss.query,
                            placeholder="🔍 Search here...",
                            label_visibility="collapsed")
    submitted = c2.form_submit_button("Search", use_container_width=True)

if submitted:
    if q_input.strip():
        run_search(q_input)
    else:
        st.warning("⚠️ Please enter a search query.")

query = ss.query

# ----------------------------------------------------------------------------
# Credentials check
# ----------------------------------------------------------------------------
if not GOOGLE_SEARCH_API_KEY or not SEARCH_ENGINE_ID \
        or GOOGLE_SEARCH_API_KEY.startswith("personal_"):
    st.error(
        "Google API credentials are missing. Add `GOOGLE_SEARCH_API_KEY` and "
        "`SEARCH_ENGINE_ID` to `.streamlit/secrets.toml` or set them as "
        "environment variables."
    )
    st.stop()

if not query:
    st.caption("Type something above and press Enter to start searching.")
    st.stop()

# ----------------------------------------------------------------------------
# Results (one API call per rerun, so only the selected view is fetched)
# ----------------------------------------------------------------------------
view = st.radio("View", ["🌐 Web", "🖼️ Images"], horizontal=True,
                key="view", on_change=reset_page, label_visibility="collapsed")
kind = "images" if "Images" in view else "web"
per_page = 9 if kind == "images" else 10

st.write(f"🔍 Searching for: **{query}**")

try:
    with st.spinner("Searching…"):
        data = google_search(query, kind, ss.page, per_page, safe_search, date_restrict)
except SearchError as e:
    st.error(f"❌ {e}")
    st.stop()

items, total = data["items"], data["total"]

if not items:
    st.info("❌ No results found.")
else:
    st.subheader("🔗 Search Results:")
    st.markdown(f'<div class="meta">About {total:,} results</div>', unsafe_allow_html=True)

    if kind == "web":
        for r in items:
            link = html.escape(r["link"], quote=True)
            st.markdown(
                '<div class="search-result">'
                f'<div class="url">{html.escape(r["display"])}</div>'
                f'<a href="{link}" target="_blank" rel="noopener noreferrer"><h3>{highlight(r["title"], query)}</h3></a>'
                f'<p>{highlight(r["snippet"], query)}</p>'
                "</div>",
                unsafe_allow_html=True,
            )
    else:
        cols = st.columns(3)
        for i, img in enumerate(items):
            with cols[i % 3]:
                st.image(img["thumb"], use_container_width=True)
                st.markdown(
                    f'<a href="{html.escape(img["page"], quote=True)}" target="_blank">'
                    f'{html.escape(img["title"][:45])}</a>',
                    unsafe_allow_html=True,
                )

    # Pagination
    pages = max(1, min(-(-total // per_page), MAX_API_RESULTS // per_page))
    if pages > 1:
        p1, p2, p3 = st.columns([1, 2, 1])
        p1.button("◀ Prev", disabled=ss.page <= 1, use_container_width=True,
                  on_click=goto_page, args=(ss.page - 1,))
        p2.markdown(
            f"<div style='text-align:center;padding-top:.4rem'>Page {ss.page} of {pages}</div>",
            unsafe_allow_html=True,
        )
        p3.button("Next ▶", disabled=ss.page >= pages, use_container_width=True,
                  on_click=goto_page, args=(ss.page + 1,))

# Related searches from your FastText model
suggestions = related_searches(query)
if suggestions:
    st.markdown("#### 🔽 Related searches")
    cols = st.columns(2)
    for i, s in enumerate(suggestions):
        cols[i % 2].button(str(s), key=f"rel_{i}_{s}", use_container_width=True,
                           on_click=run_search, args=(str(s),))