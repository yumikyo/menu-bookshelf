import streamlit as st
import os
import zipfile
import shutil
import tempfile

st.set_page_config(page_title="Menu Bookshelf", layout="wide", page_icon="📚")

# ==========================================
# UIデザイン
# ==========================================
st.title("📚 聴くメニューの本棚")
st.markdown("""
お店でダウンロードした**「メニューのZIPファイル」**をここに放り込んでください。
あなただけのメニューライブラリが作れます。
""")

# ==========================================
# サイドバー：ファイルの取り込み
# ==========================================
with st.sidebar:
    st.header("📥 メニューの追加")
    uploaded_zips = st.file_uploader(
        "ZIPファイルをアップロード（複数OK）", 
        type="zip", 
        accept_multiple_files=True
    )
    st.info("※ブラウザを閉じると本棚はリセットされます")

# ==========================================
# メイン処理：本棚の構築
# ==========================================
if not uploaded_zips:
    st.warning("👈 左のサイドバーから、メニューのZIPファイルを追加してください。")
    st.stop()

# 一時フォルダに解凍して整理する
temp_dir = tempfile.mkdtemp()
shops = {} # お店のリスト

for zip_file in uploaded_zips:
    # ZIPファイル名をお店の手がかりにする（例: menu_audio_album.zip）
    # 複数同じ名前だと困るので、アップロード順にIDを振るなどの工夫も可能だが今回はシンプルに
    shop_name = zip_file.name.replace(".zip", "").replace("menu_audio_album", "新しいお店")
    
    # 解凍用のフォルダ作成
    extract_path = os.path.join(temp_dir, shop_name)
    os.makedirs(extract_path, exist_ok=True)
    
    # 解凍実行
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        zip_ref.extractall(extract_path)
    
    # 音声ファイルを探してリスト化
    audio_files = []
    for root, dirs, files in os.walk(extract_path):
        for file in files:
            if file.endswith(".mp3"):
                audio_files.append(os.path.join(root, file))
    
    # トラック番号順に並べ替え（ファイル名が 01_... となっている前提）
    audio_files.sort()
    
    if audio_files:
        shops[shop_name] = audio_files

# ==========================================
# 本棚の表示
# ==========================================
st.divider()

if not shops:
    st.error("ZIPファイルの中に音声が見つかりませんでした。")
else:
    # お店を選ぶ（タブにするか、セレクトボックスにするか）
    # スマホだとセレクトボックスが使いやすい
    selected_shop = st.selectbox("📖 お店を選択してください", list(shops.keys()))
    
    st.header(f"📍 {selected_shop}")
    
    # 選ばれたお店のトラックを表示
    track_list = shops[selected_shop]
    
    for audio_path in track_list:
        # ファイル名からきれいなタイトルを作る
        # 例: ".../01_はじめに.mp3" -> "01 はじめに"
        file_name = os.path.basename(audio_path)
        track_title = file_name.replace(".mp3", "").replace("_", " ")
        
        # カード風に表示
        with st.container():
            st.markdown(f"**{track_title}**")
            st.audio(audio_path)
            st.write("---")

# ==========================================
# クリーンアップ（終了時）
# ==========================================
# Streamlitは再実行のたびに走るので、ここでの削除は難しいが
# OSの一時フォルダなのでいつかは消える
