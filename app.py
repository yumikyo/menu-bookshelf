import streamlit as st
import zipfile
import base64
import json
import os
import re
import hashlib
from io import BytesIO
import html as html_lib
import streamlit.components.v1 as components

# =========================
# 永続化：保存先（サーバーのローカルディスク）
# =========================
DATA_DIR = "menu_book_data"
LIB_DIR = os.path.join(DATA_DIR, "library")
INDEX_PATH = os.path.join(DATA_DIR, "index.json")

os.makedirs(LIB_DIR, exist_ok=True)

# =========================
# ページ設定
# =========================
st.set_page_config(page_title="My Menu Book", layout="centered")

st.markdown("""
<style>
    body { font-family: sans-serif; }
    h1 { color: #ff4b4b; }
    .stButton button { width: 100%; }
</style>
""", unsafe_allow_html=True)

st.title("🎧 My Menu Book")

# =========================
# 永続化ユーティリティ
# =========================
def load_index():
    if not os.path.exists(INDEX_PATH):
        return {}
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}

def save_index(index: dict):
    tmp = INDEX_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    os.replace(tmp, INDEX_PATH)

def shop_zip_path(shop_id: str) -> str:
    return os.path.join(LIB_DIR, f"{shop_id}.zip")

def normalize_https_url(u: str) -> str:
    """https:// で始まればOK（短縮URL含む）。それ以外は空。"""
    if not u:
        return ""
    u = u.strip()
    if u.lower().startswith("https://"):
        return u
    return ""

def parse_store_and_date_from_filename(zip_filename: str):
    """
    例: "中国料理八八_20251212.zip" -> ("中国料理八八", "20251212")
    例: "Cafe_Tanaka_20251212.zip" -> ("Cafe Tanaka", "20251212")
    日付が無い/形式が違う場合は date=None
    """
    name = os.path.splitext(zip_filename)[0]
    m = re.search(r"_(\d{8})(?:_.*)?$", name)
    date = m.group(1) if m else None
    store = re.sub(r"_(\d{8}).*$", "", name)
    store = store.replace("_", " ").strip()
    return store, date

def read_manifest(z: zipfile.ZipFile):
    """manifest.json があれば読む（推奨）"""
    try:
        if "manifest.json" in z.namelist():
            raw = z.read("manifest.json")
            return json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    return None

def extract_https_url_from_html_in_zip(z: zipfile.ZipFile):
    """
    旧ZIPフォールバック：
    HTML内の href="https://..." を拾う（最初に見つかったもの）
    """
    try:
        for f in z.namelist():
            if f.lower().endswith(".html"):
                html_content = z.read(f).decode("utf-8", errors="ignore")
                m = re.search(r'href="(https://[^"]+)"', html_content)
                if m:
                    return normalize_https_url(m.group(1))
    except Exception:
        pass
    return ""

def build_playlist_from_zip(z: zipfile.ZipFile, manifest: dict | None):
    """
    mp3を読み込み、base64 data URIでプレイリスト化
    - manifest.tracks があればその順を優先（title/filename）
    - 無ければファイル名順
    """
    mp3_files = [f for f in z.namelist() if f.lower().endswith(".mp3")]
    if not mp3_files:
        return []

    mp3_sorted = sorted(mp3_files)

    ordered = []
    title_map = {}

    if manifest and isinstance(manifest.get("tracks"), list):
        for t in manifest["tracks"]:
            if not isinstance(t, dict):
                continue
            fn = t.get("filename")
            ti = t.get("title")
            if isinstance(fn, str) and fn in mp3_files:
                ordered.append(fn)
                if isinstance(ti, str) and ti.strip():
                    title_map[fn] = ti.strip()

        for f in mp3_sorted:
            if f not in ordered:
                ordered.append(f)
    else:
        ordered = mp3_sorted

    playlist = []
    for f in ordered:
        data = z.read(f)
        b64_data = base64.b64encode(data).decode("utf-8")

        if f in title_map:
            title = title_map[f]
        else:
            title = os.path.splitext(os.path.basename(f))[0].replace("_", " ")
            title = re.sub(r"^\d{2}\s*", "", title)

        playlist.append({"title": title, "src": f"data:audio/mp3;base64,{b64_data}"})

    return playlist

def make_display_key(store_name: str, menu_title: str | None, date: str | None):
    parts = [store_name]
    if menu_title:
        parts.append(f"({menu_title})")
    if date:
        parts.append(date)
    return " ".join([p for p in parts if p]).strip()

def render_player(shop_meta: dict):
    path = shop_meta.get("zip_path")
    if not path or not os.path.exists(path):
        st.error("保存されたZIPが見つかりませんでした。")
        return

    try:
        with zipfile.ZipFile(path) as z:
            manifest = read_manifest(z)

            map_url = ""
            if manifest and isinstance(manifest.get("map_url"), str):
                map_url = normalize_https_url(manifest.get("map_url"))
            if not map_url:
                map_url = normalize_https_url(shop_meta.get("map_url", ""))
            if not map_url:
                map_url = extract_https_url_from_html_in_zip(z)

            playlist_data = build_playlist_from_zip(z, manifest)

    except Exception as e:
        st.error(f"ファイルの読み込みエラー: {e}")
        return

    if not playlist_data:
        st.warning("このZIPにはMP3が見つかりませんでした。")
        return

    playlist_json = json.dumps(playlist_data, ensure_ascii=False)

    map_btn_html = ""
    if map_url:
        safe_map = html_lib.escape(map_url, quote=True)
        map_btn_html = f"""
        <div style="margin: 15px 0;">
            <a href="{safe_map}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;">
                <button style="
                    width:100%; padding:10px; background:#4285F4; color:white;
                    border:none; border-radius:8px; font-weight:bold; cursor:pointer;">
                    🗺️ 地図を開く
                </button>
            </a>
        </div>
        """

    html_template = """<!DOCTYPE html><html><head><style>
        .player-container { border: 2px solid #e0e0e0; border-radius: 15px; padding: 20px; background-color: #f9f9f9; text-align: center; }
        .track-title { font-size: 20px; font-weight: bold; color: #333; margin-bottom: 15px; padding: 10px; background: #fff; border-radius: 8px; border-left: 5px solid #ff4b4b; }
        .controls { display: flex; gap: 10px; margin: 15px 0; }
        button.ctrl-btn { flex: 1; padding: 15px; font-size: 18px; font-weight: bold; color: white; background-color: #ff4b4b; border: none; border-radius: 8px; cursor: pointer; }
        .track-list { margin-top: 20px; text-align: left; max-height: 250px; overflow-y: auto; border-top: 1px solid #ddd; padding-top: 10px; }
        .track-item { padding: 10px; border-bottom: 1px solid #eee; cursor: pointer; }
        .track-item.active { background-color: #ffecec; font-weight: bold; color: #ff4b4b; }
    </style></head><body>
    <div class="player-container">
        <div class="track-title" id="title">Loading...</div>
        <audio id="audio" controls style="width:100%"></audio>

        <div class="controls">
            <button class="ctrl-btn" onclick="prev()">⏮</button>
            <button class="ctrl-btn" onclick="toggle()" id="pb">▶</button>
            <button class="ctrl-btn" onclick="next()">⏭</button>
        </div>

        __MAP_BUTTON__

        <div style="text-align:center; margin-top:10px;">
            速度: <select id="speed" onchange="spd()">
                <option value="0.8">0.8 (ゆっくり)</option>
                <option value="1.0" selected>1.0 (標準)</option>
                <option value="1.2">1.2 (少し速く)</option>
                <option value="1.5">1.5 (速く)</option>
            </select>
        </div>

        <div class="track-list" id="list"></div>
    </div>
    <script>
        const pl = __PLAYLIST__; let idx = 0;
        const au = document.getElementById('audio');
        const ti = document.getElementById('title');
        const btn = document.getElementById('pb');
        const ls = document.getElementById('list');

        function init() { render(); load(0); spd(); }
        function load(i) { idx = i; au.src = pl[idx].src; ti.innerText = pl[idx].title; highlight(); spd(); }
        function toggle() { if(au.paused){au.play(); btn.innerText="⏸";} else {au.pause(); btn.innerText="▶";} }
        function next() { if(idx < pl.length-1) { load(idx+1); au.play(); btn.innerText="⏸"; } }
        function prev() { if(idx > 0) { load(idx-1); au.play(); btn.innerText="⏸"; } }
        function spd() { au.playbackRate = parseFloat(document.getElementById('speed').value); }
        au.onended = function() { idx < pl.length-1 ? next() : btn.innerText="▶"; };

        function render() {
            ls.innerHTML = "";
            pl.forEach((t, i) => {
                const d = document.createElement('div');
                d.className = "track-item";
                d.id = "tr-" + i;
                d.innerText = (i+1) + ". " + t.title;
                d.onclick = () => { load(i); au.play(); btn.innerText="⏸"; };
                ls.appendChild(d);
            });
        }
        function highlight() {
            document.querySelectorAll('.track-item').forEach(e => e.classList.remove('active'));
            const el = document.getElementById("tr-" + idx);
            if(el) { el.classList.add('active'); el.scrollIntoView({behavior:'smooth', block:'nearest'}); }
        }
        init();
    </script></body></html>"""

    final_html = html_template.replace("__PLAYLIST__", playlist_json).replace("__MAP_BUTTON__", map_btn_html)
    components.html(final_html, height=600)


# =========================
# 起動時：永続インデックス読み込み
# =========================
index = load_index()

shops = []
for shop_id, meta in index.items():
    path = shop_zip_path(shop_id)
    if os.path.exists(path):
        shops.append({
            "id": shop_id,
            "key": meta.get("key", meta.get("store_name", "Unknown")),
            "store_name": meta.get("store_name", "Unknown"),
            "menu_title": meta.get("menu_title"),
            "date": meta.get("date"),
            "map_url": meta.get("map_url", ""),
            "zip_name": meta.get("zip_name", f"{shop_id}.zip"),
            "zip_path": path,
        })

# =========================
# サイドバー：店の追加
# =========================
with st.sidebar:
    st.header("➕ 店の追加")
    st.info("生成アプリで作ったZIPファイルを登録します（永続保存されます）。")

    uploaded_zips = st.file_uploader("ZIPファイルをドロップ", type="zip", accept_multiple_files=True)

    if uploaded_zips:
        added = 0
        skipped = 0

        for zfile in uploaded_zips:
            zip_bytes = zfile.getvalue()
            shop_id = hashlib.md5(zip_bytes).hexdigest()

            if shop_id in index:
                skipped += 1
                continue

            store_name, date = parse_store_and_date_from_filename(zfile.name)
            menu_title = None
            map_url = ""

            try:
                with zipfile.ZipFile(BytesIO(zip_bytes)) as z:
                    manifest = read_manifest(z)
                    if manifest:
                        if isinstance(manifest.get("store_name"), str) and manifest["store_name"].strip():
                            store_name = manifest["store_name"].strip()
                        if isinstance(manifest.get("menu_title"), str) and manifest["menu_title"].strip():
                            menu_title = manifest["menu_title"].strip()
                        if isinstance(manifest.get("date"), str) and re.fullmatch(r"\d{8}", manifest["date"]):
                            date = manifest["date"]
                        if isinstance(manifest.get("map_url"), str):
                            map_url = normalize_https_url(manifest.get("map_url"))
                    else:
                        map_url = extract_https_url_from_html_in_zip(z)
            except Exception:
                pass

            key = make_display_key(store_name, menu_title, date)

            # ZIPを永続保存
            path = shop_zip_path(shop_id)
            with open(path, "wb") as f:
                f.write(zip_bytes)

            index[shop_id] = {
                "key": key,
                "store_name": store_name,
                "menu_title": menu_title,
                "date": date,
                "map_url": map_url,
                "zip_name": zfile.name
            }
            added += 1

        save_index(index)

        if added:
            st.success(f"{added}店を追加しました！")
        if skipped:
            st.info(f"{skipped}店は同じ内容のため追加しませんでした。")

        st.rerun()

    st.divider()
    if st.button("🗑️ 店リストを空にする"):
        try:
            for fn in os.listdir(LIB_DIR):
                if fn.endswith(".zip"):
                    os.remove(os.path.join(LIB_DIR, fn))
        except Exception:
            pass

        index = {}
        save_index(index)
        st.session_state.selected_id = None
        st.rerun()


# =========================
# 画面表示
# =========================
if "selected_id" not in st.session_state:
    st.session_state.selected_id = None

if st.session_state.selected_id:
    shop = next((b for b in shops if b["id"] == st.session_state.selected_id), None)
    if not shop:
        st.session_state.selected_id = None
        st.rerun()

    st.markdown(f"### 🎧 再生中: {shop['key']}")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("⬅️ 店一覧に戻る", use_container_width=True):
            st.session_state.selected_id = None
            st.rerun()
    with c2:
        if st.button("🗑️ この店を削除", use_container_width=True):
            sid = shop["id"]
            try:
                if sid in index:
                    del index[sid]
                    save_index(index)
                path = shop_zip_path(sid)
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

            st.session_state.selected_id = None
            st.rerun()

    st.markdown("---")
    render_player(shop)

else:
    st.markdown("#### 🏬 店一覧")
    search_query = st.text_input("🔍 店を検索", placeholder="例: カフェ")

    if not shops:
        st.info("👈 左のサイドバーにZIPファイルをアップロードしてください。")

    filtered = shops
    if search_query:
        q = search_query.strip().lower()
        filtered = [b for b in shops if q in b["key"].lower()]

    def sort_key(b):
        d = b.get("date") or ""
        has = 1 if re.fullmatch(r"\d{8}", d) else 0
        return (has, d)

    filtered = sorted(filtered, key=sort_key, reverse=True)

    for b in filtered:
        if st.button(f"🏬 {b['key']}", use_container_width=True):
            st.session_state.selected_id = b["id"]
            st.rerun()
