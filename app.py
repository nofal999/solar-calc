import json
import math
import time
from google import genai
from google.genai import types
from PIL import Image
import streamlit as st

# 1. ضبط إعدادات الصفحة
st.set_page_config(
    page_title="حاسبة توافق الألواح والإنفيرتر والبطاريات الشاملة",
    page_icon="☀️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# 2. تخصيص الواجهة وتدفق النصوص (RTL)
st.markdown(
    """
    <style>
    [data-testid="stMainBlockContainer"], 
    [data-testid="stSidebarContent"] {
        direction: rtl;
        text-align: right;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stMarkdownContainer"] h1,
    div[data-testid="stMarkdownContainer"] h2,
    div[data-testid="stMarkdownContainer"] h3,
    div[data-testid="stMarkdownContainer"] h4,
    div[data-testid="stMarkdownContainer"] li {
        text-align: right !important;
        direction: rtl !important;
    }

    button[data-baseweb="tab"] {
        direction: rtl !important;
    }
    div[data-baseweb="tab-list"] {
        flex-direction: row-reverse !important;
        justify-content: flex-end !important;
    }

    section[data-testid="stFileUploadDropzone"] {
        direction: rtl;
        text-align: right;
    }

    .stButton>button {
        width: 100%;
        background-color: #0284c7;
        color: white;
        border-radius: 8px;
        height: 3em;
        font-weight: bold;
        margin-top: 10px;
    }

    .stAlert {
        direction: rtl;
        text-align: right;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("☀️ حاسبة توافق الألواح والإنفيرتر والبطاريات")
st.caption(
    "تحليل ذكي متكامل للمواصفات الكهربائية، نوع الجهد، نظام الفازات،"
    " البطاريات الخارجية، وتوزيع السلاسل الميدانية آلياً"
)

# 3. الشريط الجانبي
with st.sidebar:
    st.header("⚙️ الإعدادات")
    api_key = st.text_input(
        "مفتاح Gemini API Key:",
        type="password",
        help="احصل عليه مجاناً من Google AI Studio",
    )
    st.info("💡 مفتاح Gemini مطلوب لوضعي الصور والبحث النصي فقط. الإدخال اليدوي لا يحتاج مفتاحاً.")

# 4. التبديل بين طريقتي البحث
search_mode = st.radio(
    "اختر طريقة إدخال البيانات:",
    [
        "📸 1. البحث عن طريق الصور (إرفاق الملصقات)",
        "✍️ 2. البحث عن طريق اسم الشركة والموديل (نصياً)",
        "🧮 3. إدخال المواصفات يدوياً",
    ],
    index=0,
)

enable_battery = st.toggle("🔋 تفعيل فحص وتحليل بطارية خارجية مخصصة", value=False)

uploaded_panel = None
uploaded_inverter = None
uploaded_battery = None
panel_text_query = ""
inverter_text_query = ""
battery_text_query = ""
manual_data = {"panel": {}, "inverter": {}, "external_battery": {}}
mppt_string_counts = [1]
manual_cfg = None

if "📸" in search_mode:
    cols = st.columns(3 if enable_battery else 2)
    with cols[0]:
        uploaded_panel = st.file_uploader("📸 صورة ملصق اللوح الشمسي", type=["jpg", "jpeg", "png"])
    with cols[1]:
        uploaded_inverter = st.file_uploader("📸 صورة ملصق الإنفيرتر", type=["jpg", "jpeg", "png"])
    if enable_battery:
        with cols[2]:
            uploaded_battery = st.file_uploader("📸 صورة ملصق البطارية", type=["jpg", "jpeg", "png"])

elif "✍️" in search_mode:
    cols = st.columns(3 if enable_battery else 2)
    with cols[0]:
        panel_text_query = st.text_input("☀️ اسم الشركة والموديل للوح الشمسي:", placeholder="مثال: Jinko Solar 550W")
    with cols[1]:
        inverter_text_query = st.text_input("⚡ اسم الشركة والموديل للإنفيرتر:", placeholder="مثال: Deye 5K")
    if enable_battery:
        with cols[2]:
            battery_text_query = st.text_input("🔋 اسم الشركة والموديل للبطارية:", placeholder="مثال: Pylontech US3000C")

else:
    st.info("🧮 الإدخال اليدوي لا يحتاج Gemini API Key.")
    st.markdown("### ☀️ مواصفات اللوح الشمسي")
    c = st.columns(5)
    m_pmax = c[0].number_input("Pmax (W)", min_value=0.0, value=550.0, step=10.0, key="m_pmax")
    m_voc = c[1].number_input("Voc (V)", min_value=0.0, value=49.5, step=0.1, key="m_voc")
    m_vmp = c[2].number_input("Vmp (V)", min_value=0.0, value=41.5, step=0.1, key="m_vmp")
    m_isc = c[3].number_input("Isc (A)", min_value=0.0, value=14.0, step=0.1, key="m_isc")
    m_imp = c[4].number_input("Imp (A)", min_value=0.0, value=13.3, step=0.1, key="m_imp")
    m_p_brand = st.text_input("شركة اللوح", key="m_p_brand")
    m_p_model = st.text_input("موديل اللوح", key="m_p_model")

    st.markdown("### ⚡ مواصفات الإنفيرتر")
    c = st.columns(4)
    m_ac = c[0].number_input("AC Rated Power (W)", min_value=0.0, value=5000.0, step=100.0, key="m_ac")
    m_dcmax = c[1].number_input("Max DC Voltage (V)", min_value=0.0, value=500.0, step=10.0, key="m_dcmax")
    m_mpptmin = c[2].number_input("MPPT Min (V)", min_value=0.0, value=150.0, step=5.0, key="m_mpptmin")
    m_mpptmax = c[3].number_input("MPPT Max (V)", min_value=0.0, value=425.0, step=5.0, key="m_mpptmax")

    c = st.columns(4)
    m_mpptcurrent = c[0].number_input("Max Current / MPPT (A)", min_value=0.0, value=13.0, step=0.5, key="m_mpptcurrent")
    m_phase = c[1].selectbox("Phase", ["Single-Phase", "Three-Phase"], key="m_phase")
    m_type = c[2].selectbox("Inverter Type", ["Hybrid", "Off-Grid", "On-Grid"], key="m_type")
    m_arch = c[3].selectbox("Battery Architecture", ["Low Voltage LV", "High Voltage HV", "غير معروف"], key="m_arch")
    m_i_brand = st.text_input("شركة الإنفيرتر", key="m_i_brand")
    m_i_model = st.text_input("موديل الإنفيرتر", key="m_i_model")

    st.markdown("### 🔀 إعداد MPPT و Strings")
    s1 = st.number_input("MPPT 1 — عدد Strings", min_value=1, max_value=4, value=1, step=1, key="manual_s1")
    use2 = st.checkbox("➕ إضافة MPPT 2", key="manual_use2")
    s2 = st.number_input("MPPT 2 — عدد Strings", min_value=1, max_value=4, value=1, step=1, key="manual_s2") if use2 else 0
    use3 = st.checkbox("➕ إضافة MPPT 3", key="manual_use3")
    s3 = st.number_input("MPPT 3 — عدد Strings", min_value=1, max_value=4, value=1, step=1, key="manual_s3") if use3 else 0
    mppt_string_counts = [s1] + ([s2] if use2 else []) + ([s3] if use3 else [])
    manual_cfg = mppt_string_counts

    st.markdown("### 🔋 البطارية الخارجية — اختياري")
    c = st.columns(4)
    m_bv = c[0].number_input("Nominal Battery Voltage (V)", min_value=0.0, value=51.2, step=0.1, key="m_bv")
    m_bah = c[1].number_input("Capacity (Ah)", min_value=0.0, value=0.0, step=10.0, key="m_bah")
    m_bkwh = c[2].number_input("Capacity (kWh)", min_value=0.0, value=0.0, step=0.1, key="m_bkwh")
    m_bdis = c[3].number_input("Max Discharge (A)", min_value=0.0, value=0.0, step=5.0, key="m_bdis")

    manual_data = {
        "panel": {"brand": m_p_brand or "إدخال يدوي", "model": m_p_model or "Manual Panel",
                  "part_number": "غير معروف", "type": "Manual",
                  "pmax": m_pmax, "voc": m_voc, "vmp": m_vmp, "isc": m_isc, "imp": m_imp},
        "inverter": {"brand": m_i_brand or "إدخال يدوي", "model": m_i_model or "Manual Inverter",
                     "part_number": "غير معروف", "type": m_type, "phase_type": m_phase,
                     "voltage_architecture": m_arch, "ac_rated_power_w": m_ac,
                     "v_max": m_dcmax, "v_mppt_min": m_mpptmin, "v_mppt_max": m_mpptmax,
                     "v_start": 0, "mppt_count": len(mppt_string_counts),
                     "strings_per_mppt": max(mppt_string_counts), "mppt_strings_config": mppt_string_counts,
                     "max_mppt_current": m_mpptcurrent,
                     "battery": {"supported": m_type != "On-Grid", "nominal_voltage_v": m_bv if m_type != "On-Grid" else 0,
                                 "battery_type": "Manual", "max_charge_current_a": 0},
                     "ac_input_output": {"nominal_ac_voltage_v": "يدوي", "frequency_hz": "50/60",
                                         "max_ac_input_current_a": 0, "max_ac_output_current_a": 0},
                     "startup_surge": {"surge_power_va": 0, "duration_seconds": 0}},
        "external_battery": {"brand": "إدخال يدوي", "model": "Manual Battery", "chemistry": "غير معروف",
                             "capacity_ah": m_bah, "capacity_kwh": m_bkwh, "nominal_voltage_v": m_bv,
                             "max_charge_current_a": 0, "max_discharge_current_a": m_bdis}
    }


def safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=1):
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def compress_image_for_speed(pil_img, max_dim=1024):
    img_copy = pil_img.copy()
    img_copy.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    return img_copy


def is_battery_voltage_compatible(v1, v2):
    if v1 <= 0 or v2 <= 0:
        return True, "تعذر الجزم بالكامل لعدم توفر قراءة دقيقة للجهد."
    if (40.0 <= v1 <= 60.0) and (40.0 <= v2 <= 60.0):
        return True, f"جهد البطارية ({v2}V) متوافق مع نظام الإنفيرتر ({v1}V)."
    if abs(v1 - v2) <= 5.0:
        return True, f"الجهد متوافق تقريباً بين الإنفيرتر ({v1}V) والبطارية ({v2}V)."
    return False, f"غير متوافق: جهد البطارية ({v2}V) يختلف عن جهد نظام الإنفيرتر ({v1}V)."


JSON_STRUCTURE = """
{
  "panel": {"brand": "", "model": "", "part_number": "", "type": "", "pmax": 0, "voc": 0.0, "vmp": 0.0, "isc": 0.0, "imp": 0.0},
  "inverter": {"brand": "", "model": "", "part_number": "", "type": "", "phase_type": "", "voltage_architecture": "", "ac_rated_power_w": 0.0, "v_max": 0.0, "v_mppt_min": 0.0, "v_mppt_max": 0.0, "v_start": 0.0, "mppt_count": 1, "strings_per_mppt": 1, "max_mppt_current": 0.0, "battery": {"supported": true, "nominal_voltage_v": 0.0, "battery_type": "", "max_charge_current_a": 0.0}, "ac_input_output": {"nominal_ac_voltage_v": "", "frequency_hz": "", "max_ac_input_current_a": 0.0, "max_ac_output_current_a": 0.0}, "startup_surge": {"surge_power_va": 0.0, "duration_seconds": 0.0}},
  "external_battery": {"brand": "", "model": "", "chemistry": "", "capacity_ah": 0.0, "capacity_kwh": 0.0, "nominal_voltage_v": 0.0, "max_charge_current_a": 0.0, "max_discharge_current_a": 0.0}
}
"""


def extract_via_images(panel_img, inverter_img, battery_img, key):
    client = genai.Client(api_key=key)
    contents = [compress_image_for_speed(panel_img), compress_image_for_speed(inverter_img)]
    if battery_img:
        contents.append(compress_image_for_speed(battery_img))
    prompt = f"حلل الصور واستخرج البيانات وفق هيكل JSON التالي فقط:\n{JSON_STRUCTURE}"
    contents.append(prompt)
    response = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
    )
    return json.loads(response.text)


def extract_via_text(p_text, i_text, b_text, key):
    client = genai.Client(api_key=key)
    prompt = f"استخرج مواصفات اللوح ({p_text}) والإنفيرتر ({i_text}) والبطارية ({b_text}) كـ JSON:\n{JSON_STRUCTURE}"
    response = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
    )
    return json.loads(response.text)


if st.button("⚡ تحليل سريع واستخراج التقرير والحسابات"):
    if "🧮" in search_mode:
        st.session_state["analysis_result"] = manual_data
    elif not api_key:
        st.error("⚠️ يرجى إدخال مفتاح Gemini API Key.")
    else:
        try:
            if "📸" in search_mode:
                res = extract_via_images(Image.open(uploaded_panel), Image.open(uploaded_inverter), Image.open(uploaded_battery) if enable_battery else None, api_key)
            else:
                res = extract_via_text(panel_text_query, inverter_text_query, battery_text_query if enable_battery else "", api_key)
            st.session_state["analysis_result"] = res
            st.toast("🚀 تم التحليل بنجاح!", icon="⚡")
        except Exception as e:
            st.error(f"خطأ أثناء المعالجة: {e}")

if "analysis_result" in st.session_state and st.session_state["analysis_result"]:
    res = st.session_state["analysis_result"]
    st.success("✅ الكลัง والبيانات جاهزة للعرض والحسابات الهندسية.")
