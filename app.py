import json
import math
from google import genai
from google.genai import types
from PIL import Image
import streamlit as st

# ضبط إعدادات الصفحة
st.set_page_config(
    page_title="حاسبة توافق الألواح والإنفيرتر الشاملة",
    page_icon="☀️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# تخصيص واجهة المستخدم لدعم اللغة العربية وتجاوب الهاتف (Responsive RTL)
st.markdown(
    """
    <style>
    /* تطبيق اتجاه النصوص العربية دون المساس بتخطيط Streamlit الأصلي */
    [data-testid="stMainBlockContainer"], 
    [data-testid="stSidebarContent"] {
        direction: rtl;
        text-align: right;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* محاذاة العناوين والنصوص من اليمين */
    div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stMarkdownContainer"] h1,
    div[data-testid="stMarkdownContainer"] h2,
    div[data-testid="stMarkdownContainer"] h3,
    div[data-testid="stMarkdownContainer"] h4,
    div[data-testid="stMarkdownContainer"] li {
        text-align: right !important;
        direction: rtl !important;
    }

    /* إصلاح القوائم النقطية */
    ul, ol {
        padding-right: 1.5rem !important;
        padding-left: 0rem !important;
    }

    /* إصلاح اتجاه علامات التبويب Tabs */
    button[data-baseweb="tab"] {
        direction: rtl !important;
    }
    div[data-baseweb="tab-list"] {
        flex-direction: row-reverse !important;
        justify-content: flex-end !important;
    }

    /* إصلاح مربع رفع الملفات للشاشات الصغيرة */
    section[data-testid="stFileUploadDropzone"] {
        direction: rtl;
        text-align: right;
    }

    /* تحسين زر التحليل */
    .stButton>button {
        width: 100%;
        background-color: #0284c7;
        color: white;
        border-radius: 8px;
        height: 3em;
        font-weight: bold;
        margin-top: 10px;
    }

    /* تحسين محاذاة أشرطة التنبيه والمعلومات */
    .stAlert {
        direction: rtl;
        text-align: right;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("☀️ حاسبة توافق الألواح والإنفيرتر الشاملة")
st.caption("تحليل ذكي متكامل للمواصفات الكهربائية، البطاريات، فزة البدء، والتوصيل الميداني")

# الشريط الجانبي
with st.sidebar:
    st.header("⚙️ الإعدادات")
    api_key = st.text_input(
        "مفتاح Gemini API Key:",
        type="password",
        help="احصل عليه مجاناً من Google AI Studio",
    )
    st.info("💡 يتم حفظ المفتاح هنا لتسهيل الاستخدام اليومي.")

# رفع صور ملصقات الألواح والإنفيرتر
uploaded_panel = st.file_uploader(
    "📸 صورة ملصق اللوح الشمسي", type=["jpg", "jpeg", "png"]
)
uploaded_inverter = st.file_uploader(
    "📸 صورة ملصق الإنفيرتر", type=["jpg", "jpeg", "png"]
)


def safe_float(value, default=0.0):
    """دالة أمان لتحويل القيم إلى float دون التسبب في خطأ NoneType"""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=1):
    """دالة أمان لتحويل القيم إلى int دون التسبب في خطأ NoneType"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def format_val(value, unit=""):
    """دالة تنسيق تعيد 'غير موجود على الملصق' إذا كانت القيمة مفقودة أو صفر"""
    if value is None or value == "" or value == 0 or value == 0.0 or value == "غير محدد":
        return "`غير موجود على الملصق`"
    return f"`{value} {unit}`".strip()


def extract_data_via_gemini(panel_img, inverter_img, key):
    client = genai.Client(api_key=key)

    prompt = """
    أنت مهندس طاقة شمسية خبير جداً. قم بتحليل الصورتين المرفقتين (الأولى للوح الشمسي والثانية للإنفيرتر).
    استخرج جميع البيانات الفنية والتعريفية بدقة مطلقة وعد بتقرير بأسلوب JSON فقط بالهيكل التالي بدون أي مقدمات أو مشروحات:

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
          "battery_type": "أنواع البطاريات المدعومة (Lithium, Lead-Acid, etc.)",
          "max_charge_current_a": 0.0
        },
        "ac_input_output": {
          "nominal_ac_voltage_v": "جهد AC الاسمي (مثال: 230V / 400V)",
          "frequency_hz": "التردد (50Hz / 60Hz)",
          "max_ac_input_current_a": 0.0,
          "max_ac_output_current_a": 0.0
        },
        "startup_surge": {
          "surge_power_va": 0.0,
          "duration_seconds": 0.0
        }
      }
    }
    ملاحظة مهمة جداً:
    1. بالنسبة للقيم العددية، أعد أرقاماً فقط (Numbers) دون كتابة الوحدات ضمن الرقم.
    2. إذا لم تكن القيمة أو الميزة موجودة أو واضحة في الملصق استخدم 0 للقيم الرقمية و "غير موجود على الملصق" للنصوص بدلاً من null.
    """

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=[panel_img, inverter_img, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        ),
    )
    return json.loads(response.text)


if st.button("🔍 تحليل واستخراج التقرير الشامل والحسابات"):
    if not api_key:
        st.error("⚠️ يرجى إدخال مفتاح Gemini API Key في القائمة الجانبية.")
    elif not uploaded_panel or not uploaded_inverter:
        st.error("⚠️ يرجى تحميل الصورتين معاً لمتابعة الحسابات.")
    else:
        try:
            p_img = Image.open(uploaded_panel)
            i_img = Image.open(uploaded_inverter)

            with st.spinner("جاري قراءة كافة بيانات الملصقات وتطبيق الحسابات بـ معاملات الأمان..."):
                res = extract_data_via_gemini(p_img, i_img, api_key)

                panel = res.get("panel", {})
                inv = res.get("inverter", {})

                # استخراج بيانات اللوح
                p_brand = panel.get("brand", "غير موجود على الملصق")
                p_model = panel.get("model", "غير موجود على الملصق")
                p_part = panel.get("part_number", "غير موجود على الملصق")
                p_type = panel.get("type", "غير موجود على الملصق")

                pmax = safe_float(panel.get("pmax"))
                voc = safe_float(panel.get("voc"))
                vmp = safe_float(panel.get("vmp"))
                isc = safe_float(panel.get("isc"))
                imp = safe_float(panel.get("imp"))

                # استخراج بيانات الإنفيرتر
                i_brand = inv.get("brand", "غير موجود على الملصق")
                i_model = inv.get("model", "غير موجود على الملصق")
                i_part = inv.get("part_number", "غير موجود على الملصق")
                i_type = inv.get("type", "غير موجود على الملصق")
                ac_rated_power = safe_float(inv.get("ac_rated_power_w"))

                v_max = safe_float(inv.get("v_max"))
                v_mppt_min = safe_float(inv.get("v_mppt_min"))
                v_mppt_max = safe_float(inv.get("v_mppt_max"))
                mppt_count = safe_int(inv.get("mppt_count"), default=1)
                strings_per_mppt = safe_int(inv.get("strings_per_mppt"), default=1)
                max_mppt_current = safe_float(inv.get("max_mppt_current"))

                # تفاصيل البطارية و AC و Startup
                batt_info = inv.get("battery", {})
                ac_info = inv.get("ac_input_output", {})
                surge_info = inv.get("startup_surge", {})

                # عرض البيانات التعريفية الكاملة
                st.subheader("📌 البيانات التعريفية والموديلات")
                col_p_info, col_i_info = st.columns(2)

                with col_p_info:
                    st.markdown("### ☀️ اللوح الشمسي")
                    st.write(f"**الشركة المصنعة:** {format_val(p_brand)}")
                    st.write(f"**الموديل / الاسم:** {format_val(p_model)}")
                    st.write(f"**الرقم التسلسلي / Part No:** {format_val(p_part)}")
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
                    st.write(f"**الرقم التسلسلي / Model No:** {format_val(i_part)}")
                    st.write(f"**نوع الإنفيرتر:** {format_val(i_type)}")
                    st.write(f"- القدرة المستمرة الاسمية: {format_val(ac_rated_power, 'W')}")
                    st.write(f"- أقصى جهد مستمر (DC Max): {format_val(v_max, 'V')}")
                    st.write(f"- أدنى جهد MPPT: {format_val(v_mppt_min, 'V')}")
                    st.write(f"- أقصى جهد MPPT: {format_val(v_mppt_max, 'V')}")
                    st.write(f"- عدد MPPT: `{mppt_count}` | عدد Strings/MPPT: `{strings_per_mppt}`")
                    st.write(f"- أقصى تيار لكل MPPT: {format_val(max_mppt_current, 'A')}")

                st.markdown("---")

                # عرض تفاصيل البطاريات ومدخلات/مخرجات AC وفزة البدء
                st.subheader("🔋 مواصفات البطاريات، شبكة AC، وقدرة البدء (Startup)")
                c_batt, c_ac, c_surge = st.columns(3)

                with c_batt:
                    st.markdown("#### 🔋 نظام البطاريات")
                    batt_supported = batt_info.get("supported", False)
                    batt_volts = safe_float(batt_info.get("nominal_voltage_v"))
                    batt_type = batt_info.get("battery_type", "غير موجود على الملصق")
                    batt_charge = safe_float(batt_info.get("max_charge_current_a"))

                    if not batt_supported and batt_volts == 0:
                        st.write("❌ **دعم البطاريات:** `لا يدعم بطاريات (On-Grid / Direct Solar)`")
                    else:
                        st.write(f"- **جهد البطارية الاسمي:** {format_val(batt_volts, 'V')}")
                        st.write(f"- **أنواع البطاريات المدعومة:** {format_val(batt_type)}")
                        st.write(f"- **أقصى تيار شحن:** {format_val(batt_charge, 'A')}")

                with c_ac:
                    st.markdown("#### 🔌 مدخل ومخرج AC")
                    ac_v = ac_info.get("nominal_ac_voltage_v", "غير موجود على الملصق")
                    ac_freq = ac_info.get("frequency_hz", "غير موجود على الملصق")
                    ac_in_curr = safe_float(ac_info.get("max_ac_input_current_a"))
                    ac_out_curr = safe_float(ac_info.get("max_ac_output_current_a"))

                    st.write(f"- **جهد AC الاسمي:** {format_val(ac_v)}")
                    st.write(f"- **التردد:** {format_val(ac_freq)}")
                    st.write(f"- **أقصى تيار مدخل AC:** {format_val(ac_in_curr, 'A')}")
                    st.write(f"- **أقصى تيار مخرج AC:** {format_val(ac_out_curr, 'A')}")

                with c_surge:
                    st.markdown("#### 🚀 قدرة فزة البدء (Surge)")
                    s_power = safe_float(surge_info.get("surge_power_va"))
                    s_duration = safe_float(surge_info.get("duration_seconds"))

                    st.write(f"- **قدرة البدء اللحظية:** {format_val(s_power, 'VA')}")
                    st.write(f"- **مدة التحمل اللحظية:** {format_val(s_duration, 'ثانية')}")

                # التحقق من وجود القيم الأساسية قبل إجراء الحسابات
                if voc == 0 or vmp == 0 or v_max == 0:
                    st.error("⚠️ لم يتم تعيين كافة القيم الكهربائية الأساسية للجهد من الصور (مثل Voc, Vmp, DC Max). يرجى التأكد من وضوح الملصقات المحملة.")
                else:
                    # ==========================================
                    # 🛡️ الحسابات الشاملة بـ معاملات الأمان
                    # ==========================================

                    # 1. الحد الأدنى الآمن للألواح في السلسلة (+10% للحرارة)
                    v_mppt_min_safe = v_mppt_min * 1.10
                    min_string_safe = math.ceil(v_mppt_min_safe / vmp) if vmp > 0 else 0

                    # 2. الحد الأقصى الآمن للألواح في السلسلة (1.15 للبرودة + 5% هامش أمان)
                    voc_cold_safe = voc * 1.15
                    v_max_safe = v_max * 0.95
                    
                    max_by_voc = math.floor(v_max_safe / voc_cold_safe) if voc_cold_safe > 0 else 0
                    max_by_mppt = math.floor(v_mppt_max / vmp) if vmp > 0 and v_mppt_max > 0 else max_by_voc
                    max_string_safe = min(max_by_voc, max_by_mppt) if max_by_mppt > 0 else max_by_voc

                    # العدد الموصى به
                    rec_string = math.floor((min_string_safe + max_string_safe) / 2)
                    total_strings = mppt_count * strings_per_mppt

                    # حسابات الإجمالي
                    panels_per_mppt_min = min_string_safe * strings_per_mppt
                    panels_per_mppt_rec = rec_string * strings_per_mppt
                    panels_per_mppt_max = max_string_safe * strings_per_mppt

                    min_total_panels = min_string_safe * total_strings
                    rec_total_panels = rec_string * total_strings
                    max_total_panels = max_string_safe * total_strings

                    min_kw = round((min_total_panels * pmax) / 1000, 2)
                    rec_kw = round((rec_total_panels * pmax) / 1000, 2)
                    max_kw = round((max_total_panels * pmax) / 1000, 2)

                    # 3. فحص التيار
                    isc_safe = isc * 1.25

                    # عرض النتائج
                    st.markdown("---")
                    st.subheader("⚡ نتائج التوصيل وتوزيع السلاسل الآمن")

                    if max_mppt_current > 0 and isc_safe > max_mppt_current:
                        st.warning(f"⚠️ **تنبيه مطابقة التيار:** تيار القصر المعدل للوح ({round(isc_safe, 2)} A) أكبر من أقصى تيار يتحمله مدخل MPPT في الإنفيرتر ({max_mppt_current} A). سيعمل النظام ولكن قد يحدث قص للتيار (Clipping) عند الذروة.")
                    elif max_mppt_current > 0:
                        st.success(f"✅ **توافق التيار:** تيار اللوح المعدل ({round(isc_safe, 2)} A) متوافق تماماً مع مدخل الإنفيرتر ({max_mppt_current} A).")
                    else:
                        st.info("ℹ️ لم يتم تحديد أقصى تيار MPPT من صورة الإنفيرتر لفحصه.")

                    st.success(f"""
                    🛡️ **حدود الأمان للسلسلة الواحدة (String Limits):**
                    * **أقل عدد ألواح آمن بالسلسلة:** `{min_string_safe}` ألواح.
                    * **أكبر عدد ألواح آمن بالسلسلة:** `{max_string_safe}` لوحاً.
                    * **العدد الموصى به مثالياً بالسلسلة:** `{rec_string}` ألواح.
                    """)

                    st.markdown("### 🔀 تفاصيل توزيع الألواح على MPPT و String")

                    tab1, tab2, tab3 = st.tabs(["⭐ التوزيع المثالي", "🔴 الحد الأدنى", "🟢 الحد الأقصى"])

                    with tab1:
                        st.info(f"""
                        **القدرة الكلية للمنظومة:** `{rec_total_panels}` لوحاً ({rec_kw} kW)
                        * **عدد مدخلات MPPT:** {mppt_count}
                        * **عدد السلاسل (Strings) لكل MPPT:** {strings_per_mppt}
                        
                        ---
                        📌 **التوزيع الميداني:**
                        * **لكل String:** ضع `{rec_string}` لوحاً على التوالي.
                        * **لكل MPPT:** يحتاج إجمالي `{panels_per_mppt_rec}` لوحاً (موزعة على {strings_per_mppt} سلسلة).
                        """)

                    with tab2:
                        st.warning(f"""
                        **القدرة الكلية للمنظومة:** `{min_total_panels}` لوحاً ({min_kw} kW)
                        * **عدد مدخلات MPPT:** {mppt_count}
                        * **عدد السلاسل (Strings) لكل MPPT:** {strings_per_mppt}
                        
                        ---
                        📌 **التوزيع الميداني:**
                        * **لكل String:** ضع `{min_string_safe}` ألواح على التوالي.
                        * **لكل MPPT:** يحتاج إجمالي `{panels_per_mppt_min}` لوحاً (موزعة على {strings_per_mppt} سلسلة).
                        """)

                    with tab3:
                        st.success(f"""
                        **القدرة الكلية للمنظومة:** `{max_total_panels}` لوحاً ({max_kw} kW)
                        * **عدد مدخلات MPPT:** {mppt_count}
                        * **عدد السلاسل (Strings) لكل MPPT:** {strings_per_mppt}
                        
                        ---
                        📌 **التوزيع الميداني:**
                        * **لكل String:** ضع `{max_string_safe}` لوحاً على التوالي.
                        * **لكل MPPT:** يحتاج إجمالي `{panels_per_mppt_max}` لوحاً (موزعة على {strings_per_mppt} سلسلة).
                        """)

        except Exception as e:
            st.error(f"حدث خطأ أثناء معالجة الحسابات: {e}")
