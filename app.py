import json
import math
import time

import streamlit as st
from PIL import Image

try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False


# ============================================================
# 1. PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Solar System Designer & Checker",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# 2. STYLE
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
        border-radius: 8px;
        font-weight: bold;
        min-height: 42px;
    }

    div[data-testid="stMetric"] {
        direction: rtl;
    }

    .small-note {
        font-size: 0.85rem;
        color: #666;
    }

    .good-box {
        padding: 12px;
        border-radius: 8px;
        border: 1px solid #2e7d32;
        background: rgba(46, 125, 50, 0.08);
    }

    .warning-box {
        padding: 12px;
        border-radius: 8px;
        border: 1px solid #ef6c00;
        background: rgba(239, 108, 0, 0.08);
    }

    .bad-box {
        padding: 12px;
        border-radius: 8px;
        border: 1px solid #c62828;
        background: rgba(198, 40, 40, 0.08);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 3. INITIAL SESSION STATE
# ============================================================

DEFAULTS = {
    "analysis_result": None,
    "battery_enabled": False,
    "custom_panels": None,
    "number_of_mppts": 1,
    "manual_mppt_strings": [1],
    "cold_factor": 1.15,
    "voltage_margin": 0.95,
    "mppt_margin": 1.10,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# 4. HELPERS
# ============================================================

def safe_float(value, default=0.0):
    if value is None:
        return default

    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_text(value, default="غير معروف"):
    if value is None:
        return default

    text = str(value).strip()

    if not text:
        return default

    return text


def clamp(value, low, high):
    return max(low, min(high, value))


def fmt(value, digits=2):
    if value is None:
        return "—"

    try:
        return f"{float(value):,.{digits}f}"
    except Exception:
        return str(value)


def clean_old_session_state():
    """
    حماية من القيم القديمة في session_state.
    خصوصاً DoD من الإصدارات السابقة.
    """
    if "review_battery_dod" in st.session_state:
        try:
            old = float(st.session_state["review_battery_dod"])
            st.session_state["review_battery_dod"] = clamp(old, 50.0, 95.0)
        except Exception:
            st.session_state["review_battery_dod"] = 80.0

    if "dod_pct" in st.session_state:
        try:
            old = float(st.session_state["dod_pct"])
            st.session_state["dod_pct"] = int(clamp(old, 50, 95))
        except Exception:
            st.session_state["dod_pct"] = 80


clean_old_session_state()


# ============================================================
# 5. BATTERY VOLTAGE CHECK
# ============================================================

def battery_voltage_class(voltage):
    voltage = safe_float(voltage)

    if 10 <= voltage <= 15:
        return "12V"

    if 20 <= voltage <= 30:
        return "24V"

    if 40 <= voltage <= 60:
        return "48V / 51.2V"

    if voltage >= 100:
        return "HV"

    return "غير محدد"


def check_battery_voltage(inverter_voltage, battery_voltage):
    inv_v = safe_float(inverter_voltage)
    bat_v = safe_float(battery_voltage)

    if inv_v <= 0 or bat_v <= 0:
        return None, "لا توجد بيانات جهد كافية للحكم على التوافق."

    inv_class = battery_voltage_class(inv_v)
    bat_class = battery_voltage_class(bat_v)

    if inv_class == bat_class and inv_class != "غير محدد":
        return True, (
            f"جهد البطارية {bat_v:g}V يقع ضمن فئة "
            f"{bat_class} المتوافقة مع جهد النظام {inv_v:g}V."
        )

    if abs(inv_v - bat_v) <= 5:
        return True, (
            f"الجهدان متقاربان: الإنفيرتر {inv_v:g}V "
            f"والبطارية {bat_v:g}V."
        )

    return False, (
        f"اختلاف محتمل في جهد البطارية: "
        f"الإنفيرتر {inv_v:g}V مقابل البطارية {bat_v:g}V."
    )


# ============================================================
# 6. STRING ENGINEERING
# ============================================================

def calculate_string_limits(
    voc,
    vmp,
    v_max,
    v_mppt_min,
    v_mppt_max,
):
    if voc <= 0 or vmp <= 0 or v_max <= 0:
        return None

    cold_factor = safe_float(
        st.session_state.get("cold_factor", 1.15),
        1.15
    )

    voltage_margin = safe_float(
        st.session_state.get("voltage_margin", 0.95),
        0.95
    )

    mppt_margin = safe_float(
        st.session_state.get("mppt_margin", 1.10),
        1.10
    )

    safe_mppt_min = (
        v_mppt_min * mppt_margin
        if v_mppt_min > 0
        else 0
    )

    min_series = (
        math.ceil(safe_mppt_min / vmp)
        if safe_mppt_min > 0
        else 1
    )

    cold_voc_panel = voc * cold_factor

    safe_dc_max = v_max * voltage_margin

    max_by_voc = (
        math.floor(safe_dc_max / cold_voc_panel)
        if cold_voc_panel > 0
        else 999
    )

    max_by_mppt = (
        math.floor(v_mppt_max / vmp)
        if v_mppt_max > 0
        else 999
    )

    max_series = min(max_by_voc, max_by_mppt)

    return {
        "min_series": max(1, min_series),
        "max_series": max(1, max_series),
        "cold_voc_panel": cold_voc_panel,
        "safe_dc_max": safe_dc_max,
        "safe_mppt_min": safe_mppt_min,
        "cold_factor": cold_factor,
        "voltage_margin": voltage_margin,
        "mppt_margin": mppt_margin,
    }


# ============================================================
# 7. MPPT / STRING DISTRIBUTION
# ============================================================

def build_mppt_config(mppt_count, string_counts):
    """
    يحول:
    [1, 2, 1]
    إلى:
    MPPT1 = 1 string
    MPPT2 = 2 strings
    MPPT3 = 1 string
    """

    mppt_count = max(1, safe_int(mppt_count, 1))

    result = []

    for i in range(mppt_count):
        if i < len(string_counts):
            count = max(1, safe_int(string_counts[i], 1))
        else:
            count = 1

        result.append(count)

    return result


def distribute_panels(total_panels, mppt_string_counts):
    """
    توزيع الألواح بالتساوي قدر الإمكان على كل Strings.
    """

    total_panels = max(1, safe_int(total_panels, 1))

    total_strings = sum(mppt_string_counts)

    if total_strings <= 0:
        return []

    base = total_panels // total_strings
    remainder = total_panels % total_strings

    rows = []

    string_id = 1

    for mppt_no, string_count in enumerate(mppt_string_counts, 1):

        for local_string in range(1, string_count + 1):

            panels = base

            if string_id <= remainder:
                panels += 1

            rows.append(
                {
                    "MPPT": mppt_no,
                    "String": local_string,
                    "Global String": string_id,
                    "Panels": panels,
                }
            )

            string_id += 1

    return rows


# ============================================================
# 8. STRING VALIDATION
# ============================================================

def evaluate_strings(
    rows,
    pmax,
    voc,
    vmp,
    isc,
    v_max,
    mppt_min,
    mppt_max,
    max_mppt_current,
):
    errors = []
    warnings = []

    for row in rows:

        n = row["Panels"]
        mppt = row["MPPT"]
        string_no = row["String"]

        if n <= 0:
            errors.append(
                f"MPPT {mppt} / String {string_no}: "
                f"لا توجد ألواح."
            )
            continue

        string_vmp = n * vmp
        string_voc_cold = n * voc * st.session_state.get(
            "cold_factor", 1.15
        )

        # Minimum MPPT
        safe_min = (
            mppt_min
            * st.session_state.get("mppt_margin", 1.10)
        )

        if mppt_min > 0 and string_vmp < safe_min:
            errors.append(
                f"MPPT {mppt} / String {string_no}: "
                f"Vmp = {string_vmp:.1f}V أقل من "
                f"الحد الآمن للـ MPPT ({safe_min:.1f}V)."
            )

        # MPPT maximum
        if mppt_max > 0 and string_vmp > mppt_max:
            errors.append(
                f"MPPT {mppt} / String {string_no}: "
                f"Vmp = {string_vmp:.1f}V يتجاوز "
                f"MPPT Max = {mppt_max:.1f}V."
            )

        # DC maximum
        safe_vmax = (
            v_max
            * st.session_state.get("voltage_margin", 0.95)
        )

        if v_max > 0 and string_voc_cold > safe_vmax:
            errors.append(
                f"MPPT {mppt} / String {string_no}: "
                f"Voc البارد ≈ {string_voc_cold:.1f}V "
                f"يتجاوز الحد الآمن ≈ {safe_vmax:.1f}V."
            )

    # MPPT current
    by_mppt = {}

    for row in rows:
        by_mppt.setdefault(row["MPPT"], []).append(row)

    for mppt_no, mppt_rows in by_mppt.items():

        string_count = len(mppt_rows)

        design_current = string_count * isc * 1.25

        if (
            max_mppt_current > 0
            and design_current > max_mppt_current
        ):
            errors.append(
                f"MPPT {mppt_no}: "
                f"التيار التصميمي ≈ {design_current:.2f}A "
                f"أعلى من الحد {max_mppt_current:.2f}A."
            )

    return errors, warnings


# ============================================================
# 9. BATTERY CALCULATOR
# ============================================================

def calculate_battery(
    battery_voltage,
    battery_ah,
    battery_kwh,
    max_discharge,
    daily_load_kwh,
    autonomy_hours,
    dod,
    efficiency,
    peak_load_kw,
):
    if daily_load_kwh <= 0:
        return None

    if autonomy_hours <= 0:
        return None

    avg_load_w = daily_load_kwh * 1000 / 24

    required_load_wh = avg_load_w * autonomy_hours

    efficiency = max(0.1, efficiency)

    required_from_battery_wh = (
        required_load_wh / efficiency
    )

    dod = clamp(dod, 0.05, 1.0)

    required_nominal_wh = (
        required_from_battery_wh / dod
    )

    if battery_kwh > 0:
        unit_wh = battery_kwh * 1000

    elif battery_voltage > 0 and battery_ah > 0:
        unit_wh = battery_voltage * battery_ah

    else:
        unit_wh = 0

    battery_count = (
        math.ceil(required_nominal_wh / unit_wh)
        if unit_wh > 0
        else 0
    )

    total_kwh = (
        battery_count * unit_wh / 1000
        if unit_wh > 0
        else 0
    )

    theoretical_power = (
        battery_voltage * max_discharge
        if battery_voltage > 0 and max_discharge > 0
        else 0
    )

    return {
        "average_load_w": avg_load_w,
        "required_nominal_kwh": required_nominal_wh / 1000,
        "unit_kwh": unit_wh / 1000 if unit_wh else 0,
        "battery_count": battery_count,
        "total_kwh": total_kwh,
        "theoretical_power_w": theoretical_power,
        "peak_load_kw": peak_load_kw,
    }


# ============================================================
# 10. JSON STRUCTURE FOR GEMINI
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
    "imp": 0
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
    "mppt_strings_config": [1],
    "max_mppt_current": 0,

    "battery": {
      "supported": false,
      "nominal_voltage_v": 0,
      "battery_type": "",
      "max_charge_current_a": 0
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
# 11. IMAGE COMPRESSION
# ============================================================

def compress_image(img, max_dim=1200):
    copied = img.copy()

    copied.thumbnail(
        (max_dim, max_dim),
        Image.Resampling.LANCZOS
    )

    return copied


# ============================================================
# 12. GEMINI IMAGE EXTRACTION
# ============================================================

def extract_from_images(
    panel_img,
    inverter_img,
    battery_img,
    api_key,
):
    if not GEMINI_AVAILABLE:
        raise RuntimeError(
            "حزمة google-genai غير مثبتة."
        )

    client = genai.Client(api_key=api_key)

    contents = [
        compress_image(panel_img),
        compress_image(inverter_img),
    ]

    if battery_img is not None:
        contents.append(compress_image(battery_img))

    prompt = f"""
أنت مهندس تصميم وفحص منظومات طاقة شمسية.

حلل الصور المرفقة بدقة.

الصور قد تحتوي على:
1. Solar Panel
2. Solar Inverter
3. External Battery إذا تم إرفاقها

استخرج بيانات الملصقات فقط، ولا تخمن المواصفات
إذا لم تكن ظاهرة.

أعد JSON فقط وفق الهيكل التالي:

{JSON_STRUCTURE}

قواعد مهمة:
- الأرقام بدون وحدات.
- إذا لم تجد قيمة رقمية ضع 0.
- إذا لم تجد نصاً ضع "غير معروف".
- mppt_count يجب أن يمثل عدد MPPT الحقيقي إذا ظهر.
- mppt_strings_config يجب أن يحتوي عدد الـ Strings لكل MPPT
  إذا كانت المعلومات موجودة.
- لا تخترع بيانات غير موجودة في الصور.
"""

    contents.append(prompt)

    response = client.models.generate_content(
        model="models/gemini-3.6-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0,
        ),
    )

    return json.loads(response.text)


# ============================================================
# 13. GEMINI TEXT EXTRACTION
# ============================================================

def extract_from_text(
    panel_query,
    inverter_query,
    battery_query,
    api_key,
):
    if not GEMINI_AVAILABLE:
        raise RuntimeError(
            "حزمة google-genai غير مثبتة."
        )

    client = genai.Client(api_key=api_key)

    battery_part = (
        f'البطارية الخارجية: "{battery_query}"'
        if battery_query
        else "لا توجد بطارية خارجية."
    )

    prompt = f"""
أنت مهندس طاقة شمسية متخصص في Datasheets.

ابحث/حلل المواصفات للموديلات التالية:

Solar Panel:
{panel_query}

Inverter:
{inverter_query}

{battery_part}

أعد JSON فقط وفق:

{JSON_STRUCTURE}

مهم جداً:
- لا تخترع قيمة إذا لم تكن متأكداً منها.
- القيم الرقمية أرقام فقط.
- القيم المفقودة = 0.
- النصوص المفقودة = "غير معروف".
- يجب تحديد MPPT Count.
- إذا كان لكل MPPT عدد Strings مختلف، استخدم
  mppt_strings_config مثل:
  [1,2,1]
- إذا كانت البيانات غير معروفة استخدم [1].
"""

    response = client.models.generate_content(
        model="models/gemini-3.6-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0,
        ),
    )

    return json.loads(response.text)


# ============================================================
# 14. MANUAL INPUT
# ============================================================

def manual_input_section(battery_enabled):
    st.info(
        "🧮 الإدخال اليدوي مستقل عن Gemini ولا يحتاج مفتاح API."
    )

    # -------------------------
    # PANEL
    # -------------------------

    st.markdown("## ☀️ مواصفات اللوح الشمسي")

    c = st.columns(5)

    pmax = c[0].number_input(
        "Pmax (W)",
        min_value=0.0,
        value=550.0,
        step=10.0,
        key="manual_pmax",
    )

    voc = c[1].number_input(
        "Voc (V)",
        min_value=0.0,
        value=49.5,
        step=0.1,
        key="manual_voc",
    )

    vmp = c[2].number_input(
        "Vmp (V)",
        min_value=0.0,
        value=41.5,
        step=0.1,
        key="manual_vmp",
    )

    isc = c[3].number_input(
        "Isc (A)",
        min_value=0.0,
        value=14.0,
        step=0.1,
        key="manual_isc",
    )

    imp = c[4].number_input(
        "Imp (A)",
        min_value=0.0,
        value=13.3,
        step=0.1,
        key="manual_imp",
    )

    c = st.columns(2)

    p_brand = c[0].text_input(
        "شركة اللوح",
        key="manual_panel_brand",
    )

    p_model = c[1].text_input(
        "موديل اللوح",
        key="manual_panel_model",
    )

    # -------------------------
    # INVERTER
    # -------------------------

    st.markdown("## ⚡ مواصفات الإنفيرتر")

    c = st.columns(4)

    ac_power = c[0].number_input(
        "AC Rated Power (W)",
        min_value=0.0,
        value=5000.0,
        step=100.0,
        key="manual_ac_power",
    )

    dc_max = c[1].number_input(
        "Max DC Voltage (V)",
        min_value=0.0,
        value=500.0,
        step=10.0,
        key="manual_dc_max",
    )

    mppt_min = c[2].number_input(
        "MPPT Min (V)",
        min_value=0.0,
        value=150.0,
        step=5.0,
        key="manual_mppt_min",
    )

    mppt_max = c[3].number_input(
        "MPPT Max (V)",
        min_value=0.0,
        value=425.0,
        step=5.0,
        key="manual_mppt_max",
    )

    c = st.columns(4)

    mppt_current = c[0].number_input(
        "Max Current / MPPT (A)",
        min_value=0.0,
        value=13.0,
        step=0.5,
        key="manual_mppt_current",
    )

    phase = c[1].selectbox(
        "Phase",
        [
            "Single-Phase",
            "Three-Phase",
        ],
        key="manual_phase",
    )

    inverter_type = c[2].selectbox(
        "Inverter Type",
        [
            "Hybrid",
            "Off-Grid",
            "On-Grid",
        ],
        key="manual_inverter_type",
    )

    architecture = c[3].selectbox(
        "Battery Architecture",
        [
            "Low Voltage LV",
            "High Voltage HV",
            "غير معروف",
        ],
        key="manual_architecture",
    )

    c = st.columns(2)

    inverter_brand = c[0].text_input(
        "شركة الإنفيرتر",
        key="manual_inverter_brand",
    )

    inverter_model = c[1].text_input(
        "موديل الإنفيرتر",
        key="manual_inverter_model",
    )

    # -------------------------
    # MPPT
    # -------------------------

    st.markdown("## 🔀 تكوين MPPT و Strings")

    st.caption(
        "MPPT1 موجود دائماً. يمكنك إضافة أي عدد من MPPT "
        "ولكل MPPT عدد Strings مستقل."
    )

    mppt_count = st.number_input(
        "عدد MPPT",
        min_value=1,
        max_value=32,
        value=1,
        step=1,
        key="manual_mppt_count",
    )

    string_counts = []

    for i in range(int(mppt_count)):

        cols = st.columns([2, 2, 4])

        with cols[0]:
            st.markdown(
                f"### MPPT {i + 1}"
            )

        with cols[1]:
            count = st.number_input(
                f"عدد Strings لـ MPPT {i + 1}",
                min_value=1,
                max_value=16,
                value=1,
                step=1,
                key=f"manual_mppt_string_{i}",
            )

        string_counts.append(int(count))

    # -------------------------
    # BATTERY INPUT
    # -------------------------

    battery = {
        "brand": "غير مستخدمة",
        "model": "غير مستخدمة",
        "chemistry": "غير معروف",
        "capacity_ah": 0,
        "capacity_kwh": 0,
        "nominal_voltage_v": 0,
        "max_charge_current_a": 0,
        "max_discharge_current_a": 0,
    }

    if battery_enabled:

        st.markdown("## 🔋 البطارية الخارجية")

        c = st.columns(4)

        b_voltage = c[0].number_input(
            "Nominal Voltage (V)",
            min_value=0.0,
            value=51.2,
            step=0.1,
            key="manual_b_voltage",
        )

        b_ah = c[1].number_input(
            "Capacity (Ah)",
            min_value=0.0,
            value=100.0,
            step=10.0,
            key="manual_b_ah",
        )

        b_kwh = c[2].number_input(
            "Capacity (kWh)",
            min_value=0.0,
            value=5.12,
            step=0.1,
            key="manual_b_kwh",
        )

        b_discharge = c[3].number_input(
            "Max Discharge (A)",
            min_value=0.0,
            value=100.0,
            step=5.0,
            key="manual_b_discharge",
        )

        c = st.columns(3)

        b_brand = c[0].text_input(
            "شركة البطارية",
            key="manual_b_brand",
        )

        b_model = c[1].text_input(
            "موديل البطارية",
            key="manual_b_model",
        )

        b_chemistry = c[2].selectbox(
            "Chemistry",
            [
                "LiFePO4",
                "Lithium-ion",
                "Gel",
                "AGM",
                "Lead-Acid",
                "غير معروف",
            ],
            key="manual_b_chemistry",
        )

        battery = {
            "brand": b_brand or "إدخال يدوي",
            "model": b_model or "Manual Battery",
            "chemistry": b_chemistry,
            "capacity_ah": b_ah,
            "capacity_kwh": b_kwh,
            "nominal_voltage_v": b_voltage,
            "max_charge_current_a": 0,
            "max_discharge_current_a": b_discharge,
        }

    return {
        "panel": {
            "brand": p_brand or "إدخال يدوي",
            "model": p_model or "Manual Panel",
            "part_number": "غير معروف",
            "type": "Manual",
            "pmax": pmax,
            "voc": voc,
            "vmp": vmp,
            "isc": isc,
            "imp": imp,
        },

        "inverter": {
            "brand": inverter_brand or "إدخال يدوي",
            "model": inverter_model or "Manual Inverter",
            "part_number": "غير معروف",
            "type": inverter_type,
            "phase_type": phase,
            "voltage_architecture": architecture,
            "ac_rated_power_w": ac_power,
            "v_max": dc_max,
            "v_mppt_min": mppt_min,
            "v_mppt_max": mppt_max,
            "v_start": 0,
            "mppt_count": int(mppt_count),
            "strings_per_mppt": max(string_counts),
            "mppt_strings_config": string_counts,
            "max_mppt_current": mppt_current,

            "battery": {
                "supported": inverter_type != "On-Grid",
                "nominal_voltage_v": (
                    battery["nominal_voltage_v"]
                    if battery_enabled
                    else 0
                ),
                "battery_type": (
                    battery["chemistry"]
                    if battery_enabled
                    else "غير مستخدمة"
                ),
                "max_charge_current_a": 0,
            },

            "ac_input_output": {
                "nominal_ac_voltage_v": "يدوي",
                "frequency_hz": "50/60",
                "max_ac_input_current_a": 0,
                "max_ac_output_current_a": 0,
            },

            "startup_surge": {
                "surge_power_va": 0,
                "duration_seconds": 0,
            },
        },

        "external_battery": battery,
    }


# ============================================================
# 15. INPUT SECTION
# ============================================================

st.title("☀️ Solar System Designer & Compatibility Checker")

st.caption(
    "أداة تصميم وفحص منظومات Solar: "
    "Panel + Inverter + MPPT + Strings + Battery + DC/AC"
)


# ============================================================
# BATTERY TOGGLE — IMPORTANT
# ============================================================

st.markdown("## ⚙️ إعدادات الإدخال")

battery_enabled = st.toggle(
    "🔋 تفعيل البطارية الخارجية في هذه المقارنة",
    value=st.session_state.get("battery_enabled", False),
    key="battery_enabled",
    help=(
        "إذا أوقفتها فلن يتم طلب صورة البطارية "
        "ولن تدخل البطارية الخارجية في نتيجة المقارنة."
    ),
)

if battery_enabled:
    st.success(
        "🔋 البطارية مفعلة — سيتم طلب بيانات/صورة البطارية "
        "وإجراء فحص التوافق."
    )
else:
    st.info(
        "🔋 البطارية غير مفعلة — المقارنة ستكون Panel ↔ Inverter "
        "بدون بطارية خارجية."
    )


# ============================================================
# INPUT MODE
# ============================================================

search_mode = st.radio(
    "اختر طريقة إدخال البيانات:",
    [
        "📸 1. تحليل الصور",
        "✍️ 2. الشركة والموديل",
        "🧮 3. إدخال المواصفات يدوياً",
    ],
    horizontal=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ إعدادات التطبيق")

    api_key = st.text_input(
        "Gemini API Key",
        type="password",
    )

    st.markdown("---")

    st.header("🧮 الهوامش الهندسية")

    cold_factor = st.slider(
        "معامل Voc في البرد",
        min_value=1.05,
        max_value=1.30,
        value=float(
            st.session_state.get("cold_factor", 1.15)
        ),
        step=0.01,
        key="cold_factor",
    )

    voltage_margin = st.slider(
        "هامش أمان DC Voltage",
        min_value=0.90,
        max_value=1.00,
        value=float(
            st.session_state.get("voltage_margin", 0.95)
        ),
        step=0.01,
        key="voltage_margin",
    )

    mppt_margin = st.slider(
        "هامش MPPT Min",
        min_value=1.00,
        max_value=1.20,
        value=float(
            st.session_state.get("mppt_margin", 1.10)
        ),
        step=0.01,
        key="mppt_margin",
    )

    st.caption(
        "هذه هوامش تصميمية وليست بديلاً عن Datasheet."
    )


# ============================================================
# INPUT: IMAGES
# ============================================================

uploaded_panel = None
uploaded_inverter = None
uploaded_battery = None

panel_text = ""
inverter_text = ""
battery_text = ""

manual_data = None


if "📸" in search_mode:

    st.markdown("## 📸 صور الملصقات")

    columns = (
        st.columns(3)
        if battery_enabled
        else st.columns(2)
    )

    with columns[0]:

        uploaded_panel = st.file_uploader(
            "☀️ صورة ملصق اللوح",
            type=["jpg", "jpeg", "png"],
            key="uploaded_panel",
        )

    with columns[1]:

        uploaded_inverter = st.file_uploader(
            "⚡ صورة ملصق الإنفيرتر",
            type=["jpg", "jpeg", "png"],
            key="uploaded_inverter",
        )

    if battery_enabled:

        with columns[2]:

            uploaded_battery = st.file_uploader(
                "🔋 صورة ملصق البطارية",
                type=["jpg", "jpeg", "png"],
                key="uploaded_battery",
            )


# ============================================================
# INPUT: TEXT
# ============================================================

elif "✍️" in search_mode:

    st.markdown("## ✍️ البحث بالموديل")

    columns = (
        st.columns(3)
        if battery_enabled
        else st.columns(2)
    )

    with columns[0]:

        panel_text = st.text_input(
            "☀️ الشركة + موديل اللوح",
            placeholder="Jinko Solar 550W",
            key="panel_text",
        )

    with columns[1]:

        inverter_text = st.text_input(
            "⚡ الشركة + موديل الإنفيرتر",
            placeholder="Deye 5K",
            key="inverter_text",
        )

    if battery_enabled:

        with columns[2]:

            battery_text = st.text_input(
                "🔋 الشركة + موديل البطارية",
                placeholder="Pylontech US5000",
                key="battery_text",
            )


# ============================================================
# INPUT: MANUAL
# ============================================================

else:

    manual_data = manual_input_section(
        battery_enabled
    )


# ============================================================
# ANALYSIS BUTTON
# ============================================================

st.markdown("---")

analyze_clicked = st.button(
    "⚡ تحليل النظام واستخراج التقرير",
    type="primary",
)


if analyze_clicked:

    result = None

    # ---------------------------
    # MANUAL
    # ---------------------------

    if "🧮" in search_mode:

        result = manual_data

    # ---------------------------
    # IMAGE
    # ---------------------------

    elif "📸" in search_mode:

        if not uploaded_panel:
            st.error(
                "❌ يرجى رفع صورة اللوح."
            )

        elif not uploaded_inverter:
            st.error(
                "❌ يرجى رفع صورة الإنفيرتر."
            )

        elif battery_enabled and not uploaded_battery:
            st.error(
                "❌ البطارية مفعلة، يرجى رفع صورة البطارية."
            )

        elif not api_key:
            st.error(
                "❌ أدخل Gemini API Key في القائمة الجانبية."
            )

        else:

            try:

                panel_img = Image.open(
                    uploaded_panel
                )

                inverter_img = Image.open(
                    uploaded_inverter
                )

                battery_img = (
                    Image.open(uploaded_battery)
                    if battery_enabled and uploaded_battery
                    else None
                )

                with st.spinner(
                    "🔍 جاري تحليل الصور..."
                ):

                    result = extract_from_images(
                        panel_img,
                        inverter_img,
                        battery_img,
                        api_key,
                    )

            except Exception as exc:

                st.error(
                    "❌ حدث خطأ أثناء تحليل الصور."
                )

                st.code(
                    str(exc),
                    language="text",
                )

                st.info(
                    "إذا ظهر خطأ 503 من Gemini، "
                    "فهذا يعني أن النموذج غير متاح مؤقتاً "
                    "أو تحت ضغط. حاول مرة أخرى لاحقاً."
                )

    # ---------------------------
    # TEXT
    # ---------------------------

    else:

        if not panel_text:
            st.error(
                "❌ أدخل اسم وموديل اللوح."
            )

        elif not inverter_text:
            st.error(
                "❌ أدخل اسم وموديل الإنفيرتر."
            )

        elif battery_enabled and not battery_text:
            st.error(
                "❌ البطارية مفعلة، أدخل اسم وموديل البطارية."
            )

        elif not api_key:
            st.error(
                "❌ أدخل Gemini API Key."
            )

        else:

            try:

                with st.spinner(
                    "🔍 جاري استخراج المواصفات..."
                ):

                    result = extract_from_text(
                        panel_text,
                        inverter_text,
                        battery_text
                        if battery_enabled
                        else "",
                        api_key,
                    )

            except Exception as exc:

                st.error(
                    "❌ حدث خطأ أثناء استخراج البيانات."
                )

                st.code(
                    str(exc),
                    language="text",
                )

    if result:

        # إذا البطارية غير مفعلة، نجبر البيانات الخارجية
        # على أن تكون غير مستخدمة.
        if not battery_enabled:

            result["external_battery"] = {
                "brand": "غير مستخدمة",
                "model": "غير مستخدمة",
                "chemistry": "غير مستخدمة",
                "capacity_ah": 0,
                "capacity_kwh": 0,
                "nominal_voltage_v": 0,
                "max_charge_current_a": 0,
                "max_discharge_current_a": 0,
            }

        st.session_state["analysis_result"] = result

        st.success(
            "✅ تم تحليل البيانات بنجاح."
        )


# ============================================================
# RESULTS
# ============================================================

if st.session_state.get("analysis_result"):

    result = st.session_state["analysis_result"]

    panel = result.get("panel", {}) or {}
    inverter = result.get("inverter", {}) or {}
    battery = result.get("external_battery", {}) or {}
    inverter_battery = inverter.get(
        "battery",
        {}
    ) or {}

    # ========================================================
    # EXTRACT PANEL
    # ========================================================

    p_brand = safe_text(
        panel.get("brand")
    )

    p_model = safe_text(
        panel.get("model")
    )

    pmax = safe_float(
        panel.get("pmax")
    )

    voc = safe_float(
        panel.get("voc")
    )

    vmp = safe_float(
        panel.get("vmp")
    )

    isc = safe_float(
        panel.get("isc")
    )

    imp = safe_float(
        panel.get("imp")
    )

    # ========================================================
    # EXTRACT INVERTER
    # ========================================================

    i_brand = safe_text(
        inverter.get("brand")
    )

    i_model = safe_text(
        inverter.get("model")
    )

    inverter_type = safe_text(
        inverter.get("type")
    )

    phase_type = safe_text(
        inverter.get("phase_type")
    )

    architecture = safe_text(
        inverter.get("voltage_architecture")
    )

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

    max_mppt_current = safe_float(
        inverter.get("max_mppt_current")
    )

    detected_mppt_count = max(
        1,
        safe_int(
            inverter.get("mppt_count"),
            1,
        ),
    )

    detected_config = inverter.get(
        "mppt_strings_config",
        None,
    )

    # ========================================================
    # DETERMINE MPPT CONFIG
    # ========================================================

    if isinstance(detected_config, list):

        mppt_config = [
            max(1, safe_int(x, 1))
            for x in detected_config
            if safe_int(x, 1) > 0
        ]

        if not mppt_config:
            mppt_config = [1]

    else:

        old_strings = max(
            1,
            safe_int(
                inverter.get(
                    "strings_per_mppt"
                ),
                1,
            ),
        )

        mppt_config = [
            old_strings
            for _ in range(
                detected_mppt_count
            )
        ]

    # ========================================================
    # SIDEBAR: ALLOW USER TO EDIT DETECTED MPPT
    # ========================================================

    with st.sidebar:

        if st.session_state.get(
            "analysis_result"
        ):

            st.markdown("---")

            st.header(
                "🔀 تكوين MPPT النهائي"
            )

            editable_mppt_count = st.number_input(
                "عدد MPPT المستخدم فعلياً",
                min_value=1,
                max_value=32,
                value=len(mppt_config),
                step=1,
                key="result_mppt_count",
            )

            user_config = []

            for i in range(
                int(editable_mppt_count)
            ):

                default_strings = (
                    mppt_config[i]
                    if i < len(mppt_config)
                    else 1
                )

                s = st.number_input(
                    f"MPPT {i + 1} — Strings",
                    min_value=1,
                    max_value=16,
                    value=int(
                        default_strings
                    ),
                    step=1,
                    key=f"result_mppt_strings_{i}",
                )

                user_config.append(
                    int(s)
                )

            mppt_config = user_config


    # ========================================================
    # ENGINEERING STATUS
    # ========================================================

    system_errors = []
    system_warnings = []

    is_on_grid = (
        "on-grid" in inverter_type.lower()
        or "ongrid" in inverter_type.lower()
        or "grid-tied" in inverter_type.lower()
    )

    # ========================================================
    # BATTERY VALIDATION
    # ========================================================

    battery_voltage = safe_float(
        battery.get("nominal_voltage_v")
    )

    battery_ah = safe_float(
        battery.get("capacity_ah")
    )

    battery_kwh = safe_float(
        battery.get("capacity_kwh")
    )

    battery_max_discharge = safe_float(
        battery.get(
            "max_discharge_current_a"
        )
    )

    inverter_battery_voltage = safe_float(
        inverter_battery.get(
            "nominal_voltage_v"
        )
    )

    if battery_enabled:

        if is_on_grid:

            system_warnings.append(
                "تم تفعيل بطارية خارجية بينما نوع الإنفيرتر "
                "يظهر On-Grid. يجب مراجعة الـ Datasheet."
            )

        if (
            battery_voltage > 0
            and inverter_battery_voltage > 0
        ):

            ok, message = check_battery_voltage(
                inverter_battery_voltage,
                battery_voltage,
            )

            if ok is False:
                system_errors.append(
                    message
                )

            elif ok is True:
                pass

    # ========================================================
    # STRING LIMITS
    # ========================================================

    limits = calculate_string_limits(
        voc,
        vmp,
        dc_max,
        mppt_min,
        mppt_max,
    )

    # ========================================================
    # DC/AC
    # ========================================================

    # ========================================================
    # TOP STATUS
    # ========================================================

    st.markdown("---")

    st.subheader(
        "📊 لوحة الحالة الهندسية"
    )

    if system_errors:

        st.error(
            "🔴 حالة النظام: يحتاج إلى تصحيح"
        )

    elif system_warnings:

        st.warning(
            "🟡 حالة النظام: توجد تنبيهات للمراجعة"
        )

    else:

        st.success(
            "🟢 حالة النظام: متوافق مبدئياً"
        )

    # ========================================================
    # SUMMARY METRICS
    # ========================================================

    total_strings = sum(
        mppt_config
    )

    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        st.metric(
            "Panel",
            f"{pmax:.0f} W"
            if pmax
            else "N/A",
        )

    with k2:
        st.metric(
            "Inverter",
            f"{ac_power / 1000:.2f} kW"
            if ac_power
            else "N/A",
        )

    with k3:

        ratio_single = (
            pmax / ac_power
            if pmax and ac_power
            else 0
        )

        st.metric(
            "Panel/Inverter",
            f"{ratio_single:.2f}"
            if ratio_single
            else "N/A",
        )

    with k4:

        st.metric(
            "MPPT",
            len(mppt_config),
        )

    with k5:

        st.metric(
            "Total Strings",
            total_strings,
        )

    # ========================================================
    # SPECIFICATIONS
    # ========================================================

    st.markdown("---")

    st.subheader(
        "📌 المواصفات"
    )

    left, right = st.columns(2)

    with left:

        st.markdown(
            "### ☀️ Solar Panel"
        )

        st.write(
            f"**الشركة:** {p_brand}"
        )

        st.write(
            f"**الموديل:** {p_model}"
        )

        st.write(
            f"**Pmax:** {fmt(pmax)} W"
        )

        st.write(
            f"**Voc:** {fmt(voc)} V"
        )

        st.write(
            f"**Vmp:** {fmt(vmp)} V"
        )

        st.write(
            f"**Isc:** {fmt(isc)} A"
        )

        st.write(
            f"**Imp:** {fmt(imp)} A"
        )

    with right:

        st.markdown(
            "### ⚡ Inverter"
        )

        st.write(
            f"**الشركة:** {i_brand}"
        )

        st.write(
            f"**الموديل:** {i_model}"
        )

        st.write(
            f"**النوع:** {inverter_type}"
        )

        st.write(
            f"**الفازات:** {phase_type}"
        )

        st.write(
            f"**Architecture:** {architecture}"
        )

        st.write(
            f"**AC Rated:** {fmt(ac_power)} W"
        )

        st.write(
            f"**DC Max:** {fmt(dc_max)} V"
        )

        st.write(
            f"**MPPT:** {fmt(mppt_min)} – "
            f"{fmt(mppt_max)} V"
        )

    # ========================================================
    # MPPT CONFIGURATION TABLE
    # ========================================================

    st.markdown("---")

    st.subheader(
        "🔀 تكوين MPPT / Strings"
    )

    config_rows = []

    for i, string_count in enumerate(
        mppt_config,
        1,
    ):

        config_rows.append(
            {
                "MPPT": i,
                "عدد Strings": string_count,
                "الحد الأقصى النظري للتيار": (
                    string_count
                    * isc
                    * 1.25
                ),
            }
        )

    st.dataframe(
        config_rows,
        use_container_width=True,
        hide_index=True,
    )

    # ========================================================
    # STRING LIMITS
    # ========================================================

    if limits is None:

        st.error(
            "❌ لا يمكن حساب حدود String. "
            "تأكد من إدخال Voc وVmp وDC Max."
        )

    else:

        min_panels_string = limits[
            "min_series"
        ]

        max_panels_string = limits[
            "max_series"
        ]

        if (
            max_panels_string
            < min_panels_string
        ):

            st.error(
                f"❌ لا يوجد عدد String صالح. "
                f"الحد الأدنى = "
                f"{min_panels_string} "
                f"والحد الأقصى = "
                f"{max_panels_string}."
            )

        else:

            recommended_string = (
                min_panels_string
                + max_panels_string
            ) // 2

            min_total_panels = (
                min_panels_string
                * total_strings
            )

            max_total_panels = (
                max_panels_string
                * total_strings
            )

            recommended_total_panels = (
                recommended_string
                * total_strings
            )

            st.markdown("---")

            st.subheader(
                "📐 حدود تصميم الـ String"
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Min Panels / String",
                min_panels_string,
            )

            c2.metric(
                "Recommended",
                recommended_string,
            )

            c3.metric(
                "Max Panels / String",
                max_panels_string,
            )

            c4.metric(
                "Total Strings",
                total_strings,
            )

            st.info(
                f"Voc البارد للوح ≈ "
                f"{limits['cold_voc_panel']:.2f} V | "
                f"الحد الآمن لـ DC ≈ "
                f"{limits['safe_dc_max']:.2f} V | "
                f"الحد الأدنى الآمن للـ MPPT ≈ "
                f"{limits['safe_mppt_min']:.2f} V"
            )

            # =================================================
            # RECOMMENDATION
            # =================================================

            st.markdown(
                "### ⭐ التوصية الأساسية"
            )

            recommended_kwp = (
                recommended_total_panels
                * pmax
                / 1000
                if pmax
                else 0
            )

            recommended_dc_ac = (
                recommended_kwp
                / (ac_power / 1000)
                if ac_power
                else 0
            )

            st.success(
                f"**{recommended_total_panels} لوح** | "
                f"**{recommended_kwp:.2f} kWp** | "
                f"**{recommended_string} ألواح/String** | "
                f"DC/AC = "
                f"**{recommended_dc_ac:.2f}**"
            )

            # =================================================
            # PANEL COUNT SIMULATOR
            # =================================================

            st.markdown("---")

            st.subheader(
                "🧮 محاكاة عدد الألواح"
            )

            st.caption(
                "هنا يمكنك زيادة أو تقليل عدد الألواح "
                "ورؤية القراءات الجديدة مباشرة."
            )

            sim_min = min_total_panels

            sim_max = max_total_panels

            if sim_max < sim_min:
                sim_max = sim_min

            # حماية إذا كانت الحدود صغيرة جداً
            default_sim = int(
                clamp(
                    recommended_total_panels,
                    sim_min,
                    sim_max,
                )
            )

            custom_panels = st.number_input(
                "إجمالي عدد الألواح",
                min_value=int(sim_min),
                max_value=int(
                    max(
                        sim_max,
                        sim_min,
                    )
                ),
                value=default_sim,
                step=1,
                key="custom_panel_count",
            )

            # =================================================
            # DISTRIBUTION
            # =================================================

            rows = distribute_panels(
                custom_panels,
                mppt_config,
            )

            errors, warnings = evaluate_strings(
                rows,
                pmax,
                voc,
                vmp,
                isc,
                dc_max,
                mppt_min,
                mppt_max,
                max_mppt_current,
            )

            # =================================================
            # TOTAL SYSTEM VALUES
            # =================================================

            total_kwp = (
                custom_panels
                * pmax
                / 1000
                if pmax
                else 0
            )

            dc_ac_ratio = (
                total_kwp
                / (ac_power / 1000)
                if ac_power
                else 0
            )

            dc_power_w = (
                custom_panels * pmax
                if pmax
                else 0
            )

            # =================================================
            # SYSTEM POWER METRICS
            # =================================================

            st.markdown(
                "### 📊 قراءات العدد المختار"
            )

            a1, a2, a3, a4, a5 = st.columns(5)

            a1.metric(
                "Panels",
                custom_panels,
            )

            a2.metric(
                "PV Power",
                f"{total_kwp:.2f} kWp",
            )

            a3.metric(
                "DC Power",
                f"{dc_power_w:.0f} W",
            )

            a4.metric(
                "DC/AC",
                f"{dc_ac_ratio:.2f}"
                if dc_ac_ratio
                else "N/A",
            )

            a5.metric(
                "Strings",
                total_strings,
            )

            # =================================================
            # VALIDATION MESSAGES
            # =================================================

            if errors:

                st.markdown(
                    "### 🔴 أخطاء التصميم"
                )

                for message in errors:

                    st.error(
                        message
                    )

            elif warnings:

                st.markdown(
                    "### 🟡 تنبيهات"
                )

                for message in warnings:

                    st.warning(
                        message
                    )

            else:

                st.success(
                    "✅ عدد الألواح والتوزيع الحالي "
                    "متوافقان مبدئياً مع حدود الجهد والتيار."
                )

            # =================================================
            # STRING TABLE
            # =================================================

            st.markdown(
                "### 🔌 توزيع الألواح على Strings"
            )

            table_rows = []

            for row in rows:

                n = row["Panels"]

                string_vmp = (
                    n * vmp
                    if vmp
                    else 0
                )

                string_voc = (
                    n
                    * voc
                    * cold_factor
                    if voc
                    else 0
                )

                string_power = (
                    n * pmax / 1000
                    if pmax
                    else 0
                )

                string_current = (
                    isc
                    if isc
                    else 0
                )

                table_rows.append(
                    {
                        "MPPT": row["MPPT"],
                        "String": row["String"],
                        "Panels": n,
                        "Vmp (V)": round(
                            string_vmp,
                            1,
                        ),
                        "Voc Cold (V)": round(
                            string_voc,
                            1,
                        ),
                        "Current (A)": round(
                            string_current,
                            2,
                        ),
                        "Power (kW)": round(
                            string_power,
                            3,
                        ),
                    }
                )

            st.dataframe(
                table_rows,
                use_container_width=True,
                hide_index=True,
            )

            # =================================================
            # PER MPPT SUMMARY
            # =================================================

            st.markdown(
                "### 🔀 قراءة كل MPPT"
            )

            for mppt_no in range(
                1,
                len(mppt_config) + 1,
            ):

                mppt_rows = [
                    x
                    for x in rows
                    if x["MPPT"]
                    == mppt_no
                ]

                if not mppt_rows:
                    continue

                panels_in_mppt = sum(
                    x["Panels"]
                    for x in mppt_rows
                )

                mppt_power = (
                    panels_in_mppt
                    * pmax
                    / 1000
                    if pmax
                    else 0
                )

                mppt_current = (
                    len(mppt_rows)
                    * isc
                    * 1.25
                    if isc
                    else 0
                )

                mppt_vmp_values = [
                    x["Panels"] * vmp
                    for x in mppt_rows
                ]

                mppt_voc_values = [
                    x["Panels"]
                    * voc
                    * cold_factor
                    for x in mppt_rows
                ]

                c1, c2, c3, c4, c5 = st.columns(5)

                c1.metric(
                    f"MPPT {mppt_no}",
                    f"{len(mppt_rows)} Strings",
                )

                c2.metric(
                    "Panels",
                    panels_in_mppt,
                )

                c3.metric(
                    "PV",
                    f"{mppt_power:.2f} kW",
                )

                c4.metric(
                    "Design Current",
                    f"{mppt_current:.2f} A",
                )

                c5.metric(
                    "Vmp Range",
                    (
                        f"{min(mppt_vmp_values):.0f}–"
                        f"{max(mppt_vmp_values):.0f} V"
                    )
                    if mppt_vmp_values
                    else "N/A",
                )

            # =================================================
            # AUTOMATIC RANGE TABLE
            # =================================================

            st.markdown("---")

            st.subheader(
                "📈 ماذا يحدث إذا زدت أو قللت الألواح؟"
            )

            range_rows = []

            step_size = max(
                1,
                total_strings,
            )

            # نجعل المحاكاة على عدد Panels/String
            # حتى تكون النتائج هندسية ومفهومة.
            for panels_per_string in range(
                min_panels_string,
                max_panels_string + 1,
            ):

                n_total = (
                    panels_per_string
                    * total_strings
                )

                power_kw = (
                    n_total
                    * pmax
                    / 1000
                    if pmax
                    else 0
                )

                dcac = (
                    power_kw
                    / (ac_power / 1000)
                    if ac_power
                    else 0
                )

                vmp_string = (
                    panels_per_string
                    * vmp
                    if vmp
                    else 0
                )

                voc_string = (
                    panels_per_string
                    * voc
                    * cold_factor
                    if voc
                    else 0
                )

                range_rows.append(
                    {
                        "Panels/String":
                            panels_per_string,
                        "Total Panels":
                            n_total,
                        "Total kWp":
                            round(
                                power_kw,
                                2,
                            ),
                        "DC/AC":
                            round(
                                dcac,
                                2,
                            ),
                        "Vmp/String":
                            round(
                                vmp_string,
                                1,
                            ),
                        "Voc Cold/String":
                            round(
                                voc_string,
                                1,
                            ),
                    }
                )

            st.dataframe(
                range_rows,
                use_container_width=True,
                hide_index=True,
            )

    # ========================================================
    # BATTERY SECTION
    # ========================================================

    if battery_enabled:

        st.markdown("---")

        st.subheader(
            "🔋 فحص البطارية الخارجية"
        )

        b1, b2 = st.columns(2)

        with b1:

            st.write(
                f"**الشركة:** "
                f"{safe_text(battery.get('brand'))}"
            )

            st.write(
                f"**الموديل:** "
                f"{safe_text(battery.get('model'))}"
            )

            st.write(
                f"**Chemistry:** "
                f"{safe_text(battery.get('chemistry'))}"
            )

            st.write(
                f"**Voltage:** "
                f"{battery_voltage:g} V"
            )

            st.write(
                f"**Capacity:** "
                f"{battery_ah:g} Ah"
            )

            st.write(
                f"**Energy:** "
                f"{battery_kwh:g} kWh"
            )

        with b2:

            st.write(
                f"**Max Charge:** "
                f"{safe_float(battery.get('max_charge_current_a')):g} A"
            )

            st.write(
                f"**Max Discharge:** "
                f"{battery_max_discharge:g} A"
            )

            if (
                battery_voltage > 0
                and inverter_battery_voltage > 0
            ):

                ok, message = check_battery_voltage(
                    inverter_battery_voltage,
                    battery_voltage,
                )

                if ok:

                    st.success(
                        "✅ " + message
                    )

                elif ok is False:

                    st.error(
                        "❌ " + message
                    )

                else:

                    st.warning(
                        "⚠️ " + message
                    )

        # ====================================================
        # BATTERY DESIGN
        # ====================================================

        st.markdown(
            "### 🧰 حاسبة حجم البطارية"
        )

        c = st.columns(4)

        daily_load = c[0].number_input(
            "الاستهلاك اليومي (kWh/day)",
            min_value=0.0,
            value=10.0,
            step=0.5,
            key="battery_daily_load",
        )

        autonomy = c[1].number_input(
            "Autonomy (hours)",
            min_value=0.5,
            value=8.0,
            step=0.5,
            key="battery_autonomy",
        )

        # IMPORTANT:
        # لا نستخدم number_input هنا حتى لا يعود
        # StreamlitValueBelowMinError
        dod = c[2].slider(
            "DoD (%)",
            min_value=50,
            max_value=95,
            value=80,
            step=5,
            key="battery_dod_safe",
        )

        efficiency = c[3].slider(
            "Inverter Efficiency (%)",
            min_value=80,
            max_value=99,
            value=92,
            step=1,
            key="battery_efficiency",
        )

        peak_load = st.number_input(
            "الحمل الأقصى المتوقع (kW)",
            min_value=0.0,
            value=5.0,
            step=0.5,
            key="battery_peak_load",
        )

        battery_result = calculate_battery(
            battery_voltage,
            battery_ah,
            battery_kwh,
            battery_max_discharge,
            daily_load,
            autonomy,
            dod / 100,
            efficiency / 100,
            peak_load,
        )

        if battery_result:

            c = st.columns(4)

            c[0].metric(
                "Required Battery",
                f"{battery_result['required_nominal_kwh']:.2f} kWh",
            )

            c[1].metric(
                "Battery Unit",
                f"{battery_result['unit_kwh']:.2f} kWh",
            )

            c[2].metric(
                "Estimated Quantity",
                battery_result["battery_count"],
            )

            c[3].metric(
                "Total Battery",
                f"{battery_result['total_kwh']:.2f} kWh",
            )

            theoretical_power = (
                battery_result[
                    "theoretical_power_w"
                ]
                / 1000
            )

            if theoretical_power > 0:

                st.write(
                    f"**قدرة التفريغ النظرية:** "
                    f"{theoretical_power:.2f} kW"
                )

                if (
                    theoretical_power
                    < peak_load
                ):

                    st.error(
                        "❌ قدرة تفريغ البطارية "
                        "النظرية أقل من الحمل الأقصى."
                    )

                else:

                    st.success(
                        "✅ قدرة التفريغ النظرية "
                        "مناسبة للحمل المدخل."
                    )

        else:

            st.warning(
                "أدخل بيانات الحمل والاستقلالية "
                "لحساب حجم البطارية."
            )

    # ========================================================
    # LOAD CALCULATOR
    # ========================================================

    st.markdown("---")

    st.subheader(
        "🏠 حاسبة الأحمال اليومية"
    )

    st.caption(
        "هذه الحاسبة تعطي تقديراً سريعاً للاستهلاك."
    )

    load_defaults = [
        ("ثلاجة", 150, 8),
        ("إضاءة", 20, 6),
        ("تلفاز", 100, 5),
        ("حاسوب", 100, 6),
        ("مكيف", 1200, 5),
        ("مضخة", 750, 3),
    ]

    total_daily_wh = 0

    load_table = []

    for idx, (
        name,
        watts,
        hours,
    ) in enumerate(load_defaults):

        c1, c2, c3 = st.columns(
            [3, 2, 2]
        )

        with c1:

            device = st.text_input(
                "الجهاز",
                value=name,
                key=f"load_device_{idx}",
            )

        with c2:

            power = st.number_input(
                "W",
                min_value=0.0,
                value=float(watts),
                step=10.0,
                key=f"load_power_{idx}",
            )

        with c3:

            h = st.number_input(
                "ساعات/يوم",
                min_value=0.0,
                value=float(hours),
                step=0.5,
                key=f"load_hours_{idx}",
            )

        wh = power * h

        total_daily_wh += wh

        load_table.append(
            {
                "الجهاز": device,
                "Power W": power,
                "Hours": h,
                "Energy Wh/day": wh,
            }
        )

    st.metric(
        "الاستهلاك اليومي",
        f"{total_daily_wh / 1000:.2f} kWh/day",
    )

    st.dataframe(
        load_table,
        use_container_width=True,
        hide_index=True,
    )

    # ========================================================
    # FINAL ENGINEERING SUMMARY
    # ========================================================

    st.markdown("---")

    st.subheader(
        "📋 الخلاصة الهندسية"
    )

    final_checks = []

    # Panel voltage
    if limits:

        final_checks.append(
            (
                "حد String الأدنى",
                f"{limits['min_series']} ألواح",
            )
        )

        final_checks.append(
            (
                "حد String الأقصى",
                f"{limits['max_series']} ألواح",
            )
        )

    final_checks.append(
        (
            "عدد MPPT",
            str(len(mppt_config)),
        )
    )

    final_checks.append(
        (
            "إجمالي Strings",
            str(total_strings),
        )
    )

    if battery_enabled:

        final_checks.append(
            (
                "البطارية",
                "مفعلة",
            )
        )

    else:

        final_checks.append(
            (
                "البطارية",
                "غير مفعلة",
            )
        )

    final_checks.append(
        (
            "نوع الإنفيرتر",
            inverter_type,
        )
    )

    final_checks.append(
        (
            "الفازات",
            phase_type,
        )
    )

    final_checks.append(
        (
            "DC Architecture",
            architecture,
        )
    )

    st.table(
        {
            "البند": [
                x[0]
                for x in final_checks
            ],
            "النتيجة": [
                x[1]
                for x in final_checks
            ],
        }
    )

    # ========================================================
    # IMPORTANT ENGINEERING NOTE
    # ========================================================

    if system_errors:

        st.error(
            "❌ توجد نقاط يجب تصحيحها قبل اعتماد التصميم."
        )

    elif system_warnings:

        st.warning(
            "⚠️ التصميم مقبول مبدئياً، "
            "لكن توجد نقاط تحتاج مراجعة Datasheet."
        )

    else:

        st.success(
            "✅ لا توجد تعارضات رئيسية حسب البيانات المدخلة."
        )

    st.caption(
        "تنبيه هندسي: هذه الأداة للمساعدة في التصميم والفحص "
        "وليست بديلاً عن Datasheet وتعليمات الشركة المصنعة "
        "والتحقق من درجة الحرارة والكابلات والحمايات "
        "والجهد والتيار الفعليين قبل التنفيذ."
    )
