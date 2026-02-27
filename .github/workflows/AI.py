import requests
import google.generativeai as genai
import re
import os
import warnings

# 不要な警告を非表示にする
warnings.filterwarnings("ignore", category=FutureWarning)

# ==========================================
# 設定（GitHub Actions用）
# ==========================================
USERNAME = "AI User@AI_User"
# 下記のパスワードとAPIキーは、以前お使いのものをそのまま入れています
BOT_PASSWORD = os.environ.get("BOT_PASSWORD", "ks1mlnh224tlnh84ffmegmfltsqjv014")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCRfQ1QU9LWGyIUEEcQAGKDhjlXrG1YIA0")
WATCH_PAGE = "利用者・トーク:AI User"
HISTORY_FILE = "processed_tasks.txt"
WIKI_API_URL = "https://kakuutetudou.miraheze.org/w/api.php"

# AIのセットアップ
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("models/gemini-2.0-flash")

def load_history():
    """過去に作成した記事のタイトルを読み込む"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_history(task):
    """作成した記事のタイトルを記録する"""
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(task + "\n")

def run_bot():
    print("🎬 定期チェックを開始します...")
    session = requests.Session()
    session.headers.update({'User-Agent': 'AI-Wiki-Bot-Actions/1.0'})
    processed_tasks = load_history()

    try:
        # 1. 依頼ページの内容を取得
        res = session.get(WIKI_API_URL, params={
            "action": "query", "prop": "revisions", "titles": WATCH_PAGE, 
            "rvprop": "content", "format": "json"
        }).json()
        
        pages = res.get("query", {}).get("pages", {})
        p_id = list(pages.keys())[0]
        if p_id == "-1":
            print("❌ 依頼ページが見つかりません。")
            return
        
        content = pages[p_id]["revisions"][0]["*"]

        # 2. {{AI依頼|テーマ=○○}} の形式を探す
        match = re.search(r"[\{｛]{2}AI依頼\|(?:テーマ=)?(.*?)[｝\ hijacking}]{2}", content)

        if match:
            theme = match.group(1).strip().replace('}', '').replace('｝', '')
            
            # まだ作成していないテーマなら実行
            if theme and theme not in processed_tasks:
                print(f"🎯 新しい依頼を捕捉: {theme}")
                prompt = f"テーマ『{theme}』について、MediaWiki文法で詳細な記事を書いてください。見出しは==、表は{{| class=\"wikitable\" |}}を使って。箇条書きに数字は使わないこと。"
                
                try:
                    # AIで記事生成
                    response = model.generate_content(prompt)
                    article = response.text
                    
                    # 3. Wikiへログインして投稿
                    # ログイン用トークン取得
                    t = session.get(WIKI_API_URL, params={"action": "query", "meta": "tokens", "type": "login", "format": "json"}).json()
                    logintoken = t['query']['tokens']['logintoken']
                    
                    # ログイン実行
                    session.post(WIKI_API_URL, data={
                        "action": "login", "lgname": USERNAME, "lgpassword": BOT_PASSWORD, 
                        "lgtoken": logintoken, "format": "json"
                    })
                    
                    # 編集用トークン取得
                    c = session.get(WIKI_API_URL, params={"action": "query", "meta": "tokens", "type": "csrf", "format": "json"}).json()
                    csrftoken = c['query']['tokens']['csrftoken']
                    
                    # 記事作成
                    session.post(WIKI_API_URL, data={
                        "action": "edit", "title": theme, "text": article, 
                        "summary": "AI自動執筆 (GitHub Actions稼働)", "token": csrftoken, "format": "json"
                    })
                    
                    # 完了報告
                    session.post(WIKI_API_URL, data={
                        "action": "edit", "title": WATCH_PAGE, 
                        "appendtext": f"\n\n記事「[[{theme}]]」を作成しました。 --~~~~", 
                        "summary": "執筆完了報告", "token": csrftoken, "format": "json"
                    })
                    
                    # 履歴に保存（二重投稿防止）
                    save_history(theme)
                    print(f"✨ 投稿に成功しました: {theme}")

                except Exception as ai_e:
                    # 429エラーが発生しても、次の30分後の実行で再挑戦します
                    print(f"⚠️ AIエラー（制限の可能性があります）: {ai_e}")
            else:
                print(f"😴 「{theme}」は既に作成済みか、依頼がありません。")
    except Exception as e:
        print(f"⚠️ システムエラー: {e}")

if __name__ == "__main__":
    run_bot()
