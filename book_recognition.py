from google.cloud import vision
from google.oauth2 import service_account
import io
from PIL import Image
from typing import Tuple, List, Dict
import requests
import streamlit as st
import os
import re

def get_vision_client():
    """Vision APIクライアントを取得（Streamlit Cloud対応）"""
    try:
        if 'gcp_service_account' in st.secrets:
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
            return vision.ImageAnnotatorClient(credentials=credentials)
        elif os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
            return vision.ImageAnnotatorClient()
        else:
            raise Exception("Google Cloud認証情報が設定されていません")
    except Exception as e:
        raise Exception(f"Vision APIクライアントの初期化に失敗: {str(e)}")

def clean_text(text: str) -> str:
    """テキストをクリーンアップ"""
    # 英数字の誤認識を修正
    text = re.sub(r'Masciate\s+un', 'Masquerade', text, flags=re.IGNORECASE)
    # 出版社名などのノイズを除去
    text = re.sub(r'集英社.*', '', text)
    text = re.sub(r'文庫.*', '', text)
    text = re.sub(r'新潮.*', '', text)
    # 余分な空白を削除
    text = ' '.join(text.split())
    return text

def recognize_book_from_image(image: Image.Image) -> Tuple[List[Dict], str]:
    """
    Google Cloud Vision APIを使用して画像から書籍情報を認識
    """
    try:
        client = get_vision_client()
        
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        vision_image = vision.Image(content=img_byte_arr)
        response = client.text_detection(image=vision_image)
        
        if response.error.message:
            raise Exception(f'Vision API Error: {response.error.message}')
        
        texts = response.text_annotations
        
        if not texts:
            return [], "画像からテキストを検出できませんでした"
        
        extracted_text = texts[0].description
        cleaned_text = clean_text(extracted_text)
        
        # 複数の検索クエリを生成
        search_queries = generate_search_queries(cleaned_text, extracted_text)
        
        # Google Books APIで検索
        books = []
        for query in search_queries:
            found_books = search_books_by_query(query)
            if found_books:
                books.extend(found_books)
                if len(books) >= 5:
                    break
        
        unique_books = remove_duplicate_books(books)
        
        if unique_books:
            return unique_books[:5], extracted_text
        else:
            return [], f"書籍が見つかりませんでした。抽出テキスト: {extracted_text}"
            
    except Exception as e:
        return [], f"エラーが発生しました: {str(e)}"

def generate_search_queries(cleaned_text: str, original_text: str) -> List[str]:
    """
    抽出されたテキストから複数の検索クエリを生成
    """
    queries = []
    
    # 1. クリーンアップされたテキスト全体
    queries.append(cleaned_text)
    
    # 2. 行ごとに分割
    lines = original_text.split('\n')
    
    # 3. 著者名とタイトルを抽出（日本の著者名パターン）
    author_pattern = r'([ぁ-ん一-龯]{2,4}[ぁ-ん一-龯]{2,4})'
    authors = re.findall(author_pattern, original_text)
    
    # 4. カタカナのタイトルを抽出
    title_pattern = r'([ァ-ヴー・]{3,})'
    titles = re.findall(title_pattern, original_text)
    
    # 5. 著者名 + タイトルの組み合わせ
    if authors and titles:
        for author in authors[:2]:
            for title in titles[:2]:
                queries.append(f"{author} {title}")
    
    # 6. タイトルのみ
    for title in titles[:3]:
        queries.append(title)
    
    # 7. 最初の2行を結合
    if len(lines) >= 2:
        queries.append(' '.join(lines[:2]))
    
    # 8. 最初の行のみ
    if lines:
        queries.append(lines[0])
    
    # 重複を除去
    return list(dict.fromkeys([q for q in queries if len(q.strip()) > 2]))

def search_books_by_query(query: str) -> List[Dict]:
    """
    Google Books APIで書籍を検索
    """
    try:
        url = "https://www.googleapis.com/books/v1/volumes"
        params = {
            'q': query,
            'maxResults': 5,
            'langRestrict': 'ja',
            'printType': 'books'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        books = []
        for item in data.get('items', []):
            volume_info = item.get('volumeInfo', {})
            
            book = {
                'title': volume_info.get('title', '不明'),
                'authors': volume_info.get('authors', ['不明']),
                'categories': volume_info.get('categories', ['未分類']),
                'cover_image': volume_info.get('imageLinks', {}).get('thumbnail', ''),
                'description': volume_info.get('description', '説明なし'),
                'average_rating': volume_info.get('averageRating', 0),
                'published_date': volume_info.get('publishedDate', '不明')
            }
            books.append(book)
        
        return books
        
    except Exception as e:
        print(f"Google Books API検索エラー: {str(e)}")
        return []

def remove_duplicate_books(books: List[Dict]) -> List[Dict]:
    """
    重複する書籍を除去
    """
    unique_books = []
    seen_titles = set()
    
    for book in books:
        title = book['title'].lower().strip()
        if title not in seen_titles:
            unique_books.append(book)
            seen_titles.add(title)
    
    return unique_books
