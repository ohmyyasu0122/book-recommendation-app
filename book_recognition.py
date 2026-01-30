import pytesseract
from PIL import Image
import requests
import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

def extract_text_from_image(image):
    """画像からテキストを抽出（改善版）"""
    try:
        # 画像の前処理
        # グレースケール化
        image = image.convert('L')
        
        # コントラスト強化
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)
        
        # Tesseract OCRでテキスト抽出
        # 縦書き対応のため、複数の設定を試す
        configs = [
            '--psm 6',  # 単一ブロック
            '--psm 11', # 疎なテキスト
            '--psm 12', # 疎なテキスト（OSD付き）
        ]
        
        texts = []
        for config in configs:
            text = pytesseract.image_to_string(image, lang='jpn+eng', config=config)
            if text.strip():
                texts.append(text.strip())
        
        # 最も長いテキストを採用
        if texts:
            return max(texts, key=len)
        
        return ""
    except Exception as e:
        st.error(f"テキスト抽出エラー: {e}")
        return ""

def search_book_by_title(query):
    """Google Books APIで書籍を検索"""
    api_key = os.getenv('GOOGLE_BOOKS_API_KEY')
    
    # クエリをクリーンアップ
    query = query.replace('\n', ' ').strip()
    
    # 短すぎる場合はエラー
    if len(query) < 2:
        return []
    
    base_url = "https://www.googleapis.com/books/v1/volumes"
    params = {
        'q': query,
        'maxResults': 5,
        'langRestrict': 'ja',
        'printType': 'books'
    }
    
    if api_key:
        params['key'] = api_key
    
    try:
        response = requests.get(base_url, params=params, timeout=10)
        
        # ステータスコードを確認
        if response.status_code == 403:
            st.error("Google Books APIのアクセスが制限されています。APIキーの設定を確認してください。")
            return []
        
        response.raise_for_status()
        data = response.json()
        
        books = []
        if 'items' in data:
            for item in data['items']:
                volume_info = item.get('volumeInfo', {})
                
                book = {
                    'title': volume_info.get('title', '不明'),
                    'authors': volume_info.get('authors', ['不明']),
                    'description': volume_info.get('description', '説明なし'),
                    'categories': volume_info.get('categories', ['未分類']),
                    'cover_image': volume_info.get('imageLinks', {}).get('thumbnail', ''),
                    'published_date': volume_info.get('publishedDate', '不明'),
                    'average_rating': volume_info.get('averageRating', 0)
                }
                books.append(book)
        
        return books
    
    except requests.exceptions.Timeout:
        st.error("API接続がタイムアウトしました")
        return []
    except Exception as e:
        st.error(f"API検索エラー: {e}")
        return []

def recognize_book_from_image(image):
    """画像から書籍情報を取得"""
    # Step 1: OCRでテキスト抽出
    extracted_text = extract_text_from_image(image)
    
    if not extracted_text:
        return None, "テキストを抽出できませんでした"
    
    # Step 2: Google Books APIで検索
    books = search_book_by_title(extracted_text)
    
    if not books:
        return None, f"書籍が見つかりませんでした。抽出テキスト: {extracted_text}"
    
    return books, extracted_text
