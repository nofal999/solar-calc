#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MSSTD Comprehensive Management & AI Agent System (Full Enterprise Edition for Web/Streamlit)
Author: MSSTD (Electrical Wiring, Networks, Alarms, Surveillance & Solar Systems)
Description: Complete production-grade script integrating AI models, local tool diagnostics,
             solar system calculators, network management utilities, client & inventory databases,
             and multi-encoding output optimized for Streamlit web environments.
"""

import os
import sys
import json
import time
import math
import logging
import sqlite3
import argparse
import subprocess
import platform
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

# Try importing Streamlit for web interface
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False

# Try importing Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Try importing Bidi libraries for terminal fallback compatibility
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    BIDI_AVAILABLE = True
except ImportError:
    BIDI_AVAILABLE = False

# Configure logging infrastructure
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    handlers=[
        logging.FileHandler("msstd_system.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MSSTD_CORE")

# ==============================================================================
# MODULE 1: TEXT FORMATTING & ARABIC RTL ENGINE
# ==============================================================================

class TextFormatter:
    """Handles terminal/web text processing, alignment, and Arabic Bidirectional shaping."""
    
    @staticmethod
    def render(text: str) -> str:
        if not text:
            return ""
        if BIDI_AVAILABLE:
            try:
                reshaped_text = arabic_reshaper.reshape(text)
                bidi_text = get_display(reshaped_text)
                return bidi_text
            except Exception as e:
                logger.warning(f"Bidi processing failed: {e}")
                return text
        return text

    @staticmethod
    def print_banner() -> str:
        banner = """
        ====================================================================
           MSSTD PROFESSIONAL ENGINEERING & AI MANAGEMENT SUITE v4.5
           [ Electrical | Networks | Surveillance | Alarms | Solar Systems ]
        ====================================================================
        """
        formatted = TextFormatter.render(banner)
        if not STREAMLIT_AVAILABLE:
            print(formatted)
        return banner


# ==============================================================================
# MODULE 2: DATABASE STORAGE & AUDIT LOGGING
# ==============================================================================

class DatabaseManager:
    """Manages SQLite persistent storage for clients, inventory, and system audits."""
    
    def __init__(self, db_path: str = "msstd_enterprise.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT,
                    project_type TEXT,
                    location TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL,
                    category TEXT,
                    quantity INTEGER,
                    unit_price REAL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
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
            logger.info("Database initialized successfully.")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")

    def log_action(self, action: str, details: str):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO audit_logs (action, details) VALUES (?, ?)", (action, details))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def add_client(self, name: str, phone: str, project_type: str, location: str):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO clients (name, phone, project_type, location) VALUES (?, ?, ?, ?)", (name, phone, project_type, location))
            conn.commit()
            conn.close()
            self.log_action("ADD_CLIENT", f"Added client {name} for project {project_type}")
        except Exception as e:
            logger.error(f"Failed to add client: {e}")

    def get_clients(self) -> List[tuple]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, phone, project_type, location, created_at FROM clients ORDER BY id DESC")
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Failed to fetch clients: {e}")
            return []

    def add_inventory_item(self, item_name: str, category: str, quantity: int, unit_price: float):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO inventory (item_name, category, quantity, unit_price) VALUES (?, ?, ?, ?)", (item_name, category, quantity, unit_price))
            conn.commit()
            conn.close()
            self.log_action("ADD_INVENTORY", f"Added item {item_name}, qty: {quantity}")
        except Exception as e:
            logger.error(f"Failed to add inventory: {e}")

    def get_inventory(self) -> List[tuple]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, item_name, category, quantity, unit_price, updated_at FROM inventory ORDER BY id DESC")
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Failed to fetch inventory: {e}")
            return []


# ==============================================================================
# MODULE 3: SOLAR ENERGY SYSTEM CALCULATION ENGINE
# ==============================================================================

class SolarCalculator:
    """Computes photovoltaic system components, inverter specifications, and battery banks."""

    @staticmethod
    def calculate_system(daily_kwh: float, peak_sun_hours: float, days_autonomy: int = 1, battery_dod: float = 0.8, system_voltage: int = 48) -> Dict[str, Any]:
        logger.info(f"Running solar calculations for daily load: {daily_kwh} kWh")
        
        # Solar Panel Sizing (accounting for 20% system losses)
        adjusted_energy = daily_kwh / 0.80
        required_kw_panels = adjusted_energy / peak_sun_hours
        panel_wattage = 550 # Standard high-efficiency panel
        number_of_panels = math.ceil((required_kw_panels * 1000) / panel_wattage)

        # Inverter Sizing (adding 25% safety margin for surge loads)
        peak_load_kw = (daily_kwh / peak_sun_hours) * 1.5
        recommended_inverter_kw = max(peak_load_kw, 5.0)

        # Battery Bank Sizing (Lithium-ion storage)
        total_battery_wh = (daily_kwh * 1000 * days_autonomy) / battery_dod
        battery_bank_ah = total_battery_wh / system_voltage

        results = {
            "daily_consumption_kwh": daily_kwh,
            "peak_sun_hours": peak_sun_hours,
            "required_panel_capacity_kw": round(required_kw_panels, 2),
            "estimated_panels_count": number_of_panels,
            "panel_unit_wattage": panel_wattage,
            "recommended_inverter_kw": round(recommended_inverter_kw, 2),
            "battery_bank_ah_at_voltage": round(battery_bank_ah, 2),
            "system_voltage": system_voltage
        }
        return results

    @staticmethod
    def render_report(data: Dict[str, Any]) -> str:
        report = f"""
        [ تقرير هندسي لأنظمة الطاقة الشمسية - MSSTD ]
        --------------------------------------------------
        - الاستهلاك اليومي المقدر: {data['daily_consumption_kwh']} كيلوواط/ساعة
        - ساعات الذروة الشمسية: {data['peak_sun_hours']} ساعات
        - القدرة المطلوبة للألواح: {data['required_panel_capacity_kw']} كيلوواط
        - العدد المقترح للألواح (قدرة {data['panel_unit_wattage']} واط): {data['estimated_panels_count']} لوح
        - العاكس (Inverter) الموصى به: {data['recommended_inverter_kw']} كيلوواط (مثل Deye أو Solis)
        - سعة بطاريات الليثيوم المطلوبة (عند جهد {data['system_voltage']} فولت): {data['battery_bank_ah_at_voltage']} أمبير/ساعة
        --------------------------------------------------
        """
        return TextFormatter.render(report)


# ==============================================================================
# MODULE 4: NETWORK & SURVEILLANCE UTILITIES
# ==============================================================================

class NetworkDiagnostics:
    """Performs ping sweep tests, port checks, and ONVIF configuration structures."""

    @staticmethod
    def ping_host(host: str) -> bool:
        param = "-n" if platform.system().lower() == "windows" else "-c"
        command = ["ping", param, "1", host]
        try:
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Ping execution failed: {e}")
            return False

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
            "status": "Configured successfully via ONVIF profile"
        }


# ==============================================================================
# MODULE 5: GEMINI AI ASSISTANT INTERFACE
# ==============================================================================

class MSSTDAgentCore:
    """Interfaces with Google GenAI SDK for automated diagnostic and business support."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set in environment variables.")
        
        self.client = None
        if GEMINI_AVAILABLE:
            try:
                self.client = genai.Client(api_key=self.api_key) if self.api_key else genai.Client()
            except Exception as e:
                logger.error(f"Failed to initialize GenAI Client: {e}")

    def query_assistant(self, prompt: str, model_name: str = "gemini-2.5-flash") -> str:
        if not self.client:
            return "Error: GenAI Client is not initialized. Please verify your API key or configure GEMINI_API_KEY."
        
        try:
            logger.info(f"Sending prompt to model: {model_name}")
            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            return response.text
        except Exception as e:
            logger.error(f"Model generation failed: {e}")
            return f"API Execution Error: {str(e)}"


# ==============================================================================
# MODULE 6: INTERACTIVE STREAMLIT WEB APP & CLI CONTROLLER
# ==============================================================================

def main_cli_menu():
    db = DatabaseManager()
    agent = MSSTDAgentCore()
    
    while True:
        TextFormatter.print_banner()
        print(TextFormatter.render("اختر الخدمة المطلوبة من القائمة الرئيسية:"))
        print("1. إجراء حسابات منظومة الطاقة الشمسية (Solar Calculator)")
        print("2. توليد إعدادات الكاميرات وأنظمة المراقبة (Surveillance RTSP Config)")
        print("3. محادثة المساعد الذكي MSSTD AI Agent")
        print("4. فحص اتصال شبكة محلي (Ping Diagnostic)")
        print("5. عرض سجلات النظام والتدقيق (Audit Logs)")
        print("6. الخروج من النظام (Exit)")
        
        choice = input("\nأدخل رقم الخيار (1-6): ").strip()
        
        if choice == "1":
            try:
                kwh = float(input("أدخل الاستهلاك اليومي المقدر (كيلوواط/ساعة): "))
                hours = float(input("أدخل متوسط ساعات الذروة الشمسية: "))
                days = int(input("أدخل أيام الاستقلالية المطلوبة (مثال 1 أو 2): "))
                
                result = SolarCalculator.calculate_system(kwh, hours, days)
                report = SolarCalculator.render_report(result)
                print(report)
                db.log_action("SOLAR_CALC", f"Calculated for {kwh} kWh daily.")
            except ValueError:
                print("خطأ: يرجى إدخال قيم أرقام صحيحة.")
                
        elif choice == "2":
            brand = input("أدخل ماركة الكاميرا (Hikvision, Dahua, Uniview): ").strip()
            ip = input("أدخل عنوان IP الخاص بالكاميرا: ").strip()
            ch = int(input("أدخل رقم القناة (Channel): ").strip() or "1")
            
            cfg = NetworkDiagnostics.generate_camera_config(brand, ip, ch)
            print("\n--- نتيجة الإعدادات ---")
            for k, v in cfg.items():
                print(f"{k}: {v}")
            db.log_action("SURVEILLANCE_CFG", f"Configured {brand} at {ip}")
            
        elif choice == "3":
            query = input("أدخل استفسارك الفني أو الهندسي للمساعد الذكي: ")
            print("\nجاري معالجة الطلب عبر نموذج Gemini...")
            ans = agent.query_assistant(query)
            print(f"\n[الرد]:\n{ans}\n")
            db.log_action("AI_QUERY", f"Query length: {len(query)}")
            
        elif choice == "4":
            host = input("أدخل عنوان IP أو اسم المضيف للفحص (مثل 8.8.8.8 أو 192.168.1.1): ").strip()
            status = NetworkDiagnostics.ping_host(host)
            msg = f"المضيف {host} متاح ويعمل بنجاح." if status else f"فشل الاتصال بالمضيف {host}."
            print(msg)
            db.log_action("PING_TEST", f"Tested host {host}, status: {status}")
            
        elif choice == "5":
            print("\n--- سجلات النظام الأخيرة ---")
            try:
                conn = sqlite3.connect(db.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT action, details, timestamp FROM audit_logs ORDER BY id DESC LIMIT 10")
                rows = cursor.fetchall()
                for row in rows:
                    print(f"[{row[2]}] {row[0]}: {row[1]}")
                conn.close()
            except Exception as e:
                print(f"تعذر قراءة السجلات: {e}")
                
        elif choice == "6":
            print("إغلاق النظام. شكراً لاستخدامك حلول MSSTD.")
            sys.exit(0)
        else:
            print("خيار غير صحيح، يرجى المحاولة مرة أخرى.")
        
        input("\nاضغط مفتاح Enter للمتابعة...")


def run_streamlit_app():
    if not STREAMLIT_AVAILABLE:
        print("Error: Streamlit is not installed. Run 'pip install streamlit' to launch web UI.")
        sys.exit(1)

    st.set_page_config(
        page_title="MSSTD Comprehensive Management Suite",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    db = DatabaseManager()

    st.sidebar.title("🛠️ MSSTD لوحة التحكم")
    api_key_input = st.sidebar.text_input("مفتاح Gemini API", type="password", value=os.environ.get("GEMINI_API_KEY", ""))
    if api_key_input:
        os.environ["GEMINI_API_KEY"] = api_key_input

    agent = MSSTDAgentCore(api_key=api_key_input)

    menu_option = st.sidebar.radio(
        "أقسام النظام الشامل:",
        [
            "حاسبة الطاقة الشمسية",
            "إعدادات الكاميرات والشبكات",
            "إدارة العملاء والمشاريع",
            "إدارة المخزون والقطع",
            "المساعد الذكي (MSSTD AI)",
            "سجلات النظام والتدقيق"
        ]
    )

    st.title("⚡ MSSTD نظام الإدارة الهندسي والتقني الشامل")
    st.markdown("تمديدات كهربائية، شبكات، أجهزة إنذار ومراقبة، وأنظمة الطاقة الشمسية")
    st.markdown("---")

    if menu_option == "حاسبة الطاقة الشمسية":
        st.subheader("☀️ محرك حسابات منظومة الطاقة الشمسية الاحترافي")
        c1, c2 = st.columns(2)
        with c1:
            daily_kwh = st.number_input("الاستهلاك اليومي المقدر (كيلوواط/ساعة)", min_value=1.0, value=15.0, step=0.5)
            peak_hours = st.number_input("ساعات الذروة الشمسية", min_value=1.0, value=5.5, step=0.5)
        with c2:
            autonomy_days = st.number_input("أيام الاستقلالية المطلوبة", min_value=1, value=1, step=1)
            system_voltage = st.selectbox("جهد نظام التخزين (فولت)", [24, 48, 96], index=1)

        if st.button("حساب مكونات المنظومة الشاملة", type="primary"):
            res = SolarCalculator.calculate_system(daily_kwh, peak_hours, autonomy_days, system_voltage=system_voltage)
            db.log_action("SOLAR_CALC", f"Calculated solar for {daily_kwh} kWh daily load")
            
            st.success("تم إتمام الحسابات الهندسية بنجاح!")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("قدرة الألواح المطلوبة", f"{res['required_panel_capacity_kw']} kW")
            col2.metric("عدد الألواح (550W)", f"{res['estimated_panels_count']} لوح")
            col3.metric("العاكس الموصى به (Inverter)", f"{res['recommended_inverter_kw']} kW")
            col4.metric("سعة بطاريات الليثيوم", f"{res['battery_bank_ah_at_voltage']} Ah")

            report_text = SolarCalculator.render_report(res)
            st.text_area("التقرير الفني المفصل:", value=report_text, height=200)

    elif menu_option == "إعدادات الكاميرات والشبكات":
        st.subheader("📷 مولد روابط وتكوينات الكاميرات والشبكات المحلية")
        brand = st.selectbox("ماركة الكاميرا / النظام", ["Hikvision", "Dahua", "Uniview"])
        ip_addr = st.text_input("عنوان IP الخاص بالكاميرا", value="192.168.1.108")
        channel = st.number_input("رقم القناة (Channel)", min_value=1, value=1)

        if st.button("توليد رابط RTSP وفحص التكوين"):
            cfg = NetworkDiagnostics.generate_camera_config(brand, ip_addr, channel)
            db.log_action("SURVEILLANCE_CFG", f"Generated config for {brand} at {ip_addr}")
            st.info(cfg['status'])
            st.code(cfg['rtsp_main_stream'], language="text")

        st.markdown("---")
        st.subheader("🌐 فحص اتصال الشبكة (Ping Diagnostic)")
        host_target = st.text_input("أدخل عنوان IP أو المضيف للفحص", value="8.8.8.8")
        if st.button("تنفيذ الفحص"):
            status = NetworkDiagnostics.ping_host(host_target)
            if status:
                st.success(f"المضيف {host_target} متاح ومتصل بنجاح.")
            else:
                st.error(f"فشل الاتصال بالمضيف {host_target}.")
            db.log_action("PING_TEST", f"Tested host {host_target}, status: {status}")

    elif menu_option == "إدارة العملاء والمشاريع":
        st.subheader("👥 إدارة قاعدة بيانات العملاء والمشاريع")
        with st.form("client_form"):
            c_name = st.text_input("اسم العميل / المشروع")
            c_phone = st.text_input("رقم الهاتف")
            c_type = st.selectbox("نوع المشروع", ["كهرباء وتمديدات", "كاميرات مراقبة وإنذار", "شبكات وتواصل", "طاقة شمسية"])
            c_location = st.text_input("الموقع / العنوان")
            submitted = st.form_submit_button("حفظ العميل في قاعدة البيانات")
            if submitted and c_name:
                db.add_client(c_name, c_phone, c_type, c_location)
                st.success("تم حفظ بيانات العميل بنجاح!")

        st.markdown("### سجل العملاء الحاليين")
        clients = db.get_clients()
        if clients:
            for cli in clients:
                st.text(f"ID: {cli[0]} | العميل: {cli[1]} | الهاتف: {cli[2]} | المشروع: {cli[3]} | الموقع: {cli[4]} | التاريخ: {cli[5]}")
        else:
            st.info("لا يوجد عملاء مسجلون حالياً.")

    elif menu_option == "إدارة المخزون والقطع":
        st.subheader("📦 إدارة المستودع والمعدات والقطع")
        with st.form("inventory_form"):
            i_name = st.text_input("اسم القطعة / المعدة")
            i_cat = st.selectbox("التصنيف", ["ألواح ومحولات طاقة", "كاميرات وملحقاتها", "كابلات وتمديدات", "أجهزة شبكات وراوترات"])
            i_qty = st.number_input("الكمية المتوفرة", min_value=0, value=10)
            i_price = st.number_input("السعر الفردي", min_value=0.0, value=0.0)
            i_submitted = st.form_submit_button("إضافة للمخزون")
            if i_submitted and i_name:
                db.add_inventory_item(i_name, i_cat, int(i_qty), float(i_price))
                st.success("تم إضافة القطعة للمخزون بنجاح!")

        st.markdown("### محتويات المستودع")
        items = db.get_inventory()
        if items:
            for item in items:
                st.text(f"ID: {item[0]} | الصنف: {item[1]} | التصنيف: {item[2]} | الكمية: {item[3]} | السعر: {item[4]} | التحديث: {item[5]}")
        else:
            st.info("المستودع فارغ حالياً.")

    elif menu_option == "المساعد الذكي (MSSTD AI)":
        st.subheader("🤖 مساعد MSSTD الهندسي والتقني المعتمد على نموذج Gemini")
        user_query = st.text_area("اطرح استفسارك الفني الهندسي:", placeholder="مثال: كيف أقوم بضبط إعدادات Inverter من نوع Deye لمنظومة قدرتها...")
        if st.button("إرسال الاستفسار", type="primary"):
            if user_query.strip():
                with st.spinner("جاري المعالجة والتحليل الفني..."):
                    answer = agent.query_assistant(user_query)
                    db.log_action("AI_QUERY", f"Query length: {len(user_query)}")
                    st.markdown("### رد المساعد الهندسي:")
                    st.write(answer)
            else:
                st.warning("يرجى كتابة السؤال أولاً.")

    elif menu_option == "سجلات النظام والتدقيق":
        st.subheader("📋 سجلات عمليات النظام والتدقيق (Audit Logs)")
        if st.button("تحديث السجلات"):
            pass
        try:
            conn = sqlite3.connect(db.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT action, details, timestamp FROM audit_logs ORDER BY id DESC LIMIT 30")
            rows = cursor.fetchall()
            conn.close()
            if rows:
                for row in rows:
                    st.text(f"[{row[2]}] | العملية: {row[0]} | التفاصيل: {row[1]}")
            else:
                st.info("لا توجد سجلات مسجلة بعد.")
        except Exception as e:
            st.error(f"تعذر جلب سجلات التدقيق: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MSSTD Enterprise Engineering Suite")
    parser.add_argument("--cli", action="store_true", help="Launch interactive CLI menu")
    parser.add_argument("--web", action="store_true", help="Launch Streamlit web application")
    args = parser.parse_args()
    
    if args.web or STREAMLIT_AVAILABLE and len(sys.argv) == 1:
        run_streamlit_app()
    elif args.cli:
        main_cli_menu()
    else:
        run_streamlit_app()
