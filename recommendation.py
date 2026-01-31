import requests
from datetime import datetime
from collections import Counter
import random
import os


def get_user_favorite_genres(user_books, min_rating=4):
    """ユーザーの好みジャンルを特定"""
    high_rated_books = [book for book in user_books if book.get('rating', 0) >= min_rating]
    
    all_genres = []
    for book in high_rated_books:
        genres = book.get('categories', [])
        all_genres.extend(genres)
    
    # 最も多いジャンルを取得
    genre_counts = Counter(all_genres)
    return genre_counts.most_common(3)

def get_seasonal_keywords():
    """季節・イベントに応じたキーワード"""
    month = datetime.now().month
    
    seasonal_map = {
        (12, 1, 2): ["冬", "クリスマス", "新年"],
        (3, 4, 5): ["春", "新生活", "桜"],
        (6, 7, 8): ["夏", "夏休み", "海"],
        (9, 10, 11): ["秋", "読書", "芸術"]
    }
    
    for months, keywords in seasonal_map.items():
        if month in months:
            return keywords
    
    return ["おすすめ"]

def recommend_books(user_books, count=3):
    """書籍を推薦"""
    api_key = os.getenv('GOOGLE_BOOKS_API_KEY')
    
    # ユーザーの好みジャンルを取得
    favorite_genres = get_user_favorite_genres(user_books)
    
    if not favorite_genres:
        # 評価がない場合は季節のキーワードで検索
        keywords = get_seasonal_keywords()
        search_query = random.choice(keywords)
        reason_base = f"{search_query}の季節におすすめ"
    else:
        # 好みジャンル + 季節キーワード
        top_genre = favorite_genres[0][0]
        seasonal_keywords = get_seasonal_keywords()
        search_query = f"{top_genre} {random.choice(seasonal_keywords)}"
        reason_base = f"あなたが好きな「{top_genre}」ジャンルと、{get_seasonal_keywords()[0]}の季節におすすめ"
    
    # Google Books APIで検索
    base_url = "https://www.googleapis.com/books/v1/volumes"
    params = {
        'q': search_query,
        'maxResults': 20,
        'orderBy': 'relevance',
        'langRestrict': 'ja'
    }
    
    if api_key:
        params['key'] = api_key
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # 既読書籍のタイトルリスト
        read_titles = {book.get('title', '').lower() for book in user_books}
        
        recommendations = []
        if 'items' in data:
            for item in data['items']:
                volume_info = item.get('volumeInfo', {})
                title = volume_info.get('title', '')
                
                # 既読チェック
                if title.lower() in read_titles:
                    continue
                
                description = volume_info.get('description', '説明なし')
                if len(description) > 200:
                    description = description[:200] + '...'
                
                book = {
                    'title': title,
                    'authors': volume_info.get('authors', ['不明']),
                    'description': description,
                    'categories': volume_info.get('categories', ['未分類']),
                    'cover_image': volume_info.get('imageLinks', {}).get('thumbnail', ''),
                    'average_rating': volume_info.get('averageRating', 0),
                    'reason': reason_base
                }
                recommendations.append(book)
                
                if len(recommendations) >= count:
                    break
        
        return recommendations
    
    except Exception as e:
        return []
