import requests
import streamlit as st
from datetime import datetime
from collections import Counter
import random


# ---------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------
def get_api_key() -> str | None:
    """Google Books APIキーを st.secrets から取得"""
    if 'GOOGLE_BOOKS_API_KEY' in st.secrets:
        return st.secrets['GOOGLE_BOOKS_API_KEY']
    return None


# ---------------------------------------------------------------
# ジャンル・季節キーワード
# ---------------------------------------------------------------
def get_user_favorite_genres(user_books, min_rating=4):
    """ユーザーの好みジャンルを特定"""
    high_rated_books = [book for book in user_books if book.get('rating', 0) >= min_rating]

    all_genres = []
    for book in high_rated_books:
        genres = book.get('categories', [])
        all_genres.extend(genres)

    genre_counts = Counter(all_genres)
    return genre_counts.most_common(3)


def get_seasonal_keywords():
    """季節・イベントに応じたキーワード"""
    month = datetime.now().month

    seasonal_map = {
        (12, 1, 2): ["冬", "クリスマス", "新年"],
        (3, 4, 5): ["春", "新生活", "桜"],
        (6, 7, 8): ["夏", "夏休み", "海"],
        (9, 10, 11): ["秋", "読書", "芸術"],
    }

    for months, keywords in seasonal_map.items():
        if month in months:
            return keywords

    return ["おすすめ"]


# ---------------------------------------------------------------
# 検索クエリの組み立て
# ---------------------------------------------------------------
def build_search_query(user_books):
    """ジャンル・季節から検索クエリと推薦理由を組み立てる"""
    favorite_genres = get_user_favorite_genres(user_books)
    seasonal_keywords = get_seasonal_keywords()

    if not favorite_genres:
        keyword = random.choice(seasonal_keywords)
        return keyword, f"{keyword}の季節におすすめ"
    else:
        top_genre = favorite_genres[0][0]
        keyword = random.choice(seasonal_keywords)
        query = f"{top_genre} {keyword}"
        reason = f"あなたが好きな「{top_genre}」ジャンルと、{seasonal_keywords[0]}の季節におすすめ"
        return query, reason


# ---------------------------------------------------------------
# Google Books API
# ---------------------------------------------------------------
def search_google_books_for_recommendation(search_query: str, max_results: int = 20) -> list:
    """
    Google Books APIで推薦候補を検索。
    キー付き→キーなしの自動リトライ付き（GCP地理制限回避）。
    """
    api_key = get_api_key()

    attempts = [
        {"label": "APIキー付き", "use_key": True},
        {"label": "APIキーなし（GCP地理制限回避）", "use_key": False},
    ]

    for attempt in attempts:
        params = {
            'q': search_query,
            'maxResults': max_results,
            'orderBy': 'relevance',
            'hl': 'ja',
        }

        if attempt["use_key"] and api_key:
            params['key'] = api_key

        try:
            response = requests.get(
                "https://www.googleapis.com/books/v1/volumes",
                params=params,
                timeout=10,
            )

            if response.status_code == 403:
                try:
                    err_msg = response.json().get('error', {}).get('message', '')
                except Exception:
                    err_msg = response.text[:100]
                st.warning(f"⚠️ Google Books [{attempt['label']}] 403: {err_msg}")

                if attempt["use_key"]:
                    st.info("🔄 APIキーなしで再試行中（GCP地理制限回避）...")
                    continue
                else:
                    return []

            if response.status_code != 200:
                st.warning(f"⚠️ Google Books [{attempt['label']}] エラー: {response.status_code}")
                return []

            items = response.json().get('items', [])
            if items:
                st.success(f"📚 Google Books [{attempt['label']}] で推薦候補を取得しました")
            return items

        except Exception as e:
            st.warning(f"⚠️ Google Books [{attempt['label']}] 例外: {e}")
            return []

    return []


# ---------------------------------------------------------------
# Open Library API（フォールバック）
# ---------------------------------------------------------------
def search_open_library_for_recommendation(search_query: str, max_results: int = 20) -> list:
    """
    Open Library の検索API。
    language フィルタを使わず検索する。
    戻り値を Google Books と同じ items / volumeInfo 構造に正規化する。
    """
    try:
        params = {
            'q': search_query,
            'limit': max_results,
        }
        response = requests.get(
            "https://openlibrary.org/search.json",
            params=params,
            timeout=10,
        )

        if response.status_code != 200:
            st.warning(f"⚠️ Open Library 検索エラー: {response.status_code}")
            return []

        docs = response.json().get('docs', [])
        if not docs:
            return []

        # Google Books の items 構造に正規化
        normalized = []
        for doc in docs:
            cover_image = ""
            if 'cover_i' in doc:
                cover_image = f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-M.jpg"

            normalized.append({
                'volumeInfo': {
                    'title': doc.get('title', ''),
                    'authors': doc.get('author_name', ['不明']),
                    'categories': doc.get('subject', ['未分類'])[:3],
                    'imageLinks': {'thumbnail': cover_image},
                    'description': doc.get('subtitle', '説明なし') or '説明なし',
                    'averageRating': 0,
                }
            })

        st.success(f"📚 Open Library APIから{len(normalized)}件の推薦候補を取得しました")
        return normalized

    except Exception as e:
        st.warning(f"⚠️ Open Library 検索エラー: {e}")
        return []


# ---------------------------------------------------------------
# メイン: 推薦
# ---------------------------------------------------------------
def recommend_books(user_books, count=3):
    """書籍を推薦"""

    search_query, reason_base = build_search_query(user_books)

    # 既読書籍タイトルセット（重複除去用）
    read_titles = {book.get('title', '').lower() for book in user_books}

    # --- 1. Google Books API（キー付き→キーなし自動リトライ）---
    items = search_google_books_for_recommendation(search_query)

    # --- 2. 失敗・空の場合は Open Library へフォールバック ---
    if not items:
        st.info("🔄 Open Library APIにフォールバック検索中...")
        items = search_open_library_for_recommendation(search_query)

    # --- 3. 結果をパースして推薦リストに整理 ---
    recommendations = []
    for item in items:
        volume_info = item.get('volumeInfo', {})
        title = volume_info.get('title', '')

        if not title:
            continue

        if title.lower() in read_titles:
            continue

        description = volume_info.get('description', '説明なし') or '説明なし'
        if len(description) > 200:
            description = description[:200] + '...'

        book = {
            'title': title,
            'authors': volume_info.get('authors', ['不明']),
            'description': description,
            'categories': volume_info.get('categories', ['未分類']),
            'cover_image': volume_info.get('imageLinks', {}).get('thumbnail', ''),
            'average_rating': volume_info.get('averageRating', 0),
            'reason': reason_base,
        }
        recommendations.append(book)

        if len(recommendations) >= count:
            break

    return recommendations