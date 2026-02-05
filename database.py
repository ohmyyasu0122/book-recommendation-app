import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st
from datetime import datetime

def initialize_firebase():
    """Firebaseの初期化"""
    if not firebase_admin._apps:
        try:
            # Streamlit Cloudの場合
            if 'firebase_credentials' in st.secrets:
                cred = credentials.Certificate(dict(st.secrets['firebase_credentials']))
            else:
                # ローカル開発の場合
                cred = credentials.Certificate('firebase_config.json')
        except:
            # secrets.tomlが存在しない場合(ローカル開発)
            cred = credentials.Certificate('firebase_config.json')
        
        firebase_admin.initialize_app(cred)
    
    return firestore.client()

def save_book(user_id, book_data):
    """書籍データを保存"""
    db = initialize_firebase()
    book_ref = db.collection('users').document(user_id).collection('books').document()
    
    book_data['created_at'] = datetime.now()
    # ratingを明示的に整数に変換
    rating = book_data.get('rating', 0)
    book_data['rating'] = int(rating) if rating else 0
    
    book_ref.set(book_data)
    return book_ref.id

def get_user_books(user_id):
    """ユーザーの読書記録を取得"""
    db = initialize_firebase()
    books_ref = db.collection('users').document(user_id).collection('books')
    books = books_ref.order_by('completed_date', direction=firestore.Query.DESCENDING).stream()
    
    book_list = []
    for book in books:
        book_data = book.to_dict()
        book_data['id'] = book.id
        
        # ratingを明示的に整数に変換（文字列で保存されている場合に対応）
        if 'rating' in book_data:
            try:
                book_data['rating'] = int(book_data['rating'])
            except (ValueError, TypeError):
                book_data['rating'] = 0
        
        book_list.append(book_data)
    
    return book_list

def update_book_rating(user_id, book_id, rating):
    """書籍の評価を更新"""
    db = initialize_firebase()
    book_ref = db.collection('users').document(user_id).collection('books').document(book_id)
    # ratingを明示的に整数に変換
    try:
        rating_int = int(rating)
    except (ValueError, TypeError):
        rating_int = 0
    book_ref.update({'rating': rating_int})

def get_highly_rated_books(user_id, min_rating=4):
    """高評価の書籍を取得"""
    db = initialize_firebase()
    books_ref = db.collection('users').document(user_id).collection('books')
    # min_ratingを明示的に整数に
    books = books_ref.where('rating', '>=', int(min_rating)).stream()
    
    book_list = []
    for book in books:
        book_data = book.to_dict()
        # ratingを明示的に整数に変換
        if 'rating' in book_data:
            try:
                book_data['rating'] = int(book_data['rating'])
            except (ValueError, TypeError):
                book_data['rating'] = 0
        book_list.append(book_data)
    
    return book_list
