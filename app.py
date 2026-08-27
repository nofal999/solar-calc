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

# 2. تخصيص الواجهة وتدفق النصوص (RTL) مع التصميم البصري الاحترافي
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
        transition: background-color 0.3s ease;
    }
    
    .stButton>button:hover {
        background-color: #0369a1;
    }

    .stAlert {
        direction: rtl;
        text-align: right;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("☀️ حاسبة توافق الألواح والإنفيرتر والبطاريات الشاملة")
st.caption(
    "تحليل ذكي متكامل للمواصفات الكهربائية، نوع الجهد، نظام الفازات،"
    " التحكم بمداخل الـ MPPT، البطاريات الخارجية، وتوزيع السلاسل الميدانية آلياً"
)

# 3. الشريط الجانبي
with st.sidebar:
    st.header("⚙️ الإعدادات والتحكم")
    api_key = st.text_input(
        "مفتاح Gemini API Key:",
        type="password",
        help="احصل عليه مجاناً من Google AI Studio (مطلوب فقط لخيار الصور والبحث النصي)",
    )
    st.info("💡 المفتاح مطلوب فقط لعمليات الذكاء الاصطناعي (الصور أو البحث النصي).")
    
    st.markdown("---")
    st.markdown("### 📌 معلومات الاستخدام")
    st.markdown("اختر طريقة الإدخال المناسبة لعملك: صور، بحث نصي، أو إدخال يدوي مباشر للقيم.")

# 4. التبديل بين طرق الإدخال الثلاثة
search_mode = st.radio(
    "اختر طريقة إدخال البيانات للبحث والتحليل:",
    [
        "📸 1. البحث عن طريق الصور (إرفاق الملصقات)", 
        "✍️ 2. البحث عن طريق اسم الشركة والموديل (نصياً)",
        "🔢 3. الإدخال اليدوي الكامل للقيم الرقمية ومداخل MPPT"
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

# متغيرات الإدخال اليدوي الكامل مع التحكم بـ MPPT
m_pmax, m_voc, m_vmp, m_isc, m_imp = 550.0, 49.6, 41.5, 14.0, 13.2
m_ac_power, m_v_max, m_v_mppt_min, m_v_mppt_max, m_mppt_count, m_strings_per_mppt, m_max_mppt_curr = 5000.0, 550.0, 125.0, 500.0, 2, 1, 18.0
m_inv_type = "Hybrid"
m_phase_type = "Single-Phase"
m_b_volts, m_b_ah, m_b_kwh = 48.0, 100.0, 5.12
m_b_chem = "LiFePO4"

if "📸" in search_mode:
    cols = st.columns(3 if enable_battery else 2)
    with cols[0]:
        uploaded_panel = st.file_uploader("📸 صورة ملصق اللوح الشمسي", type=["jpg", "jpeg", "png", "webp"])
    with cols[1]:
        uploaded_inverter = st.file_uploader("📸 صورة ملصق الإنفيرتر", type=["jpg", "jpeg", "png", "webp"])
    if enable_battery:
        with cols[2]:
            uploaded_battery = st.file_uploader("📸 صورة ملصق البطارية", type=["jpg", "jpeg", "png", "webp"])

elif "✍️" in search_mode:
    cols = st.columns(3 if enable_battery else 2)
    with cols[0]:
        panel_text_query = st.text_input("☀️ اسم الشركة والموديل للوح الشمسي:", placeholder="مثال: Jinko Solar JKM640N-66HL4M-BDV-Z2")
    with cols[1]:
        inverter_text_query = st.text_input("⚡ اسم الشركة والموديل للإنفيرتر:", placeholder="مثال: Deye SUN-5K-SG04LP1-EU")
    if enable_battery:
        with cols[2]:
            battery_text_query = st.text_input("🔋 اسم الشركة والموديل للبطارية:", placeholder="مثال: Pylontech US3000C")

else:
    st.markdown("---")
    st.subheader("🔢 إدخال القيم الفنية والتحكم بمداخل MPPT يدوياً بالكامل")
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.markdown("#### ☀️ خصائص اللوح الشمسي")
        m_pmax = st.number_input("القدرة القصوى للوح (Pmax في Watts)", value=550.0, step=10.0)
        m_voc = st.number_input("جهد الدارة المفتوحة (Voc في Volts)", value=49.6, step=0.1)
        m_vmp = st.number_input("الجهد التشغيلي (Vmp في Volts)", value=41.5, step=0.1)
        m_isc = st.number_input("تيار القصر (Isc في Amps)", value=14.0, step=0.1)
        m_imp = st.number_input("التيار التشغيلي (Imp في Amps)", value=13.2, step=0.1)

    with col_m2:
        st.markdown("#### ⚡ خصائص الإنفيرتر ومداخل MPPT")
        m_ac_power = st.number_input("القدرة الاسمية للإنفيرتر (AC Watts)", value=5000.0, step=500.0)
        m_v_max = st.number_input("أقصى جهد مستمر مدخل (DC Max Volts)", value=550.0, step=10.0)
        m_v_mppt_min = st.number_input("أدنى جهد لنطاق MPPT", value=125.0, step=5.0)
        m_v_mppt_max = st.number_input("أقصى جهد لنطاق MPPT", value=500.0, step=5.0)
        m_mppt_count = st.number_input("عدد مداخل MPPT", value=2, step=1)
        m_strings_per_mppt = st.number_input("عدد السلاسل المسموحة لكل مدخل MPPT", value=1, step=1)
        m_max_mppt_curr = st.number_input("أقصى تيار لكل مدخل MPPT (Amps)", value=18.0, step=0.5)
        m_inv_type = st.selectbox("نوع الإنفيرتر", ["Hybrid", "On-Grid", "Off-Grid"])
        m_phase_type = st.selectbox("نظام الفازات", ["Single-Phase", "Three-Phase"])

    if enable_battery:
        st.markdown("---")
        st.markdown("#### 🔋 خصائص البطارية المرتبطة / الخارجية")
        col_mb1, col_mb2 = st.columns(2)
        with col_mb1:
            m_b_volts = st.number_input("الجهد الاسمي للبطارية (Volts)", value=48.0, step=2.4)
            m_b_ah = st.number_input("سعة البطارية (Ah)", value=100.0, step=10.0)
        with col_mb2:
            m_b_kwh = st.number_input("الطاقة الإجمالية (kWh)", value=5.12, step=0.5)
            m_b_chem = st.text_input("نوع الكيمياء", value="LiFePO4")


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


def is_battery_voltage_compatible(v1, v2):
    if v1 <= 0 or v2 <= 0:
        return True, "تعذر الجزم بالكامل لعدم توفر قراءة دقيقة للجهد."
    if (40.0 <= v1 <= 60.0) and (40.0 <= v2 <= 60.0):
        return True, f"جهد البطارية ({v2}V) متوافق مع نظام الإنفيرتر ({v1}V) ضمن فئة الـ 48V/51.2V."
    if (20.0 <= v1 <= 30.0) and (20.0 <= v2 <= 30.0):
        return True, f"جهد البطارية ({v2}V) متوافق مع نظام الإنفيرتر ({v1}V) ضمن فئة الـ 24V."
    if abs(v1 - v2) <= 5.0:
        return True, f"الجهد متوافق تقريباً بين الإنفيرتر ({v1}V) والبطارية ({v2}V)."
    return False, f"غير متوافق: جهد البطارية ({v2}V) يختلف جوهرياً عن جهد نظام الإنفيرتر ({v1}V)."


JSON_STRUCTURE = """
{
  "panel": {
    "brand": "الشركة المصنعة للوح",
    "model": "اسم وموديل اللوح",
    "part_number": "رقم القطعة",
    "type": "نوع اللوح",
    "pmax": 0,
    "voc": 0.0,
    "vmp": 0.0,
    "isc": 0.0,
    "imp": 0.0
  },
  "inverter": {
    "brand": "الشركة المصنعة للإنفيرتر",
    "model": "اسم وموديل الإنفيرتر",
    "type": "On-Grid, Off-Grid, Hybrid",
    "phase_type": "Single-Phase أو Three-Phase",
    "voltage_architecture": "HV أو LV",
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
      "frequency_hz": "50Hz / 60Hz",
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
    "model": "موديل البطارية",
    "chemistry": "LiFePO4, Gel, etc.",
    "capacity_ah": 0.0,
    "capacity_kwh": 0.0,
    "nominal_voltage_v": 0.0,
    "max_charge_current_a": 0.0,
    "max_discharge_current_a": 0.0
  }
}
"""


# 6. دوال الاستخراج بالذكاء الاصطناعي
def extract_via_images(panel_img, inverter_img, battery_img, key):
    client = genai.Client(api_key=key)
    contents = [compress_image_for_speed(panel_img), compress_image_for_speed(inverter_img)]
    if battery_img:
        contents.append(compress_image_for_speed(battery_img))

    prompt = f"""
    أنت مهندس طاقة شمسية خبير. قم بتحليل الصور المرفقة واستخرج البيانات التالية بدقة بصيغة JSON فقط دون أي نصوص إضافية:
    {JSON_STRUCTURE}
    """
    contents.append(prompt)
    response = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
    )
    return json.loads(response.text)


def extract_via_text(p_text, i_text, b_text, key):
    client = genai.Client(api_key=key)
    b_prompt = f'والبطارية: "{b_text}"' if b_text else ""
    prompt = f"""
    اللوح الشمسي: "{p_text}"
    الإنفيرتر: "{i_text}"
    {b_prompt}
    استخرج المواصفات القياسية بصيغة JSON بنفس الهيكل تماماً وبدون أي مقدمات:
    {JSON_STRUCTURE}
    """
    response = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
    )
    return json.loads(response.text)


# 7. زر التحليل وتنفيذ الحسابات
trigger_label = "🔢 تنفيذ الحسابات والتحليل الفوري" if "🔢" in search_mode else "⚡ تحليل سريع واستخراج التقرير والحسابات"

if st.button(trigger_label):
    res = None
    if "🔢" in search_mode:
        res = {
            "panel": {
                "brand": "إدخال يدوي", "model": "مخصص", "type": "Monocrystalline",
                "pmax": m_pmax, "voc": m_voc, "vmp": m_vmp, "isc": m_isc, "imp": m_imp
            },
            "inverter": {
                "brand": "إدخال يدوي", "model": "مخصص", "type": m_inv_type, "phase_type": m_phase_type,
                "voltage_architecture": "LV", "ac_rated_power_w": m_ac_power, "v_max": m_v_max, 
                "v_mppt_min": m_v_mppt_min, "v_mppt_max": m_v_mppt_max, "mppt_count": int(m_mppt_count), 
                "strings_per_mppt": int(m_strings_per_mppt), "max_mppt_current": m_max_mppt_curr,
                "battery": {"supported": m_inv_type != "On-Grid", "nominal_voltage_v": m_b_volts if enable_battery else 48.0},
                "ac_input_output": {"nominal_ac_voltage_v": "220V" if m_phase_type=="Single-Phase" else "380V", "frequency_hz": "50Hz"},
                "startup_surge": {"surge_power_va": m_ac_power * 2, "duration_seconds": 3.0}
            },
            "external_battery": {
                "brand": "إدخال يدوي", "model": "مخصص", "chemistry": m_b_chem if enable_battery else "N/A",
                "capacity_ah": m_b_ah if enable_battery else 0, "capacity_kwh": m_b_kwh if enable_battery else 0,
                "nominal_voltage_v": m_b_volts if enable_battery else 0, "max_charge_current_a": 50.0, "max_discharge_current_a": 50.0
            }
        }
    else:
        if not api_key:
            st.error("⚠️ يرجى إدخال مفتاح Gemini API Key في القائمة الجانبية.")
        else:
            try:
                if "📸" in search_mode:
                    if not uploaded_panel or not uploaded_inverter:
                        st.error("⚠️ يرجى رفع صور اللوح والإنفيرتر.")
                    else:
                        p_img = Image.open(uploaded_panel)
                        i_img = Image.open(uploaded_inverter)
                        b_img = Image.open(uploaded_battery) if enable_battery and uploaded_battery else None
                        with st.spinner("⚡ جاري قراءة الصور وتحليل الملصقات..."):
                            res = extract_via_images(p_img, i_img, b_img, api_key)
                else:
                    if not panel_text_query or not inverter_text_query:
                        st.error("⚠️ يرجى كتابة اسم اللوح والإنفيرتر.")
                    else:
                        with st.spinner("🔍 جاري البحث وجلب المواصفات الفنية..."):
                            res = extract_via_text(panel_text_query, inverter_text_query, battery_text_query if enable_battery else "", api_key)
            except Exception as e:
                st.error(f"حدث خطأ أثناء الاتصال بالخادم: {e}")

    if res:
        st.session_state["analysis_result"] = res
        st.toast("🚀 تمت الحسابات والتحليل بنجاح!", icon="⚡")


# 8. عرض النتائج والتقارير الشاملة
if "analysis_result" in st.session_state and st.session_state["analysis_result"]:
    res = st.session_state["analysis_result"]
    panel = res.get("panel", {})
    inv = res.get("inverter", {})
    ext_batt = res.get("external_battery", {})

    p_brand = panel.get("brand", "غير معروف")
    p_model = panel.get("model", "غير معروف")
    p_type = panel.get("type", "غير معروف")
    pmax = safe_float(panel.get("pmax"))
    voc = safe_float(panel.get("voc"))
    vmp = safe_float(panel.get("vmp"))
    isc = safe_float(panel.get("isc"))
    imp = safe_float(panel.get("imp"))

    i_brand = inv.get("brand", "غير معروف")
    i_model = inv.get("model", "غير معروف")
    i_type = inv.get("type", "غير معروف")
    phase_type = inv.get("phase_type", "غير معروف")
    v_arch = inv.get("voltage_architecture", "غير معروف")
    ac_rated_power = safe_float(inv.get("ac_rated_power_w"))
    v_max = safe_float(inv.get("v_max"))
    v_mppt_min = safe_float(inv.get("v_mppt_min"))
    v_mppt_max = safe_float(inv.get("v_mppt_max"))
    mppt_count = safe_int(inv.get("mppt_count"), 1)
    strings_per_mppt = safe_int(inv.get("strings_per_mppt"), 1)
    max_mppt_current = safe_float(inv.get("max_mppt_current"))

    batt_info = inv.get("battery", {})
    ac_info = inv.get("ac_input_output", {})
    surge_info = inv.get("startup_surge", {})

    b_brand = ext_batt.get("brand", "غير معروف")
    b_model = ext_batt.get("model", "غير معروف")
    b_chem = ext_batt.get("chemistry", "غير معروف")
    b_volts = safe_float(ext_batt.get("nominal_voltage_v"))
    b_ah = safe_float(ext_batt.get("capacity_ah"))
    b_kwh = safe_float(ext_batt.get("capacity_kwh"))
    b_max_chg = safe_float(ext_batt.get("max_charge_current_a"))
    b_max_dischg = safe_float(ext_batt.get("max_discharge_current_a"))

    isc_safe = isc * 1.25
    system_warnings = []
    system_errors = []

    is_on_grid = i_type.lower() in ["on-grid", "ongrid", "grid-tied"]
    has_external_battery = b_volts > 0 or (enable_battery and b_model != "غير معروف")

    if is_on_grid and has_external_battery:
        system_errors.append("⚠️ **تناقض خطير:** محولات On-Grid التقليدية لا تدعم توصيل البطاريات بشكل مباشر.")

    inv_batt_v = safe_float(batt_info.get("nominal_voltage_v"))
    if not is_on_grid and has_external_battery and inv_batt_v > 0 and b_volts > 0:
        is_compat, msg = is_battery_voltage_compatible(inv_batt_v, b_volts)
        if not is_compat:
            system_errors.append(f"❌ **خطأ في جهد البطارية:** {msg}")

    if max_mppt_current > 0 and isc_safe > max_mppt_current:
        system_warnings.append(f"⚠️ **تحذير تيار (Clipping):** تيار القصر المعدل للوح ({round(isc_safe, 2)} A) أعلى من أقصى تيار مدخل MPPT ({max_mppt_current} A).")

    if system_errors or system_warnings:
        st.markdown("---")
        st.subheader("🚨 تقرير الأخطاء والتنبيهات في المنظومة")
        for err in system_errors: st.error(err)
        for warn in system_warnings: st.warning(warn)

    st.subheader("📌 البيانات التعريفية والموديلات المكتشفة")
    col_p_info, col_i_info = st.columns(2)

    with col_p_info:
        st.markdown("### ☀️ اللوح الشمسي")
        st.write(f"**الشركة / الموديل:** {format_val(p_brand)} - {format_val(p_model)}")
        st.write(f"**نوع اللوح:** {format_val(p_type)}")
        st.write(f"- القدرة (Pmax): {format_val(pmax, 'W')}")
        st.write(f"- Voc: {format_val(voc, 'V')} | Vmp: {format_val(vmp, 'V')}")
        st.write(f"- Isc: {format_val(isc, 'A')} | Imp: {format_val(imp, 'A')}")

    with col_i_info:
        st.markdown("### ⚡ الإنفيرتر ومداخل MPPT")
        st.write(f"**الشركة / الموديل:** {format_val(i_brand)} - {format_val(i_model)}")
        st.write(f"**النوع / الفاز:** {format_val(i_type)} | {format_val(phase_type)}")
        st.write(f"- القدرة الاسمية: {format_val(ac_rated_power, 'W')}")
        st.write(f"- أقصى جهد مستمر (DC Max): {format_val(v_max, 'V')}")
        st.write(f"- نطاق MPPT: `{v_mppt_min}V` إلى `{v_mppt_max}V`")
        st.write(f"- عدد مداخل MPPT: `{mppt_count}` (أقصى تيار `{max_mppt_current}A`)")
        st.write(f"- السلاسل المسموحة لكل مدخل: `{strings_per_mppt}`")

    st.markdown("---")
    st.subheader("🔋 مواصفات البطاريات، شبكة AC، وقدرة البدء (Startup)")
    c_batt, c_ac, c_surge = st.columns(3)

    with c_batt:
        st.markdown("#### 🔋 نظام بطاريات الإنفيرتر")
        batt_supported = batt_info.get("supported", False)
        batt_volts = safe_float(batt_info.get("nominal_voltage_v"))
        if not batt_supported and batt_volts == 0:
            st.write("❌ لا يدعم بطاريات (On-Grid)")
        else:
            st.write(f"- **جهد البطارية:** {format_val(batt_volts, 'V')}")
            st.write(f"- **أنواع مدعومة:** {format_val(batt_info.get('battery_type', 'غير معروف'))}")

    with c_ac:
        st.markdown("#### 🔌 مدخل ومخرج AC")
        st.write(f"- **جهد AC:** {format_val(ac_info.get('nominal_ac_voltage_v', '220V'))}")
        st.write(f"- **التردد:** {format_val(ac_info.get('frequency_hz', '50Hz'))}")

    with c_surge:
        st.markdown("#### 🚀 قدرة البدء (Surge)")
        st.write(f"- **القدرة اللحظية:** {format_val(safe_float(surge_info.get('surge_power_va')), 'VA')}")
        st.write(f"- **المدة:** {format_val(safe_float(surge_info.get('duration_seconds')), 'ثانية')}")

    if enable_battery or (ext_batt.get("nominal_voltage_v", 0) > 0):
        st.markdown("---")
        st.subheader("🔋 تفاصيل البطارية الخارجية المخصصة")
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.write(f"**الموديل:** {format_val(b_brand)} - {format_val(b_model)}")
            st.write(f"**الكيمياء:** {format_val(b_chem)}")
            st.write(f"- **السعة:** {format_val(b_ah, 'Ah')} ({format_val(b_kwh, 'kWh')})")
        with col_b2:
            st.write(f"- **الجهد الاسمي:** {format_val(b_volts, 'V')}")
            st.write(f"- **أقصى شحن/تفريغ:** {format_val(b_max_chg, 'A')} / {format_val(b_max_dischg, 'A')}")

        inv_batt_v = safe_float(batt_info.get("nominal_voltage_v"))
        if inv_batt_v > 0 and b_volts > 0:
            is_compat, msg = is_battery_voltage_compatible(inv_batt_v, b_volts)
            if is_compat: st.success(f"✅ {msg}")
            else: st.error(f"❌ {msg}")

    if voc == 0 or vmp == 0 or v_max == 0:
        st.error("⚠️ البيانات الكهربائية للجهد غير كافية لإجراء الحسابات.")
    else:
        v_mppt_min_safe = v_mppt_min * 1.10
        min_string_safe = math.ceil(v_mppt_min_safe / vmp) if vmp > 0 else 1

        voc_cold_safe = voc * 1.15
        v_max_safe = v_max * 0.95

        max_by_voc = math.floor(v_max_safe / voc_cold_safe) if voc_cold_safe > 0 else 1
        max_by_mppt = math.floor(v_mppt_max / vmp) if vmp > 0 and v_mppt_max > 0 else max_by_voc
        max_string_safe = min(max_by_voc, max_by_mppt) if max_by_mppt > 0 else max_by_voc

        if max_string_safe < min_string_safe: max_string_safe = min_string_safe
        rec_string = math.floor((min_string_safe + max_string_safe) / 2)
        
        # إجمالي السلاسل يعتمد على عدد الـ MPPT وسعة كل مدخل
        total_strings = mppt_count * strings_per_mppt

        min_total_panels = min_string_safe * total_strings
        rec_total_panels = rec_string * total_strings
        max_total_panels = max_string_safe * total_strings

        st.markdown("---")
        st.subheader("⚡ نتائج التوصيل وتوزيع السلاسل الآمن")
        st.success(f"""
        🛡️ **حدود الأمان بالسلسلة الواحدة:**
        * **أقل عدد ألواح آمن بالسلسلة:** `{min_string_safe}` ألواح.
        * **أكبر عدد ألواح آمن بالسلسلة:** `{max_string_safe}` لوحاً.
        * **العدد الموصى به مثالياً بالسلسلة:** `{rec_string}` ألواح.
        * **إجمالي السلاسل المتاحة:** `{total_strings}` سلاسل (`{mppt_count}` مداخل × `{strings_per_mppt}` سلاسل لكل مدخل).
        """)

        st.markdown("### 🔀 تفاصيل التوزيع المقترح")
        tab1, tab2, tab3 = st.tabs(["⭐ التوزيع المثالي", "🔴 الحد الأدنى", "🟢 الحد الأقصى"])
        with tab1: st.info(f"القدرة الكلية: `{rec_total_panels}` لوحاً (`{round(rec_total_panels*pmax/1000, 2)} kW`) - لكل String ضع `{rec_string}` ألواح.")
        with tab2: st.warning(f"القدرة الكلية: `{min_total_panels}` لوحاً (`{round(min_total_panels*pmax/1000, 2)} kW`) - لكل String ضع `{min_string_safe}` ألواح.")
        with tab3: st.success(f"القدرة الكلية: `{max_total_panels}` لوحاً (`{round(max_total_panels*pmax/1000, 2)} kW`) - لكل String ضع `{max_string_safe}` ألواح.")

        st.markdown("---")
        st.subheader("🧮 فحص وتوزيع عدد ألواح مخصص")
        custom_panels_count = st.number_input(
            "أدخل إجمالي عدد الألواح التي ترغب بتركيبها:",
            min_value=max(1, int(min_total_panels)),
            max_value=max(10, int(max_total_panels * 3)),
            value=int(rec_total_panels),
            step=1
        )

        if custom_panels_count > 0:
            custom_kw = round((custom_panels_count * pmax) / 1000, 2)
            st.write(f"- **إجمالي قدرة التوليد:** `{custom_kw} kW`")
            num_strings_used = min(total_strings, custom_panels_count)
            panels_per_str = custom_panels_count // num_strings_used
            remainder = custom_panels_count % num_strings_used

            vmp_string = round(panels_per_str * vmp, 1)
            voc_string_cold = round(panels_per_str * voc * 1.15, 1)

            if panels_per_str < min_string_safe:
                st.error(f"❌ **العدد غير آمن:** الجهد التشغيلي `{vmp_string}V` أقل من الحد الأدنى للمدخل.")
            elif panels_per_str > max_string_safe:
                st.error(f"⚠️ **العدد غير آمن:** جهد الشتاء `{voc_string_cold}V` يتجاوز الحد الأقصى للإنفيرتر.")
            else:
                st.success("✅ **العدد المدخل متوافق تماماً وآمن كهربائياً.**")
                dist_msg = f"🔌 **خطة التوصيل:** استخدم `{num_strings_used}` سلاسل، وكل سلسلة تضم `{panels_per_str}` ألواح."
                if remainder > 0: dist_msg += f" (ملاحظة: يوجد باقي {remainder} ألواح موزعة)."
                st.info(dist_msg)
