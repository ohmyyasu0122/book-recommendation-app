# Book Recommendation App

書籍の表紙を撮影して、読書記録とおすすめを管理するアプリ

## 機能

- 📸 書籍の表紙をカメラで撮影
- 🔍 Google Cloud Vision APIで自動認識
- �� 読書履歴の記録
- ✨ AIによるおすすめ書籍の提案

## セットアップ

### 1. 必要なパッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. Firebase設定

`firebase_config.json` を作成してFirebaseの認証情報を設定

### 3. Google Cloud Vision API設定

1. Google Cloud Platformでプロジェクトを作成
2. Vision APIを有効化
3. サービスアカウントを作成
4. 認証キーをダウンロード (`book-app-credentials.json`)
5. 環境変数を設定:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/book-app-credentials.json"
```

### 4. アプリの起動

```bash
streamlit run app.py
```

## 技術スタック

- **フロントエンド**: Streamlit
- **バックエンド**: Python
- **データベース**: Firebase Firestore
- **OCR**: Google Cloud Vision API
- **書籍情報**: Google Books API

## 注意事項

- `book-app-credentials.json` と `firebase_config.json` は機密情報です
- これらのファイルは絶対にGitHubにプッシュしないでください
- `.gitignore` で除外されています

## ライセンス

MIT License
