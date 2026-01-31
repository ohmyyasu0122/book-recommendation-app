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

def extract_isbn(text: str) -> str:
    """テキストからISBNを抽出"""
    # ISBN-13 (978 or 979で始まる13桁)
    isbn13_pattern = r'97[89][\d\-\s]{10,17}'
    # ISBN-10 (10桁)
    isbn10_pattern = r'(?:\d[\-\s]?){9}[\dXx]'
    
    # ISBN-13を優先的に検索
    isbn13_matches = re.findall(isbn13_pattern, text)
    if isbn13_matches:
        # ハイフンとスペースを除去
        isbn = re.sub(r'[\-\s]', '', isbn13_matches[0])
        if len(isbn) == 13:
            return isbn
    
    # ISBN-10を検索
    isbn10_matches = re.findall(isbn10_pattern, text)
    if isbn10_matches:
        isbn = re.sub(r'[\-\s]', '', isbn10_matches[0])
        if len(isbn) == 10:
            return isbn
    
    return None

def search_by_isbn(isbn: str) -> List[Dict]:
    """ISBNで書籍を検索"""
    try:
        url = "https://www.googleapis.com/books/v1/volumes"
        params = {
            'q': f'isbn:{isbn}',
            'maxResults': 1
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
                'published_date': volume_info.get('publishedDate', '不明'),
                'isbn': isbn
            }
            books.append(book)
        
        return books
        
    except Exception as e:
        print(f"ISBN検索エラー: {str(e)}")
        return []

def recognize_book_from_image(image: Image.Image) -> Tuple[List[Dict], str]:
    """
    Google Cloud Vision APIを使用して画像から書籍情報を認識
    ISBNを優先的に検索
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
        
        # まずISBNを探す
        isbn = extract_isbn(extracted_text)
        
        books = []
        
        if isbn:
            # ISBNが見つかった場合、ISBNで検索
            st.info(f"📚 ISBN検出: {isbn}")
            books = search_by_isbn(isbn)
            
            if books:
                return books, f"ISBN: {isbn}\n\n{extracted_text}"
        
        # ISBNが見つからない、または検索結果がない場合、テキスト検索にフォールバック
        st.warning("ISBNが検出できませんでした。テキスト検索を試みます...")
        
        search_queries = generate_search_queries(extracted_text)
        
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
            return [], f"書籍が見つかりませんでした。\n\n抽出テキスト:\n{extracted_text}\n\n💡 ヒント: 裏表紙のISBN（978で始まる13桁の数字）を撮影すると、より確実に検索できます。"
            
    except Exception as e:
        return [], f"エラーが発生しました: {str(e)}"

def generate_search_queries(text: str) -> List[str]:
    """
    抽出されたテキストから複数の検索クエリを生成
    """
    queries = []
    
    lines = text.split('\n')
    
    # 著者名を抽出（日本の著者名パターン）
    author_pattern = r'([ぁ-ん一-龯]{2,4}[ぁ-ん一-龯]{2,4})'
    authors = re.findall(author_pattern, text)
    
    # カタカナのタイトルを抽出
    title_pattern = r'([ァ-ヴー・]{3,})'
    titles = re.findall(title_pattern, text)
    
    # 著者名 + タイトルの組み合わせ
    if authors and titles:
        for author in authors[:2]:
            for title in titles[:2]:
                queries.append(f"{author} {title}")
    
    # タイトルのみ
    for title in titles[:3]:
        queries.append(title)
    
    # 最初の2行を結合
    if len(lines) >= 2:
        queries.append(' '.join(lines[:2]))
    
    # 最初の行のみ
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
