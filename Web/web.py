import streamlit as st
import json
import os
import base64
import pandas as pd
from cryptography.fernet import Fernet
from streamlit_option_menu import option_menu
import time

# ==========================
# CONFIG
# ==========================
DATA_DIR = "data"
USER_DB = "users.json"
FOLDER_DB = "folders.json"
FILE_PERM_DB = "file_permissions.json"
KEY_FILE = "key.key"
LOG_FILE = "access_logs.csv"
ALLOWED_TYPES = ("pdf", "docx")

os.makedirs(DATA_DIR, exist_ok=True)

# ==========================
# ENCRYPTION
# ==========================
def load_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
    return Fernet(open(KEY_FILE, "rb").read())

fernet = load_key()

def encrypt_file(raw_bytes):
    return fernet.encrypt(raw_bytes)

def decrypt_file(enc_bytes):
    return fernet.decrypt(enc_bytes)

# ==========================
# LOAD/SAVE JSON
# ==========================
def load_json(path, default):
    if not os.path.exists(path):
        save_json(path, default)
        return default
    return json.load(open(path, "r", encoding="utf-8"))

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# DB
users = load_json(USER_DB, {"admin": "admin"})
folders = load_json(FOLDER_DB, {})
file_permissions = load_json(FILE_PERM_DB, {})

# ==========================
# LOGGING
# ==========================
def log_access(user, item, type_):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{time.time()},{user},{item},{type_}\n")

# ==========================
# LOGIN / REGISTER
# ==========================
def login_page():
    st.title("🔐 Đăng nhập hệ thống")

    tab_login, tab_register = st.tabs(["Đăng nhập", "Đăng ký"])

    # LOGIN
    with tab_login:
        u = st.text_input("Tên đăng nhập", key="login_username")
        p = st.text_input("Mật khẩu", type="password", key="login_password")

        if st.button("Đăng nhập", key="login_button"):
            if u in users and users[u] == p:
                st.session_state["user"] = u
                st.success("Đăng nhập thành công!")
                st.rerun()
            else:
                st.error("Sai thông tin đăng nhập!")

    # REGISTER
    with tab_register:
        new_u = st.text_input("User mới", key="reg_username")
        new_p = st.text_input("Mật khẩu (đăng ký)", type="password", key="reg_password")

        if st.button("Đăng ký", key="reg_button"):
            if new_u in users:
                st.error("User đã tồn tại!")
            else:
                users[new_u] = new_p
                save_json(USER_DB, users)
                st.success("Tạo tài khoản thành công!")

# ==========================
# ADMIN PANEL
# ==========================
def admin_panel():
    with st.sidebar:
        menu = option_menu("Admin", ["Upload file", "Quản lý user", "Phân quyền", "Xem log"])

    # --- UPLOAD FILE ---
    if menu == "Upload file":
        st.header("📁 Upload tài liệu")

        folder = st.text_input("Tên folder")
        file = st.file_uploader("Chọn file", type=ALLOWED_TYPES)

        if file and folder:
            folder_path = os.path.join(DATA_DIR, folder)
            os.makedirs(folder_path, exist_ok=True)

            enc = encrypt_file(file.read())
            save_path = os.path.join(folder_path, file.name)
            open(save_path, "wb").write(enc)

            if folder not in folders:
                folders[folder] = []

            save_json(FOLDER_DB, folders)
            st.success("Upload thành công!")

    # --- USER MANAGEMENT ---
    if menu == "Quản lý user":
        st.header("👥 Danh sách user")
        st.write(users)

        st.header("➕ Thêm user mới")
        new_u = st.text_input("Username", key="add_username")
        new_p = st.text_input("Password", key="add_password")

        if st.button("Thêm", key="add_user_button"):
            if new_u in users:
                st.error("User tồn tại!")
            else:
                users[new_u] = new_p
                save_json(USER_DB, users)
                st.success("Đã tạo user!")

    # --- PERMISSIONS ---
    if menu == "Phân quyền":
        st.header("🔐 Phân quyền xem")

        mode = st.radio("Chọn loại phân quyền", ["Folder", "File"])
        current_users = list(users.keys())

        if mode == "Folder":
            folder_list = list(folders.keys())
            folder = st.selectbox("Chọn folder", folder_list)

            default_users = [u for u in folders.get(folder, []) if u in current_users]
            selected = st.multiselect("User được xem", current_users, default=default_users, key="folder_perm")

            if st.button("Lưu phân quyền folder", key="save_folder_perm"):
                folders[folder] = selected
                save_json(FOLDER_DB, folders)
                st.success("Đã lưu!")

        else:
            file_list = []
            for fd in os.listdir(DATA_DIR):
                for f in os.listdir(os.path.join(DATA_DIR, fd)):
                    file_list.append(f"{fd}/{f}")

            file_pick = st.selectbox("Chọn file", file_list)
            default_file_users = [u for u in file_permissions.get(file_pick, []) if u in current_users]
            selected = st.multiselect("User được xem", current_users, default=default_file_users, key="file_perm")

            if st.button("Lưu phân quyền file", key="save_file_perm"):
                file_permissions[file_pick] = selected
                save_json(FILE_PERM_DB, file_permissions)
                st.success("Đã lưu!")

    # --- LOG VIEW ---
    if menu == "Xem log":
        st.header("📜 Nhật ký truy cập")
        if os.path.exists(LOG_FILE):
            df = pd.read_csv(LOG_FILE, names=["timestamp", "user", "item", "type"])
            st.dataframe(df)
        else:
            st.info("Chưa có log")

# ==========================
# USER VIEW DOCUMENTS
# ==========================
def user_view(username):
    st.title("📚 Tài liệu được phép xem")

    # CSS + JS để khóa download / print / copy
    st.markdown("""
    <style>
    /* Chặn chuột phải */
    body {
        -webkit-touch-callout: none; 
        -webkit-user-select: none; 
        -khtml-user-select: none; 
        -moz-user-select: none; 
        -ms-user-select: none; 
        user-select: none;
    }

    /* Ẩn nút download pdf của viewer (nếu trình duyệt dùng viewer nội bộ) */
    iframe::-webkit-media-controls-download-button {
        display: none !important;
    }

    /* Không cho click vào iframe để chọn text */
    iframe {
        pointer-events: auto !important;
    }
    </style>

    <script>
    // Chặn chuột phải
    document.addEventListener('contextmenu', event => event.preventDefault());

    // Chặn Ctrl+S và Ctrl+P
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey && e.key === 's') || (e.ctrlKey && e.key === 'p')) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }
    });
    </script>
    """, unsafe_allow_html=True)

    # ===== VÒNG LẶP DUYỆT FOLDER =====
    for folder in os.listdir(DATA_DIR):
        folder_path = os.path.join(DATA_DIR, folder)
        files = os.listdir(folder_path)

        # kiểm tra user có quyền xem ANY file
        can_see_folder = False
        for f in files:
            file_id = f"{folder}/{f}"
            allowed = file_permissions.get(file_id)

            if not allowed:  # nếu file không có phân quyền → fallback folder
                allowed = folders.get(folder, [])

            if username in allowed:
                can_see_folder = True
                break

        if not can_see_folder:
            continue

        st.subheader(f"📁 {folder}")

        # ===== HIỂN THỊ FILE =====
        for f in files:
            file_id = f"{folder}/{f}"
            allowed = file_permissions.get(file_id)

            if not allowed:
                allowed = folders.get(folder, [])

            if username not in allowed:
                continue

            st.write(f"📄 {f}")

            if st.button(f"Xem {f}", key=file_id):
                enc = open(os.path.join(DATA_DIR, folder, f), "rb").read()
                raw = decrypt_file(enc)
                pdf64 = base64.b64encode(raw).decode("utf8")

                # CHẾ ĐỘ CHỈ XEM — KHÔNG TẢI — KHÔNG IN
                st.markdown(f"""
                <iframe 
                    src="data:application/pdf;base64,{pdf64}#toolbar=0&navpanes=0&scrollbar=0" 
                    width="100%" 
                    height="700px"
                    style="border:none;"
                ></iframe>
                """, unsafe_allow_html=True)

                log_access(username, f, "file")


# ==========================
# MAIN APP
# ==========================
if "user" not in st.session_state:
    login_page()
else:
    if st.session_state["user"] == "admin":
        admin_panel()
    else:
        user_view(st.session_state["user"])