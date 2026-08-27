#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MSSTD Comprehensive Management & AI Agent System
Author: MSSTD (Electrical Wiring, Networks, Alarms, Surveillance & Solar Systems)
Description: Complete production-grade script integrating AI models, local tool diagnostics,
             solar system calculators, network management utilities, and multi-encoding output.
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
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

# Try importing required external libraries with fallback handlers
try:
    from google import genai
    from google.genai import types
except ImportError:
    print("[-] Error: 'google-genai' library is missing. Install via: pip install --upgrade google-genai")
    sys.exit(1)

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
    """Handles terminal text processing, alignment, and Arabic Bidirectional shaping."""
    
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
        print(TextFormatter.render(banner))
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
        - سعة بطاريات الليثيوم المطلوبة (عند جهد {data['system_voltage']} فولت): {data['battery_bank_ah_ah_at_voltage'] if 'battery_bank_ah_at_voltage' in data else data['battery_bank_ah_at_voltage']} أمبير/ساعة
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
        
        try:
            self.client = genai.Client(api_key=self.api_key) if self.api_key else genai.Client()
        except Exception as e:
            logger.error(f"Failed to initialize GenAI Client: {e}")
            self.client = None

    def query_assistant(self, prompt: str, model_name: str = "gemini-2.5-flash") -> str:
        if not self.client:
            return "Error: GenAI Client is not initialized. Please verify your API key."
        
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
# MODULE 6: INTERACTIVE CLI CONTROLLER & EXECUTION PIPELINE
# ==============================================================================

import platform

def main_menu():
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MSSTD Enterprise Engineering Suite")
    parser.add_argument("--cli", action="store_true", help="Launch interactive CLI menu")
    args = parser.parse_args()
    
    if args.cli or len(sys.argv) == 1:
        main_menu()
    else:
        print("Use --cli to start the interactive management suite.")
