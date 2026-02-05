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

# ホワイトリスト: 純粋な書籍のみを含むジャンルID
ALLOWED_BOOK_GENRES = {
    '001004',  # ビジネス・経済・就職
    '001005',  # 人文・思想・社会
    '001008',  # 文芸・小説
    '001009',  # ライフスタイル
    '001010',  # 美容・暮らし・健康・料理
    '001011',  # エンターテインメント（映画・音楽・タレント）
    '001012',  # ホビー・スポーツ・美術
    '001016',  # 語学・学習参考書
    '001017',  # 資格・検定
    '001018',  # パソコン・システム開発
    '001019',  # 科学・医学・技術
    '001020',  # 旅行・留学・アウトドア
    '001021',  # 人文・地歴・哲学・社会
    '001022',  # 教育・学参・受験
    '001023',  # 古書・希少本
}

def get_top_genre_id(user_books):
    """読んだ本のbooksGenreIdから最も多いジャンルコードを返す"""
    genre_counter = Counter()
    for book in user_books:
        genre_ids = book.get('booksGenreId', '')
        if genre_ids:
            # ジャンルIDは階層構造: "001004008/001004" のような形式
            # 最初のコード（最も広いカテゴリ）を使用
            codes = genre_ids.split('/')
            if codes and codes[0]:
                # 最初の6桁（例: 001004）を取得
                main_genre = codes[0][:6] if len(codes[0]) >= 6 else codes[0]
                if main_genre in ALLOWED_BOOK_GENRES:
                    genre_counter[main_genre] += 1
    
    if genre_counter:
        return genre_counter.most_common(1)[0][0]
    return None

def extract_keywords_from_descriptions(user_books, min_rating=4):
    """高評価の本の説明文から頻度の高いキーワードを抽出"""
    high_rated = []
    for b in user_books:
        try:
            rating = b.get('rating', 0)
            rating_int = int(rating) if rating else 0
            if rating_int >= min_rating:
                high_rated.append(b)
        except (ValueError, TypeError):
            continue
    
    if not high_rated:
        high_rated = user_books
    
    all_text = ' '.join(b.get('description', '') for b in high_rated)
    words = re.findall(r'[\u4e00-\u9fff]{2,4}', all_text)
    
    # 除外ワード
    stop_words = {
        'する', 'した', 'して', 'では', 'いる', 'った', 'ある', 'おり', 'この', 'その', 'それ', 'あの',
        '勤務', '仕事', '会社', '業務', '職場', '社員', '部署', '上司', '部下', '同僚',
        'なる', 'できる', '良い', '悪い', '多い', '少ない', '高い', '低い', 'ない', 'られ',
        '今', '今日', '明日', '昨日', '最近', '最新', 'これ', 'それ', 'どれ', 'その',
        'もの', 'こと', '人', '時', '場所', '方法', 'とき', 'ため', 'など', 'から', 'まで',
        '書籍', '出版', '発行', '著者', '読者', 'ページ', '価格', '本書'
    }
    
    words = [w for w in words if w not in stop_words]
    counter = Counter(words)
    return [w for w, _ in counter.most_common(5)]

def is_valid_book(item):
    """
    ホワイトリスト方式: 許可されたジャンルIDのみを受け入れる
    最も厳格な書籍判定
    """
    title = item.get('title', '')
    if not title:
        return False
    
    # 1. ジャンルIDチェック（最優先）
    genre_id = item.get('booksGenreId', '')
    if not genre_id:
        return False
    
    # ジャンルIDの最初の6桁を取得
    main_genre = genre_id.split('/')[0][:6] if genre_id else ''
    
    # ホワイトリストに含まれているかチェック
    if main_genre not in ALLOWED_BOOK_GENRES:
        return False
    
    # 2. ISBNチェック（書籍の証明）
    if not item.get('isbn', ''):
        return False
    
    # 3. 著者チェック（編集部や不明を除外）
    author = item.get('author', '')
    if not author:
        return False
    
    # 編集部・ムックなどを除外
    exclude_authors = ['編集部', '不明', 'ムック', 'MOOK']
    if any(x in author for x in exclude_authors):
        return False
    
    # 4. タイトルチェック（念のため）
    title_lower = title.lower()
    
    # 明らかに書籍以外のキーワード
    exclude_keywords = [
    'photobook', 'photo book', 'photo-book',
    'figure', 'figuarts', 'figma', 'nendoroid',
    'goods', 'calendar', 'poster', 'notebook',
    'dvd', 'blu-ray', 'cd', 'box', 'set',
    # 日本語
    '写真集', 'フォトブック', 'フォト',
    'レターセット', '便箋セット',
    'ノート', '手帳',
    'カレンダー', 'ポスター',
    'グッズ', 'フィギュア', 'ねんどろいど',
    'ムック', '雑誌', '月刊', '週刊',
    'DVD付', 'CD付', 'Blu-ray付',
    '限定版', '特装版', '初回限定', '特典付'
]
    
    if any(keyword in title_lower for keyword in exclude_keywords):
        return False
    
    return True

def recommend_books(user_books, count=3):
    app_id = get_rakuten_app_id()
    if not app_id:
        st.warning("⚠️ RAKUTEN_APP_ID が設定されていません")
        return []

    read_titles = {book.get('title', '').lower() for book in user_books}
    top_genre_id = get_top_genre_id(user_books)
    seasonal_keywords = get_seasonal_keywords()
    desc_keywords = extract_keywords_from_descriptions(user_books)

    # ジャンル優先のロジック
    if top_genre_id:
        keyword = random.choice(seasonal_keywords)
        reason_base = f"あなたが好きなジャンルから{keyword}の季節におすすめの本"
        use_genre = True
    elif desc_keywords:
        keyword = random.choice(desc_keywords)
        reason_base = f"あなたの好みに合った「{keyword}」に関連する本"
        use_genre = False
    else:
        keyword = random.choice(seasonal_keywords)
        reason_base = f"{keyword}の季節におすすめの本"
        use_genre = False

    try:
        url = "https://app.rakuten.co.jp/services/api/BooksBook/Search/20170404"
        params = {
            'applicationId': app_id,
            'format': 'json',
            'hits': 30,
        }
        
        # ジャンル優先
        if use_genre and top_genre_id:
            params['booksGenreId'] = top_genre_id
            if keyword:
                params['keyword'] = keyword
        else:
            params['keyword'] = keyword

        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            st.warning(f"⚠️ 楽天書籍API エラー ({response.status_code}): {response.text[:200]}")
            return []

        data = response.json()
        recommendations = []
        
        for book_item in data.get('Items', []):
            try:
                item = book_item.get('Item', {})
                
                # ホワイトリスト方式でフィルタリング
                if not is_valid_book(item):
                    continue
                
                title = item.get('title', '')
                if title.lower() in read_titles:
                    continue
                
                description = item.get('itemCaption', '')
                if not description:
                    description = '説明なし'
                if len(description) > 200:
                    description = description[:200] + '...'
                
                review_average = item.get('reviewAverage')
                if review_average is not None:
                    try:
                        review_average = float(review_average)
                        if review_average == 0:
                            review_average = None
                    except (ValueError, TypeError):
                        review_average = None
                
                author = item.get('author', '')
                if not author:
                    author = '不明'
                
                genre_id = item.get('booksGenreId', '')
                
                recommendations.append({
                    'title': title,
                    'authors': [author],
                    'description': description,
                    'categories': ['未分類'],
                    'cover_image': item.get('mediumImageUrl', ''),
                    'average_rating': review_average,
                    'booksGenreId': genre_id,
                    'reason': reason_base,
                })
                
                if len(recommendations) >= count:
                    break
            
            except Exception as item_error:
                continue

        # 評価の高い順にソート
        recommendations.sort(
            key=lambda x: (x['average_rating'] is not None, x['average_rating'] or 0),
            reverse=True
        )

        if recommendations:
            st.success(f"📚 楽天書籍APIから{len(recommendations)}件の推薦を取得しました")
        else:
            st.warning("⚠️ 条件に合う書籍が見つかりませんでした。別のジャンルや季節をお試しください。")
        
        return recommendations
    
    except Exception as e:
        st.warning(f"⚠️ 楽天書籍API エラー: {e}")
        return []