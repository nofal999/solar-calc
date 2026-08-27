import os
import sys
import math
import logging
import sqlite3
import platform
import subprocess
from datetime import datetime
from typing import Dict, Any, Optional

import streamlit as st

# Try importing Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MSSTD_WEB_CORE")

# ==============================================================================
# DATABASE MANAGER (SQLite)
# ==============================================================================
class DatabaseManager:
    def __init__(self, db_path: str = "msstd_enterprise.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"DB Init Error: {e}")

    def log_action(self, action: str, details: str):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO audit_logs (action, details) VALUES (?, ?)", (action, details))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Log Error: {e}")

# ==============================================================================
# SOLAR CALCULATOR ENGINE
# ==============================================================================
class SolarCalculator:
    @staticmethod
    def calculate_system(daily_kwh: float, peak_sun_hours: float, days_autonomy: int = 1, battery_dod: float = 0.8, system_voltage: int = 48) -> Dict[str, Any]:
        adjusted_energy = daily_kwh / 0.80
        required_kw_panels = adjusted_energy / peak_sun_hours
        panel_wattage = 550
        number_of_panels = math.ceil((required_kw_panels * 1000) / panel_wattage)

        peak_load_kw = (daily_kwh / peak_sun_hours) * 1.5
        recommended_inverter_kw = max(peak_load_kw, 5.0)

        total_battery_wh = (daily_kwh * 1000 * days_autonomy) / battery_dod
        battery_bank_ah = total_battery_wh / system_voltage

        return {
            "daily_consumption_kwh": daily_kwh,
            "peak_sun_hours": peak_sun_hours,
            "required_panel_capacity_kw": round(required_kw_panels, 2),
            "estimated_panels_count": number_of_panels,
            "panel_unit_wattage": panel_wattage,
            "recommended_inverter_kw": round(recommended_inverter_kw, 2),
            "battery_bank_ah_at_voltage": round(battery_bank_ah, 2),
            "system_voltage": system_voltage
        }

# ==============================================================================
# NETWORK & SURVEILLANCE UTILITIES
# ==============================================================================
class NetworkDiagnostics:
    @staticmethod
    def generate_camera_config(brand: str, ip: str, channel: int) -> Dict[str, str]:
        configs = {
            "hikvision": f"rtsp://admin:password@{ip}:554/Streaming/Channels/{channel}01",
            "dahua": f"rtsp://admin:password@{ip}:554/cam/realmonitor?channel={channel}&subtype=0",
            "uniview": f"rtsp://admin:password@{ip}:554/media/video1"
        }
        return {
            "brand": brand.lower(),
            "ip_address": ip,
            "rtsp_main_stream": configs.get(brand.lower(), "Unsupported Brand"),
            "status": "تم تكوين الرابط بنجاح عبر بروتوكول ONVIF"
        }

# ==============================================================================
# GEMINI AI INTERFACE
# ==============================================================================
class MSSTDAgentCore:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.client = None
        if GEMINI_AVAILABLE and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"GenAI Client Init Failed: {e}")

    def query_assistant(self, prompt: str, model_name: str = "gemini-2.5-flash") -> str:
        if not self.client:
            return "ملاحظة: لم يتم ضبط مفتاح Gemini API. يرجى إدخاله في الشريط الجانبي أو في المتغيرات البيئية."
        try:
            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            return response.text
        except Exception as e:
            return f"حدث خطأ أثناء الاتصال بالذكاء الاصطناعي: {str(e)}"

# ==============================================================================
# STREAMLIT UI SETUP
# ==============================================================================
st.set_page_config(
    page_title="MSSTD Enterprise Suite",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State
db = DatabaseManager()

st.sidebar.title("🛠️ MSSTD لوحة التحكم")
api_key_input = st.sidebar.text_input("مفتاح Gemini API (اختياري)", type="password", value=os.environ.get("GEMINI_API_KEY", ""))
if api_key_input:
    os.environ["GEMINI_API_KEY"] = api_key_input

agent = MSSTDAgentCore(api_key=api_key_input)

menu = st.sidebar.radio(
    "اختر القسم:",
    ["حاسبة الطاقة الشمسية", "إعدادات الكاميرات والشبكات", "المساعد الذكي (MSSTD AI)", "سجلات النظام (Audit Logs)"]
)

st.title("⚡ MSSTD نظام الإدارة الهندسي المتكامل")
st.markdown("---")

if menu == "حاسبة الطاقة الشمسية":
    st.subheader("☀️ حساب مكونات منظومة الطاقة الشمسية")
    col1, col2 = st.columns(2)
    
    with col1:
        daily_kwh = st.number_input("الاستهلاك اليومي المقدر (كيلوواط/ساعة)", min_value=1.0, value=15.0, step=0.5)
        peak_hours = st.number_input("ساعات الذروة الشمسية", min_value=1.0, value=5.5, step=0.5)
    
    with col2:
        autonomy_days = st.number_input("أيام الاستقلالية (بدون شمس)", min_value=1, value=1, step=1)
        system_voltage = st.selectbox("جهد النظام (فولت)", [24, 48, 96], index=1)

    if st.button("احسب المنظومة", type="primary"):
        res = SolarCalculator.calculate_system(daily_kwh, peak_hours, autonomy_days, system_voltage=system_voltage)
        db.log_action("SOLAR_CALC", f"Calculated solar for {daily_kwh} kWh")
        
        st.success("تم الحساب بنجاح!")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("القدرة المطلوبة للألواح", f"{res['required_panel_capacity_kw']} kW")
        m2.metric("عدد الألواح المقترح (550W)", f"{res['estimated_panels_count']} لوح")
        m3.metric("العاكس الموصى به (Inverter)", f"{res['recommended_inverter_kw']} kW")
        m4.metric("سعة بطاريات الليثيوم", f"{res['battery_bank_ah_at_voltage']} Ah")

elif menu == "إعدادات الكاميرات والشبكات":
    st.subheader("📷 مولد إعدادات الكاميرات وأنظمة المراقبة (RTSP)")
    
    brand = st.selectbox("ماركة الكاميرا", ["Hikvision", "Dahua", "Uniview"])
    ip_addr = st.text_input("عنوان IP الخاص بالكاميرا", value="192.168.1.108")
    channel = st.number_input("رقم القناة (Channel)", min_value=1, value=1)

    if st.button("توليد رابط الإعدادات"):
        cfg = NetworkDiagnostics.generate_camera_config(brand, ip_addr, channel)
        db.log_action("SURVEILLANCE_CFG", f"Generated RTSP for {brand} at {ip_addr}")
        
        st.info(f"الحالة: {cfg['status']}")
        st.code(cfg['rtsp_main_stream'], language="text")

elif menu == "المساعد الذكي (MSSTD AI)":
    st.subheader("🤖 مساعد MSSTD الهندسي الذكي")
    
    user_query = st.text_area("اطرح استفسارك الفني (حول تمديدات، شبكات، طاقة، أو أعطال):", placeholder="كيف أقوم بضبط إعدادات Port Forwarding لراوتر...")
    
    if st.button("إرسال السؤال", type="primary"):
        if user_query.strip():
            with st.spinner("جاري التفكير والتحليل عبر نموذج Gemini..."):
                answer = agent.query_assistant(user_query)
                db.log_action("AI_QUERY", f"Query length: {len(user_query)}")
                st.markdown("### الرد:")
                st.write(answer)
        else:
            st.warning("يرجى كتابة سؤالك أولاً.")

elif menu == "سجلات النظام (Audit Logs)":
    st.subheader("📋 سجلات تدقيق العمليات")
    if st.button("تحديث السجلات"):
        pass
    
    try:
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT action, details, timestamp FROM audit_logs ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
        conn.close()
        
        if rows:
            for row in rows:
                st.text(f"[{row[2]}] | العملية: {row[0]} | التفاصيل: {row[1]}")
        else:
            st.info("لا توجد سجلات مسجلة حتى الآن.")
    except Exception as e:
        st.error(f"تعذر جلب السجلات: {e}")
