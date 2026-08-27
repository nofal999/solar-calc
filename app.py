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

# 3. الدوال المساعدة
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


def format_val(value, unit=""):
    if (
        value is None
        or value == ""
        or value == 0
        or value == 0.0
        or value == "غير محدد"
        or value == "غير معروف"
    ):
        return "`غير موجود في البيانات`"
    return f"`{value} {unit}`".strip()


def compress_image_for_speed(pil_img, max_dim=1024):
    img_copy = pil_img.copy()
    img_copy.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    return img_copy


def is_battery_voltage_compatible(v1, v2):
    if v1 <= 0 or v2 <= 0:
        return True, "تعذر الجزم بالكامل لعدم توفر قراءة دقيقة للجهد."
    if (40.0 <= v1 <= 60.0) and (40.0 <= v2 <= 60.0):
        return True, f"جهد البطارية ({v2}V) متوافق مع نظام الإنفيرتر ({v1}V) ضمن فئة الـ 48V/51.2V Standard Lithium."
    if (20.0 <= v1 <= 30.0) and (20.0 <= v2 <= 30.0):
        return True, f"جهد البطارية ({v2}V) متوافق مع نظام الإنفيرتر ({v1}V) ضمن فئة الـ 24V."
    if (10.0 <= v1 <= 15.0) and (10.0 <= v2 <= 15.0):
        return True, f"جهد البطارية ({v2}V) متوافق مع نظام الإنفيرتر ({v1}V) ضمن فئة الـ 12V."
    if v1 >= 100.0 and v2 >= 100.0:
        if abs(v1 - v2) <= 50.0:
            return True, f"جهد البطارية العالي ({v2}V) متوافق مع نطاق الإنفيرتر HV ({v1}V)."
    if abs(v1 - v2) <= 5.0:
        return True, f"الجهد متوافق تقريباً بين الإنفيرتر ({v1}V) والبطارية ({v2}V)."
    return False, f"غير متوافق: جهد البطارية ({v2}V) يختلف جوهرياً عن جهد نظام الإنفيرتر ({v1}V)."


st.title("☀️ حاسبة توافق الألواح والإنفيرتر والبطاريات")
st.caption(
    "تحليل ذكي متكامل للمواصفات الكهربائية، نوع الجهد، نظام الفازات،"
    " البطاريات الخارجية، وتوزيع السلاسل الميدانية آلياً"
)

# 4. الشريط الجانبي
with st.sidebar:
    st.header("⚙️ الإعدادات")
    api_key = st.text_input(
        "مفتاح Gemini API Key:",
        type="password",
        help="احصل عليه مجاناً من Google AI Studio",
    )
    st.info("💡 المفتاح مطلوب فقط في حالة استخدام البحث بالصور أو النص الذكي.")

# 5. طريقة إدخال البيانات
search_mode = st.radio(
    "اختر طريقة إدخال البيانات:",
    [
        "✍️ 3. الإدخال اليدوي الكامل للقيم (بدون ذكاء اصطناعي)",
        "📸 1. البحث عن طريق الصور (إرفاق الملصقات)",
        "✍️ 2. البحث عن طريق اسم الشركة والموديل (نصياً)",
    ],
    index=0,
)

enable_battery = st.toggle("🔋 تفعيل فحص وتحليل بطارية خارجية مخصصة", value=True)

JSON_STRUCTURE = """
{
  "panel": {
    "brand": "الشركة المصنعة للوح",
    "model": "اسم وموديل اللوح",
    "pmax": 0,
    "voc": 0.0,
    "vmp": 0.0,
    "isc": 0.0,
    "imp": 0.0
  },
  "inverter": {
    "brand": "الشركة المصنعة للإنفيرتر",
    "model": "اسم وموديل الإنفيرتر",
    "type": "نوع الإنفيرتر (On-Grid, Off-Grid, Hybrid)",
    "phase_type": "عدد الفازات (Single-Phase أو Three-Phase)",
    "ac_rated_power_w": 0.0,
    "v_max": 0.0,
    "v_mppt_min": 0.0,
    "v_mppt_max": 0.0,
    "mppt_count": 1,
    "strings_per_mppt": 1,
    "max_mppt_current": 0.0,
    "battery": {
      "supported": true,
      "nominal_voltage_v": 0.0
    }
  },
  "external_battery": {
    "brand": "الشركة المصنعة للبطارية الخارجية",
    "model": "اسم وموديل البطارية الخارجية",
    "capacity_ah": 0.0,
    "capacity_kwh": 0.0,
    "nominal_voltage_v": 0.0
  }
}
"""


def extract_via_images(panel_img, inverter_img, battery_img, key):
    client = genai.Client(api_key=key)
    contents = [compress_image_for_speed(panel_img), compress_image_for_speed(inverter_img)]
    if battery_img:
        contents.append(compress_image_for_speed(battery_img))
    prompt = f"استخرج البيانات التالية بأسلوب JSON فقط دون أي مقدمات:\n{JSON_STRUCTURE}"
    contents.append(prompt)
    response = client.models.generate_content(
        model="models/gemini-3.6-flash",
        contents=contents,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
    )
    return json.loads(response.text)


def extract_via_text(p_text, i_text, b_text, key):
    client = genai.Client(api_key=key)
    prompt = f"اللوح الشمسي: '{p_text}'\nالإنفيرتر: '{i_text}'\nالبطارية: '{b_text}'\nاستخرج المواصفات كـ JSON فقط:\n{JSON_STRUCTURE}"
    response = client.models.generate_content(
        model="models/gemini-3.6-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
    )
    return json.loads(response.text)


if "3. الإدخال اليدوي" in search_mode:
    st.markdown("---")
    st.subheader("✍️ أدخل القيم الفنية يدوياً من الكتالوج (Datasheet)")

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.markdown("### ☀️ مواصفات اللوح الشمسي")
        m_p_brand = st.text_input("الشركة المصنعة للوح", value="Jinko Solar")
        m_p_model = st.text_input("موديل اللوح", value="JKM640N-66HL4M-BDV-Z2")
        m_pmax = st.number_input("القدرة القصوى Pmax (W)", value=640.0)
        m_voc = st.number_input("جهد الدارة المفتوحة Voc (V)", value=49.88)
        m_vmp = st.number_input("الجهد التشغيلي Vmp (V)", value=41.30)
        m_isc = st.number_input("تيار القصر Isc (A)", value=16.32)
        m_imp = st.number_input("تيار التشغيل Imp (A)", value=15.50)

    with col_m2:
        st.markdown("### ⚡ مواصفات الإنفيرتر")
        m_i_brand = st.text_input("الشركة المصنعة للإنفيرتر", value="Deye")
        m_i_model = st.text_input("موديل الإنفيرتر", value="SUN-5K-SG04LP1-EU")
        m_i_type = st.selectbox("نوع الإنفيرتر", ["Hybrid", "Off-Grid", "On-Grid"], index=0)
        m_phase = st.selectbox("عدد الفازات", ["Single-Phase", "Three-Phase"], index=0)
        m_ac_power = st.number_input("القدرة الاسمية AC (W)", value=5000.0)
        m_v_max = st.number_input("أقصى جهد مستمر DC Max (V)", value=500.0)
        m_v_mppt_min = st.number_input("أدنى جهد MPPT (V)", value=125.0)
        m_v_mppt_max = st.number_input("أقصى جهد MPPT (V)", value=425.0)
        m_mppt_count = st.number_input("عدد مداخل MPPT", value=1, step=1)
        m_strings_per_mppt = st.number_input("عدد السلاسل لكل MPPT", value=1, step=1)
        m_max_mppt_current = st.number_input("أقصى تيار لمدخل MPPT (A)", value=18.0)
        m_inv_batt_v = st.number_input("جهد بطارية الإنفيرتر الاسمي (V)", value=48.0)

    if enable_battery:
        st.markdown("### 🔋 مواصفات البطارية الخارجية")
        col_mb1, col_mb2, col_mb3 = st.columns(3)
        with col_mb1:
            m_b_brand = st.text_input("الشركة المصنعة للبطارية", value="Felicity Solar")
            m_b_model = st.text_input("موديل البطارية", value="LPBF48300")
        with col_mb2:
            m_b_chem = st.text_input("الكيمياء", value="LiFePO4")
            m_b_volts = st.number_input("الجهد الاسمي للبطارية (V)", value=48.0)
        with col_mb3:
            m_b_ah = st.number_input("السعة (Ah)", value=300.0)
            m_b_kwh = st.number_input("الطاقة (kWh)", value=14.4)

    if st.button("🚀 اعتماد البيانات اليدوية وبدء الحسابات"):
        res = {
            "panel": {
                "brand": m_p_brand, "model": m_p_model, "pmax": m_pmax,
                "voc": m_voc, "vmp": m_vmp, "isc": m_isc, "imp": m_imp
            },
            "inverter": {
                "brand": m_i_brand, "model": m_i_model, "type": m_i_type,
                "phase_type": m_phase, "ac_rated_power_w": m_ac_power,
                "v_max": m_v_max, "v_mppt_min": m_v_mppt_min, "v_mppt_max": m_v_mppt_max,
                "mppt_count": m_mppt_count, "strings_per_mppt": m_strings_per_mppt,
                "max_mppt_current": m_max_mppt_current,
                "battery": {"supported": True, "nominal_voltage_v": m_inv_batt_v}
            },
            "external_battery": {
                "brand": m_b_brand if enable_battery else "غير محدد",
                "model": m_b_model if enable_battery else "غير محدد",
                "capacity_ah": m_b_ah if enable_battery else 0.0,
                "capacity_kwh": m_b_kwh if enable_battery else 0.0,
                "nominal_voltage_v": m_b_volts if enable_battery else 0.0
            }
        }
        st.session_state["analysis_result"] = res
        st.success("✅ تم اعتماد البيانات اليدوية بنجاح!")

else:
    uploaded_panel = None
    uploaded_inverter = None
    uploaded_battery = None
    panel_text_query = ""
    inverter_text_query = ""
    battery_text_query = ""

    if "📸" in search_mode:
        cols = st.columns(3 if enable_battery else 2)
        with cols[0]:
            uploaded_panel = st.file_uploader("📸 صورة اللوح", type=["jpg", "jpeg", "png"])
        with cols[1]:
            uploaded_inverter = st.file_uploader("📸 صورة الإنفيرتر", type=["jpg", "jpeg", "png"])
        if enable_battery:
            with cols[2]:
                uploaded_battery = st.file_uploader("📸 صورة البطارية", type=["jpg", "jpeg", "png"])
    else:
        cols = st.columns(3 if enable_battery else 2)
        with cols[0]:
            panel_text_query = st.text_input("☀️ اللوح الشمسي:")
        with cols[1]:
            inverter_text_query = st.text_input("⚡ الإنفيرتر:")
        if enable_battery:
            with cols[2]:
                battery_text_query = st.text_input("🔋 البطارية:")

    if st.button("⚡ تحليل واستخراج البيانات ذكياً"):
        if not api_key:
            st.error("⚠️ يرجى إدخال مفتاح Gemini API Key.")
        else:
            try:
                with st.spinner("⚡ جاري المعالجة..."):
                    if "📸" in search_mode:
                        res_extracted = extract_via_images(uploaded_panel, uploaded_inverter, uploaded_battery if enable_battery else None, api_key)
                    else:
                        res_extracted = extract_via_text(panel_text_query, inverter_text_query, battery_text_query if enable_battery else "", api_key)
                    st.session_state["analysis_result"] = res_extracted
                    st.success("✅ تم الاستخراج بنجاح!")
            except Exception as e:
                st.error(f"حدث خطأ: {e}")

# 6. عرض النتائج والتحليل
if "analysis_result" in st.session_state and st.session_state["analysis_result"]:
    res = st.session_state["analysis_result"]
    panel = res.get("panel", {})
    inv = res.get("inverter", {})
    ext_batt = res.get("external_battery", {})

    pmax = safe_float(panel.get("pmax"))
    voc = safe_float(panel.get("voc"))
    vmp = safe_float(panel.get("vmp"))
    isc = safe_float(panel.get("isc"))

    v_max = safe_float(inv.get("v_max"))
    v_mppt_min = safe_float(inv.get("v_mppt_min"))
    v_mppt_max = safe_float(inv.get("v_mppt_max"))
    mppt_count = safe_int(inv.get("mppt_count"), 1)
    strings_per_mppt = safe_int(inv.get("strings_per_mppt"), 1)

    st.markdown("---")
    st.subheader("📌 البيانات المعتمدة")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"- **القدرة (Pmax):** `{pmax} W`")
        st.write(f"- **جهد الدارة (Voc):** `{voc} V`")
        st.write(f"- **الجهد التشغيلي (Vmp):** `{vmp} V`")
    with col2:
        st.write(f"- **أقصى جهد DC:** `{v_max} V`")
        st.write(f"- **نطاق MPPT:** `{v_mppt_min}V - {v_mppt_max}V`")

    if voc > 0 and vmp > 0 and v_max > 0:
        v_mppt_min_safe = v_mppt_min * 1.10
        min_string_safe = math.ceil(v_mppt_min_safe / vmp) if vmp > 0 else 1
        voc_cold_safe = voc * 1.15
        v_max_safe = v_max * 0.95

        max_by_voc = math.floor(v_max_safe / voc_cold_safe) if voc_cold_safe > 0 else 1
        max_by_mppt = math.floor(v_mppt_max / vmp) if vmp > 0 and v_mppt_max > 0 else max_by_voc
        max_string_safe = min(max_by_voc, max_by_mppt) if max_by_mppt > 0 else max_by_voc

        if max_string_safe < min_string_safe:
            max_string_safe = min_string_safe

        rec_string = math.floor((min_string_safe + max_string_safe) / 2)
        total_strings = mppt_count * strings_per_mppt

        st.markdown("---")
        st.subheader("⚡ نتائج التوصيل وتوزيع السلاسل الآمن")
        st.success(f"""
        🛡️ **حدود الأمان بالسلسلة الواحدة:**
        * **أقل عدد ألواح آمن بالسلسلة:** `{min_string_safe}` ألواح (لتجاوز أدنى جهد MPPT).
        * **أكبر عدد ألواح آمن بالسلسلة:** `{max_string_safe}` لوحاً (لعدم تجاوز أقصى جهد في الشتاء).
        * **العدد الموصى به مثالياً بالسلسلة:** `{rec_string}` ألواح.
        """)

        st.markdown("### 🧮 فحص وتوزيع عدد ألواح مخصص")
        custom_panels_count = st.number_input(
            "أدخل إجمالي عدد الألواح التي ترغب بتركيبها:",
            min_value=1,
            max_value=100,
            value=int(rec_string * total_strings),
            step=1,
        )

        if custom_panels_count > 0:
            custom_kw = round((custom_panels_count * pmax) / 1000, 2)
            st.write(f"- **إجمالي قدرة التوليد:** `{custom_kw} kW`")
            num_strings_used = min(total_strings, custom_panels_count)
            panels_per_str = custom_panels_count // num_strings_used if num_strings_used > 0 else custom_panels_count
            
            if panels_per_str < min_string_safe:
                st.error(f"❌ **العدد غير آمن:** الألواح بالسلسلة ({panels_per_str}) أقل من الحد الأدنى ({min_string_safe}).")
            elif panels_per_str > max_string_safe:
                st.error(f"⚠️ **العدد غير آمن:** الألواح بالسلسلة ({panels_per_str}) أكبر من الحد الأقصى ({max_string_safe}).")
            else:
                st.success(f"✅ **العدد متوافق وآمن:** استخدم `{num_strings_used}` سلاسل بواقع `{panels_per_str}` ألواح لكل سلسلة.")
