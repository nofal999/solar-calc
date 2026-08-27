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
        help="مطلوب فقط في حال استخدام خيار الصور أو البحث النصي بالذكاء الاصطناعي",
    )
    st.info("💡 المفتاح اختياري إذا اخترت الإدخال اليدوي المباشر للقيم.")

# 4. طرق إدخال البيانات الثلاثة
search_mode = st.radio(
    "اختر طريقة إدخال البيانات:",
    [
        "📸 1. البحث عن طريق الصور (إرفاق الملصقات)", 
        "✍️ 2. البحث عن طريق اسم الشركة والموديل (نصياً بالذكاء الاصطناعي)",
        "🔢 3. الإدخال اليدوي المباشر للقيم الكهربائية (مع خيار لا أعرف)"
    ],
    index=2,
)

enable_battery = st.toggle("🔋 تفعيل فحص وتحليل بطارية خارجية مخصصة", value=False)

uploaded_panel = None
uploaded_inverter = None
uploaded_battery = None
panel_text_query = ""
inverter_text_query = ""
battery_text_query = ""

manual_data = None

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
        panel_text_query = st.text_input("☀️ اسم الشركة والموديل للوح الشمسي:", placeholder="مثال: Jinko 550W")
    with cols[1]:
        inverter_text_query = st.text_input("⚡ اسم الشركة والموديل للإنفيرتر:", placeholder="مثال: Deye 5kW Hybrid")
    if enable_battery:
        with cols[2]:
            battery_text_query = st.text_input("🔋 اسم الشركة والموديل للبطارية:", placeholder="مثال: Pylontech US3000C")

else:
    st.markdown("---")
    st.subheader("🔢 الإدخال اليدوي المباشر (يمكنك تفعيل 'لا أعرف' عند نقص المعلومات)")
    
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.markdown("#### ☀️ اللوح الشمسي")
        unk_pmax = st.checkbox("لا أعرف Pmax", key="unk_pmax")
        m_pmax = 0.0 if unk_pmax else st.number_input("قدرة اللوح القصوى Pmax (W)", value=550.0, step=5.0)

        unk_voc = st.checkbox("لا أعرف Voc", key="unk_voc")
        m_voc = 0.0 if unk_voc else st.number_input("جهد الدارة المفتوحة Voc (V)", value=49.6, step=0.1)

        unk_vmp = st.checkbox("لا أعرف Vmp", key="unk_vmp")
        m_vmp = 0.0 if unk_vmp else st.number_input("الجهد التشغيلي Vmp (V)", value=41.96, step=0.1)

        unk_isc = st.checkbox("لا أعرف Isc", key="unk_isc")
        m_isc = 0.0 if unk_isc else st.number_input("تيار القصر Isc (A)", value=14.0, step=0.1)

        unk_imp = st.checkbox("لا أعرف Imp", key="unk_imp")
        m_imp = 0.0 if unk_imp else st.number_input("التيار التشغيلي Imp (A)", value=13.11, step=0.1)

    with col_m2:
        st.markdown("#### ⚡ الإنفيرتر")
        m_i_type = st.selectbox("نوع الإنفيرتر", ["Hybrid", "Off-Grid", "On-Grid", "لا أعرف"])
        m_phase = st.selectbox("نظام الفازات", ["Single-Phase", "Three-Phase", "لا أعرف"])
        
        unk_ac = st.checkbox("لا أعرف القدرة الاسمية AC", key="unk_ac")
        m_ac_power = 0.0 if unk_ac else st.number_input("القدرة الاسمية AC (W)", value=5000.0, step=100.0)

        unk_vmax = st.checkbox("لا أعرف أقصى جهد مستمر DC Max", key="unk_vmax")
        m_v_max = 0.0 if unk_vmax else st.number_input("أقصى جهد مستمر مدخل DC Max (V)", value=500.0, step=10.0)

        unk_vmin = st.checkbox("لا أعرف أدنى جهد MPPT", key="unk_vmin")
        m_v_min = 0.0 if unk_vmin else st.number_input("أدنى جهد MPPT (V)", value=125.0, step=5.0)

        unk_vmppt_max = st.checkbox("لا أعرف أقصى جهد MPPT", key="unk_vmppt_max")
        m_v_mppt_max = 0.0 if unk_vmppt_max else st.number_input("أقصى جهد MPPT (V)", value=425.0, step=5.0)
        
        # تحكم حر تماماً بعدد مسارات الـ MPPT وتخصيص الستريجات لكل مسار
        unk_mppt_count = st.checkbox("لا أعرف عدد مسارات MPPT (تلقائي 1)", key="unk_mppt_count")
        if unk_mppt_count:
            m_mppt_count = 1
            m_strings_list = [1]
        else:
            m_mppt_count = st.number_input("عدد مسارات MPPT", min_value=1, max_value=6, value=2, step=1)
            st.markdown("##### 📌 حدد عدد السلاسل (Strings) لكل مسار MPPT:")
            m_strings_list = []
            for i in range(int(m_mppt_count)):
                s_val = st.number_input(f"عدد الستريجات في MPPT {i+1}", min_value=1, max_value=6, value=1, step=1, key=f"manual_mppt_str_{i+1}")
                m_strings_list.append(int(s_val))
                
        total_strings_sum = sum(m_strings_list)
        st.info(f"🔌 إجمالي عدد الستريجات (Strings) في الإنفيرتر = {total_strings_sum}")

        unk_m_curr = st.checkbox("لا أعرف أقصى تيار لكل MPPT", key="unk_m_curr")
        m_max_current = 0.0 if unk_m_curr else st.number_input("أقصى تيار لكل MPPT (A)", value=15.0, step=0.5)

        unk_inv_batt_v = st.checkbox("لا أعرف جهد بطارية الإنفيرتر الاسمي", key="unk_inv_batt_v")
        m_inv_batt_v = 0.0 if unk_inv_batt_v else st.number_input("جهد بطارية الإنفيرتر الاسمي (V)", value=48.0, step=12.0)

    if enable_battery:
        st.markdown("#### 🔋 البطارية الخارجية")
        col_mb1, col_mb2 = st.columns(2)
        with col_mb1:
            unk_b_volts = st.checkbox("لا أعرف جهد البطارية", key="unk_b_volts")
            m_b_volts = 0.0 if unk_b_volts else st.number_input("جهد البطارية الاسمي (V)", value=51.2, step=0.1)

            unk_b_ah = st.checkbox("لا أعرف سعة البطارية (Ah)", key="unk_b_ah")
            m_b_ah = 0.0 if unk_b_ah else st.number_input("سعة البطارية (Ah)", value=100.0, step=10.0)
        with col_mb2:
            unk_b_kwh = st.checkbox("لا أعرف الطاقة الكلية (kWh)", key="unk_b_kwh")
            m_b_kwh = 0.0 if unk_b_kwh else st.number_input("الطاقة الكلية (kWh)", value=5.12, step=0.5)

            m_b_chem = st.text_input("نوع الكيمياء", value="LiFePO4")

    # بناء هيكل البيانات اليدوي مع القيم المجهولة
    manual_data = {
        "panel": {
            "brand": "إدخال يدوي",
            "model": "مخصص",
            "type": "Monocrystalline",
            "pmax": m_pmax,
            "voc": m_voc,
            "vmp": m_vmp,
            "isc": m_isc,
            "imp": m_imp
        },
        "inverter": {
            "brand": "إدخال يدوي",
            "model": "مخصص",
            "type": m_i_type if m_i_type != "لا أعرف" else "غير معروف",
            "phase_type": m_phase if m_phase != "لا أعرف" else "غير معروف",
            "voltage_architecture": "Low Voltage",
            "ac_rated_power_w": m_ac_power,
            "v_max": m_v_max,
            "v_mppt_min": m_v_min,
            "v_mppt_max": m_v_mppt_max,
            "v_start": m_v_min,
            "mppt_count": int(m_mppt_count),
            "strings_per_mppt_list": m_strings_list,
            "strings_per_mppt": m_strings_list[0],
            "max_mppt_current": m_max_current,
            "battery": {
                "supported": False if m_i_type == "On-Grid" else True,
                "nominal_voltage_v": m_inv_batt_v,
                "battery_type": "Lithium/Lead-Acid",
                "max_charge_current_a": 100.0
            },
            "ac_input_output": {
                "nominal_ac_voltage_v": "230V",
                "frequency_hz": "50Hz"
            },
            "startup_surge": {
                "surge_power_va": m_ac_power * 2 if m_ac_power > 0 else 0.0,
                "duration_seconds": 5.0
            }
        },
        "external_battery": {
            "brand": "إدخال يدوي",
            "model": "مخصص",
            "chemistry": m_b_chem if enable_battery else "غير معروف",
            "capacity_ah": m_b_ah if enable_battery else 0.0,
            "capacity_kwh": m_b_kwh if enable_battery else 0.0,
            "nominal_voltage_v": m_b_volts if enable_battery else 0.0,
            "max_charge_current_a": 50.0,
            "max_discharge_current_a": 50.0
        } if enable_battery else {
            "brand": "غير معروف", "model": "غير معروف", "chemistry": "غير معروف",
            "capacity_ah": 0.0, "capacity_kwh": 0.0, "nominal_voltage_v": 0.0
        }
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
        or value == 0
        or value == 0.0
        or value == 0
        or value == "غير محدد"
        or value == "غير معروف"
    ):
        return "`غير متاح (لا أعرف)`"
    return f"`{value} {unit}`".strip()


def compress_image_for_speed(pil_img, max_dim=1024):
    img_copy = pil_img.copy()
    img_copy.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    return img_copy


def is_battery_voltage_compatible(v1, v2):
    if v1 <= 0 or v2 <= 0:
        return True, "تعذر الجزم لعدم توفر قراءة دقيقة لأحد الجهود."

    if (40.0 <= v1 <= 60.0) and (40.0 <= v2 <= 60.0):
        return True, f"جهد البطارية ({v2}V) متوافق مع نظام الإنفيرتر ({v1}V) ضمن فئة الـ 48V/51.2V."

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


JSON_STRUCTURE = """
{
  "panel": {
    "brand": "الشركة المصنعة للوح",
    "model": "اسم وموديل اللوح",
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
    "type": "نوع الإنفيرتر",
    "phase_type": "عدد الفازات",
    "voltage_architecture": "نوع الجهد المستمر",
    "ac_rated_power_w": 0.0,
    "v_max": 0.0,
    "v_mppt_min": 0.0,
    "v_mppt_max": 0.0,
    "v_start": 0.0,
    "mppt_count": 1,
    "strings_per_mppt_list": [1],
    "max_mppt_current": 0.0,
    "battery": {
      "supported": true,
      "nominal_voltage_v": 0.0,
      "battery_type": "أنواع البطاريات المدعومة",
      "max_charge_current_a": 0.0
    },
    "ac_input_output": {
      "nominal_ac_voltage_v": "جهد AC الاسمي",
      "frequency_hz": "التردد"
    },
    "startup_surge": {
      "surge_power_va": 0.0,
      "duration_seconds": 0.0
    }
  },
  "external_battery": {
    "brand": "الشركة المصنعة للبطارية الخارجية",
    "model": "اسم وموديل البطارية الخارجية",
    "chemistry": "نوع الكيمياء",
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
    أنت مهندس طاقة شمسية خبير. قم بتحليل الصور المرفقة واستخرج البيانات التالية بأسلوب JSON فقط دون أي مقدمات:
    {JSON_STRUCTURE}
    إذا كانت أي معلومة غير واضحة أو غير موجودة في الصورة، ضع قيمتها 0 أو "غير معروف".
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


def extract_via_text(p_text, i_text, b_text, key):
    client = genai.Client(api_key=key)
    b_prompt = f'والبطارية الخارجية المطلوبة: "{b_text}"' if b_text else 'لا يوجد بطارية خارجية مخصصة.'

    prompt = f"""
    أنت خبير بقواعد بيانات الألواح والإنفيرترات والبطاريات.
    اللوح الشمسي: "{p_text}"
    الإنفيرتر: "{i_text}"
    {b_prompt}

    استخرج المواصفات الكهربائية وعد بتقرير JSON بنفس الهيكل تماماً بدون أي مقدمات (ضع 0 أو غير معروف لأي قيمة غير متوفرة):
    {JSON_STRUCTURE}
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


# 7. زر التفعيل والتحليل
if st.button("⚡ بدء الحسابات والتحليل الشامل"):
    res = None
    start_t = time.time()

    if "🔢" in search_mode:
        res = manual_data
        st.success("✅ تم اعتماد القيم المدخلة يدوياً بنجاح!")
    else:
        if not api_key:
            st.error("⚠️ يرجى إدخال مفتاح Gemini API Key في القائمة الجانبية لاستخدام ميزات الذكاء الاصطناعي.")
        else:
            if "📸" in search_mode:
                if not uploaded_panel or not uploaded_inverter:
                    st.error("⚠️ يرجى تحميل صورة اللوح والإنفيرتر معاً.")
                elif enable_battery and not uploaded_battery:
                    st.error("⚠️ يرجى رفع صورة ملصق البطارية.")
                else:
                    try:
                        p_img = Image.open(uploaded_panel)
                        i_img = Image.open(uploaded_inverter)
                        b_img = Image.open(uploaded_battery) if enable_battery and uploaded_battery else None
                        with st.spinner("⚡ جاري قراءة الملصقات وتفكيك البيانات..."):
                            res = extract_via_images(p_img, i_img, b_img, api_key)
                    except Exception as e:
                        st.error(f"خطأ في معالجة الصور: {e}")
            else:
                if not panel_text_query or not inverter_text_query:
                    st.error("⚠️ يرجى كتابة اسم وموديل اللوح والإنفيرتر.")
                else:
                    try:
                        with st.spinner("🔍 جاري جلب المواصفات وتحليلها..."):
                            res = extract_via_text(
                                panel_text_query, inverter_text_query, battery_text_query if enable_battery else "", api_key
                            )
                    except Exception as e:
                        st.error(f"خطأ في البحث النصي: {e}")

    if res:
        st.session_state["analysis_result"] = res
        st.toast(f"🚀 اكتملت العمليات في {round(time.time() - start_t, 2)} ثوانٍ!", icon="⚡")


# 8. عرض النتائج والحسابات
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
    mppt_count = safe_int(inv.get("mppt_count"), default=1)
    
    strings_per_mppt_list = inv.get("strings_per_mppt_list")
    if not isinstance(strings_per_mppt_list, list) or len(strings_per_mppt_list) != mppt_count:
        fallback_str = safe_int(inv.get("strings_per_mppt"), default=1)
        strings_per_mppt_list = [fallback_str] * mppt_count

    total_configured_strings = sum(strings_per_mppt_list)
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

    isc_safe = isc * 1.25 if isc > 0 else 0.0

    system_warnings = []
    system_errors = []

    is_on_grid = i_type.lower() in ["on-grid", "ongrid", "grid-tied"]
    has_external_battery = b_volts > 0 or (enable_battery and b_model != "غير معروف")

    if is_on_grid and has_external_battery:
        system_errors.append(
            "⚠️ **تناقض خطير:** تم إدخال بطارية خارجية مع إنفيرتر شبكي (On-Grid). إنفيرترات On-Grid لا تدعم البطاريات المباشرة."
        )

    inv_batt_v = safe_float(batt_info.get("nominal_voltage_v"))
    if not is_on_grid and has_external_battery and inv_batt_v > 0 and b_volts > 0:
        is_compat, msg = is_battery_voltage_compatible(inv_batt_v, b_volts)
        if not is_compat:
            system_errors.append(f"❌ **خطأ في جهد البطارية:** {msg}")

    if max_mppt_current > 0 and isc_safe > 0 and isc_safe > max_mppt_current:
        system_warnings.append(
            f"⚠️ **تحذير تيار (Clipping):** تيار القصر للوح ({round(isc_safe, 2)} A) أعلى من تيار MPPT ({max_mppt_current} A)."
        )

    if system_errors or system_warnings:
        st.markdown("---")
        st.subheader("🚨 تقرير الأخطاء والتنبيهات في المنظومة")
        for err in system_errors:
            st.error(err)
        for warn in system_warnings:
            st.warning(warn)

    st.subheader("📌 البيانات والخصائص الكهربائية")
    col_p_info, col_i_info = st.columns(2)

    with col_p_info:
        st.markdown("### ☀️ اللوح الشمسي")
        st.write(f"**الشركة/الموديل:** {format_val(p_brand)} - {format_val(p_model)}")
        st.write(f"- القدرة (Pmax): {format_val(pmax, 'W')}")
        st.write(f"- جهد الدارة (Voc): {format_val(voc, 'V')}")
        st.write(f"- الجهد التشغيلي (Vmp): {format_val(vmp, 'V')}")
        st.write(f"- تيار القصر (Isc): {format_val(isc, 'A')}")
        st.write(f"- التيار التشغيلي (Imp): {format_val(imp, 'A')}")

    with col_i_info:
        st.markdown("### ⚡ الإنفيرتر")
        st.write(f"**الشركة/الموديل:** {format_val(i_brand)} - {format_val(i_model)}")
        st.write(f"**النوع والفاز:** {format_val(i_type)} | {format_val(phase_type)}")
        st.write(f"- القدرة الاسمية: {format_val(ac_rated_power, 'W')}")
        st.write(f"- أقصى جهد مستمر (DC Max): {format_val(v_max, 'V')}")
        st.write(f"- نطاق MPPT: `{v_mppt_min}V` إلى `{v_mppt_max}V`")
        st.write(f"- عدد مسارات MPPT: `{mppt_count}`")
        
        str_desc_parts = [f"MPPT {idx+1}: `{cnt}` سترينج" for idx, cnt in enumerate(strings_per_mppt_list)]
        st.write(f"- توزيع الستريجات: " + " | ".join(str_desc_parts))
        st.write(f"- أقصى تيار MPPT: {format_val(max_mppt_current, 'A')}")

    # الشرط الحاسم للتحقق من وجود الحد الأدنى للعمليات الحسابية
    if voc == 0 or vmp == 0 or v_max == 0:
        st.warning("⚠️ **تنبيه:** بعض القيم الحرجة (مثل Voc, Vmp أو DC Max) محددة كـ 'لا أعرف' أو غير متوفرة، لذلك تم تخطي حسابات القيود الآمنة للسلسلة لتجنب أي تنبؤ غير دقيق.")
    else:
        v_mppt_min_safe = v_mppt_min * 1.10 if v_mppt_min > 0 else vmp * 2
        min_string_safe = math.ceil(v_mppt_min_safe / vmp) if vmp > 0 else 1

        voc_cold_safe = voc * 1.15
        v_max_safe = v_max * 0.95

        max_by_voc = math.floor(v_max_safe / voc_cold_safe) if voc_cold_safe > 0 else 1
        max_by_mppt = math.floor(v_mppt_max / vmp) if vmp > 0 and v_mppt_max > 0 else max_by_voc
        max_string_safe = min(max_by_voc, max_by_mppt) if max_by_mppt > 0 else max_by_voc

        if max_string_safe < min_string_safe:
            max_string_safe = min_string_safe

        rec_string = math.floor((min_string_safe + max_string_safe) / 2)

        min_total_panels = min_string_safe * total_configured_strings
        rec_total_panels = rec_string * total_configured_strings
        max_total_panels = max_string_safe * total_configured_strings

        min_kw = round((min_total_panels * pmax) / 1000, 2) if pmax > 0 else 0.0
        rec_kw = round((rec_total_panels * pmax) / 1000, 2) if pmax > 0 else 0.0
        max_kw = round((max_total_panels * pmax) / 1000, 2) if pmax > 0 else 0.0

        st.markdown("---")
        st.subheader("⚡ نتائج التوصيل وتوزيع السلاسل الآمن")

        st.success(f"""
        🛡️ **حدود الأمان بالسلسلة الواحدة (String):**
        * **أقل عدد ألواح بالسلسلة:** `{min_string_safe}` ألواح.
        * **أكبر عدد ألواح بالسلسلة:** `{max_string_safe}` لوحاً.
        * **العدد الموصى به بالسلسلة:** `{rec_string}` ألواح.
        * **إجمالي السلاسل المتاحة بالإنفيرتر:** `{total_configured_strings}` سلسلة موزعة على `{mppt_count}` مسارات MPPT.
        """)

        tab1, tab2, tab3 = st.tabs(["⭐ التوزيع المثالي", "🔴 الحد الأدنى", "🟢 الحد الأقصى"])

        with tab1:
            st.info(f"**القدرة الكلية:** `{rec_total_panels}` لوحاً (`{rec_kw} kW`) | **لكل String:** `{rec_string}` ألواح.")
        with tab2:
            st.warning(f"**القدرة الكلية:** `{min_total_panels}` لوحاً (`{min_kw} kW`) | **لكل String:** `{min_string_safe}` ألواح.")
        with tab3:
            st.success(f"**القدرة الكلية:** `{max_total_panels}` لوحاً (`{max_kw} kW`) | **لكل String:** `{max_string_safe}` ألواح.")

        st.markdown("---")
        st.subheader("🧮 تفصيل توزيع الألواح الميداني لكل مسار MPPT")

        min_allowed = max(1, int(min_total_panels))
        max_allowed = max(min_allowed, int(max_total_panels * 2))
        def_panels = int(rec_total_panels) if min_allowed <= int(rec_total_panels) <= max_allowed else min_allowed

        custom_count = st.number_input(
            "أدخل إجمالي عدد الألواح المراد تركيبها في المنظومة:",
            min_value=min_allowed,
            max_value=max_allowed,
            value=def_panels,
            step=1,
        )

        if custom_count > 0:
            c_kw = round((custom_count * pmax) / 1000, 2) if pmax > 0 else 0.0
            per_str = custom_count // total_configured_strings if total_configured_strings > 0 else custom_count
            vmp_str = round(per_str * vmp, 1)
            voc_cold_str = round(per_str * voc * 1.15, 1)

            if per_str < min_string_safe:
                st.error(f"❌ العدد قليل جداً: الجهد `{vmp_str}V` أقل من الحد الأدنى الآمن (`{round(v_mppt_min_safe, 1)}V`).")
            elif per_str > max_string_safe:
                st.error(f"⚠️ خطر تلف الإنفيرتر: الجهد الشتوي `{voc_cold_str}V` يتجاوز أقصى جهد آمن (`{round(v_max_safe, 1)}V`).")
            else:
                st.success("✅ عدد الألواح وتوزيعها متوافق وآمن تماماً.")
                
                st.markdown("##### 🗺️ خريطة التوزيع الميداني التفصيلية للمسارات:")
                alloc_cols = st.columns(mppt_count if mppt_count > 0 else 1)
                for idx, str_count in enumerate(strings_per_mppt_list):
                    panels_on_this_mppt = str_count * per_str
                    with alloc_cols[idx]:
                        st.info(f"""
                        **MPPT {idx+1}**
                        * عدد الستريجات: `{str_count}`
                        * الألواح لكل سترينج: `{per_str}`
                        * إجمالي ألواح المسار: `{panels_on_this_mppt}` لوح
                        """)

                st.markdown(f"""
                * **إجمالي قدرة الحقل الشمسي:** `{c_kw} kW` (`{custom_count}` لوح).
                * **جهد التشغيل (Vmp) لكل سلسلة:** `{vmp_str} V` | **الجهد الشتوي الأقصى (Voc):** `{voc_cold_str} V`
                """)
