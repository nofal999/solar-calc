# ============================================================
# SOLAR PV DESIGN & VERIFICATION TOOL
# Version: Dynamic MPPT + String Scenarios + Optional Battery
# ============================================================

import json
import math
import time
from copy import deepcopy

import streamlit as st
from PIL import Image


# ============================================================
# GEMINI IMPORT
# ============================================================

try:
    from google import genai
    from google.genai import types

    GEMINI_AVAILABLE = True

except ImportError:
    GEMINI_AVAILABLE = False


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Solar PV Design & Verification",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    html, body, [class*="css"] {
        font-family: "Segoe UI", Tahoma, Arial, sans-serif;
    }

    [data-testid="stMainBlockContainer"],
    [data-testid="stSidebarContent"] {
        direction: rtl;
        text-align: right;
    }

    [data-testid="stMarkdownContainer"] {
        direction: rtl;
        text-align: right;
    }

    .solar-card {
        padding: 15px;
        border-radius: 12px;
        border: 1px solid rgba(128,128,128,0.25);
        margin-bottom: 10px;
    }

    .pass-box {
        padding: 12px;
        border-radius: 10px;
        background: rgba(0, 180, 0, 0.10);
        border: 1px solid rgba(0, 180, 0, 0.35);
    }

    .warning-box {
        padding: 12px;
        border-radius: 10px;
        background: rgba(255, 180, 0, 0.10);
        border: 1px solid rgba(255, 180, 0, 0.35);
    }

    .fail-box {
        padding: 12px;
        border-radius: 10px;
        background: rgba(220, 0, 0, 0.10);
        border: 1px solid rgba(220, 0, 0, 0.35);
    }

    .small-text {
        font-size: 0.85rem;
        opacity: 0.75;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# TITLE
# ============================================================

st.title("☀️ Solar PV Design & Verification Tool")

st.caption(
    "أداة تصميم وفحص منظومات Solar PV — "
    "PV Array + MPPT + Inverter + Battery + Loads + Cable"
)


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_STATE = {
    "extracted_data": None,
    "approved_data": None,
    "last_analysis": None,
}

for key, value in DEFAULT_STATE.items():

    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# GENERAL FUNCTIONS
# ============================================================

def safe_float(value, default=0.0):

    try:

        if value is None:
            return default

        if isinstance(value, str):
            value = value.strip()

            if not value:
                return default

            value = value.replace(",", ".")

        return float(value)

    except Exception:

        return default


def safe_int(value, default=0):

    try:
        return int(float(value))

    except Exception:

        return default


def fmt(value, unit="", decimals=2):

    if value is None:
        return "N/A"

    try:

        value = float(value)

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


def clean_json_text(text):

    text = text.strip()

    if text.startswith("```"):

        text = text.replace("```json", "")
        text = text.replace("```", "")

    return text.strip()


# ============================================================
# GEMINI JSON STRUCTURE
# ============================================================

JSON_STRUCTURE = """
{
  "panel": {
    "brand": "",
    "model": "",
    "part_number": "",
    "type": "",
    "pmax_w": 0,
    "voc_v": 0,
    "vmp_v": 0,
    "isc_a": 0,
    "imp_a": 0,
    "voc_temp_coeff_pct_per_c": 0,
    "vmp_temp_coeff_pct_per_c": 0,
    "max_system_voltage_v": 0,
    "max_series_fuse_a": 0
  },

  "inverter": {
    "brand": "",
    "model": "",
    "part_number": "",
    "type": "",
    "phase_type": "",

    "ac_rated_power_w": 0,

    "max_dc_voltage_v": 0,

    "mppt_voltage_min_v": 0,
    "mppt_voltage_max_v": 0,
    "start_voltage_v": 0,

    "mppt_count": 1,

    "mppts": [
      {
        "mppt": 1,
        "max_current_a": 0,
        "max_voltage_v": 0,
        "max_short_circuit_current_a": 0,
        "max_strings": 0
      }
    ],

    "battery": {
      "supported": false,
      "nominal_voltage_v": 0,
      "min_voltage_v": 0,
      "max_voltage_v": 0,
      "max_charge_current_a": 0,
      "max_discharge_current_a": 0
    },

    "ac": {
      "nominal_voltage_v": 0,
      "frequency_hz": 0,
      "max_ac_current_a": 0
    }
  },

  "battery": {
    "brand": "",
    "model": "",
    "chemistry": "",
    "nominal_voltage_v": 0,
    "capacity_ah": 0,
    "capacity_kwh": 0,
    "max_charge_current_a": 0,
    "max_discharge_current_a": 0,
    "recommended_dod_pct": 0
  }
}
"""


# ============================================================
# GEMINI ERROR DETECTION
# ============================================================

def is_temporary_gemini_error(error):

    text = str(error).lower()

    temporary_words = [
        "503",
        "unavailable",
        "high demand",
        "overloaded",
        "temporarily",
        "service unavailable",
        "internal server error",
        "deadline exceeded",
    ]

    return any(
        word in text
        for word in temporary_words
    )


# ============================================================
# GEMINI MODEL FALLBACK
# ============================================================

GEMINI_MODELS = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
]


# ============================================================
# GEMINI IMAGE EXTRACTION
# ============================================================

def extract_from_images(
    panel_img,
    inverter_img,
    battery_img,
    api_key,
):

    if not GEMINI_AVAILABLE:

        raise RuntimeError(
            "مكتبة google-genai غير مثبتة.\n"
            "ثبتها بالأمر:\n\n"
            "pip install -U google-genai"
        )

    client = genai.Client(
        api_key=api_key
    )

    contents = []

    contents.append(panel_img)
    contents.append(inverter_img)

    if battery_img is not None:
        contents.append(battery_img)

    prompt = f"""
أنت مهندس متخصص في تصميم أنظمة الطاقة الشمسية Solar PV.

حلل الصور المرفقة.

الصورة الأولى = Solar Panel.
الصورة الثانية = Inverter.
الصورة الثالثة إن وجدت = Battery.

استخرج فقط البيانات الظاهرة أو التي يمكن قراءتها بثقة.

أعد JSON فقط وفق هذا الهيكل:

{JSON_STRUCTURE}

قواعد مهمة جداً:

1. لا تخمن القيم.
2. إذا لم تكن القيمة واضحة استخدم 0.
3. لا تحول قيمة غير موجودة إلى قيمة تقديرية.
4. استخرج عدد MPPT الحقيقي إذا كان موجوداً.
5. لكل MPPT حاول استخراج:
   - maximum current
   - maximum voltage
   - short circuit current limit
   - maximum number of strings
6. إذا لم تكن بيانات MPPT منفصلة موجودة، استخدم mppt_count فقط.
7. حافظ على الوحدات.
8. لا تضع نصاً خارج JSON.
"""

    contents.append(prompt)

    last_error = None

    for model_name in GEMINI_MODELS:

        for attempt in range(3):

            try:

                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.0,
                    ),
                )

                if not response:

                    raise RuntimeError(
                        "Gemini returned no response."
                    )

                text = response.text

                if not text:

                    raise RuntimeError(
                        "Gemini returned empty response."
                    )

                text = clean_json_text(text)

                data = json.loads(text)

                return data

            except Exception as error:

                last_error = error

                if not is_temporary_gemini_error(
                    error
                ):

                    raise

                wait_seconds = min(
                    3 * (2 ** attempt),
                    20,
                )

                time.sleep(
                    wait_seconds
                )

    raise RuntimeError(
        "Gemini غير متاح حالياً بعد تجربة عدة "
        "نماذج ومحاولات.\n\n"
        f"آخر خطأ:\n{last_error}"
    )


# ============================================================
# GEMINI TEXT EXTRACTION
# ============================================================

def extract_from_text(
    panel_query,
    inverter_query,
    battery_query,
    api_key,
):

    if not GEMINI_AVAILABLE:

        raise RuntimeError(
            "مكتبة google-genai غير مثبتة.\n"
            "نفذ:\n"
            "pip install -U google-genai"
        )

    client = genai.Client(
        api_key=api_key
    )

    prompt = f"""
أنت مهندس Solar PV.

ابحث/استخرج المواصفات الخاصة بالمكونات التالية:

Solar Panel:
{panel_query}

Inverter:
{inverter_query}

Battery:
{battery_query if battery_query else "لا توجد بطارية"}

أعد JSON فقط.

الهيكل:

{JSON_STRUCTURE}

قواعد:
- لا تخمن.
- إذا لم تجد قيمة استخدم 0.
- يجب أن تكون القيم مرتبطة بالموديل المحدد.
- حاول تمييز بيانات كل MPPT.
- لا تفترض أن جميع MPPTs لها نفس التيار إذا كانت البيانات مختلفة.
"""

    last_error = None

    for model_name in GEMINI_MODELS:

        for attempt in range(3):

            try:

                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.0,
                    ),
                )

                text = clean_json_text(
                    response.text
                )

                return json.loads(text)

            except Exception as error:

                last_error = error

                if not is_temporary_gemini_error(
                    error
                ):

                    raise

                wait_seconds = min(
                    3 * (2 ** attempt),
                    20,
                )

                time.sleep(
                    wait_seconds
                )

    raise RuntimeError(
        "تعذر الاتصال بـ Gemini.\n"
        f"آخر خطأ:\n{last_error}"
    )


# ============================================================
# NORMALIZE DATA
# ============================================================

def normalize_data(data):

    data = deepcopy(data)

    if "panel" not in data:
        data["panel"] = {}

    if "inverter" not in data:
        data["inverter"] = {}

    if "battery" not in data:
        data["battery"] = {}

    panel = data["panel"]
    inverter = data["inverter"]
    battery = data["battery"]

    panel.setdefault("pmax_w", 0)
    panel.setdefault("voc_v", 0)
    panel.setdefault("vmp_v", 0)
    panel.setdefault("isc_a", 0)
    panel.setdefault("imp_a", 0)
    panel.setdefault(
        "voc_temp_coeff_pct_per_c",
        0,
    )
    panel.setdefault(
        "vmp_temp_coeff_pct_per_c",
        0,
    )

    inverter.setdefault(
        "mppt_count",
        1,
    )

    inverter.setdefault(
        "mppts",
        [],
    )

    # إذا لم توجد بيانات MPPT تفصيلية
    # ننشئها من عدد MPPT
    if not inverter["mppts"]:

        count = max(
            1,
            safe_int(
                inverter.get(
                    "mppt_count",
                    1,
                ),
                1,
            ),
        )

        inverter["mppts"] = [
            {
                "mppt": i,
                "max_current_a": safe_float(
                    inverter.get(
                        "max_mppt_current_a",
                        0,
                    )
                ),
                "max_voltage_v": safe_float(
                    inverter.get(
                        "max_dc_voltage_v",
                        0,
                    )
                ),
                "max_short_circuit_current_a": 0,
                "max_strings": 0,
            }

            for i in range(
                1,
                count + 1,
            )
        ]

    inverter["mppt_count"] = len(
        inverter["mppts"]
    )

    return data


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ إعدادات التصميم")

    api_key = st.text_input(
        "Gemini API Key",
        type="password",
    )

    st.markdown("---")

    st.subheader("معاملات التصميم")

    current_safety_factor = st.number_input(
        "Current Safety Factor",
        min_value=1.00,
        max_value=1.50,
        value=1.25,
        step=0.01,
    )

    cold_safety_factor = st.number_input(
        "Cold Voc Safety Factor",
        min_value=1.00,
        max_value=1.30,
        value=1.00,
        step=0.01,
        help=(
            "يفضل استخدام معامل الحرارة الفعلي. "
            "يمكن وضع 1.00 إذا كان معامل الحرارة متوفراً."
        ),
    )

    system_efficiency = st.number_input(
        "System Efficiency (%)",
        min_value=50.0,
        max_value=100.0,
        value=80.0,
        step=1.0,
    )

    st.markdown("---")

    st.caption(
        "الحسابات مبدئية ويجب مراجعتها مع Datasheets "
        "والكود الكهربائي المحلي قبل التنفيذ."
    )


# ============================================================
# INPUT MODE
# ============================================================

st.header("1️⃣ إدخال بيانات النظام")

input_mode = st.radio(
    "طريقة إدخال البيانات",
    [
        "🧮 Manual Design",
        "📸 Image / Datasheet",
        "🔎 Company + Model",
    ],
    horizontal=True,
)


# ============================================================
# MANUAL INPUT
# ============================================================

if input_mode == "🧮 Manual Design":

    st.subheader(
        "🧮 Manual Solar Design"
    )

    st.info(
        "في الوضع اليدوي لا تحتاج إلى Gemini."
    )

    # --------------------------------------------------------
    # PANEL
    # --------------------------------------------------------

    st.markdown("### ☀️ Solar Panel")

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:

        panel_pmax = st.number_input(
            "Pmax (W)",
            min_value=0.0,
            value=550.0,
            step=10.0,
        )

    with c2:

        panel_voc = st.number_input(
            "Voc (V)",
            min_value=0.0,
            value=49.5,
            step=0.1,
        )

    with c3:

        panel_vmp = st.number_input(
            "Vmp (V)",
            min_value=0.0,
            value=41.5,
            step=0.1,
        )

    with c4:

        panel_isc = st.number_input(
            "Isc (A)",
            min_value=0.0,
            value=14.0,
            step=0.1,
        )

    with c5:

        panel_imp = st.number_input(
            "Imp (A)",
            min_value=0.0,
            value=13.3,
            step=0.1,
        )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        panel_brand = st.text_input(
            "Panel Brand"
        )

    with c2:

        panel_model = st.text_input(
            "Panel Model"
        )

    with c3:

        panel_voc_coeff = st.number_input(
            "Voc Temp. Coeff. (%/°C)",
            value=-0.28,
            step=0.01,
        )

    with c4:

        panel_vmp_coeff = st.number_input(
            "Vmp Temp. Coeff. (%/°C)",
            value=-0.30,
            step=0.01,
        )

    # --------------------------------------------------------
    # INVERTER
    # --------------------------------------------------------

    st.markdown("### ⚡ Inverter")

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        inverter_brand = st.text_input(
            "Inverter Brand"
        )

    with c2:

        inverter_model = st.text_input(
            "Inverter Model"
        )

    with c3:

        inverter_type = st.selectbox(
            "Inverter Type",
            [
                "Hybrid",
                "Off-Grid",
                "On-Grid",
            ],
        )

    with c4:

        inverter_phase = st.selectbox(
            "Phase",
            [
                "Single Phase",
                "Three Phase",
            ],
        )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        inverter_ac_power = st.number_input(
            "AC Rated Power (W)",
            min_value=0.0,
            value=5000.0,
            step=100.0,
        )

    with c2:

        inverter_dc_max = st.number_input(
            "Max DC Voltage (V)",
            min_value=0.0,
            value=500.0,
            step=5.0,
        )

    with c3:

        inverter_mppt_min = st.number_input(
            "MPPT Min Voltage (V)",
            min_value=0.0,
            value=150.0,
            step=5.0,
        )

    with c4:

        inverter_mppt_max = st.number_input(
            "MPPT Max Voltage (V)",
            min_value=0.0,
            value=425.0,
            step=5.0,
        )

    c1, c2 = st.columns(2)

    with c1:

        inverter_start_voltage = st.number_input(
            "Start Voltage (V)",
            min_value=0.0,
            value=120.0,
            step=5.0,
        )

    with c2:

        inverter_global_current = st.number_input(
            "Default MPPT Max Current (A)",
            min_value=0.0,
            value=13.0,
            step=0.5,
        )

    # --------------------------------------------------------
    # MPPT
    # --------------------------------------------------------

    st.markdown("### 🔀 MPPT Configuration")

    mppt_count = st.number_input(
        "عدد MPPT",
        min_value=1,
        max_value=32,
        value=3,
        step=1,
    )

    manual_mppts = []

    for mppt_no in range(
        1,
        int(mppt_count) + 1,
    ):

        with st.expander(
            f"⚡ MPPT {mppt_no}",
            expanded=(
                mppt_no == 1
            ),
        ):

            c1, c2, c3, c4 = st.columns(4)

            with c1:

                strings = st.number_input(
                    "عدد Strings",
                    min_value=1,
                    max_value=32,
                    value=1,
                    step=1,
                    key=f"manual_mppt_strings_{mppt_no}",
                )

            with c2:

                max_current = st.number_input(
                    "Max Current (A)",
                    min_value=0.0,
                    value=float(
                        inverter_global_current
                    ),
                    step=0.5,
                    key=f"manual_mppt_current_{mppt_no}",
                )

            with c3:

                max_voltage = st.number_input(
                    "Max Voltage (V)",
                    min_value=0.0,
                    value=float(
                        inverter_dc_max
                    ),
                    step=5.0,
                    key=f"manual_mppt_voltage_{mppt_no}",
                )

            with c4:

                max_isc = st.number_input(
                    "Max Isc (A)",
                    min_value=0.0,
                    value=0.0,
                    step=0.5,
                    key=f"manual_mppt_isc_{mppt_no}",
                )

            manual_mppts.append(
                {
                    "mppt": mppt_no,
                    "strings": int(strings),
                    "max_current_a": max_current,
                    "max_voltage_v": max_voltage,
                    "max_short_circuit_current_a": max_isc,
                    "max_strings": 0,
                }
            )

    # --------------------------------------------------------
    # SITE
    # --------------------------------------------------------

    st.markdown("### 🌍 Site")

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        site_min_temp = st.number_input(
            "Minimum Temperature °C",
            value=-5.0,
            step=1.0,
        )

    with c2:

        site_max_temp = st.number_input(
            "Maximum Temperature °C",
            value=45.0,
            step=1.0,
        )

    with c3:

        site_psh = st.number_input(
            "Peak Sun Hours",
            min_value=0.1,
            value=5.0,
            step=0.1,
        )

    with c4:

        site_efficiency = st.number_input(
            "System Efficiency %",
            min_value=50.0,
            max_value=100.0,
            value=float(
                system_efficiency
            ),
            step=1.0,
        )

    # --------------------------------------------------------
    # LOADS
    # --------------------------------------------------------

    st.markdown("### 🏠 Loads")

    load_count = st.number_input(
        "عدد الأحمال",
        min_value=0,
        max_value=50,
        value=4,
        step=1,
    )

    manual_loads = []

    for load_no in range(
        1,
        int(load_count) + 1,
    ):

        c1, c2, c3, c4 = st.columns(4)

        with c1:

            load_name = st.text_input(
                "الحمل",
                value=f"Load {load_no}",
                key=f"load_name_{load_no}",
            )

        with c2:

            load_power = st.number_input(
                "Power W",
                min_value=0.0,
                value=100.0,
                step=10.0,
                key=f"load_power_{load_no}",
            )

        with c3:

            load_qty = st.number_input(
                "Quantity",
                min_value=1,
                value=1,
                step=1,
                key=f"load_qty_{load_no}",
            )

        with c4:

            load_hours = st.number_input(
                "Hours/day",
                min_value=0.0,
                value=4.0,
                step=0.5,
                key=f"load_hours_{load_no}",
            )

        manual_loads.append(
            {
                "name": load_name,
                "power_w": load_power,
                "quantity": load_qty,
                "hours_per_day": load_hours,
            }
        )

    # --------------------------------------------------------
    # BATTERY ENABLE / DISABLE
    # --------------------------------------------------------

    st.markdown("### 🔋 Battery")

    battery_enabled_manual = st.toggle(
        "تفعيل قسم البطارية",
        value=True,
        help=(
            "عند إيقافه سيتم تجاهل البطارية بالكامل "
            "في التصميم والفحوصات."
        ),
    )

    manual_battery = {
        "enabled": battery_enabled_manual,
        "brand": "",
        "model": "",
        "chemistry": "",
        "nominal_voltage_v": 0,
        "capacity_ah": 0,
        "capacity_kwh": 0,
        "max_charge_current_a": 0,
        "max_discharge_current_a": 0,
        "recommended_dod_pct": 80,
    }

    if battery_enabled_manual:

        c1, c2, c3 = st.columns(3)

        with c1:

            manual_battery[
                "brand"
            ] = st.text_input(
                "Battery Brand"
            )

        with c2:

            manual_battery[
                "model"
            ] = st.text_input(
                "Battery Model"
            )

        with c3:

            manual_battery[
                "chemistry"
            ] = st.text_input(
                "Chemistry",
                value="LiFePO4",
            )

        c1, c2, c3, c4 = st.columns(4)

        with c1:

            manual_battery[
                "nominal_voltage_v"
            ] = st.number_input(
                "Nominal Voltage V",
                min_value=0.0,
                value=51.2,
                step=0.1,
            )

        with c2:

            manual_battery[
                "capacity_ah"
            ] = st.number_input(
                "Capacity Ah",
                min_value=0.0,
                value=200.0,
                step=10.0,
            )

        with c3:

            manual_battery[
                "capacity_kwh"
            ] = st.number_input(
                "Capacity kWh",
                min_value=0.0,
                value=0.0,
                step=0.1,
            )

        with c4:

            manual_battery[
                "recommended_dod_pct"
            ] = st.number_input(
                "DoD %",
                min_value=1.0,
                max_value=100.0,
                value=80.0,
                step=1.0,
            )

        c1, c2 = st.columns(2)

        with c1:

            manual_battery[
                "max_charge_current_a"
            ] = st.number_input(
                "Max Charge Current A",
                min_value=0.0,
                value=100.0,
                step=5.0,
            )

        with c2:

            manual_battery[
                "max_discharge_current_a"
            ] = st.number_input(
                "Max Discharge Current A",
                min_value=0.0,
                value=200.0,
                step=5.0,
            )

    # --------------------------------------------------------
    # BUILD MANUAL DATA
    # --------------------------------------------------------

    result = {
        "panel": {
            "brand": panel_brand,
            "model": panel_model,
            "pmax_w": panel_pmax,
            "voc_v": panel_voc,
            "vmp_v": panel_vmp,
            "isc_a": panel_isc,
            "imp_a": panel_imp,
            "voc_temp_coeff_pct_per_c":
                panel_voc_coeff,
            "vmp_temp_coeff_pct_per_c":
                panel_vmp_coeff,
        },

        "inverter": {
            "brand": inverter_brand,
            "model": inverter_model,
            "type": inverter_type,
            "phase_type": inverter_phase,
            "ac_rated_power_w":
                inverter_ac_power,
            "max_dc_voltage_v":
                inverter_dc_max,
            "mppt_voltage_min_v":
                inverter_mppt_min,
            "mppt_voltage_max_v":
                inverter_mppt_max,
            "start_voltage_v":
                inverter_start_voltage,
            "mppt_count":
                int(mppt_count),
            "mppts":
                manual_mppts,

            "battery": {
                "supported":
                    inverter_type != "On-Grid",
                "nominal_voltage_v":
                    manual_battery[
                        "nominal_voltage_v"
                    ],
                "min_voltage_v": 0,
                "max_voltage_v": 0,
                "max_charge_current_a": 0,
                "max_discharge_current_a": 0,
            },
        },

        "battery":
            manual_battery,

        "site": {
            "min_temperature_c":
                site_min_temp,
            "max_temperature_c":
                site_max_temp,
            "peak_sun_hours":
                site_psh,
            "system_efficiency_pct":
                site_efficiency,
        },

        "loads":
            manual_loads,
    }

    st.session_state[
        "approved_data"
    ] = normalize_data(result)


# ============================================================
# IMAGE MODE
# ============================================================

elif input_mode == "📸 Image / Datasheet":

    st.subheader(
        "📸 قراءة Datasheet / Label"
    )

    if not GEMINI_AVAILABLE:

        st.error(
            "google-genai غير مثبتة."
        )

        st.code(
            "pip install -U google-genai"
        )

    panel_file = st.file_uploader(
        "☀️ صورة Solar Panel",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp",
        ],
    )

    inverter_file = st.file_uploader(
        "⚡ صورة Inverter",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp",
        ],
    )

    battery_file = st.file_uploader(
        "🔋 صورة Battery — اختياري",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp",
        ],
    )

    if st.button(
        "🚀 استخراج المواصفات",
        type="primary",
    ):

        if not api_key:

            st.error(
                "أدخل Gemini API Key."
            )

        elif (
            panel_file is None
            or inverter_file is None
        ):

            st.error(
                "يجب إدخال صورة اللوح والإنفيرتر."
            )

        else:

            try:

                panel_img = Image.open(
                    panel_file
                )

                inverter_img = Image.open(
                    inverter_file
                )

                battery_img = None

                if battery_file:

                    battery_img = Image.open(
                        battery_file
                    )

                with st.spinner(
                    "جاري تحليل الصور... "
                    "سيتم تجربة نموذج احتياطي إذا حدث 503."
                ):

                    extracted = (
                        extract_from_images(
                            panel_img,
                            inverter_img,
                            battery_img,
                            api_key,
                        )
                    )

                st.session_state[
                    "extracted_data"
                ] = normalize_data(
                    extracted
                )

                st.success(
                    "تم استخراج البيانات. "
                    "راجعها قبل اعتمادها."
                )

            except Exception as error:

                st.error(
                    f"تعذر استخراج البيانات:\n{error}"
                )

                st.info(
                    "يمكنك الانتقال إلى Manual Design "
                    "وإدخال البيانات يدوياً."
                )


# ============================================================
# TEXT MODE
# ============================================================

elif input_mode == "🔎 Company + Model":

    st.subheader(
        "🔎 البحث بالموديل"
    )

    panel_query = st.text_input(
        "Solar Panel — Brand + Model"
    )

    inverter_query = st.text_input(
        "Inverter — Brand + Model"
    )

    battery_query = st.text_input(
        "Battery — Brand + Model — اختياري"
    )

    if st.button(
        "🔍 استخراج المواصفات",
        type="primary",
    ):

        if not api_key:

            st.error(
                "أدخل Gemini API Key."
            )

        elif (
            not panel_query
            or not inverter_query
        ):

            st.error(
                "أدخل موديل اللوح والإنفيرتر."
            )

        else:

            try:

                with st.spinner(
                    "جاري البحث عن المواصفات..."
                ):

                    extracted = (
                        extract_from_text(
                            panel_query,
                            inverter_query,
                            battery_query,
                            api_key,
                        )
                    )

                st.session_state[
                    "extracted_data"
                ] = normalize_data(
                    extracted
                )

                st.success(
                    "تم استخراج البيانات."
                )

            except Exception as error:

                st.error(
                    f"تعذر استخراج البيانات:\n{error}"
                )


# ============================================================
# GEMINI REVIEW SCREEN
# ============================================================

if st.session_state[
    "extracted_data"
] is not None:

    st.markdown("---")

    st.header(
        "2️⃣ مراجعة بيانات Gemini قبل اعتمادها"
    )

    st.warning(
        "لا تبدأ الحسابات مباشرة من بيانات الذكاء الاصطناعي. "
        "راجع القيم مع Datasheet، وعدل أي قيمة غير صحيحة."
    )

    extracted = deepcopy(
        st.session_state[
            "extracted_data"
        ]
    )

    panel = extracted[
        "panel"
    ]

    inverter = extracted[
        "inverter"
    ]

    battery = extracted[
        "battery"
    ]

    # --------------------------------------------------------
    # PANEL REVIEW
    # --------------------------------------------------------

    st.subheader(
        "☀️ Panel Data"
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:

        panel["pmax_w"] = st.number_input(
            "Pmax W",
            value=safe_float(
                panel.get(
                    "pmax_w"
                )
            ),
            key="review_pmax",
        )

    with c2:

        panel["voc_v"] = st.number_input(
            "Voc V",
            value=safe_float(
                panel.get(
                    "voc_v"
                )
            ),
            key="review_voc",
        )

    with c3:

        panel["vmp_v"] = st.number_input(
            "Vmp V",
            value=safe_float(
                panel.get(
                    "vmp_v"
                )
            ),
            key="review_vmp",
        )

    with c4:

        panel["isc_a"] = st.number_input(
            "Isc A",
            value=safe_float(
                panel.get(
                    "isc_a"
                )
            ),
            key="review_isc",
        )

    with c5:

        panel["imp_a"] = st.number_input(
            "Imp A",
            value=safe_float(
                panel.get(
                    "imp_a"
                )
            ),
            key="review_imp",
        )

    c1, c2 = st.columns(2)

    with c1:

        panel[
            "voc_temp_coeff_pct_per_c"
        ] = st.number_input(
            "Voc Temp Coeff. %/°C",
            value=safe_float(
                panel.get(
                    "voc_temp_coeff_pct_per_c"
                )
            ),
            step=0.01,
            key="review_voc_coeff",
        )

    with c2:

        panel[
            "vmp_temp_coeff_pct_per_c"
        ] = st.number_input(
            "Vmp Temp Coeff. %/°C",
            value=safe_float(
                panel.get(
                    "vmp_temp_coeff_pct_per_c"
                )
            ),
            step=0.01,
            key="review_vmp_coeff",
        )

    # --------------------------------------------------------
    # INVERTER REVIEW
    # --------------------------------------------------------

    st.subheader(
        "⚡ Inverter Data"
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        inverter[
            "ac_rated_power_w"
        ] = st.number_input(
            "AC Rated Power W",
            value=safe_float(
                inverter.get(
                    "ac_rated_power_w"
                )
            ),
            key="review_ac_power",
        )

    with c2:

        inverter[
            "max_dc_voltage_v"
        ] = st.number_input(
            "Max DC Voltage V",
            value=safe_float(
                inverter.get(
                    "max_dc_voltage_v"
                )
            ),
            key="review_dc_voltage",
        )

    with c3:

        inverter[
            "mppt_voltage_min_v"
        ] = st.number_input(
            "MPPT Min V",
            value=safe_float(
                inverter.get(
                    "mppt_voltage_min_v"
                )
            ),
            key="review_mppt_min",
        )

    with c4:

        inverter[
            "mppt_voltage_max_v"
        ] = st.number_input(
            "MPPT Max V",
            value=safe_float(
                inverter.get(
                    "mppt_voltage_max_v"
                )
            ),
            key="review_mppt_max",
        )

    c1, c2 = st.columns(2)

    with c1:

        inverter[
            "start_voltage_v"
        ] = st.number_input(
            "Start Voltage V",
            value=safe_float(
                inverter.get(
                    "start_voltage_v"
                )
            ),
            key="review_start_voltage",
        )

    with c2:

        inverter[
            "mppt_count"
        ] = st.number_input(
            "Number of MPPT",
            min_value=1,
            max_value=32,
            value=max(
                1,
                safe_int(
                    inverter.get(
                        "mppt_count"
                    ),
                    1,
                ),
            ),
            key="review_mppt_count",
        )

    # --------------------------------------------------------
    # MPPT REVIEW
    # --------------------------------------------------------

    st.subheader(
        "🔀 MPPT Data"
    )

    existing_mppts = inverter.get(
        "mppts",
        [],
    )

    while len(existing_mppts) < int(
        inverter["mppt_count"]
    ):

        n = len(existing_mppts) + 1

        existing_mppts.append(
            {
                "mppt": n,
                "max_current_a": 0,
                "max_voltage_v":
                    inverter.get(
                        "max_dc_voltage_v",
                        0,
                    ),
                "max_short_circuit_current_a": 0,
                "max_strings": 0,
            }
        )

    existing_mppts = existing_mppts[
        : int(inverter["mppt_count"])
    ]

    reviewed_mppts = []

    for i, mppt in enumerate(
        existing_mppts,
        start=1,
    ):

        with st.expander(
            f"MPPT {i}",
            expanded=(
                i == 1
            ),
        ):

            c1, c2, c3, c4 = st.columns(4)

            with c1:

                mppt_current = st.number_input(
                    "Max Current A",
                    value=safe_float(
                        mppt.get(
                            "max_current_a"
                        )
                    ),
                    key=f"review_mppt_i_{i}",
                )

            with c2:

                mppt_voltage = st.number_input(
                    "Max Voltage V",
                    value=safe_float(
                        mppt.get(
                            "max_voltage_v"
                        )
                    ),
                    key=f"review_mppt_v_{i}",
                )

            with c3:

                mppt_isc = st.number_input(
                    "Max Isc A",
                    value=safe_float(
                        mppt.get(
                            "max_short_circuit_current_a"
                        )
                    ),
                    key=f"review_mppt_isc_{i}",
                )

            with c4:

                mppt_max_strings = st.number_input(
                    "Max Strings",
                    min_value=0,
                    value=max(
                        0,
                        safe_int(
                            mppt.get(
                                "max_strings"
                            )
                        )
                    ),
                    key=f"review_mppt_strings_{i}",
                )

            reviewed_mppts.append(
                {
                    "mppt": i,
                    "max_current_a":
                        mppt_current,
                    "max_voltage_v":
                        mppt_voltage,
                    "max_short_circuit_current_a":
                        mppt_isc,
                    "max_strings":
                        mppt_max_strings,
                }
            )

    inverter[
        "mppts"
    ] = reviewed_mppts

    # --------------------------------------------------------
    # BATTERY REVIEW
    # --------------------------------------------------------

    st.subheader(
        "🔋 Battery"
    )

    battery_enabled_ai = st.toggle(
        "تفعيل البطارية",
        value=bool(
            battery.get(
                "enabled",
                True,
            )
        ),
        key="review_battery_enabled",
    )

    battery[
        "enabled"
    ] = battery_enabled_ai

    if battery_enabled_ai:

        c1, c2, c3, c4 = st.columns(4)

        with c1:

            battery[
                "nominal_voltage_v"
            ] = st.number_input(
                "Battery Voltage V",
                value=safe_float(
                    battery.get(
                        "nominal_voltage_v"
                    )
                ),
                key="review_battery_voltage",
            )

        with c2:

            battery[
                "capacity_ah"
            ] = st.number_input(
                "Capacity Ah",
                value=safe_float(
                    battery.get(
                        "capacity_ah"
                    )
                ),
                key="review_battery_ah",
            )

        with c3:

            battery[
                "capacity_kwh"
            ] = st.number_input(
                "Capacity kWh",
                value=safe_float(
                    battery.get(
                        "capacity_kwh"
                    )
                ),
                key="review_battery_kwh",
            )

        with c4:

            battery[
                "recommended_dod_pct"
            ] = st.number_input(
                "DoD %",
                min_value=1.0,
                max_value=100.0,
                value=safe_float(
                    battery.get(
                        "recommended_dod_pct"
                    ),
                    80,
                ),
                key="review_battery_dod",
            )

    # --------------------------------------------------------
    # SITE
    # --------------------------------------------------------

    st.subheader(
        "🌍 Site"
    )

    site = extracted.setdefault(
        "site",
        {},
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        site[
            "min_temperature_c"
        ] = st.number_input(
            "Minimum Temp °C",
            value=safe_float(
                site.get(
                    "min_temperature_c"
                ),
                -5,
            ),
            key="review_min_temp",
        )

    with c2:

        site[
            "max_temperature_c"
        ] = st.number_input(
            "Maximum Temp °C",
            value=safe_float(
                site.get(
                    "max_temperature_c"
                ),
                45,
            ),
            key="review_max_temp",
        )

    with c3:

        site[
            "peak_sun_hours"
        ] = st.number_input(
            "Peak Sun Hours",
            min_value=0.1,
            value=safe_float(
                site.get(
                    "peak_sun_hours"
                ),
                5,
            ),
            key="review_psh",
        )

    with c4:

        site[
            "system_efficiency_pct"
        ] = st.number_input(
            "System Efficiency %",
            min_value=50.0,
            max_value=100.0,
            value=safe_float(
                site.get(
                    "system_efficiency_pct"
                ),
                80,
            ),
            key="review_efficiency",
        )

    # --------------------------------------------------------
    # APPROVE
    # --------------------------------------------------------

    extracted[
        "panel"
    ] = panel

    extracted[
        "inverter"
    ] = inverter

    extracted[
        "battery"
    ] = battery

    extracted[
        "site"
    ] = site

    if st.button(
        "✅ اعتماد البيانات والانتقال للتصميم",
        type="primary",
    ):

        st.session_state[
            "approved_data"
        ] = normalize_data(
            extracted
        )

        st.success(
            "تم اعتماد البيانات."
        )


# ============================================================
# STOP IF NO APPROVED DATA
# ============================================================

if st.session_state[
    "approved_data"
] is None:

    st.info(
        "أدخل البيانات أو اعتمد البيانات المستخرجة للمتابعة."
    )

    st.stop()


# ============================================================
# APPROVED DATA
# ============================================================

data = normalize_data(
    st.session_state[
        "approved_data"
    ]
)

panel = data[
    "panel"
]

inverter = data[
    "inverter"
]

battery = data[
    "battery"
]

site = data[
    "site"
]

loads = data.get(
    "loads",
    [],
)


# ============================================================
# ENGINEERING INPUTS
# ============================================================

pmax = safe_float(
    panel.get(
        "pmax_w"
    )
)

voc = safe_float(
    panel.get(
        "voc_v"
    )
)

vmp = safe_float(
    panel.get(
        "vmp_v"
    )
)

isc = safe_float(
    panel.get(
        "isc_a"
    )
)

imp = safe_float(
    panel.get(
        "imp_a"
    )
)

voc_coeff = safe_float(
    panel.get(
        "voc_temp_coeff_pct_per_c"
    )
)

vmp_coeff = safe_float(
    panel.get(
        "vmp_temp_coeff_pct_per_c"
    )
)

max_dc_voltage = safe_float(
    inverter.get(
        "max_dc_voltage_v"
    )
)

mppt_min_voltage = safe_float(
    inverter.get(
        "mppt_voltage_min_v"
    )
)

mppt_max_voltage = safe_float(
    inverter.get(
        "mppt_voltage_max_v"
    )
)

start_voltage = safe_float(
    inverter.get(
        "start_voltage_v"
    )
)

ac_power = safe_float(
    inverter.get(
        "ac_rated_power_w"
    )
)

mppts = inverter.get(
    "mppts",
    [],
)


# ============================================================
# TEMPERATURE CORRECTION
# ============================================================

min_temperature = safe_float(
    site.get(
        "min_temperature_c"
    ),
    -5,
)

max_temperature = safe_float(
    site.get(
        "max_temperature_c"
    ),
    45,
)


# Voc at cold temperature
#
# If coefficient is negative:
# Voc increases when temperature decreases.
# ============================================================

if voc > 0:

    if voc_coeff != 0:

        voc_cold_panel = (
            voc *
            (
                1
                +
                (
                    abs(voc_coeff)
                    / 100
                    *
                    (
                        25
                        -
                        min_temperature
                    )
                )
            )
        )

    else:

        voc_cold_panel = (
            voc *
            cold_safety_factor
        )

else:

    voc_cold_panel = 0


# Vmp at hot temperature
#
# Usually Vmp decreases with increasing temperature.
# ============================================================

if vmp > 0:

    if vmp_coeff != 0:

        vmp_hot_panel = (
            vmp *
            (
                1
                +
                (
                    vmp_coeff
                    / 100
                    *
                    (
                        max_temperature
                        -
                        25
                    )
                )
            )
        )

    else:

        vmp_hot_panel = vmp

else:

    vmp_hot_panel = 0


# ============================================================
# STRING MIN / MAX
# ============================================================

if vmp_hot_panel > 0 and mppt_min_voltage > 0:

    min_by_mppt = math.ceil(
        mppt_min_voltage /
        vmp_hot_panel
    )

else:

    min_by_mppt = 1


if vmp > 0 and mppt_max_voltage > 0:

    max_by_mppt = math.floor(
        mppt_max_voltage /
        vmp
    )

else:

    max_by_mppt = 999


if voc_cold_panel > 0 and max_dc_voltage > 0:

    max_by_dc = math.floor(
        max_dc_voltage /
        voc_cold_panel
    )

else:

    max_by_dc = 999


if vmp > 0 and start_voltage > 0:

    min_by_start = math.ceil(
        start_voltage /
        vmp
    )

else:

    min_by_start = 1


min_panels_per_string = max(
    1,
    min_by_mppt,
    min_by_start,
)

max_panels_per_string = min(
    max_by_mppt,
    max_by_dc,
)


# ============================================================
# MAIN DESIGN CONTROLS
# ============================================================

st.markdown("---")

st.header(
    "3️⃣ PV String Design"
)

if (
    max_panels_per_string
    < min_panels_per_string
):

    st.error(
        "🔴 لا يوجد عدد ألواح/سترينج صالح يحقق "
        "حدود MPPT و Max DC Voltage."
    )

    st.write(
        f"Minimum = {min_panels_per_string}"
    )

    st.write(
        f"Maximum = {max_panels_per_string}"
    )

    st.stop()


# ============================================================
# NUMBER OF PANELS PER STRING
# ============================================================

c1, c2, c3 = st.columns(3)

with c1:

    selected_panels_per_string = st.number_input(
        "عدد الألواح في كل String",
        min_value=int(
            min_panels_per_string
        ),
        max_value=int(
            max_panels_per_string
        ),
        value=int(
            min_panels_per_string
        ),
        step=1,
    )

with c2:

    st.metric(
        "الحد الأدنى",
        f"{min_panels_per_string} Panel/String",
    )

with c3:

    st.metric(
        "الحد الأقصى",
        f"{max_panels_per_string} Panel/String",
    )


# ============================================================
# TOTAL STRINGS
# ============================================================

total_strings = 0

for mppt in mppts:

    total_strings += max(
        1,
        safe_int(
            mppt.get(
                "strings"
            ),
            1,
        ),
    )


# ============================================================
# PV DESIGN CALCULATOR
# ============================================================

def calculate_design(
    panels_per_string,
    panel,
    inverter,
    mppts,
    site,
    battery,
    loads,
    current_safety_factor,
):

    pmax = safe_float(
        panel.get(
            "pmax_w"
        )
    )

    voc = safe_float(
        panel.get(
            "voc_v"
        )
    )

    vmp = safe_float(
        panel.get(
            "vmp_v"
        )
    )

    isc = safe_float(
        panel.get(
            "isc_a"
        )
    )

    imp = safe_float(
        panel.get(
            "imp_a"
        )
    )

    voc_coeff = safe_float(
        panel.get(
            "voc_temp_coeff_pct_per_c"
        )
    )

    vmp_coeff = safe_float(
        panel.get(
            "vmp_temp_coeff_pct_per_c"
        )
    )

    min_temp = safe_float(
        site.get(
            "min_temperature_c"
        ),
        -5,
    )

    max_temp = safe_float(
        site.get(
            "max_temperature_c"
        ),
        45,
    )

    mppt_min = safe_float(
        inverter.get(
            "mppt_voltage_min_v"
        )
    )

    mppt_max = safe_float(
        inverter.get(
            "mppt_voltage_max_v"
        )
    )

    max_dc = safe_float(
        inverter.get(
            "max_dc_voltage_v"
        )
    )

    start = safe_float(
        inverter.get(
            "start_voltage_v"
        )
    )

    ac_power = safe_float(
        inverter.get(
            "ac_rated_power_w"
        )
    )

    # --------------------------------------------------------
    # Temperature corrected panel values
    # --------------------------------------------------------

    if voc_coeff != 0:

        cold_voc_panel = (
            voc *
            (
                1
                +
                abs(voc_coeff)
                / 100
                *
                (
                    25
                    -
                    min_temp
                )
            )
        )

    else:

        cold_voc_panel = (
            voc *
            cold_safety_factor
        )

    if vmp_coeff != 0:

        hot_vmp_panel = (
            vmp *
            (
                1
                +
                vmp_coeff
                / 100
                *
                (
                    max_temp
                    -
                    25
                )
            )
        )

    else:

        hot_vmp_panel = vmp

    # --------------------------------------------------------
    # String electrical values
    # --------------------------------------------------------

    string_vmp = (
        panels_per_string *
        vmp
    )

    string_hot_vmp = (
        panels_per_string *
        hot_vmp_panel
    )

    string_voc = (
        panels_per_string *
        voc
    )

    string_cold_voc = (
        panels_per_string *
        cold_voc_panel
    )

    # --------------------------------------------------------
    # Total strings
    # --------------------------------------------------------

    total_strings = 0

    for mppt in mppts:

        total_strings += max(
            1,
            safe_int(
                mppt.get(
                    "strings"
                ),
                1,
            ),
        )

    total_panels = (
        total_strings *
        panels_per_string
    )

    pv_kw = (
        total_panels *
        pmax /
        1000
    )

    # --------------------------------------------------------
    # DC / AC
    # --------------------------------------------------------

    if ac_power > 0:

        dc_ac_ratio = (
            pv_kw /
            (
                ac_power /
                1000
            )
        )

    else:

        dc_ac_ratio = 0

    # --------------------------------------------------------
    # MPPT
    # --------------------------------------------------------

    mppt_results = []

    overall_mppt_status = "PASS"

    for index, mppt in enumerate(
        mppts,
        start=1,
    ):

        strings = max(
            1,
            safe_int(
                mppt.get(
                    "strings"
                ),
                1,
            ),
        )

        current_limit = safe_float(
            mppt.get(
                "max_current_a"
            )
        )

        voltage_limit = safe_float(
            mppt.get(
                "max_voltage_v"
            )
        )

        short_circuit_limit = safe_float(
            mppt.get(
                "max_short_circuit_current_a"
            )
        )

        max_strings = safe_int(
            mppt.get(
                "max_strings"
            )
        )

        if current_limit <= 0:

            current_limit = safe_float(
                inverter.get(
                    "max_mppt_current_a"
                )
            )

        if voltage_limit <= 0:

            voltage_limit = max_dc

        design_current = (
            strings *
            isc *
            current_safety_factor
        )

        operating_current = (
            strings *
            imp
        )

        short_circuit_design = (
            strings *
            isc
        )

        # Current check
        current_ok = (
            current_limit <= 0
            or
            design_current <=
            current_limit
        )

        # Short circuit check
        isc_ok = (
            short_circuit_limit <= 0
            or
            short_circuit_design <=
            short_circuit_limit
        )

        # Voltage check
        voltage_ok = (
            voltage_limit <= 0
            or
            string_cold_voc <=
            voltage_limit
        )

        # MPPT operating window
        mppt_window_ok = (
            (
                mppt_min <= 0
                or
                string_hot_vmp >=
                mppt_min
            )
            and
            (
                mppt_max <= 0
                or
                string_vmp <=
                mppt_max
            )
        )

        # Max strings
        strings_count_ok = (
            max_strings <= 0
            or
            strings <= max_strings
        )

        statuses = [
            current_ok,
            isc_ok,
            voltage_ok,
            mppt_window_ok,
            strings_count_ok,
        ]

        if all(statuses):

            status = "PASS"

        elif any(
            x is False
            for x in statuses
        ):

            status = "FAIL"

            overall_mppt_status = "FAIL"

        else:

            status = "WARNING"

            if overall_mppt_status != "FAIL":
                overall_mppt_status = "WARNING"

        mppt_results.append(
            {
                "MPPT":
                    index,

                "Strings":
                    strings,

                "Panels/String":
                    panels_per_string,

                "Total Panels":
                    strings *
                    panels_per_string,

                "Vmp String V":
                    round(
                        string_vmp,
                        2,
                    ),

                "Hot Vmp String V":
                    round(
                        string_hot_vmp,
                        2,
                    ),

                "Voc String V":
                    round(
                        string_voc,
                        2,
                    ),

                "Cold Voc String V":
                    round(
                        string_cold_voc,
                        2,
                    ),

                "Operating Current A":
                    round(
                        operating_current,
                        2,
                    ),

                "Design Current A":
                    round(
                        design_current,
                        2,
                    ),

                "Max Current A":
                    round(
                        current_limit,
                        2,
                    ),

                "Design Isc A":
                    round(
                        short_circuit_design,
                        2,
                    ),

                "Max Isc A":
                    round(
                        short_circuit_limit,
                        2,
                    ),

                "Current":
                    "PASS"
                    if current_ok
                    else "FAIL",

                "Isc":
                    "PASS"
                    if isc_ok
                    else "FAIL",

                "Voltage":
                    "PASS"
                    if voltage_ok
                    else "FAIL",

                "MPPT Window":
                    "PASS"
                    if mppt_window_ok
                    else "FAIL",

                "Strings Limit":
                    "PASS"
                    if strings_count_ok
                    else "FAIL",

                "Status":
                    status,
            }
        )

    # --------------------------------------------------------
    # Daily load
    # --------------------------------------------------------

    daily_load_kwh = 0

    peak_load_w = 0

    for load in loads:

        power = safe_float(
            load.get(
                "power_w"
            )
        )

        qty = safe_float(
            load.get(
                "quantity"
            ),
            1,
        )

        hours = safe_float(
            load.get(
                "hours_per_day"
            )
        )

        daily_load_kwh += (
            power *
            qty *
            hours /
            1000
        )

        peak_load_w += (
            power *
            qty
        )

    # --------------------------------------------------------
    # PV energy
    # --------------------------------------------------------

    psh = safe_float(
        site.get(
            "peak_sun_hours"
        )
    )

    efficiency = (
        safe_float(
            site.get(
                "system_efficiency_pct"
            ),
            80,
        )
        /
        100
    )

    estimated_pv_energy = (
        pv_kw *
        psh *
        efficiency
    )

    if (
        daily_load_kwh > 0
        and psh > 0
        and efficiency > 0
    ):

        required_pv_kw = (
            daily_load_kwh /
            psh /
            efficiency
        )

    else:

        required_pv_kw = 0

    # --------------------------------------------------------
    # Battery
    # --------------------------------------------------------

    battery_enabled = bool(
        battery.get(
            "enabled",
            False,
        )
    )

    battery_status = "DISABLED"

    required_battery_kwh = 0

    actual_battery_kwh = 0

    battery_voltage = 0

    if battery_enabled:

        battery_voltage = safe_float(
            battery.get(
                "nominal_voltage_v"
            )
        )

        battery_ah = safe_float(
            battery.get(
                "capacity_ah"
            )
        )

        actual_battery_kwh = safe_float(
            battery.get(
                "capacity_kwh"
            )
        )

        if (
            actual_battery_kwh <= 0
            and
            battery_voltage > 0
            and
            battery_ah > 0
        ):

            actual_battery_kwh = (
                battery_voltage *
                battery_ah /
                1000
            )

        dod = safe_float(
            battery.get(
                "recommended_dod_pct"
            ),
            80,
        )

        autonomy_days = safe_float(
            battery.get(
                "autonomy_days"
            ),
            1,
        )

        if daily_load_kwh > 0:

            required_battery_kwh = (
                daily_load_kwh *
                autonomy_days /
                (
                    dod /
                    100
                )
            )

        if required_battery_kwh <= 0:

            battery_status = "WARNING"

        elif actual_battery_kwh >= required_battery_kwh:

            battery_status = "PASS"

        else:

            battery_status = "FAIL"

    # --------------------------------------------------------
    # Overall
    # --------------------------------------------------------

    fail_count = 0
    warning_count = 0

    for row in mppt_results:

        if row["Status"] == "FAIL":
            fail_count += 1

        elif row["Status"] == "WARNING":
            warning_count += 1

    # PV sizing
    if (
        required_pv_kw > 0
        and pv_kw < required_pv_kw
    ):

        fail_count += 1

    # Battery
    if battery_enabled:

        if battery_status == "FAIL":

            fail_count += 1

        elif battery_status == "WARNING":

            warning_count += 1

    # DC / AC
    if dc_ac_ratio > 0:

        if (
            dc_ac_ratio < 0.8
            or
            dc_ac_ratio > 1.5
        ):

            warning_count += 1

    if fail_count > 0:

        overall_status = "FAIL"

    elif warning_count > 0:

        overall_status = "WARNING"

    else:

        overall_status = "PASS"

    return {
        "panels_per_string":
            panels_per_string,

        "total_strings":
            total_strings,

        "total_panels":
            total_panels,

        "pv_kw":
            pv_kw,

        "dc_ac_ratio":
            dc_ac_ratio,

        "string_vmp":
            string_vmp,

        "string_hot_vmp":
            string_hot_vmp,

        "string_voc":
            string_voc,

        "string_cold_voc":
            string_cold_voc,

        "cold_voc_panel":
            cold_voc_panel,

        "hot_vmp_panel":
            hot_vmp_panel,

        "mppt_results":
            mppt_results,

        "daily_load_kwh":
            daily_load_kwh,

        "peak_load_w":
            peak_load_w,

        "estimated_pv_energy":
            estimated_pv_energy,

        "required_pv_kw":
            required_pv_kw,

        "battery_enabled":
            battery_enabled,

        "battery_status":
            battery_status,

        "battery_voltage":
            battery_voltage,

        "actual_battery_kwh":
            actual_battery_kwh,

        "required_battery_kwh":
            required_battery_kwh,

        "overall_status":
            overall_status,

        "fail_count":
            fail_count,

        "warning_count":
            warning_count,
    }


# ============================================================
# CURRENT DESIGN CALCULATION
# ============================================================

current_result = calculate_design(
    panels_per_string=int(
        selected_panels_per_string
    ),
    panel=panel,
    inverter=inverter,
    mppts=mppts,
    site=site,
    battery=battery,
    loads=loads,
    current_safety_factor=
        current_safety_factor,
)


# ============================================================
# MAIN RESULT
# ============================================================

st.markdown("---")

st.header(
    "4️⃣ نتيجة التصميم الحالية"
)

status = current_result[
    "overall_status"
]

if status == "PASS":

    st.success(
        "🟢 DESIGN STATUS — PASS"
    )

elif status == "WARNING":

    st.warning(
        "🟡 DESIGN STATUS — WARNING"
    )

else:

    st.error(
        "🔴 DESIGN STATUS — FAIL"
    )


# ============================================================
# MAIN METRICS
# ============================================================

c1, c2, c3, c4, c5, c6 = st.columns(6)

with c1:

    st.metric(
        "Panels/String",
        current_result[
            "panels_per_string"
        ],
    )

with c2:

    st.metric(
        "Total Strings",
        current_result[
            "total_strings"
        ],
    )

with c3:

    st.metric(
        "Total Panels",
        current_result[
            "total_panels"
        ],
    )

with c4:

    st.metric(
        "PV Capacity",
        f'{current_result["pv_kw"]:.2f} kWp',
    )

with c5:

    st.metric(
        "DC / AC",
        f'{current_result["dc_ac_ratio"]:.2f}',
    )

with c6:

    st.metric(
        "Status",
        status_icon(
            status
        ),
    )


# ============================================================
# CURRENT ELECTRICAL VALUES
# ============================================================

st.subheader(
    "📐 قراءات الـString الحالية"
)

c1, c2, c3, c4, c5 = st.columns(5)

with c1:

    st.metric(
        "Vmp/String",
        f'{current_result["string_vmp"]:.1f} V',
    )

with c2:

    st.metric(
        "Hot Vmp/String",
        f'{current_result["string_hot_vmp"]:.1f} V',
    )

with c3:

    st.metric(
        "Voc/String",
        f'{current_result["string_voc"]:.1f} V',
    )

with c4:

    st.metric(
        "Cold Voc/String",
        f'{current_result["string_cold_voc"]:.1f} V',
    )

with c5:

    st.metric(
        "Estimated PV Energy",
        f'{current_result["estimated_pv_energy"]:.2f} kWh/day',
    )


# ============================================================
# MPPT RESULTS
# ============================================================

st.subheader(
    "🔀 MPPT Verification"
)

mppt_table = current_result[
    "mppt_results"
]

if mppt_table:

    st.dataframe(
        mppt_table,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# MPPT DETAILED STATUS
# ============================================================

st.subheader(
    "🔎 تفاصيل كل MPPT"
)

for row in mppt_table:

    mppt_status = row[
        "Status"
    ]

    title = (
        f'MPPT {row["MPPT"]} — '
        f'{status_icon(mppt_status)}'
    )

    with st.expander(
        title,
        expanded=(
            mppt_status == "FAIL"
        ),
    ):

        c1, c2, c3, c4 = st.columns(4)

        with c1:

            st.metric(
                "Strings",
                row[
                    "Strings"
                ],
            )

        with c2:

            st.metric(
                "Panels",
                row[
                    "Total Panels"
                ],
            )

        with c3:

            st.metric(
                "Design Current",
                f'{row["Design Current A"]:.2f} A',
            )

        with c4:

            st.metric(
                "Max Current",
                f'{row["Max Current A"]:.2f} A',
            )

        st.write(
            f'**Cold Voc:** '
            f'{row["Cold Voc String V"]:.2f} V'
        )

        st.write(
            f'**Hot Vmp:** '
            f'{row["Hot Vmp String V"]:.2f} V'
        )

        if row["Current"] == "FAIL":

            st.error(
                "تيار الـMPPT يتجاوز الحد."
            )

        if row["Isc"] == "FAIL":

            st.error(
                "Isc التصميمي يتجاوز الحد."
            )

        if row["Voltage"] == "FAIL":

            st.error(
                "Cold Voc يتجاوز Max Voltage."
            )

        if row["MPPT Window"] == "FAIL":

            st.error(
                "جهد التشغيل خارج نطاق MPPT."
            )

        if row["Strings Limit"] == "FAIL":

            st.error(
                "عدد Strings يتجاوز الحد المسموح."
            )

        if mppt_status == "PASS":

            st.success(
                "جميع فحوصات MPPT ناجحة."
            )


# ============================================================
# SCENARIO TABLE
# ============================================================

st.markdown("---")

st.header(
    "5️⃣ مقارنة عدد الألواح"
)

st.info(
    "هذا الجدول مهم جداً: يمكنك رؤية ماذا يحدث عند "
    "تقليل أو زيادة عدد الألواح داخل الـString، "
    "بدون إعادة إدخال البيانات."
)

scenario_rows = []

for n in range(
    int(min_panels_per_string),
    int(max_panels_per_string) + 1,
):

    scenario = calculate_design(
        panels_per_string=n,
        panel=panel,
        inverter=inverter,
        mppts=mppts,
        site=site,
        battery=battery,
        loads=loads,
        current_safety_factor=
            current_safety_factor,
    )

    scenario_rows.append(
        {
            "Panels/String":
                n,

            "Total Panels":
                scenario[
                    "total_panels"
                ],

            "PV kWp":
                round(
                    scenario[
                        "pv_kw"
                    ],
                    2,
                ),

            "Vmp/String":
                round(
                    scenario[
                        "string_vmp"
                    ],
                    1,
                ),

            "Hot Vmp":
                round(
                    scenario[
                        "string_hot_vmp"
                    ],
                    1,
                ),

            "Voc/String":
                round(
                    scenario[
                        "string_voc"
                    ],
                    1,
                ),

            "Cold Voc":
                round(
                    scenario[
                        "string_cold_voc"
                    ],
                    1,
                ),

            "PV Energy kWh/day":
                round(
                    scenario[
                        "estimated_pv_energy"
                    ],
                    2,
                ),

            "DC/AC":
                round(
                    scenario[
                        "dc_ac_ratio"
                    ],
                    2,
                ),

            "Required PV kWp":
                round(
                    scenario[
                        "required_pv_kw"
                    ],
                    2,
                ),

            "Status":
                status_icon(
                    scenario[
                        "overall_status"
                    ]
                ),
        }
    )


st.dataframe(
    scenario_rows,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# SCENARIO DETAILS
# ============================================================

st.subheader(
    "📊 تجربة سيناريو معين"
)

scenario_number = st.slider(
    "اختر عدد الألواح/سترينج لرؤية التفاصيل",
    min_value=int(
        min_panels_per_string
    ),
    max_value=int(
        max_panels_per_string
    ),
    value=int(
        selected_panels_per_string
    ),
    step=1,
)

selected_scenario = calculate_design(
    panels_per_string=
        int(scenario_number),
    panel=panel,
    inverter=inverter,
    mppts=mppts,
    site=site,
    battery=battery,
    loads=loads,
    current_safety_factor=
        current_safety_factor,
)

c1, c2, c3, c4, c5 = st.columns(5)

with c1:

    st.metric(
        "Panels/String",
        scenario_number,
    )

with c2:

    st.metric(
        "PV",
        f'{selected_scenario["pv_kw"]:.2f} kWp',
    )

with c3:

    st.metric(
        "Vmp",
        f'{selected_scenario["string_vmp"]:.1f} V',
    )

with c4:

    st.metric(
        "Cold Voc",
        f'{selected_scenario["string_cold_voc"]:.1f} V',
    )

with c5:

    st.metric(
        "Status",
        status_icon(
            selected_scenario[
                "overall_status"
            ]
        ),
    )


# ============================================================
# LOAD ANALYSIS
# ============================================================

st.markdown("---")

st.header(
    "6️⃣ Load Analysis"
)

daily_load = current_result[
    "daily_load_kwh"
]

peak_load = current_result[
    "peak_load_w"
]

c1, c2, c3 = st.columns(3)

with c1:

    st.metric(
        "Daily Energy",
        f"{daily_load:.2f} kWh/day",
    )

with c2:

    st.metric(
        "Peak Load",
        f"{peak_load:.0f} W",
    )

with c3:

    st.metric(
        "Required PV",
        f'{current_result["required_pv_kw"]:.2f} kWp',
    )


if loads:

    load_rows = []

    for load in loads:

        power = safe_float(
            load.get(
                "power_w"
            )
        )

        qty = safe_float(
            load.get(
                "quantity"
            ),
            1,
        )

        hours = safe_float(
            load.get(
                "hours_per_day"
            )
        )

        energy = (
            power *
            qty *
            hours /
            1000
        )

        load_rows.append(
            {
                "Load":
                    load.get(
                        "name",
                        "",
                    ),

                "Quantity":
                    qty,

                "Power W":
                    power,

                "Hours/day":
                    hours,

                "Energy kWh/day":
                    round(
                        energy,
                        3,
                    ),
            }
        )

    st.dataframe(
        load_rows,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# BATTERY ANALYSIS
# ============================================================

st.markdown("---")

st.header(
    "7️⃣ Battery Analysis"
)

battery_enabled = bool(
    battery.get(
        "enabled",
        False,
    )
)

if not battery_enabled:

    st.info(
        "🔵 البطارية غير مفعلة. "
        "تم تجاهل جميع حسابات البطارية."
    )

else:

    battery_voltage = current_result[
        "battery_voltage"
    ]

    actual_battery_kwh = current_result[
        "actual_battery_kwh"
    ]

    required_battery_kwh = current_result[
        "required_battery_kwh"
    ]

    battery_status = current_result[
        "battery_status"
    ]

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "Battery Voltage",
            f"{battery_voltage:.1f} V",
        )

    with c2:

        st.metric(
            "Available",
            f"{actual_battery_kwh:.2f} kWh",
        )

    with c3:

        st.metric(
            "Required",
            f"{required_battery_kwh:.2f} kWh",
        )

    with c4:

        st.metric(
            "Status",
            status_icon(
                battery_status
            ),
        )

    if battery_status == "PASS":

        st.success(
            "سعة البطارية تحقق المتطلب المبدئي."
        )

    elif battery_status == "FAIL":

        st.error(
            "سعة البطارية أقل من المتطلب."
        )

    else:

        st.warning(
            "بيانات البطارية غير كافية لإجراء فحص كامل."
        )


# ============================================================
# DESIGN SUMMARY
# ============================================================

st.markdown("---")

st.header(
    "8️⃣ Final Design Summary"
)

summary = {
    "Panel": (
        f'{panel.get("brand", "")} '
        f'{panel.get("model", "")}'
    ),

    "Panel Power W":
        pmax,

    "Panel Voc V":
        voc,

    "Panel Vmp V":
        vmp,

    "Panel Isc A":
        isc,

    "Panel Imp A":
        imp,

    "Minimum Panels/String":
        min_panels_per_string,

    "Maximum Panels/String":
        max_panels_per_string,

    "Selected Panels/String":
        selected_panels_per_string,

    "Total MPPT":
        len(mppts),

    "Total Strings":
        current_result[
            "total_strings"
        ],

    "Total Panels":
        current_result[
            "total_panels"
        ],

    "PV Capacity kWp":
        round(
            current_result[
                "pv_kw"
            ],
            3,
        ),

    "DC/AC Ratio":
        round(
            current_result[
                "dc_ac_ratio"
            ],
            3,
        ),

    "String Vmp V":
        round(
            current_result[
                "string_vmp"
            ],
            2,
        ),

    "String Cold Voc V":
        round(
            current_result[
                "string_cold_voc"
            ],
            2,
        ),

    "Daily Load kWh":
        round(
            current_result[
                "daily_load_kwh"
            ],
            3,
        ),

    "Required PV kWp":
        round(
            current_result[
                "required_pv_kw"
            ],
            3,
        ),

    "Battery Enabled":
        battery_enabled,

    "Design Status":
        status,
}

st.json(
    summary
)


# ============================================================
# EXPORT JSON
# ============================================================

st.markdown("---")

st.header(
    "9️⃣ Export"
)

export_data = {
    "input_data":
        data,

    "design":
        summary,

    "mppt_results":
        current_result[
            "mppt_results"
        ],

    "scenarios":
        scenario_rows,
}

export_json = json.dumps(
    export_data,
    ensure_ascii=False,
    indent=2,
)

st.download_button(
    "⬇️ تحميل تقرير التصميم JSON",
    data=export_json,
    file_name="solar_design_report.json",
    mime="application/json",
)


# ============================================================
# ENGINEERING DISCLAIMER
# ============================================================

st.markdown("---")

st.warning(
    """
⚠️ **تنبيه هندسي**

هذه الأداة مخصصة للتصميم والتحقق المبدئي.

قبل التنفيذ الفعلي يجب مراجعة:

• Datasheet الأصلي للوح والإنفيرتر والبطارية  
• معامل الحرارة الفعلي  
• أقل وأعلى درجة حرارة للموقع  
• Ampacity للكابلات  
• DC/AC breakers  
• DC/AC isolators  
• SPD  
• String fuses  
• Earthing  
• Short Circuit calculations  
• Voltage drop  
• متطلبات شركة الكهرباء  
• الكود الكهربائي المحلي  

لا تعتمد اختيار الكابل أو الفيوز أو القاطع أو SPD للتنفيذ النهائي اعتماداً
على هذه الأداة وحدها.
"""
)
