import requests
import streamlit as st
from datetime import datetime
from collections import Counter
import random
import re

def get_rakuten_app_id():
    if 'RAKUTEN_APP_ID' in st.secrets:
        return st.secrets['RAKUTEN_APP_ID']
    return None

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

def get_top_genre_id(user_books):
    """読んだ本のbooksGenreIdから最も多いジャンルコードを返す"""
    genre_counter = Counter()
    for book in user_books:
        genre_ids = book.get('booksGenreId', '')
        if genre_ids:
            # "001019007/001019001/..." の末尾のコードが最も詳細なジャンル
            codes = genre_ids.split('/')
            if codes:
                genre_counter[codes[-1]] += 1
    if genre_counter:
        return genre_counter.most_common(1)[0][0]
    return None

def extract_keywords_from_descriptions(user_books, min_rating=4):
    """高評価の本の説明文から頻度の高いキーワードを抽出"""
    high_rated = [b for b in user_books if b.get('rating', 0) >= min_rating]
    if not high_rated:
        high_rated = user_books  # 全部使う
    # 説明文を結合
    all_text = ' '.join(b.get('description', '') for b in high_rated)
    # 2文字以上の日本語の語を抽出（単語切り出しの簡易版）
    words = re.findall(r'[\u4e00-\u9fff]{2,4}', all_text)
    # 除外語
    stop_words = {'する', 'した', 'して', 'では', 'した', 'いる', 'った', 'ある', 'おり', 'した', 'この', 'その', 'それ', 'あの'}
    words = [w for w in words if w not in stop_words]
    counter = Counter(words)
    return [w for w, _ in counter.most_common(3)]

def recommend_books(user_books, count=3):
    app_id = get_rakuten_app_id()
    if not app_id:
        st.warning("⚠️ RAKUTEN_APP_ID が設定されていません")
        return []

    read_titles = {book.get('title', '').lower() for book in user_books}
    top_genre_id = get_top_genre_id(user_books)
    seasonal_keywords = get_seasonal_keywords()
    desc_keywords = extract_keywords_from_descriptions(user_books)

    # 検索キーワード構築
    if desc_keywords:
        keyword = random.choice(desc_keywords)
        reason_base = f"あなたの好みに合った「{keyword}」に関連する本"
    else:
        keyword = random.choice(seasonal_keywords)
        reason_base = f"{keyword}の季節におすすめの本"

    try:
        url = "https://app.rakuten.co.jp/services/api/BooksBook/Search/20170404"
        params = {
            'applicationId': app_id,
            'keyword': keyword,
            'format': 'json',
            'hits': 30,
        }
        # ジャンル情報がある場合はジャンル検索にする
        if top_genre_id:
            params['booksGenreId'] = top_genre_id
            reason_base = f"あなたが好きなジャンルの「{keyword}」に関連する本"

        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            st.warning(f"⚠️ 楽天書籍API エラー ({response.status_code}): {response.text[:200]}")
            return []

        data = response.json()
        recommendations = []
        for book_item in data.get('Items', []):
            item = book_item.get('Item', {})
            title = item.get('title', '')
            if not title or title.lower() in read_titles:
                continue
            description = item.get('itemCaption', '') or '説明なし'
            if len(description) > 200:
                description = description[:200] + '...'
            # booksGenreId も保存
            genre_id = item.get('booksGenreId', '')
            recommendations.append({
                'title': title,
                'authors': [item.get('author', '不明')],
                'description': description,
                'categories': ['未分類'],
                'cover_image': item.get('mediumImageUrl', ''),
                'average_rating': item.get('reviewAverage', 0),
                'booksGenreId': genre_id,
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
