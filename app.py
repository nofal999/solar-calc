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
    st.info("💡 المفتاح مطلوب لعمليات التحليل والاستخراج.")

# 4. التبديل بين طريقتي البحث
search_mode = st.radio(
    " اختر طريقة إدخال البيانات للبحث والتحليل:",
    ["📸 1. البحث عن طريق الصور (إرفاق الملصقات)", "✍️ 2. البحث عن طريق اسم الشركة والموديل (نصياً)"],
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

if "📸" in search_mode:
    cols = st.columns(3 if enable_battery else 2)
    with cols[0]:
        uploaded_panel = st.file_uploader(
            "📸 صورة ملصق اللوح الشمسي", type=["jpg", "jpeg", "png"]
        )
    with cols[1]:
        uploaded_inverter = st.file_uploader(
            "📸 صورة ملصق الإنفيرتر", type=["jpg", "jpeg", "png"]
        )
    if enable_battery:
        with cols[2]:
            uploaded_battery = st.file_uploader(
                "📸 صورة ملصق البطارية", type=["jpg", "jpeg", "png"]
            )
else:
    cols = st.columns(3 if enable_battery else 2)
    with cols[0]:
        panel_text_query = st.text_input(
            "☀️ اسم الشركة والموديل للوح الشمسي:",
            placeholder="مثال: Jinko Solar JKM640N-66HL4M-BDV-Z2",
        )
    with cols[1]:
        inverter_text_query = st.text_input(
            "⚡ اسم الشركة والموديل للإنفيرتر:",
            placeholder="مثال: Deye SUN-5K-SG04LP1-EU أو Growatt 5000ES",
        )
    if enable_battery:
        with cols[2]:
            battery_text_query = st.text_input(
                "🔋 اسم الشركة والموديل للبطارية:",
                placeholder="مثال: Felicity solar LPBF48300 أو Pylontech US3000C",
            )


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


# 6. دالة الاستخراج عن طريق الصور مع نظام إعادة المحاولة التلقائي (Retry)
def extract_via_images(panel_img, inverter_img, battery_img, key):
    client = genai.Client(api_key=key)
    contents = []
    
    contents.append(compress_image_for_speed(panel_img))
    contents.append(compress_image_for_speed(inverter_img))
    if battery_img:
        contents.append(compress_image_for_speed(battery_img))

    prompt = f"""
    أنت مهندس طاقة شمسية خبير. قم بتحليل الصور المرفقة (لوح شمسي، إنفيرتر، وبطارية إن وجدت) واستخرج البيانات التالية بأسلوب JSON فقط دون أي مقدمات:
    {JSON_STRUCTURE}
    ملاحظة: 
    - أعد أرقاماً فقط للقيم الرقمية دون وحدات، واستخدم 0 للقيم المفقودة.
    - إذا لم تكن صورة البطارية مرفقة، اجعل قيم external_battery تساوي 0 أو "غير معروف".
    """
    contents.append(prompt)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="models/gemini-3.6-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2 * (attempt + 1))


# 7. دالة الاستخراج عن طريق اسم الموديل (نصياً) مع نظام إعادة المحاولة التلقائي (Retry)
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
    - التزم بدقة المواصفات الفنية الحقيقية (Datasheet) وتجنب أي تخمين عشوائي للقيم الكهربائية (مثل Voc, Vmp, Pmax).
    - إذا لم تطلب بطارية، اجعل قيم external_battery تساوي 0 أو "غير معروف".
    """

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="models/gemini-3.6-flash",
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2 * (attempt + 1))


# 8. زر التفعيل والتحليل
if st.button("⚡ تحليل سريع واستخراج التقرير والحسابات"):
    if not api_key:
        st.error("⚠️ يرجى إدخال مفتاح Gemini API Key في القائمة الجانبية.")
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
                    with st.spinner("⚡ جاري قراءة الملصقات وتحليل الصور (مع إعادة محاولة تلقائية عند الضغط)..."):
                        res = extract_via_images(p_img, i_img, b_img, api_key)
                except Exception as e:
                    st.error(f"حدث خطأ أثناء معالجة الصور أو ضغط الخادم: {e}")
        else:
            if not panel_text_query or not inverter_text_query:
                st.error("⚠️ يرجى كتابة اسم الشركة والموديل للوح والإنفيرتر معاً.")
            elif enable_battery and not battery_text_query:
                st.error("⚠️ لقد قمت بتفعيل فحص البطارية، يرجى كتابة اسم وموديل البطارية أيضاً.")
            else:
                try:
                    with st.spinner("🔍 جاري البحث والاتصال بقواعد البيانات (مع إعادة محاولة تلقائية)..."):
                        res = extract_via_text(
                            panel_text_query, inverter_text_query, battery_text_query if enable_battery else "", api_key
                        )
                except Exception as e:
                    st.error(f"حدث خطأ أثناء البحث أو ضغط الخادم المؤقت: {e}")

        if res:
            st.session_state["analysis_result"] = res
            st.toast(
                f"🚀 تم التحليل واستخراج المواصفات في {round(time.time() - start_t, 2)} ثوانٍ!",
                icon="⚡",
            )


# 9. عرض النتائج والحسابات
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
    strings_per_mppt = safe_int(inv.get("strings_per_mppt"), default=1)
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
        system_errors.append(
            "⚠️ **تناقض خطير:** لقد قمت بإدخال/تفعيل بطارية خارجية مع إنفيرتر شبكي (On-Grid). إنفيرترات On-Grid لا تدعم توصيل البطاريات بشكل مباشر."
        )

    inv_batt_v = safe_float(batt_info.get("nominal_voltage_v"))
    if not is_on_grid and has_external_battery and inv_batt_v > 0 and b_volts > 0:
        is_compat, msg = is_battery_voltage_compatible(inv_batt_v, b_volts)
        if not is_compat:
            system_errors.append(f"❌ **خطأ في جهد البطارية:** {msg}")

    if max_mppt_current > 0 and isc_safe > max_mppt_current:
        system_warnings.append(
            f"⚠️ **تحذير تيار (Clipping):** تيار القصر المعدل للوح ({round(isc_safe, 2)} A) أعلى من أقصى تيار لمدخل MPPT ({max_mppt_current} A)."
        )

    if system_errors or system_warnings:
        st.markdown("---")
        st.subheader("🚨 تقرير الأخطاء والتنبيهات في المنظومة")
        for err in system_errors:
            st.error(err)
        for warn in system_warnings:
            st.warning(warn)

    st.subheader("📌 البيانات التعريفية والموديلات المكتشفة")
    col_p_info, col_i_info = st.columns(2)

    with col_p_info:
        st.markdown("### ☀️ اللوح الشمسي")
        st.write(f"**الشركة المصنعة:** {format_val(p_brand)}")
        st.write(f"**الموديل / الاسم:** {format_val(p_model)}")
        st.write(f"**نوع اللوح:** {format_val(p_type)}")
        st.write(f"- القدرة (Pmax): {format_val(pmax, 'W')}")
        st.write(f"- جهد الدارة المفتوحة (Voc): {format_val(voc, 'V')}")
        st.write(f"- الجهد التشغيلي (Vmp): {format_val(vmp, 'V')}")
        st.write(f"- تيار القصر (Isc): {format_val(isc, 'A')}")
        st.write(f"- التيار التشغيلي (Imp): {format_val(imp, 'A')}")

    with col_i_info:
        st.markdown("### ⚡ الإنفيرتر")
        st.write(f"**الشركة المصنعة:** {format_val(i_brand)}")
        st.write(f"**الموديل / الاسم:** {format_val(i_model)}")
        st.write(f"**نوع الإنفيرتر:** {format_val(i_type)}")
        st.write(f"**نظام الفازات (Phase):** {format_val(phase_type)}")
        st.write(f"**معمارية الجهد (DC Architecture):** {format_val(v_arch)}")
        st.write(f"- القدرة الاسمية: {format_val(ac_rated_power, 'W')}")
        st.write(f"- أقصى جهد مستمر (DC Max): {format_val(v_max, 'V')}")
        st.write(f"- أدنى جهد MPPT: {format_val(v_mppt_min, 'V')}")
        st.write(f"- أقصى جهد MPPT: {format_val(v_mppt_max, 'V')}")
        st.write(f"- عدد MPPT: `{mppt_count}` | عدد Strings/MPPT: `{strings_per_mppt}`")
        st.write(f"- أقصى تيار لكل MPPT: {format_val(max_mppt_current, 'A')}")

    st.markdown("---")
    st.subheader("🔋 مواصفات البطاريات، شبكة AC، وقدرة البدء (Startup)")
    c_batt, c_ac, c_surge = st.columns(3)

    with c_batt:
        st.markdown("#### 🔋 نظام بطاريات الإنفيرتر")
        batt_supported = batt_info.get("supported", False)
        batt_volts = safe_float(batt_info.get("nominal_voltage_v"))
        batt_type = batt_info.get("battery_type", "غير معروف")
        batt_charge = safe_float(batt_info.get("max_charge_current_a"))

        if not batt_supported and batt_volts == 0:
            st.write("❌ **دعم البطاريات:** `لا يدعم بطاريات (On-Grid / Direct Solar)`")
        else:
            st.write("- **يدعم بطاريات:** `نعم`")
            st.write(f"- **جهد البطارية الاسمي:** {format_val(batt_volts, 'V')}")
            st.write(f"- **أنواع البطاريات:** {format_val(batt_type)}")
            st.write(f"- **أقصى تيار شحن:** {format_val(batt_charge, 'A')}")

    with c_ac:
        st.markdown("#### 🔌 مدخل ومخرج AC")
        ac_v = ac_info.get("nominal_ac_voltage_v", "غير معروف")
        ac_freq = ac_info.get("frequency_hz", "غير معروف")
        ac_in_curr = safe_float(ac_info.get("max_ac_input_current_a"))
        ac_out_curr = safe_float(ac_info.get("max_ac_output_current_a"))
        st.write(f"- **نظام الفاز:** {format_val(phase_type)}")
        st.write(f"- **جهد AC الاسمي:** {format_val(ac_v)}")
        st.write(f"- **التردد:** {format_val(ac_freq)}")
        st.write(f"- **أقصى تيار مدخل AC:** {format_val(ac_in_curr, 'A')}")
        st.write(f"- **أقصى تيار مخرج AC:** {format_val(ac_out_curr, 'A')}")

    with c_surge:
        st.markdown("#### 🚀 قدرة البدء (Surge)")
        s_power = safe_float(surge_info.get("surge_power_va"))
        s_duration = safe_float(surge_info.get("duration_seconds"))
        st.write(f"- **قدرة البدء اللحظية:** {format_val(s_power, 'VA')}")
        st.write(f"- **مدة التحمل:** {format_val(s_duration, 'ثانية')}")

    if enable_battery or (ext_batt.get("nominal_voltage_v", 0) > 0):
        st.markdown("---")
        st.subheader("🔋 مطابقة البطارية الخارجية المدخلة")
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.write(f"**الشركة المصنعة:** {format_val(b_brand)}")
            st.write(f"**الموديل:** {format_val(b_model)}")
            st.write(f"**نوع الكيمياء:** {format_val(b_chem)}")
            st.write(f"- **السعة:** {format_val(b_ah, 'Ah')} ({format_val(b_kwh, 'kWh')})")
        with col_b2:
            st.write(f"- **الجهد الاسمي:** {format_val(b_volts, 'V')}")
            st.write(f"- **أقصى تيار شحن:** {format_val(b_max_chg, 'A')}")
            st.write(f"- **أقصى تيار تفريغ:** {format_val(b_max_dischg, 'A')}")

        inv_batt_v = safe_float(batt_info.get("nominal_voltage_v"))
        if inv_batt_v > 0 and b_volts > 0:
            is_compat, msg = is_battery_voltage_compatible(inv_batt_v, b_volts)
            if is_compat:
                st.success(f"✅ **مطابقة الجهد:** {msg}")
            else:
                st.error(f"❌ **عدم مطابقة الجهد:** {msg}")

    if voc == 0 or vmp == 0 or v_max == 0:
        st.error("⚠️ البيانات الكهربائية الأساسية للجهد غير كافية لإجراء الحسابات (مثل Voc, Vmp, DC Max).")
    else:
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

        min_total_panels = min_string_safe * total_strings
        rec_total_panels = rec_string * total_strings
        max_total_panels = max_string_safe * total_strings

        min_kw = round((min_total_panels * pmax) / 1000, 2)
        rec_kw = round((rec_total_panels * pmax) / 1000, 2)
        max_kw = round((max_total_panels * pmax) / 1000, 2)

        st.markdown("---")
        st.subheader("⚡ نتائج التوصيل وتوزيع السلاسل الآمن")

        st.success(f"""
        🛡️ **حدود الأمان بالسلسلة الواحدة:**
        * **أقل عدد ألواح آمن بالسلسلة:** `{min_string_safe}` ألواح.
        * **أكبر عدد ألواح آمن بالسلسلة:** `{max_string_safe}` لوحاً.
        * **العدد الموصى به مثالياً بالسلسلة:** `{rec_string}` ألواح.
        """)

        st.markdown("### 🔀 تفاصيل التوزيع المقترح من النظام")
        tab1, tab2, tab3 = st.tabs(["⭐ التوزيع المثالي", "🔴 الحد الأدنى", "🟢 الحد الأقصى"])

        with tab1:
            st.info(f"**القدرة الكلية للمنظومة:** `{rec_total_panels}` لوحاً ({rec_kw} kW)\n* **لكل String:** ضع `{rec_string}` ألواح على التوالي.")
        with tab2:
            st.warning(f"**القدرة الكلية للمنظومة:** `{min_total_panels}` لوحاً ({min_kw} kW)\n* **لكل String:** ضع `{min_string_safe}` ألواح على التوالي.")
        with tab3:
            st.success(f"**القدرة الكلية للمنظومة:** `{max_total_panels}` لوحاً ({max_kw} kW)\n* **لكل String:** ضع `{max_string_safe}` لوحاً على التوالي.")

        st.markdown("---")
        st.subheader("🧮 فحص وتوزيع عدد ألواح مخصص")

        min_allowed_panels = max(1, int(min_total_panels))
        max_allowed_panels = max(min_allowed_panels, int(max_total_panels * 2))
        default_panels_count = int(rec_total_panels) if rec_total_panels >= min_allowed_panels else min_allowed_panels
        if default_panels_count > max_allowed_panels:
            default_panels_count = max_allowed_panels

        custom_panels_count = st.number_input(
            "أدخل إجمالي عدد الألواح التي ترغب بتركيبها:",
            min_value=min_allowed_panels,
            max_value=max_allowed_panels,
            value=default_panels_count,
            step=1,
            key="custom_panels_input",
        )

        if custom_panels_count > 0:
            custom_kw = round((custom_panels_count * pmax) / 1000, 2)
            st.markdown(f"#### 📊 النتائج للعدد المدخل ({custom_panels_count} لوحاً):")
            st.write(f"- **إجمالي قدرة التوليد:** `{custom_kw} kW`")

            num_strings_used = min(total_strings, custom_panels_count)
            panels_per_str = custom_panels_count // num_strings_used if num_strings_used > 0 else custom_panels_count
            remainder = custom_panels_count % num_strings_used if num_strings_used > 0 else 0

            vmp_string = round(panels_per_str * vmp, 1)
            voc_string_cold = round(panels_per_str * voc * 1.15, 1)

            if panels_per_str < min_string_safe:
                st.error(f"❌ **العدد المدخل غير آمن (أقل من الحد الأدنى):** الجهد التشغيلي `{vmp_string}V` أقل من المسموح.")
            elif panels_per_str > max_string_safe:
                st.error(f"⚠️ **العدد المدخل غير آمن (يتجاوز أقصى جهد):** جهد الشتاء `{voc_string_cold}V` يتجاوز الحد الأقصى للإنفيرتر.")
            else:
                st.success("✅ **العدد المدخل متوافق تماماً وآمن كهربائياً.**")
                st.info(f"🔌 **خطة التوصيل:** استخدم `{num_strings_used}` سلاسل، وكل سلسلة تضم `{panels_per_str}` ألواح.")
