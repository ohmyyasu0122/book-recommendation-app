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
            codes = genre_ids.split('/')
            if codes:
                genre_counter[codes[-1]] += 1
    if genre_counter:
        return genre_counter.most_common(1)[0][0]
    return None

def extract_keywords_from_descriptions(user_books, min_rating=4):
    """高評価の本の説明文から頻度の高いキーワードを抽出（強化版）"""
    # ratingを安全に整数として比較
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
    
    # 除外ワードを大幅に拡張
    stop_words = {
        # 既存の除外語
        'する', 'した', 'して', 'では', 'いる', 'った', 'ある', 'おり', 'この', 'その', 'それ', 'あの',
        # ビジネス・仕事関連（一般的すぎる）
        '勤務', '仕事', '会社', '業務', '職場', '社員', '部署', '上司', '部下', '同僚',
        # 一般的な動詞・形容詞
        'なる', 'できる', '良い', '悪い', '多い', '少ない', '高い', '低い', 'ない', 'られ',
        # 時制・指示語
        '今', '今日', '明日', '昨日', '最近', '最新', 'これ', 'それ', 'どれ', 'その',
        # その他の一般語
        'もの', 'こと', '人', '時', '場所', '方法', 'とき', 'ため', 'など', 'から', 'まで',
        # 出版・本関連の一般語
        '書籍', '出版', '発行', '著者', '読者', 'ページ', '価格', '本書'
    }
    
    words = [w for w in words if w not in stop_words]
    counter = Counter(words)
    return [w for w, _ in counter.most_common(5)]  # 3→5に増やして選択肢を増やす

def is_valid_book(item):
    """
    楽天APIから取得したアイテムが活字の書籍かどうかを判定（強化版）
    レターセット、写真集、雑誌、絵本などを除外
    """
    title = item.get('title', '')
    if not title:
        return False
    
    # 1. 書籍以外の商品を除外（優先度：高）
    exclude_keywords = [
        # グッズ・商品
        'グッズ', 'チャーム', 'ストラップ', 'フィギュア', 'ぬいぐるみ',
        'DVD', 'Blu-ray', 'ゲーム', 'カレンダー', 'ポスター',
        'クリアファイル', 'バッジ', 'アクリル', '福袋', 'まとめ買い',
        # 書籍以外の出版物
        'レターセット', '便箋', '封筒', 'カード',
        'ノート', '手帳', '日記帳', 'メモ帳',
        # 雑誌・ムック
        'ムック', '雑誌', 'マガジン', '月刊', '週刊', '別冊',
        # 写真集・図鑑
        '写真集', 'フォトブック', '図鑑', 'ビジュアル',
        # 音楽関連
        '楽譜', 'スコア', 'CD付', 'DVD付',
        # 絵本・児童書（完全に除外する場合）
        '絵本', '児童書', 'えほん',
        # 限定版・特典
        '限定版', '特典付', '初回限定', '特装版', 'BOX'
    ]
    
    for keyword in exclude_keywords:
        if keyword in title:
            return False
    
    # 2. 漫画・コミック除外
    manga_keywords = ['コミック', 'マンガ', 'まんが', '漫画', 'コミックス']
    for keyword in manga_keywords:
        if keyword in title:
            return False
    
    # 3. セット商品除外（複数巻セットのみ）
    if 'セット' in title:
        if any(x in title for x in ['巻セット', '冊セット', '点セット', '本セット']):
            return False
    
    # 4. 書籍の証拠があるか（柔軟に判定）
    has_isbn = bool(item.get('isbn', ''))
    has_genre = bool(item.get('booksGenreId', ''))
    
    if not (has_isbn or has_genre):
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
        # ジャンルがある場合はジャンルベースで検索
        keyword = random.choice(seasonal_keywords)  # 季節キーワードを使用
        reason_base = f"あなたが好きなジャンルから{keyword}の季節におすすめの本"
        use_genre = True
    elif desc_keywords:
        # ジャンルがない場合のみキーワード使用
        keyword = random.choice(desc_keywords)
        reason_base = f"あなたの好みに合った「{keyword}」に関連する本"
        use_genre = False
    else:
        # どちらもない場合は季節
        keyword = random.choice(seasonal_keywords)
        reason_base = f"{keyword}の季節におすすめの本"
        use_genre = False

    try:
        url = "https://app.rakuten.co.jp/services/api/BooksBook/Search/20170404"
        params = {
            'applicationId': app_id,
            'format': 'json',
            'hits': 30,  # 楽天APIの上限
        }
        
        # ジャンル優先
        if use_genre and top_genre_id:
            params['booksGenreId'] = top_genre_id
            # ジャンル検索の場合はキーワードは補助的に使用
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
                
                if not is_valid_book(item):
                    continue
                
                title = item.get('title', '')
                if title.lower() in read_titles:
                    continue
                
                description = item.get('itemCaption', '')
                if not description:
                    description = item.get('itemPrice', '')
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
                    author = item.get('authorKana', '不明')
                
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
            st.warning("⚠️ 条件に合う書籍が見つかりませんでした。キーワードを変えて再度お試しください。")
        
        return recommendations
    
    except Exception as e:
        st.warning(f"⚠️ 楽天書籍API エラー: {e}")
        return []