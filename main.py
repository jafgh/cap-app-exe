import os
import re
import threading
import time
import base64
import io
import random
import requests
try:
    from PIL import Image, ImageTk, UnidentifiedImageError
except ImportError:
    print("خطأ: مكتبة Pillow (PIL) غير مثبتة. يرجى تثبيتها باستخدام: pip install Pillow")
    exit()
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
try:
    import numpy as np
except ImportError:
    print("خطأ: مكتبة numpy غير مثبتة. يرجى تثبيتها باستخدام: pip install numpy")
    exit()
try:
    import cv2
except ImportError:
    print("خطأ: مكتبة opencv-python غير مثبتة. يرجى تثبيتها باستخدام: pip install opencv-python")
    exit()
try:
    import onnxruntime as ort
except ImportError:
    print("خطأ: مكتبة onnxruntime غير مثبتة. يرجى تثبيتها باستخدام: pip install onnxruntime")
    exit()
try:
    import torchvision.transforms as transforms
except ImportError:
     print("خطأ: مكتبة torchvision غير مثبتة. يرجى تثبيتها باستخدام: pip install torchvision")
     exit()

CHARSET = '0123456789abcdefghijklmnopqrstuvwxyz'
CHAR2IDX = {c: i for i, c in enumerate(CHARSET)}
IDX2CHAR = {i: c for c, i in CHAR2IDX.items()}
NUM_CLASSES = len(CHARSET)
NUM_POS = 5
ONNX_MODEL_PATH = r"C:\Users\ccl\Desktop\holako bag.onnx"

def preprocess_for_model():
    """إعداد تحويلات الصور للنموذج."""
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.Grayscale(num_output_channels=3),
        transforms.ToTensor(), # تحويل إلى Tensor
        transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
    ])

# تجاهل تحذيرات SSL (كن حذرًا في بيئة الإنتاج)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class CaptchaApp:
    def __init__(self, root):
        """تهيئة التطبيق الرئيسي."""
        self.root = root
        self.root.title("Captcha Solver (ONNX Runtime) - v1.3") # تحديث الإصدار
        self.device = 'cpu' # تحديد الجهاز

        # --- تحميل نموذج ONNX ---
        if not os.path.exists(ONNX_MODEL_PATH):
            # استخدام print بدلاً من messagebox للإبلاغ عن الخطأ الفادح قبل بدء الواجهة الرسومية
            print(f"خطأ فادح: ملف نموذج ONNX غير موجود في المسار: {ONNX_MODEL_PATH}")
            print("الرجاء التأكد من صحة المسار في الكود.")
            self.root.quit() # استخدام quit بدلاً من destroy قبل بدء mainloop
            return
        try:
            # الحصول على مقدمي الخدمة المتاحين واختيار CPU
            available_providers = ort.get_available_providers()
            print(f"مقدمو الخدمة المتاحون لـ ONNX Runtime: {available_providers}")
            provider_to_use = ['CPUExecutionProvider'] # الأولوية لوحدة المعالجة المركزية
            self.session = ort.InferenceSession(ONNX_MODEL_PATH, providers=provider_to_use)
            print(f"تم تحميل نموذج ONNX بنجاح باستخدام: {self.session.get_providers()}")
        except Exception as e:
            # استخدام print بدلاً من messagebox للخطأ أثناء تحميل النموذج
            print(f"خطأ في تحميل النموذج: فشل تحميل نموذج ONNX من المسار: {ONNX_MODEL_PATH}")
            print(f"الخطأ: {e}")
            self.root.quit() # الخروج من التطبيق
            return
        # --- نهاية تحميل النموذج ---

        self.accounts = {} # قاموس لتخزين بيانات الحسابات
        self.current_captcha = None # يخزن tuple (user, pid) للكابتشا المعروضة حالياً
        self.current_captcha_frame = None # *** إضافة: لتخزين مرجع لإطار عرض الكابتشا الحالي ***
        self.proxy_entry = None # مربع إدخال البروكسي
        self.apply_proxy_button = None # زر تطبيق البروكسي
        self.notification_label = None # ملصق لعرض الإشعارات
        self.speed_label = None # ملصق لعرض سرعة المعالجة والتنبؤ
        self.accounts_frame = None # الإطار الرئيسي لعرض الحسابات

        self._build_gui() # بناء الواجهة الرسومية

    def _build_gui(self):
        """بناء الواجهة الرسومية للتطبيق."""
        # --- إطار الإعدادات (البروكسي وزر إضافة حساب) ---
        settings_frame = tk.Frame(self.root)
        settings_frame.pack(padx=10, pady=10, fill=tk.X)

        # ملصق الإشعارات الديناميكية
        self.notification_label = tk.Label(settings_frame, text="مرحباً! أدخل البروكسي (إذا أردت) ثم أضف حسابًا.", font=("Helvetica", 10), justify=tk.RIGHT, fg="blue")
        self.notification_label.pack(pady=5, fill=tk.X)

        # زر إضافة حساب
        btn_add = tk.Button(settings_frame, text="إضافة حساب", command=self.add_account, width=15)
        btn_add.pack(pady=5)

        # إطار البروكسي
        proxy_frame = tk.Frame(settings_frame)
        proxy_frame.pack(pady=(5, 5), fill=tk.X)

        # زر تطبيق البروكسي
        self.apply_proxy_button = tk.Button(proxy_frame, text="تطبيق البروكسي", command=self.apply_proxy_settings, width=15)
        self.apply_proxy_button.pack(side=tk.LEFT, padx=(0, 10))

        # ملصق ومربع إدخال البروكسي
        proxy_label = tk.Label(proxy_frame, text=":بروكسي (IP:Port)")
        proxy_label.pack(side=tk.RIGHT, padx=(5, 0))
        self.proxy_entry = tk.Entry(proxy_frame, justify=tk.RIGHT)
        self.proxy_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # --- الإطار الرئيسي لعرض تفاصيل الحسابات والكابتشا ---
        self.accounts_frame = tk.Frame(self.root, bd=1, relief="solid")
        self.accounts_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        # *** لا شيء يتم إضافته هنا مباشرة، سيتم إضافة إطارات الحسابات وإطار الكابتشا لاحقًا ***

        # --- ملصق عرض سرعة المعالجة (في الأسفل) ---
        self.speed_label = tk.Label(self.root, text="المعالجة الأولية: - | التنبؤ: -", font=("Helvetica", 9))
        self.speed_label.pack(side=tk.BOTTOM, pady=(0, 5))

    def update_notification(self, message, color="black"):
        """تحديث نص ملصق الإشعارات وطباعته في الطرفية."""
        if self.notification_label and self.notification_label.winfo_exists():
            self.notification_label.config(text=message, fg=color)
        print(f"[{time.strftime('%H:%M:%S')}] [{color.upper()}] {message}") # إضافة وقت للطباعة

    def generate_user_agent(self):
        """اختيار User-Agent عشوائي من قائمة محدثة."""
        ua_list = [ # قائمة محدثة ومنوعة
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 14; Pixel 8a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/124.0.2478.80 Safari/537.36",
        ]
        return random.choice(ua_list)

    def apply_proxy_settings(self):
        """تطبيق إعدادات البروكسي المدخلة على جميع الجلسات النشطة."""
        if not self.proxy_entry:
            print("خطأ داخلي: لم يتم تهيئة مربع إدخال البروكسي.")
            return

        proxy_address = self.proxy_entry.get().strip()
        new_proxies = {} # قاموس لتخزين البروكسي الجديد

        # التحقق من صحة تنسيق البروكسي المدخل
        if proxy_address:
            if ':' not in proxy_address or not proxy_address.split(':')[0] or not proxy_address.split(':')[-1].isdigit():
                # استخدام messagebox هنا مقبول لأنه ناتج عن تفاعل المستخدم مع الواجهة مباشرة
                messagebox.showwarning("تحذير البروكسي", f"تنسيق البروكسي يبدو غير صالح: '{proxy_address}'.\nالتنسيق المتوقع هو IP:Port.\nلم يتم تطبيق التغيير.", parent=self.root)
                return
            else:
                # تهيئة البروكسي إذا كان التنسيق صحيحًا
                formatted_proxy = f"http://{proxy_address}"
                new_proxies = {'http': formatted_proxy, 'https': formatted_proxy}

        updated_count = 0 # عداد الجلسات التي تم تحديثها
        error_count = 0 # عداد الأخطاء أثناء التحديث

        # التحقق من وجود حسابات لتطبيق البروكسي عليها
        if not self.accounts:
             self.update_notification("لا توجد حسابات نشطة لتطبيق إعدادات البروكسي عليها.", "orange")
             return

        # المرور على جميع الحسابات وتحديث البروكسي في جلساتها
        for user, account_data in self.accounts.items():
            if "session" in account_data and isinstance(account_data["session"], requests.Session):
                try:
                    account_data["session"].proxies = new_proxies # تطبيق البروكسي الجديد أو إزالته
                    updated_count += 1
                except Exception as e:
                     error_count += 1
                     print(f"خطأ أثناء تحديث البروكسي للحساب {user}: {e}")

        # عرض إشعارات بناءً على نتيجة التحديث
        if error_count > 0:
             self.update_notification(f"حدث خطأ أثناء تحديث البروكسي لـ {error_count} حساب(ات).", "red")
        if updated_count > 0:
             if new_proxies:
                 # تم تطبيق بروكسي جديد
                 self.update_notification(f"تم تطبيق البروكسي '{proxy_address}' على {updated_count} حساب(ات).", "blue")
                 print(f"Applied proxy {new_proxies} to {updated_count} sessions.")
             else:
                 # تم إزالة البروكسي
                 self.update_notification(f"تم إزالة إعدادات البروكسي من {updated_count} حساب(ات).", "blue")
                 print(f"Cleared proxy settings for {updated_count} sessions.")
        elif error_count == 0 and self.accounts :
              # لم يتم إدخال بروكسي ولم تكن هناك أخطاء
              self.update_notification("لم يتم تغيير إعدادات البروكسي.", "grey")

    def create_session(self, user_agent):
        """إنشاء جلسة requests جديدة مع الهيدرات والبروكسي الأولي (إذا وجد)."""
        headers = { # هيدرات محدثة ومنظمة
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
            "Content-Type": "application/json",
            "Origin": "https://ecsc.gov.sy",
            "Referer": "https://ecsc.gov.sy/", # Referer عام، يتم تخصيصه عند الحاجة
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Source": "WEB",
            "Host": "api.ecsc.gov.sy:8443",
            "Connection": "keep-alive",
            "Priority": "u=1", # قد يكون خاص ببعض المتصفحات، يمكن إزالته إذا سبب مشاكل
            "TE": "trailers", # قد يكون خاص ببعض المتصفحات، يمكن إزالته
        }
        session = requests.Session() # إنشاء الجلسة
        session.headers.update(headers) # تطبيق الهيدرات الافتراضية
        session.verify = False # تعطيل التحقق من شهادة SSL

        # تطبيق البروكسي الأولي من مربع الإدخال عند إنشاء الجلسة
        if self.proxy_entry:
            proxy_address = self.proxy_entry.get().strip()
            if proxy_address and ':' in proxy_address:
                 try:
                    # التأكد من التنسيق قبل تطبيقه
                    ip, port = proxy_address.split(':', 1)
                    if ip and port.isdigit():
                        formatted_proxy = f"http://{proxy_address}"
                        proxies = {'http': formatted_proxy, 'https': formatted_proxy}
                        session.proxies = proxies
                        print(f"جلسة جديدة تم إنشاؤها باستخدام البروكسي: {proxies}")
                    else:
                         print(f"تنسيق البروكسي الأولي '{proxy_address}' غير صالح، لم يتم تطبيقه على الجلسة الجديدة.")
                 except Exception as e:
                      print(f"خطأ في تعيين البروكسي الأولي للجلسة الجديدة: {e}")

        return session

    def login(self, username, password, session, retries=2):
        """محاولة تسجيل الدخول باستخدام بيانات الاعتماد والجلسة المقدمة."""
        url = "https://api.ecsc.gov.sy:8443/secure/auth/login"
        payload = {"username": username, "password": password}
        # تحديث Referer خصيصًا لطلب تسجيل الدخول
        login_headers = {'Referer': 'https://ecsc.gov.sy/login'}

        for attempt in range(retries):
            try:
                self.update_notification(f"[{username}] محاولة تسجيل الدخول ({attempt + 1}/{retries})...", "grey")
                # إرسال طلب POST مع بيانات الدخول والهيدر المخصص والمهلة
                r = session.post(url, json=payload, headers=login_headers, timeout=(10, 20)) # (connect_timeout, read_timeout)

                # تحليل استجابة الخادم
                if r.status_code == 200:
                    # نجاح تسجيل الدخول
                    self.update_notification(f"[{username}] تم تسجيل الدخول بنجاح.", "green")
                    return True
                elif r.status_code == 401:
                    # خطأ في بيانات الاعتماد
                    self.update_notification(f"[{username}] فشل تسجيل الدخول (401): بيانات الاعتماد غير صحيحة.", "red")
                    return False # لا داعي للمحاولة مرة أخرى إذا كانت البيانات خاطئة
                else:
                    # أخطاء أخرى (مثل خطأ خادم 5xx)
                    self.update_notification(f"[{username}] فشل تسجيل الدخول ({r.status_code}).", "red")
                    print(f"Login failed for {username}. Status: {r.status_code}, Response: {r.text[:200]}") # طباعة جزء من الاستجابة للمساعدة في التشخيص
                    # إعادة المحاولة فقط لأخطاء الخادم (5xx)
                    if 500 <= r.status_code < 600 and attempt < retries - 1:
                         time.sleep(attempt + 1) # انتظار قصير قبل إعادة المحاولة
                         continue
                    else:
                         return False # فشل نهائي بعد المحاولات أو لخطأ غير 5xx

            except requests.exceptions.RequestException as e: # التقاط جميع أخطاء requests الرئيسية (Timeout, ConnectionError, ProxyError, etc.)
                 self.update_notification(f"[{username}] خطأ شبكة أثناء تسجيل الدخول: {type(e).__name__}", "red")
                 print(f"Network error during login for {username}: {e}")
                 # لا تعيد المحاولة لخطأ البروكسي لأنه غالبًا مشكلة إعدادات
                 if isinstance(e, requests.exceptions.ProxyError): return False
                 # إعادة المحاولة للأخطاء الأخرى إذا لم نصل للحد الأقصى
                 if attempt < retries - 1:
                      time.sleep(attempt + 1)
                      continue
                 else:
                      return False # فشل نهائي بعد محاولات الشبكة
            except Exception as e:
                # التقاط أي أخطاء غير متوقعة أخرى
                self.update_notification(f"[{username}] خطأ غير متوقع أثناء تسجيل الدخول: {e}", "red")
                import traceback
                print(f"Unexpected error during login for {username}:\n{traceback.format_exc()}")
                return False # فشل لأي خطأ غير متوقع

        # إذا انتهت جميع المحاولات دون نجاح
        self.update_notification(f"[{username}] فشل تسجيل الدخول بعد {retries} محاولات.", "red")
        return False

    def add_account(self):
        """إضافة حساب جديد: طلب البيانات، تسجيل الدخول، جلب العمليات، وإنشاء الواجهة."""
        # طلب اسم المستخدم وكلمة المرور من المستخدم
        user = simpledialog.askstring("اسم المستخدم", "أدخل اسم المستخدم:", parent=self.root)
        if user is None: return # المستخدم ألغى الإدخال
        pwd = simpledialog.askstring("كلمة المرور", "أدخل كلمة المرور:", show="*", parent=self.root)
        if pwd is None: return # المستخدم ألغى الإدخال

        # التحقق من أن المستخدم أدخل البيانات
        if not user or not pwd:
            messagebox.showwarning("إدخال ناقص", "الرجاء إدخال اسم المستخدم وكلمة المرور.", parent=self.root)
            return

        # التحقق من أن الحساب غير مضاف بالفعل
        if user in self.accounts:
             messagebox.showwarning("حساب مكرر", f"الحساب '{user}' موجود بالفعل.", parent=self.root)
             return

        # إنشاء جلسة جديدة لهذا الحساب
        session = self.create_session(self.generate_user_agent())
        start_time = time.time() # بدء قياس وقت تسجيل الدخول

        # محاولة تسجيل الدخول
        if not self.login(user, pwd, session):
            # فشل تسجيل الدخول، لا داعي للمتابعة
            # رسالة الفشل تم عرضها بالفعل بواسطة دالة login
            return

        # تسجيل الدخول نجح
        elapsed_time = time.time() - start_time
        self.update_notification(f"تم تسجيل الدخول للحساب {user} في {elapsed_time:.2f} ثانية", "green")

        # إضافة الحساب وبياناته إلى القاموس الرئيسي
        self.accounts[user] = {"password": pwd, "session": session}

        # جلب قائمة العمليات المتاحة لهذا الحساب
        proc_ids_data = self.fetch_process_ids(session, user)

        # إنشاء واجهة المستخدم الخاصة بالحساب فقط إذا نجح جلب العمليات
        if proc_ids_data is not None: # Note: [] is a valid result (no processes)
            self._create_account_ui(user, proc_ids_data)
        else:
            # فشل جلب العمليات، إزالة الحساب الذي تم تسجيل دخوله للتو
            self.update_notification(f"[{user}] لم يتم إضافة واجهة الحساب بسبب خطأ في جلب بيانات العمليات.", "red")
            # تأكد من إزالة الحساب من القاموس إذا فشل جلب العمليات
            if user in self.accounts:
                del self.accounts[user]


    def fetch_process_ids(self, session, username):
        """جلب قائمة معرفات وأسماء العمليات المتاحة للحساب."""
        url = "https://api.ecsc.gov.sy:8443/dbm/db/execute"
        # بيانات الطلب لجلب العمليات
        payload = {"ALIAS": "OPkUVkYsyq", "P_USERNAME": "WebSite", "P_PAGE_INDEX": 0, "P_PAGE_SIZE": 100}
        # هيدر خاص لهذا الطلب
        headers = {"Alias": "OPkUVkYsyq", "Referer": "https://ecsc.gov.sy/requests"}

        try:
            self.update_notification(f"[{username}] جارٍ جلب قائمة العمليات المتاحة...", "grey")
            # إرسال الطلب لجلب العمليات
            r = session.post(url, json=payload, headers=headers, timeout=(10, 20))

            # تحليل الاستجابة
            if r.status_code == 200:
                 result = r.json() # محاولة قراءة الاستجابة كـ JSON
                 # التحقق من وجود قائمة النتائج وأنها ليست فارغة
                 if "P_RESULT" in result and result["P_RESULT"]:
                    self.update_notification(f"[{username}] تم جلب {len(result['P_RESULT'])} عملية متاحة.", "green")
                    return result["P_RESULT"] # إرجاع قائمة العمليات
                 else:
                    # لا توجد عمليات متاحة (استجابة 200 ولكن القائمة فارغة)
                    self.update_notification(f"[{username}] لا توجد عمليات متاحة حاليًا.", "orange")
                    return [] # إرجاع قائمة فارغة
            elif r.status_code in (401, 403):
                 # خطأ صلاحية (قد تكون الجلسة انتهت أو تغيرت الصلاحيات)
                 self.update_notification(f"[{username}] خطأ صلاحية ({r.status_code}) عند جلب العمليات.", "red")
                 # محاولة إعادة تسجيل الدخول قد تكون مفيدة هنا، ولكن للتبسيط سنعيد None
                 return None
            else:
                # خطأ آخر من الخادم
                self.update_notification(f"[{username}] فشل جلب العمليات ({r.status_code}).", "red")
                print(f"Fetch IDs failed for {username}. Status: {r.status_code}, Response: {r.text[:200]}")
                return None # فشل جلب العمليات

        except requests.exceptions.RequestException as e:
             # خطأ في الشبكة
             self.update_notification(f"[{username}] خطأ شبكة أثناء جلب العمليات: {type(e).__name__}", "red")
             print(f"Network error during fetch_process_ids for {username}: {e}")
             return None
        except Exception as e:
            # خطأ غير متوقع
            self.update_notification(f"[{username}] خطأ غير متوقع أثناء جلب العمليات: {e}", "red")
            import traceback
            print(f"Unexpected error during fetch_process_ids for {username}:\n{traceback.format_exc()}")
            return None

    def _create_account_ui(self, user, processes_data):
        """إنشاء قسم واجهة المستخدم لحساب معين وعرض أزرار عملياته."""
        # إنشاء إطار خاص لهذا الحساب داخل الإطار الرئيسي للحسابات
        account_frame = tk.Frame(self.accounts_frame, bd=2, relief="groove")
        account_frame.pack(fill=tk.X, padx=5, pady=5)

        # عرض اسم المستخدم
        tk.Label(account_frame, text=f"الحساب: {user}", anchor="e", font=("Helvetica", 11, "bold")).pack(fill=tk.X, padx=5, pady=(2, 4))

        # إنشاء إطار فرعي لأزرار العمليات
        processes_frame = tk.Frame(account_frame)
        processes_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        # التحقق إذا كانت قائمة العمليات فارغة
        if not processes_data:
             tk.Label(processes_frame, text="لا توجد عمليات متاحة لهذا الحساب حالياً.", fg="grey").pack(pady=5)
             return # لا داعي لإضافة أزرار

        # إنشاء الأزرار لكل عملية
        for proc in processes_data:
            pid = proc.get("PROCESS_ID") # الحصول على معرف العملية
            name = proc.get("ZCENTER_NAME", f"عملية {pid}") # الحصول على اسم العملية أو استخدام اسم افتراضي

            # تخطي العملية إذا لم يكن لها معرف
            if pid is None:
                print(f"تحذير: تم تخطي عملية بدون PROCESS_ID للحساب {user}: {proc}")
                continue

            # إنشاء إطار فرعي لكل زر وشريط تقدم خاص به
            sub_frame = tk.Frame(processes_frame)
            sub_frame.pack(fill=tk.X, padx=5, pady=2)

            # شريط التقدم (غير مرئي في البداية)
            prog = ttk.Progressbar(sub_frame, mode='indeterminate')
            # لا يتم عمل pack له الآن، سيظهر عند الضغط على الزر

            # إنشاء الزر بدون أمر أولاً
            btn = tk.Button(sub_frame, text=name, width=25, state=tk.NORMAL)
            btn.pack(side=tk.RIGHT) # وضع الزر على اليمين

            # إنشاء وتعيين الأمر بعد إنشاء الزر لتجنب مشاكل الإغلاق (closure)
            # نمرر الزر نفسه (clicked_btn=btn) وشريط التقدم (prog_bar=prog) إلى الدالة الهدف
            command_lambda = lambda u=user, p=pid, pr=prog, clicked_btn=btn: threading.Thread(
                                 target=self._handle_captcha_request, args=(u, p, pr, clicked_btn), daemon=True
                             ).start()
            btn.config(command=command_lambda) # تعيين الأمر للزر


    def _handle_captcha_request(self, user, pid, prog_bar, clicked_btn):
        """معالجة طلب الكابتشا عند الضغط على زر العملية."""
        # محاولة تعطيل الزر لمنع الضغطات المتعددة وإظهار شريط التقدم
        try:
            # التأكد من أن الزر ما زال موجوداً قبل محاولة تعديله
            if clicked_btn.winfo_exists():
                clicked_btn.config(state=tk.DISABLED) # تعطيل الزر
                 # إظهار شريط التقدم وتشغيله
                parent_frame = prog_bar.master # الإطار الحاوي للزر والشريط
                # وضع شريط التقدم على يسار الزر وملء المساحة المتبقية
                prog_bar.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True, before=clicked_btn)
                prog_bar.start(10) # بدء حركة شريط التقدم
            else:
                 print(f"تحذير: الزر للعملية {pid} لم يعد موجودًا عند بدء الطلب.")
                 return # الخروج إذا لم يكن الزر موجوداً
        except tk.TclError:
             print(f"تحذير: خطأ TclError عند محاولة تعطيل الزر/إظهار الشريط للعملية {pid} (قد تكون النافذة أغلقت).")
             return # الخروج في حالة حدوث خطأ

        # تحديث الإشعار
        self.update_notification(f"[{user}] جارٍ طلب كابتشا للعملية '{pid}'...", "blue")

        captcha_data = None # لتهيئة المتغير
        try:
            # التأكد من وجود بيانات الحساب والجلسة
            if user not in self.accounts or 'session' not in self.accounts[user]:
                  raise ValueError(f"معلومات جلسة الحساب {user} غير موجودة.") # إثارة خطأ إذا كانت البيانات مفقودة

            session = self.accounts[user]["session"] # الحصول على الجلسة الخاصة بالحساب

            # طلب بيانات الكابتشا من الخادم
            captcha_data = self.get_captcha(session, pid, user)

        except Exception as e:
             # التعامل مع أي خطأ يحدث أثناء جلب الكابتشا
             self.update_notification(f"[{user}] خطأ فادح أثناء تحضير/طلب الكابتشا: {e}", "red")

        finally:
            # هذا الكود سينفذ دائماً، سواء نجح جلب الكابتشا أو فشل
            # إيقاف وإخفاء شريط التقدم وإعادة تفعيل الزر (إذا كانت العناصر لا تزال موجودة)
            try:
                 # التأكد من وجود شريط التقدم قبل محاولة إيقافه وإخفائه
                 if prog_bar.winfo_exists():
                      prog_bar.stop() # إيقاف الحركة
                      prog_bar.pack_forget() # إخفاء الشريط
            except tk.TclError:
                 print(f"تحذير: خطأ TclError عند محاولة إيقاف/إخفاء شريط التقدم للعملية {pid}.")
            try:
                 # التأكد من وجود الزر قبل محاولة إعادة تفعيله
                 if clicked_btn.winfo_exists():
                      clicked_btn.config(state=tk.NORMAL) # إعادة تفعيل الزر
            except tk.TclError:
                  print(f"تحذير: خطأ TclError عند محاولة إعادة تفعيل الزر للعملية {pid}.")

        # إذا تم الحصول على بيانات الكابتشا بنجاح
        if captcha_data:
            # التحقق إذا كان هناك كابتشا أخرى قيد المعالجة
            if self.current_captcha is not None:
                 u_curr, p_curr = self.current_captcha
                 self.update_notification(f"[{user}] طلب كابتشا جديد للعملية {pid}، ولكن هناك كابتشا أخرى ({u_curr}/{p_curr}) قيد المعالجة. تجاهل الطلب الجديد.", "orange")
            else:
                 # لا توجد كابتشا حالية، يمكن المتابعة
                 self.current_captcha = (user, pid) # تسجيل الكابتشا الحالية
                 self.show_and_process_captcha(captcha_data) # عرض الكابتشا ومعالجتها
        else:
            # فشل الحصول على الكابتشا
            self.update_notification(f"[{user}] لم يتم الحصول على كابتشا للعملية '{pid}'.", "orange")
            # التأكد من أن الحالة الحالية فارغة إذا فشل الحصول على الكابتشا
            self.current_captcha = None
            # مسح أي إطار كابتشا قديم قد يكون عالقاً (احتياطي)
            self.clear_captcha_display()


    def get_captcha(self, session, pid, user):
        """جلب صورة الكابتشا (base64) من الخادم مع محاولات إعادة وإعادة تسجيل الدخول."""
        url = f"https://api.ecsc.gov.sy:8443/captcha/get/{pid}"
        max_login_retries = 1 # أقصى عدد محاولات لإعادة تسجيل الدخول عند خطأ 401/403
        login_attempts = 0 # عداد محاولات إعادة تسجيل الدخول الحالية
        max_request_retries = 3 # أقصى عدد محاولات لطلب الكابتشا نفسه
        request_attempts = 0 # عداد محاولات الطلب الحالية

        while request_attempts < max_request_retries:
            request_attempts += 1 # زيادة عداد محاولات الطلب
            try:
                # إرسال طلب GET للحصول على الكابتشا
                r = session.get(url, timeout=(15, 30)) # زيادة المهلة قليلاً (connect, read)

                # --- تحليل استجابة الخادم ---
                if r.status_code == 200:
                    # نجاح الطلب
                    captcha_info = r.json() # قراءة الاستجابة كـ JSON
                    # التحقق من وجود بيانات الصورة في الاستجابة
                    if "file" in captcha_info and captcha_info["file"]:
                         self.update_notification(f"[{user}] تم استلام بيانات الكابتشا (PID: {pid}).", "green")
                         return captcha_info["file"] # إرجاع بيانات الصورة (base64)
                    else:
                         # استجابة 200 ولكن لا تحتوي على بيانات الصورة المتوقعة
                         self.update_notification(f"[{user}] استجابة الكابتشا (PID: {pid}) لا تحتوي على ملف.", "orange")
                         return None # فشل

                elif r.status_code == 429:
                    # خطأ "Too Many Requests"
                    # انتظار مدة قصيرة ومتزايدة قبل إعادة المحاولة
                    wait_time = 0.5 * request_attempts
                    self.update_notification(f"[{user}] الخادم مشغول (429) لـ PID {pid}. الانتظار {wait_time:.1f} ثانية...", "orange")
                    time.sleep(wait_time)
                    # لا نزيد request_attempts هنا لأننا نعيد المحاولة بسبب ظرف مؤقت من الخادم
                    # ولكن يجب التأكد من أننا لا ندخل في حلقة لا نهائية إذا كان الخادم مشغولاً باستمرار
                    # يمكن إضافة شرط للخروج إذا تكرر 429 كثيراً
                    continue # الانتقال للمحاولة التالية

                elif r.status_code in (401, 403):
                    # خطأ صلاحية (الجلسة قد تكون انتهت)
                    self.update_notification(f"[{user}] خطأ صلاحية ({r.status_code}) لـ PID {pid}. قد تحتاج لإعادة تسجيل الدخول.", "orange")

                    # التحقق إذا كان يمكننا محاولة إعادة تسجيل الدخول
                    if login_attempts < max_login_retries:
                        login_attempts += 1 # زيادة عداد محاولات إعادة الدخول
                        self.update_notification(f"[{user}] محاولة إعادة تسجيل الدخول ({login_attempts}/{max_login_retries})...", "orange")

                        # محاولة إعادة تسجيل الدخول بنفس الجلسة
                        if self.login(user, self.accounts[user]["password"], session):
                             # نجحت إعادة تسجيل الدخول
                             self.update_notification(f"[{user}] إعادة الدخول نجحت. إعادة محاولة طلب كابتشا لـ PID {pid}...", "green")
                             request_attempts = 0 # إعادة تعيين عداد محاولات الطلب لأن الجلسة تجددت
                             continue # إعادة محاولة طلب الكابتشا بالجلسة الجديدة
                        else:
                             # فشلت إعادة تسجيل الدخول
                             self.update_notification(f"[{user}] فشل إعادة تسجيل الدخول.", "red")
                             return None # فشل نهائي
                    else:
                        # تم الوصول للحد الأقصى لمحاولات إعادة الدخول
                        self.update_notification(f"[{user}] تم الوصول للحد الأقصى لمحاولات إعادة الدخول.", "red")
                        return None # فشل نهائي
                else:
                    # خطأ آخر من الخادم (مثل 5xx)
                    self.update_notification(f"[{user}] خطأ سيرفر ({r.status_code}) عند طلب كابتشا لـ PID {pid}.", "red")
                    print(f"Server error {r.status_code} getting captcha for {user} pid {pid}: {r.text[:200]}")
                    # يمكن إعادة المحاولة لأخطاء 5xx إذا أردنا
                    if 500 <= r.status_code < 600 and request_attempts < max_request_retries:
                        time.sleep(1) # انتظار قصير
                        continue # إعادة المحاولة
                    else:
                        return None # فشل نهائي

            except requests.exceptions.RequestException as e:
                  # خطأ في الشبكة (Timeout, ConnectionError, ProxyError)
                  self.update_notification(f"[{user}] خطأ شبكة ({type(e).__name__}) عند طلب كابتشا لـ PID {pid}.", "red")
                  print(f"Network error getting captcha for {user} pid {pid}: {e}")
                  # لا نعيد المحاولة لخطأ البروكسي
                  if isinstance(e, requests.exceptions.ProxyError): return None
                  # إعادة المحاولة للأخطاء المؤقتة الأخرى إذا لم نصل للحد الأقصى
                  if request_attempts < max_request_retries:
                      time.sleep(1) # انتظار قصير
                      continue # إعادة المحاولة
                  else:
                      return None # فشل نهائي
            except Exception as e:
                # خطأ غير متوقع
                self.update_notification(f"[{user}] خطأ غير متوقع عند طلب كابتشا لـ PID {pid}: {e}", "red")
                import traceback
                print(f"Unexpected error getting captcha for {user} pid {pid}:\n{traceback.format_exc()}")
                return None # فشل نهائي

        # إذا انتهت جميع محاولات الطلب دون نجاح
        self.update_notification(f"[{user}] فشل الحصول على الكابتشا لـ PID {pid} بعد {max_request_retries} محاولات.", "red")
        return None


    def predict_captcha(self, pil_image):
        """التنبؤ بالنص في صورة الكابتشا باستخدام نموذج ONNX."""
        preprocess = preprocess_for_model() # الحصول على دالة المعالجة الأولية
        img_rgb = pil_image.convert("RGB") # التأكد من أن الصورة RGB (قد تكون رمادية)

        start_preprocess = time.time() # بدء قياس وقت المعالجة
        try:
            # تطبيق المعالجة الأولية وتحويلها إلى numpy array بالشكل المناسب
            input_tensor = preprocess(img_rgb).unsqueeze(0).numpy().astype(np.float32)
        except Exception as e:
            print(f"خطأ أثناء المعالجة الأولية للصورة للنموذج: {e}")
            return "preprocess_err", 0, 0 # إرجاع رمز خطأ مميز
        end_preprocess = time.time() # نهاية قياس وقت المعالجة

        start_predict = time.time() # بدء قياس وقت التنبؤ
        predicted_text = "error" # قيمة افتراضية في حالة الخطأ

        try:
            # الحصول على اسم مدخل النموذج
            input_name = self.session.get_inputs()[0].name
            # تهيئة المدخلات للنموذج
            ort_inputs = {input_name: input_tensor}
            # تشغيل النموذج (الاستدلال)
            ort_outs = self.session.run(None, ort_inputs)[0] # الحصول على المخرجات الأولى

            # التحقق الأساسي من شكل المخرجات (قد يحتاج لتعديل حسب نموذجك)
            # هذا المثال يفترض أن المخرجات هي (batch_size, sequence_length * num_classes) أو (batch_size, sequence_length, num_classes)
            # هنا نفترض الشكل المسطح ونعيد تشكيله
            expected_elements = NUM_POS * NUM_CLASSES
            if len(ort_outs.shape) < 2 or ort_outs.shape[0] != 1 or ort_outs.shape[1] < expected_elements:
                 raise ValueError(f"شكل مخرجات النموذج غير متوقع: {ort_outs.shape}. كان متوقعاً على الأقل (1, {expected_elements})")

            # قص المخرجات إذا كانت أطول من المتوقع (بعض النماذج قد تضيف padding)
            ort_outs_trimmed = ort_outs[:, :expected_elements]

            # إعادة تشكيل المخرجات للحصول على احتمالات كل حرف في كل موقع
            # الشكل المتوقع: (batch_size, num_positions, num_classes)
            ort_outs_reshaped = ort_outs_trimmed.reshape(1, NUM_POS, NUM_CLASSES)

            # الحصول على فهرس الحرف ذو الاحتمالية الأعلى في كل موقع
            predicted_indices = np.argmax(ort_outs_reshaped, axis=2)[0] # [0] لإزالة بعد الـ batch

            # تحويل الفهارس إلى نص باستخدام القاموس
            predicted_text = ''.join(IDX2CHAR[i] for i in predicted_indices if i in IDX2CHAR) # التأكد من وجود الفهرس

        except IndexError:
             # خطأ يحدث إذا كان الفهرس المتوقع غير موجود في IDX2CHAR (مشكلة في CHARSET أو مخرجات النموذج)
             print(f"خطأ فك الترميز: فهرس خارج النطاق. تحقق من CHARSET ({CHARSET}) و NUM_CLASSES ({NUM_CLASSES}) ومخرجات النموذج.")
             predicted_text = "decode_err"
        except ValueError as e:
              # خطأ يحدث إذا كانت عملية reshape فشلت بسبب عدم تطابق الأبعاد
              print(f"خطأ في شكل مخرجات النموذج أثناء إعادة التشكيل: {e}")
              predicted_text = "shape_err"
        except Exception as e:
            # أي خطأ آخر أثناء تشغيل النموذج
            print(f"خطأ أثناء تشغيل استدلال النموذج (ONNX Runtime): {e}")
            import traceback
            print(traceback.format_exc())
            predicted_text = "onnx_err"

        end_predict = time.time() # نهاية قياس وقت التنبؤ

        # حساب الأزمنة بالمللي ثانية
        preprocess_time_ms = (end_preprocess - start_preprocess) * 1000
        predict_time_ms = (end_predict - start_predict) * 1000

        return predicted_text, preprocess_time_ms, predict_time_ms

    def show_and_process_captcha(self, base64_data):
        """عرض الكابتشا، التنبؤ بها، وعرض النتيجة، ثم بدء الإرسال."""
        # التأكد من مسح أي إطار كابتشا سابق قبل إنشاء واحد جديد
        self.clear_captcha_display(immediately=True)

        # إنشاء إطار جديد لعرض الكابتشا والنتيجة داخل إطار الحسابات الرئيسي
        # *** تخزين مرجع لهذا الإطار في self.current_captcha_frame ***
        self.current_captcha_frame = tk.Frame(self.accounts_frame, bd=2, relief="sunken")
        # إضافة علامة مميزة لهذا الإطار لتسهيل العثور عليه لاحقاً
        self.current_captcha_frame._is_captcha_frame = True
        # وضع الإطار في الأسفل داخل accounts_frame
        self.current_captcha_frame.pack(pady=10, padx=5, fill=tk.X, side=tk.BOTTOM)


        try:
            # --- فك ترميز ومعالجة الصورة (قد تكون GIF متحركة) ---
            # إزالة الجزء الأول "data:image/gif;base64," إذا كان موجوداً
            if "," in base64_data: base64_string = base64_data.split(",")[1]
            else: base64_string = base64_data

            # فك ترميز Base64 للحصول على بيانات الصورة الخام
            raw_image_data = base64.b64decode(base64_string)
            # فتح الصورة باستخدام PIL
            pil_image_orig = Image.open(io.BytesIO(raw_image_data))

            # --- معالجة الـ GIF المتحرك (إذا كانت الصورة GIF) ---
            frames = []
            try:
                # محاولة قراءة كل إطارات الـ GIF
                pil_image_orig.seek(0) # الانتقال إلى الإطار الأول
                while True:
                    # تحويل الإطار إلى RGB وإضافته كـ numpy array
                    frames.append(np.array(pil_image_orig.convert("RGB")))
                    pil_image_orig.seek(pil_image_orig.tell() + 1) # الانتقال للإطار التالي
            except EOFError:
                # تم الوصول لنهاية الإطارات
                pass
            except Exception as img_err:
                 print(f"خطأ أثناء قراءة إطارات الصورة: {img_err}")
                 # إذا فشلت قراءة الإطارات، حاول استخدام الإطار الأول فقط (إذا كان متاحاً)
                 if not frames:
                     try:
                         pil_image_orig.seek(0)
                         frames.append(np.array(pil_image_orig.convert("RGB")))
                     except Exception:
                          raise ValueError("فشل قراءة أي إطار من الصورة.") from img_err

            if not frames:
                 # إذا لم يتم قراءة أي إطارات بنجاح
                 raise ValueError("لم يتم قراءة أي إطارات من بيانات الصورة.")

            # تكديس الإطارات للحصول على مصفوفة واحدة
            stacked_frames = np.stack(frames).astype(np.uint8)

            # حساب الوسيط (median) عبر الإطارات لإزالة العناصر المتحركة (الحصول على الخلفية)
            median_background = np.median(stacked_frames, axis=0).astype(np.uint8)

            # --- معالجة إضافية لتحسين التباين (اختياري ولكن مفيد) ---
            # تحويل صورة الخلفية إلى رمادية
            gray_image = cv2.cvtColor(median_background, cv2.COLOR_RGB2GRAY)

            # تطبيق CLAHE (Contrast Limited Adaptive Histogram Equalization) لتحسين التباين المحلي
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            enhanced_image = clahe.apply(gray_image)

            # تحويل الصورة المحسنة إلى ثنائية (أسود وأبيض) باستخدام Otsu's thresholding
            # هذا يساعد في فصل النص عن الخلفية بشكل أوضح للنموذج
            _, binary_image = cv2.threshold(enhanced_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # تحويل الصورة المعالجة النهائية (الثنائية) مرة أخرى إلى صيغة PIL
            processed_pil_image = Image.fromarray(binary_image)
            # --- نهاية معالجة الصورة ---

            # --- التنبؤ باستخدام النموذج ---
            predicted_solution, preprocess_ms, predict_ms = self.predict_captcha(processed_pil_image)

            # التحقق مرة أخرى إذا تم إلغاء الكابتشا أثناء عملية التنبؤ الطويلة
            if not self.current_captcha or not self.current_captcha_frame or not self.current_captcha_frame.winfo_exists():
                 print("تم إلغاء معالجة الكابتشا أو إغلاق إطارها قبل اكتمال التنبؤ.")
                 # التأكد من مسح الإطار إذا كان لا يزال موجوداً بطريقة ما
                 self.clear_captcha_display(immediately=True)
                 return

            # الحصول على المستخدم والمعرف من الحالة الحالية
            user, pid = self.current_captcha
            self.update_notification(f"[{user}] النص المتوقع للكابتشا (PID: {pid}): {predicted_solution}", "blue")

            # تحديث ملصق السرعة
            self.speed_label.config(text=f"معالجة أولية: {preprocess_ms:.1f} ms | التنبؤ: {predict_ms:.1f} ms")

            # --- عرض الصورة المعالجة والنص المتوقع في الإطار ---
            # تغيير حجم الصورة المعالجة للعرض (لتكون أوضح)
            display_image = processed_pil_image.resize((180, 70), Image.Resampling.LANCZOS) # استخدام Lanczos لجودة أفضل
            tk_image = ImageTk.PhotoImage(display_image)

            # إنشاء ملصق لعرض الصورة
            img_label = tk.Label(self.current_captcha_frame, image=tk_image)
            img_label.image = tk_image # الاحتفاظ بمرجع للصورة لتجنب حذفها بواسطة جامع القمامة
            img_label.pack(pady=5)

            # إنشاء ملصق لعرض النص المتوقع
            prediction_label = tk.Label(self.current_captcha_frame, text=f"الحل المتوقع: {predicted_solution}", font=("Helvetica", 12, "bold"))
            prediction_label.pack(pady=(0, 5)) # تقليل المسافة السفلية قليلاً

            # --- بدء عملية الإرسال إذا كان التنبؤ ناجحًا ---
            if predicted_solution not in ["error", "onnx_err", "shape_err", "decode_err", "preprocess_err"]:
                # تشغيل عملية الإرسال في thread منفصل لتجنب تجميد الواجهة
                # *** تمرير الإطار الحالي إلى دالة الإرسال لعرض النتيجة فيه ***
                threading.Thread(target=self.submit_captcha_solution,
                                 args=(predicted_solution, self.current_captcha_frame),
                                 daemon=True).start()
            else:
                # حدث خطأ أثناء التنبؤ، عرض رسالة خطأ في الإطار بدلاً من الإرسال
                error_message = f"خطأ في التنبؤ: {predicted_solution}"
                self.show_submission_result_in_frame(
                    self.current_captcha_frame, # الإطار الحالي
                    user,
                    pid,
                    -1, # كود حالة افتراضي للخطأ الداخلي
                    error_message,
                    False # فشل
                )
                # مسح الكابتشا الحالية لأن التنبؤ فشل
                self.current_captcha = None
                # جدولة مسح الإطار بعد فترة للسماح برؤية الخطأ
                self.root.after(4000, lambda frame=self.current_captcha_frame: self.clear_captcha_display(frame_to_clear=frame))


        except Exception as e: # التقاط أي خطأ خلال العملية بأكملها (فك التشفير، المعالجة، التنبؤ، العرض)
            error_msg = f"خطأ أثناء عرض/معالجة الكابتشا: {e}"
            self.update_notification(error_msg, "red")
            import traceback
            print(f"Unexpected error in show_and_process_captcha:\n{traceback.format_exc()}")

            # عرض رسالة الخطأ في الإطار إذا كان لا يزال موجودًا
            if self.current_captcha_frame and self.current_captcha_frame.winfo_exists():
                 try:
                     user_disp, pid_disp = self.current_captcha if self.current_captcha else ("غير معروف", "N/A")
                     self.show_submission_result_in_frame(
                         self.current_captcha_frame, user_disp, pid_disp, -2, f"خطأ معالجة: {e}", False
                     )
                     # جدولة مسح الإطار بعد فترة
                     self.root.after(4000, lambda frame=self.current_captcha_frame: self.clear_captcha_display(frame_to_clear=frame))
                 except Exception as inner_e:
                      print(f"خطأ إضافي أثناء محاولة عرض خطأ المعالجة في الإطار: {inner_e}")
                      # محاولة أخيرة لمسح الإطار فوراً إذا فشل عرض الخطأ
                      self.clear_captcha_display(immediately=True)

            # مسح الحالة الحالية عند حدوث أي خطأ فادح في هذه المرحلة
            self.current_captcha = None
            # التأكد من أن المرجع للإطار يمسح أيضاً
            if self.current_captcha_frame:
                self.current_captcha_frame = None


    def submit_captcha_solution(self, solution, display_frame):
        """إرسال حل الكابتشا إلى الخادم وعرض النتيجة في الإطار المحدد."""
        # الحصول على نسخة من الكابتشا الحالية *قبل* بدء الطلب الشبكي الطويل
        current_task = self.current_captcha
        if not current_task:
            print("تحذير: محاولة إرسال حل ولكن لا توجد مهمة كابتشا حالية.")
            # قد يكون الإطار لا يزال موجوداً، نحاول مسحه
            self.clear_captcha_display(frame_to_clear=display_frame)
            return

        user, pid = current_task # الحصول على المستخدم والمعرف من المهمة الحالية

        # التحقق من وجود بيانات الحساب والجلسة
        if user not in self.accounts or "session" not in self.accounts[user]:
             self.update_notification(f"[{user}] لا يمكن إرسال الحل لـ PID {pid}، معلومات الحساب/الجلسة غير موجودة.", "red")
             # مسح المهمة إذا كانت لا تزال هي الحالية
             if self.current_captcha == current_task:
                 self.current_captcha = None
             self.clear_captcha_display(frame_to_clear=display_frame) # مسح الإطار
             return

        session = self.accounts[user]["session"] # الحصول على الجلسة الصحيحة
        url = f"https://api.ecsc.gov.sy:8443/rs/reserve?id={pid}&captcha={solution}" # بناء الرابط
        self.update_notification(f"[{user}] جارٍ إرسال الحل '{solution}' للعملية (PID: {pid})...", "blue")

        response_text = "لم يتم استلام استجابة" # قيمة افتراضية لنص الاستجابة
        status_code = -1 # قيمة افتراضية لكود الحالة
        success = False # افتراض الفشل

        try:
            # إرسال طلب GET لإرسال الحل (قد يكون POST حسب الـ API الفعلي)
            r = session.get(url, timeout=(10, 45)) # زيادة مهلة القراءة لأن هذا الطلب قد يستغرق وقتاً
            response_text = r.text # الحصول على نص الاستجابة
            status_code = r.status_code # الحصول على كود الحالة

            # تحليل كود الحالة
            if status_code == 200:
                # نجاح مبدئي (قد يحتوي النص على تفاصيل أكثر)
                self.update_notification(f"[{user}] تم استلام استجابة ناجحة ({status_code}) للإرسال لـ PID {pid}.", "green")
                success = True # اعتبار 200 نجاحًا مبدئيًا
            elif status_code == 400:
                 # خطأ (Bad Request) - غالبًا يعني حل خاطئ أو انتهاء صلاحية الكابتشا
                 self.update_notification(f"[{user}] فشل الإرسال لـ PID {pid} (400 - Bad Request). الحل خاطئ أو الكابتشا انتهت صلاحيتها.", "red")
            elif status_code in (401, 403):
                 # خطأ صلاحية
                 self.update_notification(f"[{user}] فشل الإرسال لـ PID {pid} - خطأ صلاحية ({status_code}). قد تحتاج لإعادة تسجيل الدخول.", "red")
            else:
                # أخطاء أخرى
                self.update_notification(f"[{user}] فشل إرسال الحل لـ PID {pid}. استجابة الخادم ({status_code}): {response_text[:150]}...", "red")

            # طباعة النتيجة للمساعدة في التشخيص
            print(f"Submit result for {user} pid {pid}. Status: {status_code}, Response: {response_text}")

        except requests.exceptions.RequestException as e:
             # خطأ في الشبكة أثناء الإرسال
             self.update_notification(f"[{user}] خطأ شبكة ({type(e).__name__}) أثناء إرسال الحل لـ PID {pid}.", "red")
             print(f"Network error submitting solution for {user} pid {pid}: {e}")
             response_text = f"خطأ شبكة: {type(e).__name__}" # تحديث نص الاستجابة للخطأ
        except Exception as e:
            # خطأ غير متوقع أثناء الإرسال
            self.update_notification(f"[{user}] خطأ غير متوقع أثناء إرسال الحل لـ PID {pid}: {e}", "red")
            import traceback
            print(f"Unexpected error submitting solution for {user} pid {pid}:\n{traceback.format_exc()}")
            response_text = f"خطأ غير متوقع: {e}" # تحديث نص الاستجابة للخطأ

        finally:
            # هذا الجزء سينفذ دائماً بعد محاولة الإرسال

            # التحقق إذا كانت المهمة الحالية لا تزال هي نفسها التي بدأنا بها
            # هذا لمنع مسح حالة كابتشا جديدة إذا بدأت واحدة أخرى أثناء هذا الطلب
            if self.current_captcha == current_task:
                 self.current_captcha = None # مسح حالة الكابتشا الحالية لأن العملية انتهت (نجاح أو فشل)
                 print(f"تم مسح حالة الكابتشا الحالية لـ {user} / {pid} بعد محاولة الإرسال.")

            # *** استدعاء الدالة الجديدة لعرض النتيجة داخل الإطار المحدد ***
            # استخدام root.after(0, ...) لضمان تنفيذ تحديث الواجهة في الـ thread الرئيسي
            self.root.after(0, lambda: self.show_submission_result_in_frame(
                display_frame, user, pid, status_code, response_text, success
            ))

            # جدولة مسح إطار العرض بعد فترة (مثلاً 5 ثواني) للسماح بقراءة النتيجة
            # استخدام lambda لضمان تمرير الإطار الصحيح للدالة بعد التأخير
            self.root.after(5000, lambda frame=display_frame: self.clear_captcha_display(frame_to_clear=frame))


    # *** دالة جديدة: لعرض نتيجة الإرسال داخل إطار الكابتشا ***
    def show_submission_result_in_frame(self, display_frame, user, pid, status_code, response_text, success):
        """يعرض نتيجة الإرسال كملصق نصي داخل إطار الكابتشا المحدد."""

        # التحقق أولاً إذا كان الإطار لا يزال موجوداً
        if not display_frame or not display_frame.winfo_exists():
            print(f"[{user}] حاول عرض نتيجة الإرسال لـ PID {pid} ولكن الإطار لم يعد موجوداً.")
            return

        # تحديد الرسالة واللون بناءً على النتيجة
        result_message = f"[{user} | PID: {pid}] "
        color = "black" # اللون الافتراضي

        if success: # status_code == 200
            # تحليل أكثر تفصيلاً للنص لتحديد النجاح الفعلي
            if "نجاح" in response_text or "success" in response_text.lower() or "تم الحجز" in response_text:
                 result_message += "نجاح! تم التثبيت."
                 color = "green"
            elif "خطأ" in response_text or "incorrect" in response_text.lower() or "failed" in response_text.lower() or "غير صحيح" in response_text:
                 result_message += "فشل: يبدو أن الحل كان خاطئًا أو أن العملية انتهت."
                 color = "orange" # استخدام برتقالي للحل الخاطئ
            else:
                 result_message += f"تم الإرسال (200)، الاستجابة: {response_text[:80]}..." # عرض جزء من الاستجابة غير المؤكدة
                 color = "blue" # استخدام أزرق للاستجابة غير المؤكدة
        elif status_code == 400:
              result_message += "فشل (400): الحل خاطئ أو الكابتشا انتهت صلاحيتها."
              color = "red"
        elif status_code in (401, 403):
             result_message += f"فشل ({status_code}): خطأ صلاحية."
             color = "red"
        elif status_code < 0: # للأخطاء الداخلية (مثل خطأ المعالجة أو الشبكة)
             result_message += f"خطأ ({status_code}): {response_text}"
             color = "red"
        else: # فشل آخر
              result_message += f"فشل ({status_code}): {response_text[:100]}..."
              color = "red"

        try:
            # --- إضافة أو تحديث ملصق النتيجة في الإطار ---
            result_label = None
            # البحث عن ملصق نتيجة موجود بالفعل في الإطار (لتجنب إضافة ملصقات متعددة)
            for widget in display_frame.winfo_children():
                if isinstance(widget, tk.Label) and hasattr(widget, '_is_result_label') and widget._is_result_label:
                    result_label = widget
                    break

            if result_label:
                # تحديث الملصق الموجود
                result_label.config(text=result_message, fg=color)
                print(f"[{user}] تم تحديث ملصق النتيجة في الإطار.")
            else:
                # إنشاء ملصق جديد إذا لم يتم العثور على واحد
                result_label = tk.Label(display_frame, text=result_message, fg=color, font=("Helvetica", 10), wraplength=display_frame.winfo_width() - 10) # wrap text
                result_label._is_result_label = True # إضافة علامة للملصق
                # وضعه في الأسفل داخل إطار الكابتشا
                result_label.pack(pady=(5, 5), fill=tk.X, side=tk.BOTTOM)
                print(f"[{user}] تم إنشاء ملصق نتيجة جديد في الإطار.")

        except tk.TclError as e:
            print(f"[{user}] خطأ TclError أثناء محاولة عرض نتيجة الإرسال في الإطار لـ PID {pid}: {e}")
        except Exception as e:
             print(f"[{user}] خطأ عام أثناء عرض نتيجة الإرسال في الإطار لـ PID {pid}: {e}")


    def clear_captcha_display(self, immediately=False, frame_to_clear=None):
         """مسح إطار عرض الكابتشا الحالي (إن وجد)."""

         # دالة المسح الفعلية
         def do_clear():
             target_frame = frame_to_clear # استخدام الإطار الممرر إذا وجد

             # إذا لم يتم تمرير إطار محدد، ابحث عن الإطار الحالي باستخدام المرجع أو العلامة
             if target_frame is None:
                 target_frame = self.current_captcha_frame # استخدام المرجع المباشر أولاً

             # إذا لم يكن المرجع موجودًا أو كان الإطار قد دُمّر، حاول البحث بالعلامة
             if target_frame is None or not target_frame.winfo_exists():
                 try:
                     if hasattr(self, 'accounts_frame') and self.accounts_frame.winfo_exists():
                         # البحث في العناصر التابعة لإطار الحسابات الرئيسي
                         for widget in self.accounts_frame.winfo_children():
                             # التحقق من وجود العلامة وأن العنصر هو إطار
                             if isinstance(widget, tk.Frame) and hasattr(widget, '_is_captcha_frame') and widget._is_captcha_frame:
                                 target_frame = widget
                                 print("تم العثور على إطار الكابتشا بواسطة العلامة.")
                                 break
                 except tk.TclError:
                     # قد يحدث هذا إذا تم إغلاق النافذة الرئيسية أثناء البحث
                     print("خطأ TclError أثناء البحث عن إطار الكابتشا لمسحه.")
                     target_frame = None
                 except Exception as e:
                      print(f"خطأ غير متوقع أثناء البحث عن إطار الكابتشا لمسحه: {e}")
                      target_frame = None


             # إذا تم العثور على إطار صالح وموجود، قم بتدميره
             if target_frame and target_frame.winfo_exists():
                 try:
                     target_frame.destroy()
                     print("تم مسح إطار عرض الكابتشا.")
                     # إذا كان هذا هو الإطار الحالي المخزن، قم بمسح المرجع أيضًا
                     if target_frame == self.current_captcha_frame:
                         self.current_captcha_frame = None
                 except tk.TclError:
                     print("خطأ TclError أثناء تدمير إطار الكابتشا (ربما تم تدميره بالفعل).")
                 except Exception as e:
                      print(f"خطأ غير متوقع أثناء تدمير إطار الكابتشا: {e}")
             # else:
                 # print("لم يتم العثور على إطار كابتشا لمسحه أو أنه غير موجود.")

         if immediately:
             do_clear()
         else:
             self.root.after(4000, do_clear)


# --- نقطة انطلاق البرنامج ---
if __name__ == "__main__":
    try:
        requests.packages.urllib3.disable_warnings() # تعطيل تحذيرات SSL مرة أخرى (احتياطي)

        root = tk.Tk() # إنشاء النافذة الرئيسية
        # يمكنك تحديد حجم أولي للنافذة إذا أردت
        # root.geometry("600x500")
        app = CaptchaApp(root) # إنشاء نسخة من التطبيق

        # التحقق مما إذا كان التحميل الأولي فشل (مثلاً، ملف النموذج غير موجود)
        # إذا فشل، app.__init__ سيقوم باستدعاء root.quit() ولن نصل إلى mainloop
        # نحتاج طريقة للتحقق من ذلك قبل استدعاء mainloop
        # يمكن إضافة متغير حالة في init أو التحقق من وجود self.session
        if hasattr(app, 'session') and app.session is not None :
            root.mainloop() # تشغيل حلقة الأحداث الرئيسية لـ Tkinter
        else:
             print("فشل تهيئة التطبيق، الخروج...")
             # تأكد من أن النافذة (إذا تم إنشاؤها جزئيًا) يتم تدميرها
             if root.winfo_exists():
                 root.destroy()

    except ImportError as e:
         print(f"خطأ: لم يتم العثور على مكتبة مطلوبة: {e.name}")
         print("يرجى التأكد من تثبيت جميع المكتبات المطلوبة:")
         print("pip install requests Pillow numpy opencv-python onnxruntime torchvision") # أضفنا torchvision للمعالجة
    except Exception as e:
        print("\n--- حدث خطأ غير متوقع في المستوى الأعلى ---")
        import traceback
        print(traceback.format_exc())
        print("--- نهاية تتبع الخطأ ---")
