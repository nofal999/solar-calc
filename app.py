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
    "اختر طريقة إدخال البيانات للبحث والتحليل:",
    ["📸 1. البحث عن طريق الصور (إرفاق الملصقات)", "✍️ 2. البحث عن طريق اسم الشركة والموديل (نصياً)"],
    index=0,
)

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
            placeholder="مثال: Jinko Solar JKMM550M-72HL4-V",
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


# 6. دالة الاستخراج عن طريق الصور
def extract_via_images(panel_img, inverter_img, battery_img, key):
    client = genai.Client(api_key=key)
    contents = []
    
    contents.append(compress_image_for_speed(panel_img))
    contents.append(compress_image_for_speed(inverter_img))
    
    if battery_img:
        contents.append(compress_image_for_speed(battery_img))

    prompt = f"""
    أنت مهندس طاقة شمسية خبير. قم بتحليل الصور المرفقة واستخرج البيانات التالية بأسلوب JSON فقط دون أي مقدمات:
    {JSON_STRUCTURE}
    ملاحظة: أعد أرقاماً فقط للقيم الرقمية، واستخدم 0 للقيم المفقودة.
    """
    contents.append(prompt)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    return json.loads(response.text)


# 7. دالة الاستخراج عن طريق النص
def extract_via_text(p_text, i_text, b_text, key):
    client = genai.Client(api_key=key)
    b_prompt = f'والبطارية الخارجية المطلوبة: "{b_text}"' if b_text else 'لا يوجد بطارية خارجية مخصصة.'

    prompt = f"""
    أنت خبير بقواعد بيانات كتالوجات الألواح الشمسية والإنفيرترات والبطاريات.
    اللوح الشمسي: "{p_text}"
    الإنفيرتر: "{i_text}"
    {b_prompt}

    استخرج المواصفات القياسية وعد بتقرير JSON بنفس الهيكل تماماً بدون أي مقدمات:
    {JSON_STRUCTURE}
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    return json.loads(response.text)


# 8. زر التحليل
if st.button("⚡ تحليل سريع واستخراج التقرير والحسابات"):
    if not api_key:
        st.error("⚠️ يرجى إدخال مفتاح Gemini API Key في القائمة الجانبية.")
    else:
        res = None
        start_t = time.time()

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
                    with st.spinner("⚡ جاري تحليل الصور عبر Gemini..."):
                        res = extract_via_images(p_img, i_img, b_img, api_key)
                except Exception as e:
                    st.error(f"خطأ أثناء معالجة الصور: {e}")
        else:
            if not panel_text_query or not inverter_text_query:
                st.error("⚠️ يرجى كتابة اسم الشركة والموديل للوح والإنفيرتر.")
            elif enable_battery and not battery_text_query:
                st.error("⚠️ يرجى كتابة اسم وموديل البطارية.")
            else:
                try:
                    with st.spinner("🔍 جاري البحث والتحليل..."):
                        res = extract_via_text(panel_text_query, inverter_text_query, battery_text_query if enable_battery else "", api_key)
                except Exception as e:
                    st.error(f"خطأ أثناء البحث بالنص: {e}")

        if res:
            st.session_state["analysis_result"] = res
            st.toast(f"🚀 تم الاستخراج بنجاح في {round(time.time() - start_t, 2)} ثوانٍ!", icon="⚡")


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

    st.subheader("📌 البيانات التعريفية والموديلات المكتشفة")
    col_p_info, col_i_info = st.columns(2)

    with col_p_info:
        st.markdown("### ☀️ اللوح الشمسي")
        st.write(f"**الشركة:** {format_val(p_brand)}")
        st.write(f"**الموديل:** {format_val(p_model)}")
        st.write(f"**النوع:** {format_val(p_type)}")
        st.write(f"- Pmax: {format_val(pmax, 'W')}")
        st.write(f"- Voc: {format_val(voc, 'V')}")
        st.write(f"- Vmp: {format_val(vmp, 'V')}")
        st.write(f"- Isc: {format_val(isc, 'A')}")
        st.write(f"- Imp: {format_val(imp, 'A')}")

    with col_i_info:
        st.markdown("### ⚡ الإنفيرتر")
        st.write(f"**الشركة:** {format_val(i_brand)}")
        st.write(f"**الموديل:** {format_val(i_model)}")
        st.write(f"**النوع:** {format_val(i_type)}")
        st.write(f"**الفاز:** {format_val(phase_type)}")
        st.write(f"**معمارية الجهد:** {format_val(v_arch)}")
        st.write(f"- القدرة الاسمية: {format_val(ac_rated_power, 'W')}")
        st.write(f"- DC Max: {format_val(v_max, 'V')}")
        st.write(f"- أدنى MPPT: {format_val(v_mppt_min, 'V')}")
        st.write(f"- أقصى MPPT: {format_val(v_mppt_max, 'V')}")
        st.write(f"- عدادات MPPT: `{mppt_count}` | سلاسل/MPPT: `{strings_per_mppt}`")
        st.write(f"- أقصى تيار MPPT: {format_val(max_mppt_current, 'A')}")

    st.markdown("---")
    st.subheader("🔋 مواصفات البطاريات، شبكة AC، وقدرة البدء")
    c_batt, c_ac, c_surge = st.columns(3)

    with c_batt:
        st.markdown("#### 🔋 بطاريات الإنفيرتر")
        batt_supported = batt_info.get("supported", False)
        batt_volts = safe_float(batt_info.get("nominal_voltage_v"))
        if not batt_supported and batt_volts == 0:
            st.write("❌ لا يدعم بطاريات (On-Grid)")
        else:
            st.write("✅ يدعم بطاريات")
            st.write(f"- الجهد الاسمي: {format_val(batt_volts, 'V')}")
            st.write(f"- الأنواع: {format_val(batt_info.get('battery_type'))}")

    with c_ac:
        st.markdown("#### 🔌 مدخل ومخرج AC")
        st.write(f"- الجهد الاسمي: {format_val(ac_info.get('nominal_ac_voltage_v'))}")
        st.write(f"- التردد: {format_val(ac_info.get('frequency_hz'))}")

    with c_surge:
        st.markdown("#### 🚀 قدرة البدء")
        st.write(f"- Surge VA: {format_val(surge_info.get('surge_power_va'), 'VA')}")

    if enable_battery or (ext_batt.get("nominal_voltage_v", 0) > 0):
        st.markdown("---")
        st.subheader("🔋 مطابقة البطارية الخارجية")
        b_volts = safe_float(ext_batt.get("nominal_voltage_v"))
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.write(f"**الموديل:** {format_val(ext_batt.get('model'))}")
            st.write(f"- السعة: {format_val(ext_batt.get('capacity_ah'), 'Ah')} ({format_val(ext_batt.get('capacity_kwh'), 'kWh')})")
        with col_b2:
            st.write(f"- الجهد الاسمي: {format_val(b_volts, 'V')}")

        inv_batt_v = safe_float(batt_info.get("nominal_voltage_v"))
        if inv_batt_v > 0 and b_volts > 0:
            is_compat, msg = is_battery_voltage_compatible(inv_batt_v, b_volts)
            if is_compat:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")

    if voc == 0 or vmp == 0 or v_max == 0:
        st.error("⚠️ البيانات الكهربائية غير كافية لإجراء الحسابات.")
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
        * **أقل عدد ألواح آمن:** `{min_string_safe}`
        * **أكبر عدد ألواح آمن:** `{max_string_safe}`
        * **العدد الموصى به:** `{rec_string}`
        """)

        tab1, tab2, tab3 = st.tabs(["⭐ التوزيع المثالي", "🔴 الحد الأدنى", "🟢 الحد الأقصى"])

        with tab1:
            st.info(f"القدرة الكلية: `{rec_total_panels}` لوح (`{rec_kw} kW`) | بكل String: `{rec_string}` ألواح.")
        with tab2:
            st.warning(f"القدرة الكلية: `{min_total_panels}` لوح (`{min_kw} kW`) | بكل String: `{min_string_safe}` ألواح.")
        with tab3:
            st.success(f"القدرة الكلية: `{max_total_panels}` لوح (`{max_kw} kW`) | بكل String: `{max_string_safe}` ألواح.")

        st.markdown("---")
        st.subheader("🧮 فحص وتوزيع عدد ألواح مخصص")

        min_allowed_panels = max(1, int(min_total_panels))
        max_allowed_panels = max(min_allowed_panels, int(max_total_panels * 2))
        default_panels_count = int(rec_total_panels) if rec_total_panels >= min_allowed_panels else min_allowed_panels

        custom_panels_count = st.number_input(
            "إجمالي عدد الألواح المراد تركيبها:",
            min_value=min_allowed_panels,
            max_value=max_allowed_panels,
            value=default_panels_count,
            step=1,
        )

        if custom_panels_count > 0:
            custom_kw = round((custom_panels_count * pmax) / 1000, 2)
            num_strings_used = min(total_strings, custom_panels_count)
            panels_per_str = custom_panels_count // num_strings_used if num_strings_used > 0 else custom_panels_count
            vmp_string = round(panels_per_str * vmp, 1)
            voc_string_cold = round(panels_per_str * voc * 1.15, 1)

            st.write(f"- إجمالي القدرة: `{custom_kw} kW`")
            if panels_per_str < min_string_safe:
                st.error(f"❌ العدد المدخل قليل جداً (الجهد `{vmp_string}V` أقل من المسموح).")
            elif panels_per_str > max_string_safe:
                st.error(f"⚠️ العدد المدخل يتجاوز أقصى جهد آمن (`{voc_string_cold}V`).")
            else:
                st.success(f"✅ العدد مدعوم وآمن كهربائياً. اربط `{panels_per_str}` ألواح لكل سلسلة من أصل `{num_strings_used}` سلاسل.")
