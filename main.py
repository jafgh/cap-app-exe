import os
import re
import threading
import time
import base64
import io
import random
import requests
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import numpy as np
import cv2  # OpenCV
import onnxruntime as ort
import torchvision.transforms as transforms

# --------------------------------------------------
# ثوابت
# --------------------------------------------------
CHARSET = '0123456789abcdefghijklmnopqrstuvwxyz'
CHAR2IDX = {c: i for i, c in enumerate(CHARSET)}
IDX2CHAR = {i: c for c, i in CHAR2IDX.items()}
NUM_CLASSES = len(CHARSET)
NUM_POS = 5
# مسار نموذج ONNX
ONNX_MODEL_PATH = r"C:\Users\ccl\Desktop\holako bag.onnx"

# --------------------------------------------------
# معالجة الصورة لتكون متوافقة مع النموذج (3 قنوات)
# --------------------------------------------------
def preprocess_for_model():
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.Grayscale(num_output_channels=3),
        transforms.ToTensor(),
        transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
    ])

# --------------------------------------------------
# الكلاس الرئيسي لتطبيق حل الكابتشا
# --------------------------------------------------
class CaptchaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Captcha Solver (ONNX Runtime)")
        self.device = 'cpu'

        # تحميل نموذج ONNX Runtime
        if not os.path.exists(ONNX_MODEL_PATH):
            messagebox.showerror("Load Error", f"ONNX model not found at:\n{ONNX_MODEL_PATH}")
            self.root.destroy()
            return
        try:
            self.session = ort.InferenceSession(ONNX_MODEL_PATH, providers=['CPUExecutionProvider'])
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load ONNX model:\n{e}")
            self.root.destroy()
            return

        self.accounts = {}
        self.current_captcha = None

        # بناء واجهة المستخدم
        self._build_gui()

    def _build_gui(self):
        frame = tk.Frame(self.root)
        frame.pack(padx=10, pady=10)

        self.notification_label = tk.Label(frame, text="", font=("Helvetica", 10))
        self.notification_label.pack(pady=5)

        btn_add = tk.Button(frame, text="Add Account", command=self.add_account)
        btn_add.pack(pady=5)

        # ملصق لعرض سرعة المعالجة والتنبؤ
        self.speed_label = tk.Label(self.root, text="Preprocess: 0 ms | Predict: 0 ms", font=("Helvetica", 10))
        self.speed_label.pack(side=tk.BOTTOM, pady=5)

    def update_notification(self, message, color):
        self.notification_label.config(text=message, fg=color)
        print(f"{color}: {message}")

    def generate_user_agent(self):
        ua_list = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.61 Mobile Safari/537.36",
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:98.0) Gecko/20100101 Firefox/98.0"
        ]
        return random.choice(ua_list)

    def create_session(self, user_agent):
        headers = {
            "User-Agent": user_agent,
            "Host": "api.ecsc.gov.sy:8443",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ar,en-US;q=0.7,en;q=0.3",
            "Referer": "https://ecsc.gov.sy/login",
            "Content-Type": "application/json",
            "Source": "WEB",
            "Origin": "https://ecsc.gov.sy",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Priority": "u=1",
        }
        session = requests.Session()
        session.headers.update(headers)
        return session

    def login(self, username, password, session, retries=3):
        url = "https://api.ecsc.gov.sy:8443/secure/auth/login"
        payload = {"username": username, "password": password}
        for _ in range(retries):
            try:
                r = session.post(url, json=payload, verify=False)
                if r.status_code == 200:
                    self.update_notification("Login successful.", "green")
                    return True
                else:
                    self.update_notification(f"Login failed ({r.status_code})", "red")
                    return False
            except Exception as e:
                self.update_notification(f"Login error: {e}", "red")
                return False
        return False

    def add_account(self):
        user = simpledialog.askstring("Username", "Enter username:", parent=self.root)
        pwd = simpledialog.askstring("Password", "Enter password:", show="*", parent=self.root)
        if not user or not pwd:
            return

        session = self.create_session(self.generate_user_agent())
        start = time.time()
        if not self.login(user, pwd, session):
            self.update_notification(f"Login failed for {user}", "red")
            return
        elapsed = time.time() - start
        self.update_notification(f"Logged in {user} in {elapsed:.2f}s", "green")
        self.accounts[user] = {"password": pwd, "session": session}

        proc = self.fetch_process_ids(session)
        if proc:
            self._create_account_ui(user, proc)
        else:
            self.update_notification(f"Can't fetch process IDs for {user}", "red")

    def fetch_process_ids(self, session):
        try:
            url = "https://api.ecsc.gov.sy:8443/dbm/db/execute"
            payload = {
                "ALIAS": "OPkUVkYsyq",
                "P_USERNAME": "WebSite",
                "P_PAGE_INDEX": 0,
                "P_PAGE_SIZE": 100
            }
            headers = {
                "Content-Type": "application/json",
                "Alias": "OPkUVkYsyq",
                "Referer": "https://ecsc.gov.sy/requests",
                "Origin": "https://ecsc.gov.sy",
            }
            r = session.post(url, json=payload, headers=headers, verify=False)
            if r.status_code == 200:
                return r.json().get("P_RESULT", [])
            else:
                self.update_notification(f"Fetch IDs failed ({r.status_code})", "red")
        except Exception as e:
            self.update_notification(f"Error fetching IDs: {e}", "red")
        return []

    def _create_account_ui(self, user, processes):
        frame = tk.Frame(self.root, bd=2, relief="groove")
        frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(frame, text=f"Account: {user}").pack(side=tk.LEFT, padx=5)
        for proc in processes:
            pid = proc.get("PROCESS_ID")
            name = proc.get("ZCENTER_NAME", "Unknown")
            sub = tk.Frame(frame)
            sub.pack(fill=tk.X, padx=10, pady=2)
            prog = ttk.Progressbar(sub, mode='indeterminate')
            btn = tk.Button(sub, text=name,
                            command=lambda u=user, p=pid, pr=prog: threading.Thread(
                                target=self._handle_captcha, args=(u, p, pr)
                            ).start())
            btn.pack(side=tk.LEFT)
            prog.pack(side=tk.LEFT, padx=5)

    def _handle_captcha(self, user, pid, prog):
        prog.start()
        data = self.get_captcha(self.accounts[user]["session"], pid, user)
        prog.stop()
        if data:
            self.current_captcha = (user, pid)
            self.show_captcha(data)

    def get_captcha(self, session, pid, user):
        url = f"https://api.ecsc.gov.sy:8443/captcha/get/{pid}"
        try:
            while True:
                r = session.get(url, verify=False)
                if r.status_code == 200:
                    return r.json().get("file")
                elif r.status_code == 429:
                    time.sleep(0.1)
                elif r.status_code in (401, 403):
                    if not self.login(user, self.accounts[user]["password"], session):
                        return None
                else:
                    self.update_notification(f"Server error: {r.status_code}", "red")
                    return None
        except Exception as e:
            self.update_notification(f"Captcha error: {e}", "red")
            return None

    def predict_captcha(self, pil_img):
        tf = preprocess_for_model()
        img = pil_img.convert("RGB")
        start_pre = time.time()
        x = tf(img).unsqueeze(0).numpy().astype(np.float32)
        end_pre = time.time()

        # Run inference with ONNX Runtime
        start_pred = time.time()
        ort_outs = self.session.run(None, {'input': x})[0]  # shape [1, NUM_POS*NUM_CLASSES]
        end_pred = time.time()

        # Reshape and decode
        ort_outs = ort_outs.reshape(1, NUM_POS, NUM_CLASSES)
        idxs = np.argmax(ort_outs, axis=2)[0]
        pred = ''.join(IDX2CHAR[i] for i in idxs)

        pre_ms = (end_pre - start_pre) * 1000
        pred_ms = (end_pred - start_pred) * 1000
        return pred, pre_ms, pred_ms

    def show_captcha(self, b64data):
        if hasattr(self, 'captcha_frame') and self.captcha_frame:
            self.captcha_frame.destroy()
        self.captcha_frame = tk.Frame(self.root, bd=2, relief="sunken")
        self.captcha_frame.pack(pady=10)

        b64 = b64data.split(",")[1] if "," in b64data else b64data
        raw = base64.b64decode(b64)
        pil = Image.open(io.BytesIO(raw))

        frames = []
        try:
            while True:
                frames.append(np.array(pil.convert("RGB")))
                pil.seek(pil.tell() + 1)
        except EOFError:
            pass
        stack = np.stack(frames).astype(np.uint8)
        bg = np.median(stack, axis=0).astype(np.uint8)
        gray = cv2.cvtColor(bg, cv2.COLOR_RGB2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enh = clahe.apply(gray)
        _, binary = cv2.threshold(enh, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        img = Image.fromarray(binary)

        pred, pre_ms, pred_ms = self.predict_captcha(img)
        self.update_notification(f"Predicted CAPTCHA: {pred}", "blue")
        self.speed_label.config(text=f"Preprocess: {pre_ms:.2f} ms | Predict: {pred_ms:.2f} ms")
        self.submit_captcha(pred)

        tk_img = ImageTk.PhotoImage(img.resize((160, 90)))
        lbl = tk.Label(self.captcha_frame, image=tk_img)
        lbl.image = tk_img
        lbl.pack(pady=5)

    def submit_captcha(self, solution):
        user, pid = self.current_captcha
        session = self.accounts[user]["session"]
        url = f"https://api.ecsc.gov.sy:8443/rs/reserve?id={pid}&captcha={solution}"
        try:
            r = session.get(url, verify=False)
            color = "green" if r.status_code == 200 else "red"
            self.update_notification(f"Submit response: {r.text}", color)
        except Exception as e:
            self.update_notification(f"Submit error: {e}", "red")


if __name__ == "__main__":
    root = tk.Tk()
    app = CaptchaApp(root)
    root.mainloop()
