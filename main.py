import os
import threading
import time
import base64
import io
import random
import requests  # تأكد من أن requests مثبت
from PIL import Image as PILImage, ImageTk, ImageOps
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
        self.current_captcha_frame = None

        # إشعار
        self.notification_label = tk.Label(self, text="", font=("Arial", 10))
        self.notification_label.pack(fill="x", pady=(0,10))

        # زر إضافة حساب
        tk.Button(self, text="Add Account", command=self.open_add_account_popup).pack(fill="x")

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
        if not self.login(user, pwd, sess):
            self.update_notification(f"Login failed for {user}", "red")
            return
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
                    return True
                return False
            except Exception:
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
            self.show_and_process_captcha(data, user, pid)

    def get_captcha(self, session, pid, user):
        url = f"https://api.ecsc.gov.sy:8443/captcha/get/{pid}"
        try:
            # إشعار بداية المحاولة
            self.update_notification(f"[{user}] محاولة جلب الكابتشا لـ PID {pid} (محاولة وحيدة).", "grey")
            
            r = session.get(url, timeout=(15, 30), verify=False)
            text_preview = r.text.replace("\n", " ")[:200]
            
            if r.status_code == 200:
                captcha_info = r.json()
                if captcha_info.get("file"):
                    self.update_notification(f"[{user}] تم جلب الكابتشا بنجاح لـ PID {pid}.", "green")
                    return captcha_info["file"]
                else:
                    self.update_notification(
                        f"[{user}] استجابة الكابتشا (PID: {pid}) لا تحتوي على ملف. النص: {text_preview}",
                        "orange"
                    )
                    return None

            elif r.status_code in (401, 403):
                self.update_notification(
                    f"[{user}] خطأ صلاحية ({r.status_code}) عند طلب كابتشا لـ PID {pid}. النص: {text_preview}."
                    " سيتم محاولة إعادة تسجيل الدخول مرة واحدة.",
                    "orange"
                )
                # محاولة إعادة تسجيل الدخول
                pwd = self.accounts[user].get("password")
                if pwd and self.login(user, pwd, session):
                    self.update_notification(
                        f"[{user}] تم إعادة تسجيل الدخول بنجاح بعد خطأ الصلاحية. لن يتم إعادة محاولة جلب الكابتشا تلقائياً هنا.",
                        "blue"
                    )
                else:
                    self.update_notification(
                        f"[{user}] فشلت محاولة إعادة تسجيل الدخول بعد خطأ الصلاحية.",
                        "red"
                    )
                return None

            else:
                self.update_notification(
                    f"[{user}] خطأ سيرفر ({r.status_code}) عند طلب كابتشا لـ PID {pid}. النص: {text_preview}",
                    "red"
                )
                return None

        except requests.exceptions.RequestException as e:
            err_name = type(e).__name__
            self.update_notification(
                f"[{user}] خطأ شبكة ({err_name}) عند طلب كابتشا لـ PID {pid}.",
                "red"
            )
            # تفصيل خطأ البروكسي
            if isinstance(e, requests.exceptions.ProxyError):
                self.update_notification(
                    f"[{user}] خطأ بروكسي ({err_name}) عند طلب كابتشا لـ PID {pid}.",
                    "red"
                )
            return None

        except Exception as e:
            self.update_notification(
                f"[{user}] خطأ غير متوقع عند طلب كابتشا لـ PID {pid}: {e}",
                "red"
            )
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
            result = response.json().get("result")
            total_api_time_ms = (time.time() - t_api_start)*1000
            return result, 0, total_api_time_ms
        except Exception as e:
            return None, 0, (time.time() - t_api_start)*1000

    def show_and_process_captcha(self, base64_data, task_user, task_pid):
        # إنشاء إطار جديد للعرض والمعالجة
        if self.current_captcha_frame and getattr(self.current_captcha_frame, '_is_captcha_frame', False):
            self.clear_specific_frame(self.current_captcha_frame)
        current_display_frame = tk.Frame(self.accounts_frame, bd=2, relief="sunken")
        current_display_frame._is_captcha_frame = True
        current_display_frame.pack(pady=10, padx=5, fill=tk.X, side=tk.BOTTOM)
        self.current_captcha_frame = current_display_frame

        try:
            # فك ترميز Base64
            b64 = base64_data.split(",",1)[1] if "," in base64_data else base64_data
            raw = base64.b64decode(b64)
            pil = PILImage.open(io.BytesIO(raw))

            # استخراج الإطارات
            frames = []
            try:
                pil.seek(0)
                while True:
                    arr = np.array(pil.convert("RGB"), dtype=np.float32)
                    frames.append(arr)
                    pil.seek(pil.tell() + 1)
            except EOFError:
                pass

            if not frames:
                raise ValueError("لم يتم قراءة أي إطارات من بيانات الصورة.")

            stack = np.stack(frames, axis=0)
            summed = np.sum(stack, axis=0)
            summed_clipped = np.clip(summed / summed.max() * 255.0, 0, 255).astype(np.uint8)
            gray_pil = PILImage.fromarray(summed_clipped).convert("L")
            auto = ImageOps.autocontrast(gray_pil, cutoff=1)
            equalized = ImageOps.equalize(auto)
            binary = equalized.point(lambda p: 255 if p > 128 else 0)
            processed_pil = binary

            # التنبؤ
            predicted_solution, preprocess_ms, predict_ms = self.predict_captcha(processed_pil)

            # التأكد من السياق الحالي
            if self.current_captcha != (task_user, task_pid) or \
               not current_display_frame.winfo_exists() or \
               self.current_captcha_frame != current_display_frame:
                self.update_notification(
                    f"[{task_user}] تم إلغاء معالجة الكابتشا لـ {task_pid}.",
                    "orange"
                )
                self.clear_specific_frame(current_display_frame)
                return

            # عرض النتائج
            self.update_notification(
                f"[{task_user}] النص المتوقع: {predicted_solution}",
                "blue"
            )
            self.speed_label.config(
                text=f"معالجة: {preprocess_ms:.1f} ms | تنبؤ: {predict_ms:.1f} ms"
            )

            # عرض الصورة
            disp = processed_pil.resize((180,70), PILImage.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(disp)
            lbl = tk.Label(current_display_frame, image=tk_img)
            lbl.image = tk_img
            lbl.pack(pady=5)

            # عرض النص
            tk.Label(
                current_display_frame,
                text=f"الحل المتوقع: {predicted_solution}",
                font=("Helvetica", 12, "bold")
            ).pack(pady=(0,5))

            # الإرسال
            threading.Thread(
                target=self.submit_captcha_solution,
                args=(task_user, task_pid, predicted_solution, current_display_frame),
                daemon=True
            ).start()

        except Exception as e:
            self.update_notification(f"خطأ في معالجة الصورة: {e}", "red")
            self.clear_specific_frame(current_display_frame)

    def submit_captcha_solution(self, user, pid, sol, frame):
        sess = self.accounts[user]["session"]
        url = f"https://api.ecsc.gov.sy:8443/rs/reserve?id={pid}&captcha={sol}"
        try:
            self.update_notification(f"[{user}] إرسال الحل للكابتشا لـ PID {pid}…", "grey")
            r = sess.get(url, timeout=(15, 30), verify=False)
            text_preview = r.text.replace("\n", " ")[:200]

            # حاول فكّ JSON لأجل رسالة منسقة
            try:
                payload = r.json()
                server_msg = payload.get("message", text_preview)
            except ValueError:
                server_msg = text_preview

            if r.status_code == 200:
                self.update_notification(
                    f"[{user}] نجح إرسال الحل لـ PID {pid}. الرد: {server_msg}",
                    "green"
                )
                success = True
            else:
                self.update_notification(
                    f"[{user}] فشل إرسال الحل لـ PID {pid} (Status {r.status_code}). الرد: {server_msg}",
                    "red"
                )
                success = False

            # عرض ضمن الإطار المخصّص للنتيجة
            self.show_submission_result_in_frame(frame, user, pid, r.status_code, server_msg, success)

        except requests.exceptions.RequestException as e:
            err_name = type(e).__name__
            self.update_notification(
                f"[{user}] خطأ شبكة ({err_name}) عند إرسال الحل لـ PID {pid}.",
                "red"
            )
            self.show_submission_result_in_frame(frame, user, pid, -1, str(e), False)

        except Exception as e:
            self.update_notification(
                f"[{user}] خطأ غير متوقع عند إرسال الحل لـ PID {pid}: {e}",
                "red"
            )
            self.show_submission_result_in_frame(frame, user, pid, -1, str(e), False)

    def clear_specific_frame(self, frame):
        for w in frame.winfo_children():
            w.destroy()
        frame.destroy()

if __name__ == '__main__':
    app = CaptchaApp()
    app.mainloop()
