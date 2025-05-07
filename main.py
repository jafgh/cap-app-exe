import os
import threading
import time
import base64
import io
import random
import requests  # تأكد من أن requests مثبت
from PIL import Image as PILImage, ImageTk
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

# --------------------------------------------------
# رابط API الخاص بك
# --------------------------------------------------
CAPTCHA_API_URL = "https://jafgh.pythonanywhere.com/predict"

class CaptchaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Captcha Solver")
        self.geometry("480x640")
        self.configure(padx=10, pady=10)
        self.accounts = {}
        self.current_captcha = None

        # إشعار
        self.notification_label = tk.Label(self, text="", font=("Arial", 10))
        self.notification_label.pack(fill="x", pady=(0,10))

        # زر إضافة حساب
        tk.Button(self, text="Add Account", command=self.open_add_account_popup).pack(fill="x")

        # إطار عرض CAPTCHA
        self.captcha_frame = tk.Frame(self)
        self.captcha_frame.pack(fill="x", pady=10)

        # Scrollable frame للحسابات
        container = tk.Frame(self)
        container.pack(fill="both", expand=True)
        canvas = tk.Canvas(container)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.accounts_frame = tk.Frame(canvas)
        self.accounts_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.accounts_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Label لوقت استدعاء ال API
        self.speed_label = tk.Label(self, text="API Call Time: 0 ms", font=("Arial", 9))
        self.speed_label.pack(fill="x", pady=(10,0))

    # دوال مساعدة
    def update_notification(self, msg, color="black"):
        self.notification_label.config(text=msg, fg=color)

    def generate_user_agent(self):
        ua_list = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.61 Mobile Safari/537.36",
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:98.0) Gecko/20100101 Firefox/98.0"
        ]
        return random.choice(ua_list)

    def create_session_requests(self, ua):
        headers = {
            "User-Agent": ua,
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
            "Priority": "u=1"
        }
        sess = requests.Session()
        sess.headers.update(headers)
        return sess

    # إضافة حساب
    def open_add_account_popup(self):
        user = simpledialog.askstring("Username", "Enter username:", parent=self)
        pwd = simpledialog.askstring("Password", "Enter password:", show='*', parent=self)
        if user and pwd:
            threading.Thread(target=self.add_account, args=(user.strip(), pwd.strip()), daemon=True).start()

    def add_account(self, user, pwd):
        sess = self.create_session_requests(self.generate_user_agent())
        t0 = time.time()
        if not self.login(user, pwd, sess):
            self.update_notification(f"Login failed for {user}", "red")
            return
        self.update_notification(f"Logged in {user} in {time.time() - t0:.2f}s", "green")
        self.accounts[user] = {"password": pwd, "session": sess}
        procs = self.fetch_process_ids(sess)
        if procs:
            self._create_account_ui(user, procs)
        else:
            self.update_notification(f"Can't fetch process IDs for {user}", "red")

    def login(self, user, pwd, sess, retries=3):
        url = "https://api.ecsc.gov.sy:8443/secure/auth/login"
        for _ in range(retries):
            try:
                r = sess.post(url, json={"username": user, "password": pwd}, verify=False)
                if r.status_code == 200:
                    self.update_notification("Login successful.", "green")
                    return True
                self.update_notification(f"Login failed ({r.status_code})", "red")
                return False
            except Exception as e:
                self.update_notification(f"Login error: {e}", "red")
                return False
        return False

    def fetch_process_ids(self, sess):
        try:
            r = sess.post(
                "https://api.ecsc.gov.sy:8443/dbm/db/execute",
                json={"ALIAS": "OPkUVkYsyq", "P_USERNAME": "WebSite", "P_PAGE_INDEX": 0, "P_PAGE_SIZE": 100},
                headers={
                    "Content-Type": "application/json",
                    "Alias": "OPkUVkYsyq",
                    "Referer": "https://ecsc.gov.sy/requests",
                    "Origin": "https://ecsc.gov.sy"
                },
                verify=False
            )
            if r.status_code == 200:
                return r.json().get("P_RESULT", [])
            self.update_notification(f"Fetch IDs failed ({r.status_code})", "red")
        except Exception as e:
            self.update_notification(f"Error fetching IDs: {e}", "red")
        return []

    def _create_account_ui(self, user, processes):
        def _ui():
            tk.Label(self.accounts_frame, text=f"Account: {user}", font=("Arial", 10, "bold")).pack(anchor="w", pady=(10,0))
            for proc in processes:
                pid = proc.get("PROCESS_ID")
                name = proc.get("ZCENTER_NAME", "Unknown")
                frame = tk.Frame(self.accounts_frame)
                frame.pack(fill="x", pady=2)
                btn = tk.Button(frame, text=name, width=20)
                prog = ttk.Progressbar(frame, length=150, mode="determinate", maximum=1, value=0)
                btn.pack(side="left")
                prog.pack(side="left", padx=5)
                btn.config(command=lambda u=user, p=pid, pr=prog: threading.Thread(
                    target=self._handle_captcha, args=(u, p, pr), daemon=True).start())
        self.after(0, _ui)

    def _handle_captcha(self, user, pid, prog):
        self.after(0, lambda: prog.config(value=0))
        data = self.get_captcha(self.accounts[user]["session"], pid, user)
        self.after(0, lambda: prog.config(value=1))
        if data:
            self.current_captcha = (user, pid)
            self.after(0, lambda: self._display_captcha(data))

    def get_captcha(self, sess, pid, user):
        url = f"https://api.ecsc.gov.sy:8443/captcha/get/{pid}"
        try:
            while True:
                r = sess.get(url, verify=False)
                if r.status_code == 200:
                    return r.json().get("file")
                if r.status_code == 429:
                    time.sleep(0.1)
                elif r.status_code in (401, 403):
                    if not self.login(user, self.accounts[user]["password"], sess):
                        return None
                else:
                    self.update_notification(f"Server error: {r.status_code}", "red")
                    return None
        except Exception as e:
            self.update_notification(f"Captcha error: {e}", "red")
        return None

    def predict_captcha(self, pil_img: PILImage.Image):
        t_api_start = time.time()
        try:
            img_byte_arr = io.BytesIO()
            pil_img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            files = {"image": ("captcha.png", img_byte_arr, "image/png")}
            response = requests.post(CAPTCHA_API_URL, files=files, timeout=30)
            response.raise_for_status()
            api_response = response.json()
            predicted_text = api_response.get("result")
            if predicted_text is None and predicted_text != "":
                self.update_notification("API Error: Prediction result is missing or null.", "#cc6600")
                return None, 0, (time.time() - t_api_start)*1000
            total_api_time_ms = (time.time() - t_api_start)*1000
            return predicted_text, 0, total_api_time_ms
        except requests.exceptions.Timeout:
            self.update_notification(f"API Request Error: Timeout connecting to {CAPTCHA_API_URL}", "red")
            return None, 0, (time.time() - t_api_start)*1000
        except requests.exceptions.ConnectionError:
            self.update_notification(f"API Request Error: Could not connect to {CAPTCHA_API_URL}", "red")
            return None, 0, (time.time() - t_api_start)*1000
        except requests.exceptions.RequestException as e:
            self.update_notification(f"API Request Error: {e}", "red")
            return None, 0, (time.time() - t_api_start)*1000
        except ValueError as e:
            self.update_notification(f"API Response Error: Invalid JSON received. {e}", "red")
            return None, 0, (time.time() - t_api_start)*1000
        except Exception as e:
            self.update_notification(f"Error calling prediction API: {e}", "red")
            return None, 0, (time.time() - t_api_start)*1000

    def _display_captcha(self, b64data):
        for w in self.captcha_frame.winfo_children():
            w.destroy()
        b64 = b64data.split(',')[1] if ',' in b64data else b64data
        raw = base64.b64decode(b64)
        pil_original = PILImage.open(io.BytesIO(raw))

        frames = []
        try:
            while True:
                frames.append(np.array(pil_original.convert('RGB'), dtype=np.uint8))
                pil_original.seek(pil_original.tell() + 1)
        except EOFError:
            pass

        if frames:
            bg = np.median(np.stack(frames), axis=0).astype(np.uint8)
        else:
            bg = np.array(pil_original.convert('RGB'), dtype=np.uint8)

        gray = (0.2989 * bg[...,0] + 0.5870 * bg[...,1] + 0.1140 * bg[...,2]).astype(np.uint8)
        hist, _ = np.histogram(gray.flatten(), bins=256, range=(0,256))
        total = gray.size
        sum_tot = np.dot(np.arange(256), hist)
        sumB = wB = max_var = thresh = 0
        for i, h in enumerate(hist):
            wB += h
            if wB == 0: continue
            wF = total - wB
            if wF == 0: break
            sumB += i * h
            mB = sumB / wB
            mF = (sum_tot - sumB) / wF
            varBetween = wB * wF * (mB - mF) ** 2
            if varBetween > max_var:
                max_var = varBetween
                thresh = i

        binary_pil_img = PILImage.fromarray(gray, 'L').point(lambda p: 255 if p > thresh else 0)
        img_tk = ImageTk.PhotoImage(binary_pil_img.resize((300, 90), PILImage.NEAREST))
        lbl_img = tk.Label(self.captcha_frame, image=img_tk)
        lbl_img.image = img_tk
        lbl_img.pack()

        pred_text, pre_ms, api_call_ms = self.predict_captcha(binary_pil_img)
        if pred_text is not None:
            self.update_notification(f"Predicted CAPTCHA (API): {pred_text}", "blue")
            self.speed_label.config(text=f"API Call Time: {api_call_ms:.2f} ms")
            self.submit_captcha(pred_text)

    def submit_captcha(self, sol):
        if not self.current_captcha:
            self.update_notification("Error: No current CAPTCHA context for submission.", "red")
            return
        user, pid = self.current_captcha
        sess = self.accounts[user]["session"]
        url = f"https://api.ecsc.gov.sy:8443/rs/reserve?id={pid}&captcha={sol}"
        try:
            r = sess.get(url, verify=False)
            col = "green" if r.status_code == 200 else "red"
            msg_text = r.content.decode('utf-8', errors='replace')
            self.update_notification(f"Submit response: تم التثبيت بنجاح{msg_text}", col)
        except Exception as e:
            self.update_notification(f"Submit error: {e}", "red")

if __name__ == '__main__':
    app = CaptchaApp()
    app.mainloop()
