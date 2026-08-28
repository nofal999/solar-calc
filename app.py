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
    st.info("💡 مفتاح Gemini مطلوب لوضعي الصور والبحث النصي فقط. الإدخال اليدوي لا يحتاج مفتاحاً[cite: 2].")

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

# تفعيل أو إيقاف تحليل البطارية الخارجية
enable_battery = st.toggle("🔋 تفعيل فحص وتحليل بطارية خارجية مخصصة", value=False)

uploaded_panel = None
uploaded_inverter = None
uploaded_battery = None
panel_text_query = ""
inverter_text_query = ""
battery_text_query = ""
 manual_data = {"panel": {}, "inverter": {}, "external_battery": {}}
mppt_string_counts = [1]

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
    st.info("🧮 الإدخال اليدوي لا يحتاج Gemini API Key[cite: 2].")
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
    st.caption("الحد الأدنى MPPT1 + String1. يمكنك إضافة MPPT2 وMPPT3، ولكل MPPT عدد Strings مستقل[cite: 2].")

    s1 = st.number_input("MPPT 1 — عدد Strings", min_value=1, max_value=4, value=1, step=1, key="manual_s1")
    use2 = st.checkbox("➕ إضافة MPPT 2", key="manual_use2")
    s2 = st.number_input("MPPT 2 — عدد Strings", min_value=1, max_value=4, value=1, step=1, key="manual_s2") if use2 else 0
    use3 = st.checkbox("➕ إضافة MPPT 3", key="manual_use3")
    s3 = st.number_input("MPPT 3 — عدد Strings", min_value=1, max_value=4, value=1, step=1, key="manual_s3") if use3 else 0
    mppt_string_counts = [s1] + ([s2] if use2 else []) + ([s3] if use3 else [])

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

# 5. دوال مساعدة
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


# دالة ذكية للتحقق من توافق فئة جهد البطارية (12V, 24V, 48V/51.2V, HV)
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


# هيكل الـ JSON الموحد
JSON_STRUCTURE = """
{
  "panel": {
    "brand": "الشركة المصنعة للوح",
    "model": "اسم وموديل اللوح",
    "part_number": "الرقم التسلسلي أو رقم القطعة للوح إن وجد",
    "type": "نوع اللوح (Monocrystalline, Polycrystalline, N-Type, etc.)",
    "pmax": 0,
    "voc": 0.0,
    "vmp": 0.0,
    "isc": 0.0,
    "imp": 0.0
  },
  "inverter": {
    "brand": "الشركة المصنعة للإنفيرتر",
    "model": "اسم وموديل الإنفيرتر",
    "part_number": "الرقم التسلسلي أو رقم الموديل الدقيق للإنفيرتر",
    "type": "نوع الإنفيرتر (On-Grid, Off-Grid, Hybrid)",
    "phase_type": "عدد الفازات (Single-Phase أو Three-Phase)",
    "voltage_architecture": "نوع الجهد المستمر (High Voltage HV أو Low Voltage LV)",
    "ac_rated_power_w": 0.0,
    "v_max": 0.0,
    "v_mppt_min": 0.0,
    "v_mppt_max": 0.0,
    "v_start": 0.0,
    "mppt_count": 1,
    "strings_per_mppt": 1,
    "max_mppt_current": 0.0,
    "battery": {
      "supported": true,
      "nominal_voltage_v": 0.0,
      "battery_type": "أنواع البطاريات المدعومة",
      "max_charge_current_a": 0.0
    },
    "ac_input_output": {
      "nominal_ac_voltage_v": "جهد AC الاسمي",
      "frequency_hz": "التردد (50Hz / 60Hz)",
      "max_ac_input_current_a": 0.0,
      "max_ac_output_current_a": 0.0
    },
    "startup_surge": {
      "surge_power_va": 0.0,
      "duration_seconds": 0.0
    }
  },
  "external_battery": {
    "brand": "الشركة المصنعة للبطارية الخارجية",
    "model": "اسم وموديل البطارية الخارجية",
    "chemistry": "نوع الكيمياء (LiFePO4, Gel, Lead-Acid, etc.)",
    "capacity_ah": 0.0,
    "capacity_kwh": 0.0,
    "nominal_voltage_v": 0.0,
    "max_charge_current_a": 0.0,
    "max_discharge_current_a": 0.0
  }
}
"""


# 6. دالة الاستخراج عن طريق الصور
def extract_via_images(panel_img, inverter_img, battery_img, key):
    client = genai.Client(api_key=key)
    contents = []
    
    p_img_small = compress_image_for_speed(panel_img)
    contents.append(p_img_small)
    
    i_img_small = compress_image_for_speed(inverter_img)
    contents.append(i_img_small)
    
    if battery_img:
        b_img_small = compress_image_for_speed(battery_img)
        contents.append(b_img_small)

    prompt = f"""
    أنت مهندس طاقة شمسية خبير. قم بتحليل الصور المرفقة (لوح شمسي، إنفيرتر، وبطارية إن وجدت) واستخرج البيانات التالية بأسلوب JSON فقط دون أي مقدمات:
    {JSON_STRUCTURE}
    ملاحظة: 
    - أعد أرقاماً فقط للقيم الرقمية دون وحدات، واستخدم 0 للقيم المفقودة.
    - إذا لم تكن صورة البطارية مرفقة، اجعل قيم external_battery تساوي 0 أو "غير معروف".
    """
    contents.append(prompt)

    response = client.models.generate_content(
        model="models/gemini-3.6-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    return json.loads(response.text)


# 7. دالة الاستخراج عن طريق اسم الموديل (نصياً)
def extract_via_text(p_text, i_text, b_text, key):
    client = genai.Client(api_key=key)

    b_prompt = f'والبطارية الخارجية المطلوبة: "{b_text}"' if b_text else 'لا يوجد بطارية خارجية مخصصة.'

    prompt = f"""
    أنت خبير ومدرك لقواعد بيانات كتالوجات الألواح الشمسية والإنفيرترات والبطاريات (Datasheets).
    اللوح الشمسي المطلوب: "{p_text}"
    الإنفيرتر المطلوب: "{i_text}"
    {b_prompt}

    استخرج المواصفات الكهربائية القياسية لهذه الموديلات المحددة وعد بتقرير بأسلوب JSON بنفس الهيكل تماماً بدون أي مقدمات:
    {JSON_STRUCTURE}

    تنبه هام:
    - أعد أرقاماً فقط للقيم الرقمية (Numbers).
    - إذا كانت المواصفات دقيقة من الكتالوج استخدمها مباشرة، وإن تعذر معرفة قيمة معينة استخدم 0 للرقم و "غير معروف" للنص.
    - إذا لم تطلب بطارية، اجعل قيم external_battery تساوي 0 أو "غير معروف".
    """

    response = client.models.generate_content(
        model="models/gemini-3.6-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    return json.loads(response.text)


# 8. زر التفعيل والتحليل
if st.button("⚡ تحليل سريع واستخراج التقرير والحسابات"):
    if "🧮" in search_mode:
        res = manual_data
    elif not api_key:
        st.error("⚠️ يرجى إدخال مفتاح Gemini API Key في القائمة الجانبية.")
        res = None
    else:
        res = None
        start_t = time.time()

        if "📸" in search_mode:
            if not uploaded_panel or not uploaded_inverter:
                st.error("⚠️ يرجى تحميل صورة اللوح والإنفيرتر معاً لمتابعة الحسابات.")
            elif enable_battery and not uploaded_battery:
                st.error("⚠️ لقد قمت بتفعيل فحص البطارية، يرجى رفع صورة ملصق البطارية أيضاً.")
            else:
                try:
                    p_img = Image.open(uploaded_panel)
                    i_img = Image.open(uploaded_inverter)
                    b_img = Image.open(uploaded_battery) if enable_battery and uploaded_battery else None
                    with st.spinner("⚡ جاري قراءة الملصقات وتحليل الصور عبر Gemini..."):
                        res = extract_via_images(p_img, i_img, b_img, api_key)
                except Exception as e:
                    st.error(f"حدث خطأ أثناء معالجة الصور: {e}")
        else:
            if not panel_text_query or not inverter_text_query:
                st.error(
                    "⚠️ يرجى كتابة اسم الشركة والموديل للوح والإنفيرتر معاً."
                )
            elif enable_battery and not battery_text_query:
                st.error("⚠️ لقد قمت بتفعيل فحص البطارية، يرجى كتابة اسم وموديل البطارية أيضاً.")
            else:
                try:
                    with st.spinner(
                        "🔍 جاري البحث عن مواصفات الكتالوج والتحليل..."
                    ):
                        res = extract_via_text(
                            panel_text_query, inverter_text_query, battery_text_query if enable_battery else "", api_key
                        )
                except Exception as e:
                    st.error(f"حدث خطأ أثناء البحث بالنص: {e}")

        if res:
            st.session_state["analysis_result"] = res
            st.toast(
                f"🚀 تم التحليل واستخراج المواصفات في {round(time.time() - start_t, 2)} ثوانٍ!",
                icon="⚡",
            )


# 9. أدوات وحسابات V2
def safe_text(value, default="غير معروف"):
    if value is None or value == "":
        return default
    return str(value)


def clamp_positive_int(value, default=1):
    try:
        return max(1, int(value))
    except (ValueError, TypeError):
        return default


def calculate_string_limits(pmax, voc, vmp, isc, v_max, v_mppt_min, v_mppt_max):
    """حساب حدود السلسلة مع هوامش أمان محافظة."""
    if min(voc, vmp, v_max) <= 0:
        return None

    # هامش تصميم قابل للتعديل من الواجهة
    cold_factor = st.session_state.get("cold_factor", 1.15)
    voltage_margin = st.session_state.get("voltage_margin", 0.95)
    mppt_margin = st.session_state.get("mppt_margin", 1.10)

    mppt_min_safe = v_mppt_min * mppt_margin if v_mppt_min > 0 else 0
    min_series = math.ceil(mppt_min_safe / vmp) if mppt_min_safe > 0 else 1

    voc_cold = voc * cold_factor
    max_by_voc = math.floor((v_max * voltage_margin) / voc_cold) if voc_cold > 0 else 1
    max_by_mppt = (
        math.floor(v_mppt_max / vmp)
        if v_mppt_max > 0 and vmp > 0
        else max_by_voc
    )
    max_series = min(max_by_voc, max_by_mppt)

    return {
        "min_series": max(1, min_series),
        "max_series": max(1, max_series),
        "mppt_min_safe": mppt_min_safe,
        "voc_cold_factor": cold_factor,
        "voc_cold_panel": voc_cold,
        "vmax_safe": v_max * voltage_margin,
        "isc_safe": isc * 1.25 if isc > 0 else 0,
    }


def distribute_panels(total_panels, mppt_count, strings_per_mppt):
    """توزيع متوازن فعلياً للألواح على MPPTs وStrings."""
    total_strings = max(1, mppt_count * strings_per_mppt)
    base = total_panels // total_strings
    remainder = total_panels % total_strings

    strings = []
    for s in range(total_strings):
        n = base + (1 if s < remainder else 0)
        mppt = (s // strings_per_mppt) + 1
        strings.append({"string": s + 1, "mppt": mppt, "panels": n})

    return strings


def validate_string_distribution(strings, pmax, voc, vmp, isc,
                                 v_max, v_mppt_min, v_mppt_max,
                                 max_mppt_current, max_strings_per_mppt):
    warnings = []
    errors = []

    by_mppt = {}
    for item in strings:
        by_mppt.setdefault(item["mppt"], []).append(item)

    for item in strings:
        n = item["panels"]
        if n <= 0:
            errors.append(f"MPPT {item['mppt']} / String {item['string']}: لا توجد ألواح.")

        vmp_s = n * vmp
        voc_cold_s = n * voc * 1.15

        if v_mppt_min > 0 and vmp_s < v_mppt_min * 1.10:
            errors.append(
                f"MPPT {item['mppt']} / String {item['string']}: "
                f"Vmp={vmp_s:.1f}V أقل من حد MPPT الآمن."
            )

        if v_mppt_max > 0 and vmp_s > v_mppt_max:
            errors.append(
                f"MPPT {item['mppt']} / String {item['string']}: "
                f"Vmp={vmp_s:.1f}V يتجاوز نطاق MPPT."
            )

        if v_max > 0 and voc_cold_s > v_max * 0.95:
            errors.append(
                f"MPPT {item['mppt']} / String {item['string']}: "
                f"Voc البارد التقريبي={voc_cold_s:.1f}V قريب/أعلى من الحد الآمن."
            )

    for mppt, mppt_strings in by_mppt.items():
        current = len(mppt_strings) * isc * 1.25
        if max_mppt_current > 0 and current > max_mppt_current:
            warnings.append(
                f"MPPT {mppt}: التيار التصميمي للتوازي ≈ {current:.2f}A "
                f"أعلى من حد MPPT {max_mppt_current:.2f}A."
            )

    return errors, warnings


def battery_design(batt_voltage, batt_ah, batt_kwh, max_discharge,
                   load_w, autonomy_h, dod, inverter_efficiency):
    """تقدير عدد البطاريات/السعة المطلوبة عند توفر بيانات كافية."""
    if load_w <= 0 or autonomy_h <= 0:
        return None

    required_wh = load_w * autonomy_h / max(inverter_efficiency, 0.1)
    usable_factor = max(0.05, min(dod, 1.0))
    required_nominal_wh = required_wh / usable_factor

    if batt_kwh > 0:
        unit_wh = batt_kwh * 1000
    elif batt_voltage > 0 and batt_ah > 0:
        unit_wh = batt_voltage * batt_ah
    else:
        unit_wh = 0

    count = math.ceil(required_nominal_wh / unit_wh) if unit_wh > 0 else 0
    total_kwh = count * unit_wh / 1000 if unit_wh > 0 else 0

    discharge_power = batt_voltage * max_discharge if batt_voltage > 0 and max_discharge > 0 else 0

    return {
        "required_nominal_kwh": required_nominal_wh / 1000,
        "unit_kwh": unit_wh / 1000 if unit_wh else 0,
        "battery_count": count,
        "total_kwh": total_kwh,
        "max_battery_power_w": discharge_power,
    }


# 10. عرض النتائج والحسابات
if "analysis_result" in st.session_state and st.session_state["analysis_result"]:
    res = st.session_state["analysis_result"]
    panel = res.get("panel", {})
    inv = res.get("inverter", {})
    ext_batt = res.get("external_battery", {})

    # Sidebar engineering controls
    with st.sidebar:
        st.markdown("---")
        st.header("🧮 إعدادات الحساب الهندسي")
        st.slider("هامش برودة Voc", 1.05, 1.30, 1.15, 0.01, key="cold_factor")
        st.slider("هامش أمان جهد DC", 0.90, 1.00, 0.95, 0.01, key="voltage_margin")
        st.slider("هامش رفع حد MPPT الأدنى", 1.00, 1.20, 1.10, 0.01, key="mppt_margin")
        st.caption("هذه الهوامش تصميمية وليست بديلاً عن Datasheet وتعليمات الشركة المصنعة.")

    p_brand = safe_text(panel.get("brand"))
    p_model = safe_text(panel.get("model"))
    p_part = safe_text(panel.get("part_number"))
    p_type = safe_text(panel.get("type"))

    pmax = safe_float(panel.get("pmax"))
    voc = safe_float(panel.get("voc"))
    vmp = safe_float(panel.get("vmp"))
    isc = safe_float(panel.get("isc"))
    imp = safe_float(panel.get("imp"))

    i_brand = safe_text(inv.get("brand"))
    i_model = safe_text(inv.get("model"))
    i_part = safe_text(inv.get("part_number"))
    i_type = safe_text(inv.get("type"))
    phase_type = safe_text(inv.get("phase_type"))
    v_arch = safe_text(inv.get("voltage_architecture"))
    ac_rated_power = safe_float(inv.get("ac_rated_power_w"))

    v_max = safe_float(inv.get("v_max"))
    v_mppt_min = safe_float(inv.get("v_mppt_min"))
    v_mppt_max = safe_float(inv.get("v_mppt_max"))
    mppt_count = clamp_positive_int(inv.get("mppt_count"), 1)
    strings_per_mppt = clamp_positive_int(inv.get("strings_per_mppt"), 1)
    max_mppt_current = safe_float(inv.get("max_mppt_current"))
    manual_cfg = inv.get("mppt_strings_config", None)

    batt_info = inv.get("battery", {}) or {}
    ac_info = inv.get("ac_input_output", {}) or {}
    surge_info = inv.get("startup_surge", {}) or {}

    b_brand = safe_text(ext_batt.get("brand"))
    b_model = safe_text(ext_batt.get("model"))
    b_chem = safe_text(ext_batt.get("chemistry"))
    b_volts = safe_float(ext_batt.get("nominal_voltage_v"))
    b_ah = safe_float(ext_batt.get("capacity_ah"))
    b_kwh = safe_float(ext_batt.get("capacity_kwh"))
    b_max_chg = safe_float(ext_batt.get("max_charge_current_a"))
    b_max_dischg = safe_float(ext_batt.get("max_discharge_current_a"))

    isc_safe = isc * 1.25 if isc > 0 else 0

    # Engineering validation
    system_errors = []
    system_warnings = []

    i_type_lower = i_type.lower()
    is_on_grid = any(x in i_type_lower for x in ["on-grid", "ongrid", "grid-tied"])
    has_external_battery = b_volts > 0 or (enable_battery and b_model not in ["غير معروف", ""])

    if is_on_grid and has_external_battery:
        system_errors.append(
            "تناقض: تم إدخال بطارية خارجية مع إنفيرتر مصنف On-Grid."
        )

    inv_batt_v = safe_float(batt_info.get("nominal_voltage_v"))
    if not is_on_grid and has_external_battery and inv_batt_v > 0 and b_volts > 0:
        ok, msg = is_battery_voltage_compatible(inv_batt_v, b_volts)
        if not ok:
            system_errors.append(msg)

    if max_mppt_current > 0 and isc_safe > max_mppt_current:
        system_warnings.append(
            f"تيار اللوح التصميمي {isc_safe:.2f}A أعلى من حد MPPT "
            f"{max_mppt_current:.2f}A عند String واحد."
        )

    # Header / summary
    st.markdown("---")
    st.subheader("📊 لوحة الحالة الهندسية")

    status = "متوافق مبدئياً" if not system_errors else "يحتاج تصحيح"
    if system_errors:
        st.error(f"🔴 حالة النظام: **{status}**")
    elif system_warnings:
        st.warning(f"🟡 حالة النظام: **{status} مع تنبيهات**")
    else:
        st.success(f"🟢 حالة النظام: **{status}**")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("قدرة اللوح", f"{pmax:.0f} W" if pmax else "N/A")
    with k2:
        st.metric("قدرة الإنفيرتر", f"{ac_rated_power/1000:.2f} kW" if ac_rated_power else "N/A")
    with k3:
        ratio = (pmax / ac_rated_power) if ac_rated_power and pmax else 0
        st.metric("DC/AC", f"{ratio:.2f}" if ratio else "N/A")
    with k4:
        st.metric("MPPT", f"{mppt_count}")

    # Identity
    st.subheader("📌 المواصفات المكتشفة")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### ☀️ اللوح الشمسي")
        st.write(f"**الشركة:** {p_brand}")
        st.write(f"**الموديل:** {p_model}")
        st.write(f"**Part Number:** {p_part}")
        st.write(f"**النوع:** {p_type}")
        st.write(f"**Pmax:** {pmax:g} W")
        st.write(f"**Voc / Vmp:** {voc:g} V / {vmp:g} V")
        st.write(f"**Isc / Imp:** {isc:g} A / {imp:g} A")

    with c2:
        st.markdown("### ⚡ الإنفيرتر")
        st.write(f"**الشركة:** {i_brand}")
        st.write(f"**الموديل:** {i_model}")
        st.write(f"**Part Number:** {i_part}")
        st.write(f"**النوع:** {i_type}")
        st.write(f"**الفازات:** {phase_type}")
        st.write(f"**DC Architecture:** {v_arch}")
        st.write(f"**AC Rated:** {ac_rated_power:g} W")
        st.write(f"**DC Max:** {v_max:g} V")
        st.write(f"**MPPT:** {v_mppt_min:g}–{v_mppt_max:g} V")
        st.write(f"**MPPT Count:** {mppt_count} × {strings_per_mppt} String")

    # Battery / AC / Surge
    st.markdown("---")
    b1, b2, b3 = st.columns(3)

    with b1:
        st.markdown("### 🔋 البطارية")
        st.write(f"**دعم البطارية:** {'نعم' if batt_info.get('supported', False) else 'لا/غير مؤكد'}")
        st.write(f"**جهد الإنفيرتر:** {inv_batt_v:g} V")
        st.write(f"**الأنواع:** {safe_text(batt_info.get('battery_type'))}")
        st.write(f"**أقصى شحن:** {safe_float(batt_info.get('max_charge_current_a')):g} A")

    with b2:
        st.markdown("### 🔌 AC")
        st.write(f"**الجهد:** {safe_text(ac_info.get('nominal_ac_voltage_v'))}")
        st.write(f"**التردد:** {safe_text(ac_info.get('frequency_hz'))}")
        st.write(f"**Max Input:** {safe_float(ac_info.get('max_ac_input_current_a')):g} A")
        st.write(f"**Max Output:** {safe_float(ac_info.get('max_ac_output_current_a')):g} A")

    with b3:
        st.markdown("### 🚀 Startup / Surge")
        st.write(f"**Surge:** {safe_float(surge_info.get('surge_power_va')):g} VA")
        st.write(f"**Duration:** {safe_float(surge_info.get('duration_seconds')):g} s")

    # String calculations
    st.markdown("---")
    st.subheader("🔀 التصميم الذكي للسلاسل MPPT / Strings")

    limits = calculate_string_limits(
        pmax, voc, vmp, isc, v_max, v_mppt_min, v_mppt_max
    )

    if not limits:
        st.error("لا يمكن إجراء تصميم السلاسل بسبب نقص Voc/Vmp/DC Max.")
    else:
        min_s = limits["min_series"]
        max_s = limits["max_series"]
        total_strings = sum(manual_cfg) if manual_cfg and isinstance(manual_cfg, list) else (mppt_count * strings_per_mppt)

        if max_s < min_s:
            st.error(
                f"❌ لا يوجد نطاق سلسلة صالح: الحد الأدنى {min_s} والحد الأقصى {max_s}. "
                "راجع اللوح والإنفيرتر."
            )
        else:
            rec_s = (min_s + max_s) // 2
            min_panels = min_s * total_strings
            rec_panels = rec_s * total_strings
            max_panels = max_s * total_strings

            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Min / String", min_s)
            r2.metric("Recommended", rec_s)
            r3.metric("Max / String", max_s)
            r4.metric("إجمالي Strings", total_strings)

            st.info(
                f"حد MPPT الأدنى الآمن ≈ {limits['mppt_min_safe']:.1f}V | "
                f"Voc البارد للوح ≈ {limits['voc_cold_panel']:.1f}V | "
                f"DC Max الآمن ≈ {limits['vmax_safe']:.1f}V"
            )

            st.markdown("### ⭐ التوصية الأساسية")
            rec_kw = rec_panels * pmax / 1000 if pmax else 0
            dc_ac = rec_kw / (ac_rated_power / 1000) if ac_rated_power else 0

            if manual_cfg and isinstance(manual_cfg, list):
                st.info("🔀 إعداد المداخل: " + " | ".join(
                    f"MPPT{i+1}: {n} String" for i, n in enumerate(manual_cfg)
                ))

            st.success(
                f"**{rec_panels} لوحاً** = **{rec_kw:.2f} kWp**، "
                f"بواقع **{rec_s} ألواح لكل String** على **{total_strings} Strings**. "
                f"نسبة DC/AC ≈ **{dc_ac:.2f}**."
            )

            # Custom number of panels
            st.markdown("---")
            st.subheader("🧮 محاكاة عدد ألواح مخصص")

            default_n = int(rec_panels)
            custom_n = st.number_input(
                "إجمالي عدد الألواح:",
                min_value=1,
                max_value=max(1, max_panels * 4),
                value=default_n,
                step=1,
                key="v2_custom_panels",
            )

            if custom_n:
                if manual_cfg and isinstance(manual_cfg, list):
                    base = custom_n // total_strings
                    rem = custom_n % total_strings
                    strings = []
                    sid = 1
                    for mppt_no, count in enumerate(manual_cfg, 1):
                        for _ in range(count):
                            n = base + (1 if sid <= rem else 0)
                            strings.append({"string": sid, "mppt": mppt_no, "panels": n})
                            sid += 1
                else:
                    strings = distribute_panels(custom_n, mppt_count, strings_per_mppt)

                errors, warnings = validate_string_distribution(
                    strings, pmax, voc, vmp, isc, v_max,
                    v_mppt_min, v_mppt_max, max_mppt_current,
                    strings_per_mppt
                )

                if errors:
                    for msg in errors:
                        st.error("❌ " + msg)
                elif warnings:
                    for msg in warnings:
                        st.warning("⚠️ " + msg)
                else:
                    st.success("✅ توزيع العدد المدخل آمن مبدئياً ضمن البيانات المتاحة.")

                total_kw = custom_n * pmax / 1000 if pmax else 0
                st.metric("قدرة الألواح", f"{total_kw:.2f} kWp")

                rows = []
                for item in strings:
                    n = item["panels"]
                    rows.append({
                        "MPPT": item["mppt"],
                        "String": item["string"],
                        "Panels": n,
                        "Vmp (V)": round(n * vmp, 1) if vmp else 0,
                        "Voc Cold (V)": round(n * voc * 1.15, 1) if voc else 0,
                        "Power (kW)": round(n * pmax / 1000, 3) if pmax else 0,
                    })

                st.dataframe(rows, use_container_width=True, hide_index=True)

    # External battery section
    if enable_battery or b_volts > 0:
        st.markdown("---")
        st.subheader("🔋 تحليل البطارية الخارجية")

        q1, q2 = st.columns(2)
        with q1:
            st.write(f"**الشركة:** {b_brand}")
            st.write(f"**الموديل:** {b_model}")
            st.write(f"**الكيمياء:** {b_chem}")
            st.write(f"**الجهد:** {b_volts:g} V")
            st.write(f"**السعة:** {b_ah:g} Ah")
            st.write(f"**الطاقة:** {b_kwh:g} kWh")

        with q2:
            st.write(f"**Max Charge:** {b_max_chg:g} A")
            st.write(f"**Max Discharge:** {b_max_dischg:g} A")

            if inv_batt_v > 0 and b_volts > 0:
                ok, msg = is_battery_voltage_compatible(inv_batt_v, b_volts)
                (st.success if ok else st.error)(msg)

        st.markdown("#### 🧰 حاسبة حجم البطارية حسب الأحمال")
        load_col1, load_col2, load_col3 = st.columns(3)
        with load_col1:
            daily_load_kwh = st.number_input(
                "الاستهلاك اليومي (kWh/day)",
                min_value=0.0, value=10.0, step=0.5, key="daily_load_kwh"
            )
        with load_col2:
            autonomy_h = st.number_input(
                "زمن الاستقلالية (ساعة)",
                min_value=0.5, value=8.0, step=0.5, key="autonomy_h"
            )
        with load_col3:
            dod_pct = st.slider("نسبة التفريغ DoD %", 50, 95, 80, 5, key="dod_pct")

        peak_load_kw = st.number_input(
            "الحمل الأقصى المتوقع (kW)",
            min_value=0.0, value=5.0, step=0.5, key="peak_load_kw"
        )
        efficiency_pct = st.slider(
            "كفاءة الإنفيرتر %", 80, 99, 92, 1, key="efficiency_pct"
        )

        # Convert average daily energy to average load only for the autonomy calculation.
        avg_load_w = daily_load_kwh * 1000 / 24
        batt_result = battery_design(
            b_volts, b_ah, b_kwh, b_max_dischg,
            avg_load_w, autonomy_h, dod_pct / 100,
            efficiency_pct / 100
        )

        if batt_result:
            st.info(
                f"السعة الاسمية المطلوبة تقريباً: "
                f"**{batt_result['required_nominal_kwh']:.2f} kWh**"
            )
            if batt_result["battery_count"] > 0:
                st.success(
                    f"عدد البطاريات التقريبي: **{batt_result['battery_count']}** "
                    f"(كل بطارية ≈ {batt_result['unit_kwh']:.2f} kWh)."
                )
                if batt_result["max_battery_power_w"] > 0:
                    if batt_result["max_battery_power_w"] < peak_load_kw * 1000:
                        st.error(
                            f"قدرة تفريغ البطارية النظرية ≈ "
                            f"{batt_result['max_battery_power_w']/1000:.2f} kW "
                            f"أقل من الحمل الأقصى {peak_load_kw:.2f} kW."
                        )
                    else:
                        st.success("قدرة التفريغ النظرية مناسبة للحمل الأقصى المدخل.")
            else:
                st.warning("لا تتوفر سعة بطارية كافية في البيانات لحساب عدد الوحدات.")

    # Load calculator
    st.markdown("---")
    st.subheader("🏠 حاسبة الأحمال اليومية")

    st.caption("أدخل الأجهزة الأكثر أهمية للحصول على تقدير يومي سريع للطاقة.")
    load_defaults = [
        ("ثلاجة", 150, 8),
        ("إضاءة", 20, 6),
        ("تلفاز", 100, 5),
        ("حاسوب", 100, 6),
        ("مكيف", 1200, 5),
    ]

    load_rows = []
    total_daily_wh = 0
    for idx, (name, watts, hours) in enumerate(load_defaults):
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            n = st.text_input("الجهاز", value=name, key=f"load_name_{idx}")
        with c2:
            w = st.number_input("W", min_value=0.0, value=float(watts), step=10.0, key=f"load_w_{idx}")
        with c3:
            h = st.number_input("ساعات/يوم", min_value=0.0, value=float(hours), step=0.5, key=f"load_h_{idx}")
        wh = w * h
        total_daily_wh += wh
        load_rows.append((n, w, h, wh))

    st.metric("الاستهلاك اليومي المقدر", f"{total_daily_wh/1000:.2f} kWh/day")

    # Final report
    st.markdown("---")
    st.subheader("📋 الخلاصة الهندسية")

    if system_errors:
        st.error("❌ توجد أخطاء يجب حلها قبل اعتماد التصميم.")
    elif system_warnings:
        st.warning("⚠️ التصميم قابل للمراجعة، لكن توجد تنبيهات.")
    else:
        st.success("✅ لا توجد تعارضات رئيسية وفق البيانات المدخلة.")

    st.markdown(
        f"""
        **اللوح:** {p_brand} {p_model}  
        **الإنفيرتر:** {i_brand} {i_model}  
        **الفازات:** {phase_type}  
        **معمارية DC:** {v_arch}  
        **عدد MPPT:** {mppt_count}  
        **Strings/MPPT:** {strings_per_mppt}  
        """
    )

    st.caption(
        "تنبيه هندسي: نتائج التطبيق تقديرية وتعتمد على صحة الـ Datasheet والظروف الفعلية "
        "ودرجة الحرارة والكابلات والحماية وتعليمات الشركة المصنعة. لا تعتمد التوصيل "
        "النهائي دون مراجعة مهندس/فني مؤهل."
    )
