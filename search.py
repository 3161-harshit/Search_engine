import streamlit as st
import requests
import pandas as pd
import os
from train_search_history import load_search_history, get_related_searches, process_search, train_fasttext_model

# Constants
GOOGLE_SEARCH_API_KEY = "AIzaSyD30IVyVndnxcAPuGIsVWySTvkEovj_PzM"
SEARCH_ENGINE_ID = "810a40fa74b054e3c"
IMAGE_PATH = "L:\\search_engine\\image.png"


def get_google_search_results(query):
    url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_SEARCH_API_KEY}&cx={SEARCH_ENGINE_ID}"
    try:
        response = requests.get(url).json()
        search_results = []
        if "items" in response:
            for item in response["items"][:10]:  # Limit to top 10 results
                search_results.append({
                    "title": item.get("title", "No Title"),
                    "link": item.get("link", "#"),
                    "snippet": item.get("snippet", "No description available.")
                })
        return search_results if search_results else [{"title": "❌ No results found.", "link": "#", "snippet": ""}]
    except Exception as e:
        return [{"title": f"❌ API Error: {str(e)}", "link": "#", "snippet": ""}]


st.set_page_config(page_title="HFS Search Engine", layout="wide")

st.markdown(
    """
    <style>
    body {
        background-color: #FFFFFF;
        font-family: 'serif', sans-serif;
    }
    .stButton>button {
        background-color: #ea1515 !important;
        color: white;
        font-size: 16px;
        border-radius: 10px;
    }
    .stTextInput>div>div>input {
        font-size: 18px;
        padding: 10px;
        border-radius: 10px;
        font-family: 'serif', sans-serif;
    }
    .search-container {
        text-align: center;
    }
    .image-container {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        margin: 20px 0;
    }
    h1 {
        font-family: 'serif', sans-serif;
        text-align: center;
    }
    .search-box {
        display: flex;
        justify-content: center;
        align-items: center;
    }
    .search-box input {
        width: 50%;
        padding: 10px;
        font-size: 18px;
        border-radius: 10px;
        border: 1px solid #ccc;
    }
    .search-result {
        margin: 10px 0;
        padding: 10px;
        border: 1px solid #ddd;
        border-radius: 5px;
        background-color: #fff;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown("<div class='image-container'>", unsafe_allow_html=True)

page_bg_img = f"""
<style>
.stApp {{
    background-image: url("https://e1.pxfuel.com/desktop-wallpaper/944/1008/desktop-wallpaper-light-orange-color-backgrounds-orange-colour-background.jpg");
    background-attachment: fixed;
    background-size: cover;
    background-repeat: no-repeat;
    background-position: center;
}}
</style>
"""
st.markdown(page_bg_img, unsafe_allow_html=True)

st.markdown(page_bg_img, unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<h1>HFS Search Engine</h1>", unsafe_allow_html=True)

search_history = load_search_history()

search_query = st.text_input("🔍 Search here...", key="search_input")

if search_query:
    suggestions = get_related_searches(search_query, search_history, train_fasttext_model())
    if suggestions:
        selected_query = st.selectbox("🔽 Previous Searches:", suggestions, index=0)
        if st.button("Use Selected Query"):
            search_query = selected_query


if st.button("Search", key="search_button"):
    if search_query.strip():
        st.write(f"🔍 Searching for: **{search_query}**")
        results = get_google_search_results(search_query)
        st.subheader("🔗 Search Results:")
        for result in results:
            st.markdown(
                f"""
                <div class="search-result">
                    <a href="{result['link']}" target="_blank"><h3>{result['title']}</h3></a>
                    <p>{result['snippet']}</p>
                </div>
                """,
                unsafe_allow_html=True
            )
        process_search(search_query)  # Save and retrain
    else:
        st.warning("⚠️ Please enter a search query.")
