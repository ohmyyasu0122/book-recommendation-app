from google.cloud import vision
import io
from PIL import Image
from typing import Tuple, List, Dict
import requests

def recognize_book_from_image(image: Image.Image) -> Tuple[List[Dict], str]:
    """
    Google Cloud Vision APIを使用して画像から書籍情報を認識
    
    Args:
        image: PIL Image object
        
    Returns:
        Tuple[List[Dict], str]: (書籍情報リスト, 抽出されたテキスト)
    """
    try:
        # Vision APIクライアントを初期化
        client = vision.ImageAnnotatorClient()
        
        # PIL Imageをバイトデータに変換
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        # Vision API用のImageオブジェクトを作成
        vision_image = vision.Image(content=img_byte_arr)
        
        # テキスト検出を実行
        response = client.text_detection(image=vision_image)
        
        # エラーチェック
        if response.error.message:
            raise Exception(f'Vision API Error: {response.error.message}')
        
        # テキストを抽出
        texts = response.text_annotations
        
        if not texts:
            return [], "画像からテキストを検出できませんでした"
        
        # 最初の要素に全体のテキストが含まれる
        extracted_text = texts[0].description
        
        # 改行を空白に置換してクリーンアップ
        cleaned_text = ' '.join(extracted_text.split())
        
        # 複数の検索クエリを生成
        search_queries = generate_search_queries(cleaned_text)
        
        # Google Books APIで検索
        books = []
        for query in search_queries:
            found_books = search_books_by_query(query)
            if found_books:
                books.extend(found_books)
                if len(books) >= 5:
                    break
        
        # 重複を除去
        unique_books = remove_duplicate_books(books)
        
        if unique_books:
            return unique_books[:5], extracted_text
        else:
            return [], f"書籍が見つかりませんでした。抽出テキスト: {extracted_text}"
            
    except Exception as e:
        return [], f"エラーが発生しました: {str(e)}"

def generate_search_queries(text: str) -> List[str]:
    """
    抽出されたテキストから複数の検索クエリを生成
    
    Args:
        text: 抽出されたテキスト
        
    Returns:
        List[str]: 検索クエリのリスト
    """
    queries = []
    
    # 全体のテキスト
    queries.append(text)
    
    # 最初の50文字（タイトルの可能性が高い）
    if len(text) > 10:
        queries.append(text[:50])
    
    # 行ごとに分割して最初の数行
    lines = text.split('\n')
    if len(lines) > 1:
        # 最初の2行を結合
        queries.append(' '.join(lines[:2]))
        # 最初の行のみ
        queries.append(lines[0])
    
    # 重複を除去
    return list(dict.fromkeys(queries))

def search_books_by_query(query: str) -> List[Dict]:
    """
    Google Books APIで書籍を検索
    
    Args:
        query: 検索クエリ
        
    Returns:
        List[Dict]: 書籍情報のリスト
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
    
    Args:
        books: 書籍情報のリスト
        
    Returns:
        List[Dict]: 重複を除去した書籍情報のリスト
    """
    unique_books = []
    seen_titles = set()
    
    for book in books:
        title = book['title'].lower().strip()
        if title not in seen_titles:
            unique_books.append(book)
            seen_titles.add(title)
    
    return unique_books
