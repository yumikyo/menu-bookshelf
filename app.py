import streamlit as st
import zipfile
import base64
import json
import os
import streamlit.components.v1 as components

# ページ設定
st.set_page_config(page_title="My Menu Book", layout="centered")

st.markdown("""
<style>
    body { font-family: sans-serif; }
    h1 { color: #ff4b4b; }
    .stButton button { width: 100%; }
</style>
""", unsafe_allow_html=True)

st.title("🎧 My Menu Book")

# データ管理（メモリ保存）
if 'my_library' not in st.session_state:
    st.session_state.my_library = {}

# --- サイドバー：本の追加 ---
with st.sidebar:
    st.header("➕ 本の追加")
    st.info("生成アプリで作ったZIPファイルをここで登録します。")
    
    uploaded_zips = st.file_uploader("ZIPファイルをドロップ", type="zip", accept_multiple_files=True)
    
    if uploaded_zips:
        for zfile in uploaded_zips:
            store_name = os.path.splitext(zfile.name)[0].replace("_", " ")
            st.session_state.my_library[store_name] = zfile
        st.success(f"{len(uploaded_zips)}冊を追加しました！")

    st.divider()
    if st.button("🗑️ 本棚を空にする"):
        st.session_state.my_library = {}
        st.session_state.selected_shop = None
        st.rerun()

# プレイヤー生成関数
def render_player(shop_name):
    zfile = st.session_state.my_library[shop_name]
    playlist_data = []

    try:
        with zipfile.ZipFile(zfile) as z:
            file_list = sorted(z.namelist())
            for f in file_list:
                if f.endswith(".mp3"):
                    data = z.read(f)
                    b64_data = base64.b64encode(data).decode()
                    title = f.replace(".mp3", "").replace("_", " ")
                    playlist_data.append({"title": title, "src": f"data:audio/mp3;base64,{b64_data}"})
    except Exception as e:
        st.error(f"ファイルの読み込みエラー: {e}"); return

    playlist_json = json.dumps(playlist_data, ensure_ascii=False)

    html_template = """<!DOCTYPE html><html><head><style>
        .player-container { border: 2px solid #e0e0e0; border-radius: 15px; padding: 20px; background-color: #f9f9f9; text-align: center; }
        .track-title { font-size: 20px; font-weight: bold; color: #333; margin-bottom: 15px; padding: 10px; background: #fff; border-radius: 8px; border-left: 5px solid #ff4b4b; }
        .controls { display: flex; gap: 10px; margin: 15px 0; }
        button { flex: 1; padding: 15px; font-size: 18px; font-weight: bold; color: white; background-color: #ff4b4b; border: none; border-radius: 8px; cursor: pointer; }
        .track-list { margin-top: 20px; text-align: left; max-height: 250px; overflow-y: auto; border-top: 1px solid #ddd; padding-top: 10px; }
        .track-item { padding: 10px; border-bottom: 1px solid #eee; cursor: pointer; }
        .track-item.active { background-color: #ffecec; font-weight: bold; color: #ff4b4b; }
    </style></head><body>
    <div class="player-container">
        <div class="track-title" id="title">Loading...</div>
        <audio id="audio" controls style="width:100%"></audio>
        <div class="controls"><button onclick="prev()">⏮</button><button onclick="toggle()" id="pb">▶</button><button onclick="next()">⏭</button></div>
        <div style="text-align:center; margin-top:10px;">速度: <select id="speed" onchange="spd()"><option value="1.0">1.0</option><option value="1.4" selected>1.4</option><option value="2.0">2.0</option></select></div>
        <div class="track-list" id="list"></div>
    </div>
    <script>
        const pl = __PLAYLIST__; let idx = 0;
        const au = document.getElementById('audio'); const ti = document.getElementById('title'); const pb = document.getElementById('play-btn'); const ls = document.getElementById('list');
        function init() { render(); load(0); spd(); }
        function load(i) { idx = i; au.src = pl[idx].src; ti.innerText = pl[idx].title; highlight(); spd(); }
        function toggle() { au.paused ? (au.play(), pb.innerText="⏸") : (au.pause(), pb.innerText="▶"); }
        function next() { if(idx < pl.length-1) { load(idx+1); au.play(); pb.innerText="⏸"; } }
        function prev() { if(idx > 0) { load(idx-1); au.play(); pb.innerText="⏸"; } }
        function spd() { au.playbackRate = parseFloat(document.getElementById('speed').value); }
        au.onended = function() { idx < pl.length-1 ? next() : pb.innerText="▶"; };
        function render() { ls.innerHTML = ""; pl.forEach((t, i) => { const d = document.createElement('div'); d.className = "track-item"; d.id = "tr-" + i; d.innerText = (i+1) + ". " + t.title; d.onclick = () => { load(i); au.play(); pb.innerText="⏸"; }; ls.appendChild(d); }); }
        function highlight() { document.querySelectorAll('.track-item').forEach(e => e.classList.remove('active')); const el = document.getElementById("tr-" + idx); if(el) { el.classList.add('active'); el.scrollIntoView({behavior:'smooth', block:'nearest'}); } }
        init();
    </script></body></html>"""
    
    st.components.v1.html(html_template.replace("__PLAYLIST__", playlist_json), height=550)

# --- 画面切り替え ---
if 'selected_shop' not in st.session_state:
    st.session_state.selected_shop = None

if st.session_state.selected_shop:
    shop_name = st.session_state.selected_shop
    st.markdown(f"### 🎧 再生中: {shop_name}")
    if st.button("⬅️ リストに戻る", use_container_width=True):
        st.session_state.selected_shop = None
        st.rerun()
    st.markdown("---")
    render_player(shop_name)
else:
    st.markdown("#### 📚 本棚")
    search_query = st.text_input("🔍 お店を検索", placeholder="例: カフェ")
    if not st.session_state.my_library:
        st.info("👈 左のサイドバーにZIPファイルをアップロードしてください。")
    shop_list = list(st.session_state.my_library.keys())
    if search_query:
        shop_list = [name for name in shop_list if search_query in name]
    for shop_name in shop_list:
        if st.button(f"📖 {shop_name} を開く", use_container_width=True):
            st.session_state.selected_shop = shop_name
            st.rerun()
