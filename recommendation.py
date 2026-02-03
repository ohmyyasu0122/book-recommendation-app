import requests
import streamlit as st
from datetime import datetime
from collections import Counter
import random

def get_rakuten_app_id():
    if 'RAKUTEN_APP_ID' in st.secrets:
        return st.secrets['RAKUTEN_APP_ID']
    return None

def get_user_favorite_genres(user_books, min_rating=4):
    high_rated_books = [book for book in user_books if book.get('rating', 0) >= min_rating]
    all_genres = []
    for book in high_rated_books:
        all_genres.extend(book.get('categories', []))
    return Counter(all_genres).most_common(3)

def get_seasonal_keywords():
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

def build_search_query(user_books):
    favorite_genres = get_user_favorite_genres(user_books)
    seasonal_keywords = get_seasonal_keywords()
    if not favorite_genres:
        keyword = random.choice(seasonal_keywords)
        return keyword, f"{keyword}の季節におすすめ"
    else:
        top_genre = favorite_genres[0][0]
        keyword = random.choice(seasonal_keywords)
        return f"{top_genre} {keyword}", f"あなたが好きな「{top_genre}」ジャンルと、{seasonal_keywords[0]}の季節におすすめ"

def recommend_books(user_books, count=3):
    app_id = get_rakuten_app_id()
    if not app_id:
        st.warning("⚠️ RAKUTEN_APP_ID が設定されていません")
        return []
    search_query, reason_base = build_search_query(user_books)
    read_titles = {book.get('title', '').lower() for book in user_books}
    try:
        url = "https://app.rakuten.co.jp/services/api/BooksBook/Search/20170404"
        params = {
            'applicationId': app_id,
            'keyword': search_query,
            'format': 'json',
            'formatVersion': 2,
            'hits': 30,
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            st.warning(f"⚠️ 楽天書籍API エラー ({response.status_code}): {response.text[:200]}")
            return []
        data = response.json()
        recommendations = []
        for item in data.get('Items', []):
            title = item.get('title', '')
            if not title or title.lower() in read_titles:
                continue
            description = item.get('itemCaption', '') or '説明なし'
            if len(description) > 200:
                description = description[:200] + '...'
            recommendations.append({
                'title': title,
                'authors': [item.get('author', '不明')],
                'description': description,
                'categories': ['未分類'],
                'cover_image': item.get('mediumImageUrl', ''),
                'average_rating': item.get('reviewAverage', 0),
                'reason': reason_base,
            })
            if len(recommendations) >= count:
                break
        if recommendations:
            st.success(f"📚 楽天書籍APIから{len(recommendations)}件の推薦を取得しました")
        return recommendations
    except Exception as e:
        st.warning(f"⚠️ 楽天書籍API エラー: {e}")
        return []
