import json
import math
import time

import streamlit as st
from PIL import Image

# Gemini اختياري؛ الوضع اليدوي لا يحتاج API Key
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False


# ============================================================
# 1. إعداد الصفحة
# ============================================================

st.set_page_config(
    page_title="Solar PV Design & Verification Tool",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# 2. CSS / RTL
# ============================================================

st.markdown(
    """
    <style>
    [data-testid="stMainBlockContainer"],
    [data-testid="stSidebarContent"] {
        direction: rtl;
        text-align: right;
        font-family: "Segoe UI", Tahoma, Arial, sans-serif;
    }

    div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stMarkdownContainer"] h1,
    div[data-testid="stMarkdownContainer"] h2,
    div[data-testid="stMarkdownContainer"] h3,
    div[data-testid="stMarkdownContainer"] h4,
    div[data-testid="stMarkdownContainer"] li {
        direction: rtl !important;
        text-align: right !important;
    }

    .stButton > button {
        width: 100%;
        font-weight: bold;
    }

    .status-pass {
        padding: 10px;
        border-radius: 8px;
        font-weight: bold;
    }

    .small-note {
        font-size: 0.85rem;
        opacity: 0.8;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 3. العنوان
# ============================================================

st.title("☀️ Solar PV Design & Verification Tool")

st.caption(
    "أداة تصميم وفحص مبدئي لمنظومات الطاقة الشمسية: "
    "PV Array + MPPT + Inverter + Battery + Loads + Cables"
)


# ============================================================
# 4. الدوال العامة
# ============================================================

def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=1):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def fmt(value, unit="", decimals=2):
    if value is None:
        return "غير معروف"

    try:
        value = float(value)

        if value == 0:
            return "غير متوفر"

        return f"{value:.{decimals}f} {unit}".strip()

    except Exception:
        return str(value)


def status_icon(status):
    if status == "PASS":
        return "🟢 PASS"
    if status == "WARNING":
        return "🟡 WARNING"
    if status == "FAIL":
        return "🔴 FAIL"
    return "🔵 INFO"


def add_check(checks, name, status, value, message):
    checks.append(
        {
            "الفحص": name,
            "الحالة": status,
            "القيمة": value,
            "التفصيل": message,
        }
    )


# ============================================================
# 5. توافق جهد البطارية
# ============================================================

def battery_voltage_compatibility(inverter_voltage, battery_voltage):

    inverter_voltage = safe_float(inverter_voltage)
    battery_voltage = safe_float(battery_voltage)

    if inverter_voltage <= 0 or battery_voltage <= 0:
        return (
            "WARNING",
            "لا توجد بيانات كافية للحكم على توافق جهد البطارية."
        )

    # 12V
    if 10 <= inverter_voltage <= 15 and 10 <= battery_voltage <= 15:
        return "PASS", "كلاهما ضمن فئة 12V."

    # 24V
    if 20 <= inverter_voltage <= 30 and 20 <= battery_voltage <= 30:
        return "PASS", "كلاهما ضمن فئة 24V."

    # 48/51.2V
    if 40 <= inverter_voltage <= 60 and 40 <= battery_voltage <= 60:
        return "PASS", "كلاهما ضمن فئة 48V/51.2V."

    # HV
    if inverter_voltage >= 100 and battery_voltage >= 100:
        if abs(inverter_voltage - battery_voltage) <= 50:
            return "WARNING", (
                "كلاهما ضمن فئة HV، لكن يجب مطابقة نطاق البطارية "
                "الفعلية مع Datasheet الإنفيرتر."
            )

    if abs(inverter_voltage - battery_voltage) <= 5:
        return "WARNING", "الجهد متقارب، لكن يجب التأكد من Datasheet."

    return "FAIL", (
        f"جهد الإنفيرتر {inverter_voltage}V لا يتطابق مع "
        f"جهد البطارية {battery_voltage}V."
    )


# ============================================================
# 6. هيكل Gemini
# ============================================================

JSON_STRUCTURE = """
{
  "panel": {
    "brand": "",
    "model": "",
    "part_number": "",
    "type": "",
    "pmax": 0,
    "voc": 0,
    "vmp": 0,
    "isc": 0,
    "imp": 0,
    "voc_temp_coeff_pct_per_c": 0
  },

  "inverter": {
    "brand": "",
    "model": "",
    "part_number": "",
    "type": "",
    "phase_type": "",
    "voltage_architecture": "",

    "ac_rated_power_w": 0,

    "v_max": 0,
    "v_mppt_min": 0,
    "v_mppt_max": 0,
    "v_start": 0,

    "mppt_count": 1,
    "strings_per_mppt": 1,
    "max_mppt_current": 0,

    "mppts": [],

    "battery": {
      "supported": false,
      "nominal_voltage_v": 0,
      "battery_type": "",
      "max_charge_current_a": 0,
      "max_discharge_current_a": 0
    },

    "ac_input_output": {
      "nominal_ac_voltage_v": "",
      "frequency_hz": "",
      "max_ac_input_current_a": 0,
      "max_ac_output_current_a": 0
    },

    "startup_surge": {
      "surge_power_va": 0,
      "duration_seconds": 0
    }
  },

  "external_battery": {
    "brand": "",
    "model": "",
    "chemistry": "",
    "capacity_ah": 0,
    "capacity_kwh": 0,
    "nominal_voltage_v": 0,
    "max_charge_current_a": 0,
    "max_discharge_current_a": 0
  }
}
"""


# ============================================================
# 7. Gemini - صورة
# ============================================================

def extract_from_images(panel_img, inverter_img, battery_img, api_key):

    if not GEMINI_AVAILABLE:
        raise RuntimeError(
            "google-genai غير مثبتة. استخدم pip install google-genai"
        )

    client = genai.Client(api_key=api_key)

    contents = []

    contents.append(panel_img)
    contents.append(inverter_img)

    if battery_img is not None:
        contents.append(battery_img)

    prompt = f"""
أنت مهندس تصميم أنظمة طاقة شمسية.

اقرأ الصور المرفقة واستخرج مواصفات:
1. Solar Panel
2. Inverter
3. External Battery إن وجدت

أعد JSON فقط.

الهيكل:
{JSON_STRUCTURE}

قواعد مهمة:
- لا تخمن القيم غير الظاهرة.
- القيمة الرقمية غير المعروفة = 0.
- يجب الحفاظ على الوحدات الصحيحة.
- حاول استخراج مواصفات كل MPPT إذا كانت موجودة في الملصق.
- إذا كان عدد MPPT غير واضح لا تخترع الرقم.
"""

    contents.append(prompt)

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )

    return json.loads(response.text)


# ============================================================
# 8. Gemini - بحث نصي
# ============================================================

def extract_from_text(panel_text, inverter_text, battery_text, api_key):

    if not GEMINI_AVAILABLE:
        raise RuntimeError(
            "google-genai غير مثبتة. استخدم pip install google-genai"
        )

    client = genai.Client(api_key=api_key)

    prompt = f"""
أنت مهندس طاقة شمسية متخصص في Datasheets.

ابحث/استخرج المواصفات المعروفة للموديلات التالية:

Solar Panel:
{panel_text}

Inverter:
{inverter_text}

Battery:
{battery_text if battery_text else "لا توجد بطارية"}

أعد JSON فقط وفق الهيكل التالي:

{JSON_STRUCTURE}

ممنوع اختراع المواصفات.
إذا لم تعرف القيمة استخدم 0.
"""


    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )

    return json.loads(response.text)


# ============================================================
# 9. الشريط الجانبي
# ============================================================

with st.sidebar:

    st.header("⚙️ إعدادات البرنامج")

    api_key = st.text_input(
        "Gemini API Key",
        type="password",
    )

    st.caption(
        "API Key مطلوب فقط عند استخدام الصور أو البحث النصي."
    )

    st.markdown("---")

    cold_factor = st.number_input(
        "Cold Voc Safety Factor",
        min_value=1.00,
        max_value=1.50,
        value=1.15,
        step=0.01,
        help="يمكن تغييره حسب دراسة درجة الحرارة ومعامل Voc.",
    )

    design_factor = st.number_input(
        "PV Current Safety Factor",
        min_value=1.00,
        max_value=1.50,
        value=1.25,
        step=0.01,
    )


# ============================================================
# 10. اختيار طريقة الإدخال
# ============================================================

mode = st.radio(
    "اختر طريقة العمل:",
    [
        "📸 إدخال عن طريق الصور",
        "🔎 إدخال عن طريق الشركة والموديل",
        "🧮 التصميم اليدوي الكامل",
    ],
    horizontal=False,
)


# ============================================================
# 11. المتغيرات
# ============================================================

result = None


# ============================================================
# 12. Manual Design
# ============================================================

if mode == "🧮 التصميم اليدوي الكامل":

    st.header("🧮 التصميم اليدوي الكامل")

    st.info(
        "هذا الوضع هو الأساس الحقيقي لأداة التصميم. "
        "لا يحتاج Gemini API."
    )

    # --------------------------------------------------------
    # Panel
    # --------------------------------------------------------

    st.subheader("☀️ Solar Panel")

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        pmax = st.number_input(
            "Pmax (W)",
            min_value=0.0,
            value=550.0,
            step=10.0,
        )

    with c2:
        voc = st.number_input(
            "Voc (V)",
            min_value=0.0,
            value=49.5,
            step=0.1,
        )

    with c3:
        vmp = st.number_input(
            "Vmp (V)",
            min_value=0.0,
            value=41.5,
            step=0.1,
        )

    with c4:
        isc = st.number_input(
            "Isc (A)",
            min_value=0.0,
            value=14.0,
            step=0.1,
        )

    with c5:
        imp = st.number_input(
            "Imp (A)",
            min_value=0.0,
            value=13.3,
            step=0.1,
        )

    c1, c2, c3 = st.columns(3)

    with c1:
        panel_brand = st.text_input(
            "الشركة",
            value="",
        )

    with c2:
        panel_model = st.text_input(
            "الموديل",
            value="",
        )

    with c3:
        voc_temp_coeff = st.number_input(
            "Voc Temperature Coefficient (%/°C)",
            value=-0.28,
            step=0.01,
            help="مثال -0.28 %/°C",
        )

    # --------------------------------------------------------
    # Inverter
    # --------------------------------------------------------

    st.subheader("⚡ Inverter")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        inverter_brand = st.text_input(
            "شركة الإنفيرتر",
            value="",
        )

    with c2:
        inverter_model = st.text_input(
            "موديل الإنفيرتر",
            value="",
        )

    with c3:
        inverter_type = st.selectbox(
            "نوع الإنفيرتر",
            [
                "Hybrid",
                "Off-Grid",
                "On-Grid",
            ],
        )

    with c4:
        phase = st.selectbox(
            "Phase",
            [
                "Single-Phase",
                "Three-Phase",
            ],
        )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        ac_power = st.number_input(
            "AC Rated Power (W)",
            min_value=0.0,
            value=5000.0,
            step=100.0,
        )

    with c2:
        dc_max = st.number_input(
            "Max DC Voltage (V)",
            min_value=0.0,
            value=500.0,
            step=10.0,
        )

    with c3:
        mppt_min = st.number_input(
            "MPPT Min Voltage (V)",
            min_value=0.0,
            value=150.0,
            step=5.0,
        )

    with c4:
        mppt_max = st.number_input(
            "MPPT Max Voltage (V)",
            min_value=0.0,
            value=425.0,
            step=5.0,
        )

    c1, c2, c3 = st.columns(3)

    with c1:
        start_voltage = st.number_input(
            "Start Voltage (V)",
            min_value=0.0,
            value=120.0,
            step=5.0,
        )

    with c2:
        inverter_mppt_global_current = st.number_input(
            "Global Max Current / MPPT (A)",
            min_value=0.0,
            value=13.0,
            step=0.5,
        )

    with c3:
        battery_arch = st.selectbox(
            "Battery Architecture",
            [
                "LV",
                "HV",
                "Unknown",
            ],
        )

    # --------------------------------------------------------
    # Dynamic MPPT
    # --------------------------------------------------------

    st.subheader("🔀 MPPT Configuration")

    mppt_count = st.number_input(
        "عدد MPPTs",
        min_value=1,
        max_value=32,
        value=3,
        step=1,
        help="يمكن أن يكون 1 أو 2 أو 3 أو 4 أو أكثر.",
    )

    manual_mppts = []

    for mppt_no in range(1, int(mppt_count) + 1):

        with st.expander(
            f"⚡ MPPT {mppt_no}",
            expanded=(mppt_no == 1),
        ):

            c1, c2, c3 = st.columns(3)

            with c1:
                number_strings = st.number_input(
                    f"عدد Strings — MPPT {mppt_no}",
                    min_value=1,
                    max_value=16,
                    value=1,
                    step=1,
                    key=f"mppt_strings_{mppt_no}",
                )

            with c2:
                current_limit = st.number_input(
                    f"Max Current — MPPT {mppt_no} (A)",
                    min_value=0.0,
                    value=0.0,
                    step=0.5,
                    key=f"mppt_current_{mppt_no}",
                    help="0 = استخدم الحد العام.",
                )

            with c3:
                voltage_limit = st.number_input(
                    f"Max Voltage — MPPT {mppt_no} (V)",
                    min_value=0.0,
                    value=0.0,
                    step=5.0,
                    key=f"mppt_voltage_{mppt_no}",
                    help="0 = استخدم Max DC Voltage.",
                )

            manual_mppts.append(
                {
                    "mppt": mppt_no,
                    "strings": int(number_strings),
                    "max_current": float(current_limit),
                    "max_voltage": float(voltage_limit),
                }
            )

    # --------------------------------------------------------
    # Site
    # --------------------------------------------------------

    st.subheader("🌍 Site & Solar Resource")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        peak_sun_hours = st.number_input(
            "Peak Sun Hours / day",
            min_value=0.1,
            value=5.0,
            step=0.1,
        )

    with c2:
        system_efficiency = st.number_input(
            "System Efficiency (%)",
            min_value=50.0,
            max_value=100.0,
            value=80.0,
            step=1.0,
        )

    with c3:
        min_temp = st.number_input(
            "Minimum Temperature °C",
            min_value=-50.0,
            max_value=50.0,
            value=-5.0,
            step=1.0,
        )

    with c4:
        max_temp = st.number_input(
            "Maximum Temperature °C",
            min_value=-20.0,
            max_value=80.0,
            value=45.0,
            step=1.0,
        )

    # --------------------------------------------------------
    # Loads
    # --------------------------------------------------------

    st.subheader("🏠 Electrical Loads")

    load_count = st.number_input(
        "عدد الأحمال",
        min_value=1,
        max_value=50,
        value=4,
        step=1,
    )

    loads = []

    for load_no in range(1, int(load_count) + 1):

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            load_name = st.text_input(
                f"الحمل {load_no}",
                value=f"Load {load_no}",
                key=f"load_name_{load_no}",
            )

        with c2:
            load_power = st.number_input(
                f"Power W",
                min_value=0.0,
                value=100.0,
                step=10.0,
                key=f"load_power_{load_no}",
            )

        with c3:
            load_qty = st.number_input(
                f"Quantity",
                min_value=1,
                value=1,
                step=1,
                key=f"load_qty_{load_no}",
            )

        with c4:
            load_hours = st.number_input(
                f"Hours/day",
                min_value=0.0,
                value=4.0,
                step=0.5,
                key=f"load_hours_{load_no}",
            )

        loads.append(
            {
                "name": load_name,
                "watts": load_power,
                "qty": load_qty,
                "hours": load_hours,
            }
        )

    # --------------------------------------------------------
    # Battery
    # --------------------------------------------------------

    st.subheader("🔋 Battery Bank")

    battery_enabled = st.checkbox(
        "تفعيل تصميم البطارية",
        value=True,
    )

    battery_voltage = 0.0
    battery_capacity_ah = 0.0
    battery_capacity_kwh = 0.0
    battery_dod = 80.0
    autonomy_days = 1.0
    battery_charge_current = 0.0
    battery_discharge_current = 0.0

    if battery_enabled:

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            battery_voltage = st.number_input(
                "Battery Nominal Voltage (V)",
                min_value=0.0,
                value=51.2,
                step=0.1,
            )

        with c2:
            battery_capacity_ah = st.number_input(
                "Battery Capacity (Ah)",
                min_value=0.0,
                value=200.0,
                step=10.0,
            )

        with c3:
            battery_capacity_kwh = st.number_input(
                "Battery Capacity (kWh)",
                min_value=0.0,
                value=0.0,
                step=0.1,
            )

        with c4:
            battery_dod = st.number_input(
                "DoD (%)",
                min_value=1.0,
                max_value=100.0,
                value=80.0,
                step=1.0,
            )

        c1, c2 = st.columns(2)

        with c1:
            autonomy_days = st.number_input(
                "Autonomy Days",
                min_value=0.1,
                value=1.0,
                step=0.1,
            )

        with c2:
            battery_discharge_current = st.number_input(
                "Max Discharge Current (A)",
                min_value=0.0,
                value=200.0,
                step=5.0,
            )

    # --------------------------------------------------------
    # Cable
    # --------------------------------------------------------

    st.subheader("🔌 DC Cable")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        cable_length = st.number_input(
            "One-way Cable Length (m)",
            min_value=0.0,
            value=20.0,
            step=1.0,
        )

    with c2:
        conductor = st.selectbox(
            "Conductor",
            ["Copper", "Aluminum"],
        )

    with c3:
        target_voltage_drop = st.number_input(
            "Maximum Voltage Drop (%)",
            min_value=0.1,
            max_value=5.0,
            value=2.0,
            step=0.1,
        )

    with c4:
        cable_temp = st.number_input(
            "Cable Ambient Temp °C",
            min_value=-40.0,
            max_value=80.0,
            value=35.0,
            step=1.0,
        )

    # --------------------------------------------------------
    # Build manual result
    # --------------------------------------------------------

    result = {
        "panel": {
            "brand": panel_brand,
            "model": panel_model,
            "type": "Manual",
            "pmax": pmax,
            "voc": voc,
            "vmp": vmp,
            "isc": isc,
            "imp": imp,
            "voc_temp_coeff_pct_per_c": voc_temp_coeff,
        },

        "inverter": {
            "brand": inverter_brand,
            "model": inverter_model,
            "type": inverter_type,
            "phase_type": phase,
            "voltage_architecture": battery_arch,
            "ac_rated_power_w": ac_power,
            "v_max": dc_max,
            "v_mppt_min": mppt_min,
            "v_mppt_max": mppt_max,
            "v_start": start_voltage,
            "mppt_count": int(mppt_count),
            "strings_per_mppt": max(
                [x["strings"] for x in manual_mppts]
            ),
            "max_mppt_current": inverter_mppt_global_current,
            "mppts": manual_mppts,
            "battery": {
                "supported": inverter_type != "On-Grid",
                "nominal_voltage_v": battery_voltage,
                "battery_type": battery_arch,
                "max_charge_current_a": 0,
                "max_discharge_current_a": 0,
            },
        },

        "external_battery": {
            "brand": "Manual",
            "model": "Manual Battery",
            "chemistry": "",
            "capacity_ah": battery_capacity_ah,
            "capacity_kwh": battery_capacity_kwh,
            "nominal_voltage_v": battery_voltage,
            "max_charge_current_a": battery_charge_current,
            "max_discharge_current_a": battery_discharge_current,
        },

        "loads": loads,

        "site": {
            "peak_sun_hours": peak_sun_hours,
            "system_efficiency_pct": system_efficiency,
            "min_temp": min_temp,
            "max_temp": max_temp,
            "battery_dod_pct": battery_dod,
            "autonomy_days": autonomy_days,
        },

        "cable": {
            "length_m": cable_length,
            "conductor": conductor,
            "max_voltage_drop_pct": target_voltage_drop,
            "ambient_temp": cable_temp,
        },
    }


# ============================================================
# 13. Image Mode
# ============================================================

elif mode == "📸 إدخال عن طريق الصور":

    st.header("📸 تحليل Datasheets / Labels")

    panel_file = st.file_uploader(
        "صورة اللوح",
        type=["png", "jpg", "jpeg"],
    )

    inverter_file = st.file_uploader(
        "صورة الإنفيرتر",
        type=["png", "jpg", "jpeg"],
    )

    battery_file = st.file_uploader(
        "صورة البطارية - اختياري",
        type=["png", "jpg", "jpeg"],
    )

    if st.button("🚀 استخراج المواصفات"):

        if not api_key:
            st.error("أدخل Gemini API Key.")
        elif not panel_file or not inverter_file:
            st.error("يجب إدخال صورة اللوح والإنفيرتر.")
        else:

            try:

                panel_img = Image.open(panel_file)
                inverter_img = Image.open(inverter_file)

                battery_img = (
                    Image.open(battery_file)
                    if battery_file
                    else None
                )

                with st.spinner("جاري تحليل الصور..."):

                    result = extract_from_images(
                        panel_img,
                        inverter_img,
                        battery_img,
                        api_key,
                    )

            except Exception as e:

                st.error(
                    f"حدث خطأ أثناء تحليل الصور: {e}"
                )


# ============================================================
# 14. Text Mode
# ============================================================

else:

    st.header("🔎 البحث بالموديل")

    panel_query = st.text_input(
        "Solar Panel Company + Model",
        placeholder="مثال: Jinko 550W",
    )

    inverter_query = st.text_input(
        "Inverter Company + Model",
        placeholder="مثال: Deye 5K",
    )

    battery_query = st.text_input(
        "Battery Company + Model - اختياري",
        placeholder="مثال: Pylontech US5000",
    )

    if st.button("🔍 البحث واستخراج المواصفات"):

        if not api_key:
            st.error("أدخل Gemini API Key.")
        elif not panel_query or not inverter_query:
            st.error(
                "أدخل موديل اللوح والإنفيرتر."
            )
        else:

            try:

                with st.spinner(
                    "جاري تحليل المواصفات..."
                ):

                    result = extract_from_text(
                        panel_query,
                        inverter_query,
                        battery_query,
                        api_key,
                    )

            except Exception as e:

                st.error(
                    f"حدث خطأ: {e}"
                )


# ============================================================
# 15. حفظ النتيجة
# ============================================================

if result:

    st.session_state["solar_result"] = result


if (
    "solar_result" in st.session_state
    and st.session_state["solar_result"]
):

    result = st.session_state["solar_result"]


# ============================================================
# 16. إذا لا يوجد تصميم
# ============================================================

if not result:

    st.info(
        "ابدأ بإدخال البيانات أو اختر التصميم اليدوي."
    )

    st.stop()


# ============================================================
# 17. استخراج البيانات
# ============================================================

panel = result.get("panel", {})
inverter = result.get("inverter", {})
battery = result.get("external_battery", {})
loads = result.get("loads", [])
site = result.get("site", {})
cable = result.get("cable", {})


pmax = safe_float(panel.get("pmax"))
voc = safe_float(panel.get("voc"))
vmp = safe_float(panel.get("vmp"))
isc = safe_float(panel.get("isc"))
imp = safe_float(panel.get("imp"))

ac_power = safe_float(
    inverter.get("ac_rated_power_w")
)

dc_max = safe_float(
    inverter.get("v_max")
)

mppt_min = safe_float(
    inverter.get("v_mppt_min")
)

mppt_max = safe_float(
    inverter.get("v_mppt_max")
)

start_voltage = safe_float(
    inverter.get("v_start")
)

global_mppt_current = safe_float(
    inverter.get("max_mppt_current")
)

mppt_list = inverter.get("mppts", [])

if not mppt_list:

    count = safe_int(
        inverter.get("mppt_count"),
        1,
    )

    strings = safe_int(
        inverter.get("strings_per_mppt"),
        1,
    )

    mppt_list = [
        {
            "mppt": i,
            "strings": strings,
            "max_current": global_mppt_current,
            "max_voltage": dc_max,
        }
        for i in range(1, count + 1)
    ]


# ============================================================
# 18. درجات الحرارة وحساب Voc
# ============================================================

min_temp = safe_float(
    site.get("min_temp"),
    -5,
)

max_temp = safe_float(
    site.get("max_temp"),
    45,
)

voc_coeff = safe_float(
    panel.get("voc_temp_coeff_pct_per_c"),
    -0.28,
)

# تحويل معامل الحرارة
voc_coeff_decimal = voc_coeff / 100.0

# زيادة Voc عندما تنخفض الحرارة
delta_cold = 25 - min_temp

if voc > 0:

    voc_cold_panel = (
        voc *
        (
            1 +
            abs(voc_coeff_decimal) *
            delta_cold
        )
    )

else:

    voc_cold_panel = 0


# ============================================================
# 19. Series Range
# ============================================================

if vmp > 0 and mppt_min > 0:

    min_series_mppt = math.ceil(
        mppt_min / vmp
    )

else:

    min_series_mppt = 1


if vmp > 0 and mppt_max > 0:

    max_series_mppt = math.floor(
        mppt_max / vmp
    )

else:

    max_series_mppt = 999


if voc_cold_panel > 0 and dc_max > 0:

    max_series_dc = math.floor(
        dc_max / voc_cold_panel
    )

else:

    max_series_dc = 999


max_series = min(
    max_series_mppt,
    max_series_dc,
)


# Start Voltage
if (
    start_voltage > 0
    and vmp > 0
):

    min_series_start = math.ceil(
        start_voltage / vmp
    )

else:

    min_series_start = 1


min_series = max(
    1,
    min_series_mppt,
    min_series_start,
)


# ============================================================
# 20. اختيار Series مناسب
# ============================================================

if max_series >= min_series:

    recommended_series = (
        min_series + max_series
    ) // 2

else:

    recommended_series = None


# ============================================================
# 21. Load Energy
# ============================================================

daily_load_kwh = 0.0
peak_load_w = 0.0

for load in loads:

    watts = safe_float(
        load.get("watts")
    )

    qty = safe_float(
        load.get("qty"),
        1,
    )

    hours = safe_float(
        load.get("hours")
    )

    daily_load_kwh += (
        watts *
        qty *
        hours /
        1000
    )

    peak_load_w += (
        watts *
        qty
    )


# ============================================================
# 22. PV Energy
# ============================================================

psh = safe_float(
    site.get("peak_sun_hours")
)

efficiency = (
    safe_float(
        site.get(
            "system_efficiency_pct"
        )
    )
    / 100
)

if recommended_series:

    total_strings = sum(
        safe_int(
            x.get("strings"),
            1,
        )
        for x in mppt_list
    )

    total_panels = (
        recommended_series *
        total_strings
    )

else:

    total_strings = sum(
        safe_int(
            x.get("strings"),
            1,
        )
        for x in mppt_list
    )

    total_panels = 0


dc_kw = (
    total_panels *
    pmax /
    1000
    if pmax > 0
    else 0
)


pv_daily_kwh = (
    dc_kw *
    psh *
    efficiency
    if dc_kw > 0
    else 0
)


required_pv_kw = (
    daily_load_kwh /
    psh /
    efficiency
    if (
        daily_load_kwh > 0
        and psh > 0
        and efficiency > 0
    )
    else 0
)


# ============================================================
# 23. DC/AC Ratio
# ============================================================

if ac_power > 0:

    dc_ac_ratio = (
        dc_kw /
        (ac_power / 1000)
    )

else:

    dc_ac_ratio = 0


# ============================================================
# 24. MPPT Analysis
# ============================================================

mppt_results = []

for mppt in mppt_list:

    number = safe_int(
        mppt.get("mppt"),
        1,
    )

    strings = safe_int(
        mppt.get("strings"),
        1,
    )

    current_limit = safe_float(
        mppt.get("max_current")
    )

    voltage_limit = safe_float(
        mppt.get("max_voltage")
    )

    if current_limit <= 0:
        current_limit = global_mppt_current

    if voltage_limit <= 0:
        voltage_limit = dc_max

    string_vmp = (
        recommended_series *
        vmp
        if recommended_series
        else 0
    )

    string_voc = (
        recommended_series *
        voc_cold_panel
        if recommended_series
        else 0
    )

    # Strings على التوازي داخل MPPT
    mppt_current = (
        strings *
        isc *
        design_factor
    )

    current_ok = (
        current_limit <= 0
        or mppt_current <= current_limit
    )

    voltage_ok = (
        voltage_limit <= 0
        or string_voc <= voltage_limit
    )

    mppt_window_ok = (
        (
            mppt_min <= 0
            or string_vmp >= mppt_min
        )
        and
        (
            mppt_max <= 0
            or string_vmp <= mppt_max
        )
    )

    mppt_results.append(
        {
            "MPPT": number,
            "Strings": strings,
            "Panels/String": (
                recommended_series
                or 0
            ),
            "Vmp/String V": round(
                string_vmp,
                2,
            ),
            "Voc Cold/String V": round(
                string_voc,
                2,
            ),
            "Design Current A": round(
                mppt_current,
                2,
            ),
            "Current Limit A": round(
                current_limit,
                2,
            ),
            "Voltage Limit V": round(
                voltage_limit,
                2,
            ),
            "Current": (
                "PASS"
                if current_ok
                else "FAIL"
            ),
            "Voltage": (
                "PASS"
                if voltage_ok
                else "FAIL"
            ),
            "MPPT Window": (
                "PASS"
                if mppt_window_ok
                else "FAIL"
            ),
        }
    )


# ============================================================
# 25. Battery Design
# ============================================================

battery_voltage = safe_float(
    battery.get("nominal_voltage_v")
)

battery_ah = safe_float(
    battery.get("capacity_ah")
)

battery_kwh = safe_float(
    battery.get("capacity_kwh")
)

battery_dod = safe_float(
    site.get(
        "battery_dod_pct"
    ),
    80,
)

autonomy = safe_float(
    site.get(
        "autonomy_days"
    ),
    1,
)

if battery_kwh <= 0 and (
    battery_voltage > 0
    and battery_ah > 0
):

    battery_kwh = (
        battery_voltage *
        battery_ah /
        1000
    )


if daily_load_kwh > 0:

    required_battery_kwh = (
        daily_load_kwh *
        autonomy /
        (battery_dod / 100)
    )

else:

    required_battery_kwh = 0


battery_status = "INFO"

if required_battery_kwh > 0:

    if battery_kwh <= 0:

        battery_status = "WARNING"

    elif battery_kwh >= required_battery_kwh:

        battery_status = "PASS"

    else:

        battery_status = "FAIL"


# ============================================================
# 26. Battery Inverter Compatibility
# ============================================================

inverter_battery = inverter.get(
    "battery",
    {},
)

inverter_battery_voltage = safe_float(
    inverter_battery.get(
        "nominal_voltage_v"
    )
)

battery_compat_status, battery_compat_message = (
    battery_voltage_compatibility(
        inverter_battery_voltage,
        battery_voltage,
    )
)


# ============================================================
# 27. Cable Calculation
# ============================================================

cable_length = safe_float(
    cable.get("length_m")
)

target_drop = safe_float(
    cable.get(
        "max_voltage_drop_pct"
    ),
    2,
)

conductor_material = cable.get(
    "conductor",
    "Copper",
)

if conductor_material == "Copper":

    resistivity = 0.0175

else:

    resistivity = 0.0282


if (
    cable_length > 0
    and isc > 0
    and vmp > 0
):

    design_current_cable = (
        isc *
        design_factor
    )

    design_voltage_cable = (
        vmp *
        (
            recommended_series
            or 1
        )
    )

    allowed_drop_v = (
        design_voltage_cable *
        target_drop /
        100
    )

    if allowed_drop_v > 0:

        cable_area = (
            resistivity *
            2 *
            cable_length *
            design_current_cable /
            allowed_drop_v
        )

    else:

        cable_area = 0

else:

    cable_area = 0


# ============================================================
# 28. Overall Checks
# ============================================================

checks = []


# Series
if recommended_series:

    add_check(
        checks,
        "PV Series Range",
        "PASS",
        f"{min_series} - {max_series}",
        "يوجد نطاق صالح بين الحد الأدنى والأقصى.",
    )

else:

    add_check(
        checks,
        "PV Series Range",
        "FAIL",
        "No valid range",
        "لا يوجد عدد Series يحقق حدود MPPT وDC Voltage.",
    )


# Cold Voc
if (
    recommended_series
    and dc_max > 0
):

    cold_voc_string = (
        recommended_series *
        voc_cold_panel
    )

    if cold_voc_string <= dc_max:

        add_check(
            checks,
            "Cold Voc",
            "PASS",
            fmt(
                cold_voc_string,
                "V",
            ),
            "ضمن Max DC Voltage.",
        )

    else:

        add_check(
            checks,
            "Cold Voc",
            "FAIL",
            fmt(
                cold_voc_string,
                "V",
            ),
            "يتجاوز Max DC Voltage.",
        )


# MPPT
for row in mppt_results:

    if (
        row["Current"] == "FAIL"
        or row["Voltage"] == "FAIL"
        or row["MPPT Window"] == "FAIL"
    ):

        add_check(
            checks,
            f'MPPT {row["MPPT"]}',
            "FAIL",
            (
                f'{row["Strings"]} Strings'
            ),
            (
                "يوجد تجاوز لحد التيار "
                "أو الجهد أو نطاق MPPT."
            ),
        )

    else:

        add_check(
            checks,
            f'MPPT {row["MPPT"]}',
            "PASS",
            (
                f'{row["Strings"]} Strings'
            ),
            "جميع الفحوصات الأساسية ناجحة.",
        )


# DC/AC
if dc_ac_ratio > 0:

    if 0.8 <= dc_ac_ratio <= 1.5:

        add_check(
            checks,
            "DC / AC Ratio",
            "PASS",
            f"{dc_ac_ratio:.2f}",
            "النسبة ضمن نطاق تصميمي شائع مبدئياً.",
        )

    else:

        add_check(
            checks,
            "DC / AC Ratio",
            "WARNING",
            f"{dc_ac_ratio:.2f}",
            "راجع سياسة Oversizing الخاصة بالإنفيرتر.",
        )


# PV Energy
if required_pv_kw > 0:

    if dc_kw >= required_pv_kw:

        add_check(
            checks,
            "PV Energy Sizing",
            "PASS",
            f"{dc_kw:.2f} / {required_pv_kw:.2f} kWp",
            "قدرة PV الفعلية تحقق القدرة المطلوبة مبدئياً.",
        )

    else:

        add_check(
            checks,
            "PV Energy Sizing",
            "FAIL",
            f"{dc_kw:.2f} / {required_pv_kw:.2f} kWp",
            "قدرة PV أقل من المطلوب.",
        )


# Battery
if battery_enabled if "battery_enabled" in locals() else True:

    add_check(
        checks,
        "Battery Sizing",
        battery_status,
        (
            f"{battery_kwh:.2f} / "
            f"{required_battery_kwh:.2f} kWh"
        ),
        "مقارنة السعة الفعلية بالمطلوبة.",
    )


# Battery voltage
if battery_voltage > 0:

    add_check(
        checks,
        "Battery Voltage Compatibility",
        battery_compat_status,
        f"{battery_voltage:.1f} V",
        battery_compat_message,
    )


# Cable
if cable_area > 0:

    add_check(
        checks,
        "DC Cable",
        "INFO",
        f"{cable_area:.2f} mm²",
        "المقطع نظري من ناحية Voltage Drop فقط.",
    )


# ============================================================
# 29. Dashboard
# ============================================================

st.markdown("---")

st.header("📊 لوحة التصميم")

c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.metric(
        "PV Capacity",
        f"{dc_kw:.2f} kWp",
    )

with c2:
    st.metric(
        "Panels",
        total_panels,
    )

with c3:
    st.metric(
        "Panels/String",
        recommended_series
        if recommended_series
        else "FAIL",
    )

with c4:
    st.metric(
        "Strings",
        total_strings,
    )

with c5:
    st.metric(
        "DC/AC",
        f"{dc_ac_ratio:.2f}"
        if dc_ac_ratio
        else "N/A",
    )


# ============================================================
# 30. Solar Sizing
# ============================================================

st.subheader("☀️ PV Energy Sizing")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        "Daily Load",
        f"{daily_load_kwh:.2f} kWh/day",
    )

with c2:
    st.metric(
        "Required PV",
        f"{required_pv_kw:.2f} kWp"
        if required_pv_kw
        else "N/A",
    )

with c3:
    st.metric(
        "Actual PV",
        f"{dc_kw:.2f} kWp",
    )

with c4:
    st.metric(
        "Estimated PV Energy",
        f"{pv_daily_kwh:.2f} kWh/day",
    )


# ============================================================
# 31. MPPT Table
# ============================================================

st.subheader("🔀 MPPT Design")

if mppt_results:

    st.dataframe(
        mppt_results,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# 32. Physical String Layout
# ============================================================

st.subheader("🔧 التوزيع الميداني")

if recommended_series:

    layout_rows = []

    string_id = 1

    for mppt in mppt_list:

        mppt_number = safe_int(
            mppt.get("mppt"),
            1,
        )

        strings = safe_int(
            mppt.get("strings"),
            1,
        )

        for local_string in range(
            1,
            strings + 1,
        ):

            layout_rows.append(
                {
                    "MPPT": mppt_number,
                    "String": (
                        f"S{string_id}"
                    ),
                    "Local String": (
                        local_string
                    ),
                    "Panels": (
                        recommended_series
                    ),
                    "Vmp": round(
                        recommended_series *
                        vmp,
                        1,
                    ),
                    "Voc Cold": round(
                        recommended_series *
                        voc_cold_panel,
                        1,
                    ),
                    "Imp": round(
                        imp,
                        2,
                    ),
                }
            )

            string_id += 1

    st.dataframe(
        layout_rows,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# 33. Detailed Electrical Checks
# ============================================================

st.subheader("🛡️ Electrical Verification")

st.dataframe(
    checks,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# 34. Battery
# ============================================================

st.subheader("🔋 Battery Design")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        "Battery Voltage",
        f"{battery_voltage:.1f} V"
        if battery_voltage
        else "N/A",
    )

with c2:
    st.metric(
        "Available Battery",
        f"{battery_kwh:.2f} kWh"
        if battery_kwh
        else "N/A",
    )

with c3:
    st.metric(
        "Required Battery",
        f"{required_battery_kwh:.2f} kWh"
        if required_battery_kwh
        else "N/A",
    )

with c4:
    st.metric(
        "Battery Status",
        status_icon(
            battery_status
        ),
    )

if battery_compat_status == "PASS":

    st.success(
        f"🔋 {battery_compat_message}"
    )

elif battery_compat_status == "FAIL":

    st.error(
        f"🔋 {battery_compat_message}"
    )

else:

    st.warning(
        f"🔋 {battery_compat_message}"
    )


# ============================================================
# 35. Cable
# ============================================================

st.subheader("🔌 DC Cable Design")

if cable_area > 0:

    st.info(
        f"""
        **المقطع النظري الأدنى:** {cable_area:.2f} mm²

        **التيار التصميمي:** {isc * design_factor:.2f} A

        **طول المسار:** {cable_length:.1f} m ذهاباً

        **هبوط الجهد المستهدف:** {target_drop:.2f}%

        ⚠️ يجب بعد ذلك اختيار أقرب مقطع قياسي والتحقق من
        Ampacity، درجة الحرارة، طريقة التركيب، التجميع والكود المحلي.
        """
    )

else:

    st.warning(
        "لا توجد بيانات كافية لحساب الكابل."
    )


# ============================================================
# 36. الأحمال
# ============================================================

st.subheader("🏠 Load Analysis")

if loads:

    load_table = []

    for load in loads:

        watts = safe_float(
            load.get("watts")
        )

        qty = safe_float(
            load.get("qty"),
            1,
        )

        hours = safe_float(
            load.get("hours")
        )

        energy = (
            watts *
            qty *
            hours /
            1000
        )

        load_table.append(
            {
                "Load": load.get(
                    "name",
                    "",
                ),
                "Qty": qty,
                "Power W": watts,
                "Hours/day": hours,
                "Energy kWh/day": round(
                    energy,
                    3,
                ),
            }
        )

    st.dataframe(
        load_table,
        use_container_width=True,
        hide_index=True,
    )

    st.write(
        f"**Peak Load:** "
        f"{peak_load_w:.0f} W"
    )

    st.write(
        f"**Daily Energy:** "
        f"{daily_load_kwh:.2f} kWh/day"
    )


# ============================================================
# 37. التقرير النهائي
# ============================================================

st.markdown("---")

st.header("📋 Final Engineering Report")

fail_count = sum(
    1
    for x in checks
    if x["الحالة"] == "FAIL"
)

warning_count = sum(
    1
    for x in checks
    if x["الحالة"] == "WARNING"
)

pass_count = sum(
    1
    for x in checks
    if x["الحالة"] == "PASS"
)


if fail_count == 0 and warning_count == 0:

    st.success(
        "🟢 DESIGN STATUS: PASS"
    )

elif fail_count == 0:

    st.warning(
        f"🟡 DESIGN STATUS: WARNING — "
        f"{warning_count} تحذير"
    )

else:

    st.error(
        f"🔴 DESIGN STATUS: FAIL — "
        f"{fail_count} فشل"
    )


c1, c2, c3 = st.columns(3)

with c1:
    st.metric(
        "PASS",
        pass_count,
    )

with c2:
    st.metric(
        "WARNING",
        warning_count,
    )

with c3:
    st.metric(
        "FAIL",
        fail_count,
    )


# ============================================================
# 38. ملخص التصميم
# ============================================================

st.subheader("📌 Design Summary")

summary = {
    "Panel": (
        f'{panel.get("brand", "")} '
        f'{panel.get("model", "")}'
    ),
    "Panel Power": f"{pmax:.0f} W",
    "Inverter": (
        f'{inverter.get("brand", "")} '
        f'{inverter.get("model", "")}'
    ),
    "Inverter Power": f"{ac_power / 1000:.2f} kW",
    "MPPT Count": len(mppt_list),
    "Total Strings": total_strings,
    "Panels/String": (
        recommended_series
        if recommended_series
        else "NO VALID VALUE"
    ),
    "Total Panels": total_panels,
    "PV Capacity": f"{dc_kw:.2f} kWp",
    "DC/AC Ratio": (
        f"{dc_ac_ratio:.2f}"
        if dc_ac_ratio
        else "N/A"
    ),
    "Daily Load": (
        f"{daily_load_kwh:.2f} kWh/day"
    ),
    "Required PV": (
        f"{required_pv_kw:.2f} kWp"
        if required_pv_kw
        else "N/A"
    ),
    "Battery": (
        f"{battery_kwh:.2f} kWh"
        if battery_kwh
        else "N/A"
    ),
}

st.json(summary)


# ============================================================
# 39. ملاحظات السلامة
# ============================================================

st.markdown("---")

st.warning(
    """
    ⚠️ **ملاحظة هندسية مهمة**

    هذه الأداة تقوم بالتصميم والفحص المبدئي اعتماداً على البيانات المدخلة.
    قبل التنفيذ الفعلي يجب التحقق من Datasheet الأصلي للوح والإنفيرتر والبطارية،
    ومعاملات الحرارة الفعلية، أقل/أعلى درجة حرارة للموقع، الكابلات، الحمايات،
    التأريض، SPD، القواطع، الفيوزات، متطلبات الشبكة والكود الكهربائي المحلي.

    لا تعتمد قيمة الكابل أو القاطع أو SPD للتنفيذ النهائي اعتماداً على هذا
    الحساب وحده.
    """
)


# ============================================================
# 40. JSON Export داخل الصفحة
# ============================================================

st.subheader("💾 بيانات التصميم")

json_output = json.dumps(
    result,
    ensure_ascii=False,
    indent=2,
)

st.download_button(
    "⬇️ تحميل بيانات التصميم JSON",
    data=json_output,
    file_name="solar_design.json",
    mime="application/json",
)
