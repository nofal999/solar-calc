import json
import math
import time
from google import genai
from google.genai import types
from google.genai.errors import APIError
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

    ul, ol {
        padding-right: 1.5rem !important;
        padding-left: 0rem !important;
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

st.title("☀️ حاسبة توافق الألواح والإنفيرتر الشاملة")
st.caption("تحليل ذكي متكامل للمواصفات الكهربائية، نوع الجهد، عدد الفازات، البطاريات، فزة البدء، والتوصيل الميداني")

# الشريط الجانبي
with st.sidebar:
    st.header("⚙️ الإعدادات")
    api_key = st.text_input(
        "مفتاح Gemini API Key:",
        type="password",
        help="احصل عليه مجاناً من Google AI Studio",
    )
    selected_model = st.selectbox(
        "اختر الموديل:",
        ["gemini-2.5-flash", "gemini-1.5-flash"],
        index=0,
        help="إذا واجهت خطأ حصة استخدام أو عدم العثور، يمكنك التبديل بينهم."
    )
    st.info("💡 يتم حفظ المفتاح والإعدادات هنا لتسهيل الاستخدام.")

# رفع صور ملصقات الألواح والإنفيرتر
uploaded_panel = st.file_uploader(
    "📸 صورة ملصق اللوح الشمسي", type=["jpg", "jpeg", "png"]
)
uploaded_inverter = st.file_uploader(
    "📸 صورة ملصق الإنفيرتر", type=["jpg", "jpeg", "png"]
)


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
    if value is None or value == "" or value == 0 or value == 0.0 or value == "غير محدد":
        return "`غير موجود على الملصق`"
    return f"`{value} {unit}`".strip()


def extract_data_via_gemini(panel_img, inverter_img, key, model_name="gemini-2.5-flash"):
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
        "phase_type": "عدد الفازات (Single-Phase أو Three-Phase 3-Phase)",
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
          "battery_type": "أنواع البطاريات المدعومة (Lithium, Lead-Acid, High Voltage Battery, etc.)",
          "max_charge_current_a": 0.0
        },
        "ac_input_output": {
          "nominal_ac_voltage_v": "جهد AC الاسمي (مثال: 230V, 380V/400V)",
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

    # التعامل مع خطأ 429 وإعادة المحاولة التلقائية
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[panel_img, inverter_img, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            err_str = str(e)
            if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str) and attempt < max_retries - 1:
                time.sleep(10)  # الانتظار 10 ثوانٍ وإعادة المحاولة تلقائياً
                continue
            else:
                raise e


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
                res = extract_data_via_gemini(p_img, i_img, api_key, selected_model)

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
                phase_type = inv.get("phase_type", "غير موجود على الملصق")
                v_arch = inv.get("voltage_architecture", "غير موجود على الملصق")
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
                    st.write(f"**نظام الفازات (Phase):** {format_val(phase_type)}")
                    st.write(f"**معمارية الجهد (DC Voltage System):** {format_val(v_arch)}")
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
                        st.write(f"- **يدعم بطاريات:** `نعم`")
                        st.write(f"- **جهد البطارية الاسمي:** {format_val(batt_volts, 'V')}")
                        st.write(f"- **أنواع البطاريات المدعومة:** {format_val(batt_type)}")
                        st.write(f"- **أقصى تيار شحن:** {format_val(batt_charge, 'A')}")

                with c_ac:
                    st.markdown("#### 🔌 مدخل ومخرج AC")
                    ac_v = ac_info.get("nominal_ac_voltage_v", "غير موجود على الملصق")
                    ac_freq = ac_info.get("frequency_hz", "غير موجود على الملصق")
                    ac_in_curr = safe_float(ac_info.get("max_ac_input_current_a"))
                    ac_out_curr = safe_float(ac_info.get("max_ac_output_current_a"))

                    st.write(f"- **نوع الفاز:** {format_val(phase_type)}")
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

                if voc == 0 or vmp == 0 or v_max == 0:
                    st.error("⚠️ لم يتم تعيين كافة القيم الكهربائية الأساسية للجهد من الصور (مثل Voc, Vmp, DC Max). يرجى التأكد من وضوح الملصقات المحملة.")
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

                    isc_safe = isc * 1.25

                    st.markdown("---")
                    st.subheader("⚡ نتائج التوصيل وتوزيع السلاسل الآمن")

                    if max_mppt_current > 0 and isc_safe > max_mppt_current:
                        st.warning(f"⚠️ **تنبيه مطابقة التيار:** تيار القصر المعدل للوح ({round(isc_safe, 2)} A) أكبر من أقصى تيار يتحمله مدخل MPPT في الإنفيرتر ({max_mppt_current} A). سيعمل النظام ولكن قد يحدث قص للتيار (Clipping) عند الذروة.")
                    elif max_mppt_current > 0:
                        st.success(f"✅ **توافق التيار:** تيار اللوح المعدل ({round(isc_safe, 2)} A) متوافق تماماً مع مدخل الإنفيرتر ({max_mppt_current} A).")

                    st.success(f"""
                    🛡️ **حدود الأمان بالسلسلة الواحدة (بناءً على ملصق الصور):**
                    * **أقل عدد ألواح آمن بالسلسلة:** `{min_string_safe}` ألواح.
                    * **أكبر عدد ألواح آمن بالسلسلة:** `{max_string_safe}` لوحاً.
                    * **العدد الموصى به مثالياً بالسلسلة:** `{rec_string}` ألواح.
                    """)

                    st.markdown("### 🔀 تفاصيل التوزيع المقترح من النظام")

                    tab1, tab2, tab3 = st.tabs(["⭐ التوزيع المثالي", "🔴 الحد الأدنى", "🟢 الحد الأقصى"])

                    with tab1:
                        st.info(f"""
                        **القدرة الكلية للمنظومة:** `{rec_total_panels}` لوحاً ({rec_kw} kW)
                        * **عدد مدخلات MPPT:** {mppt_count}
                        * **عدد السلاسل (Strings) لكل MPPT:** {strings_per_mppt}
                        
                        ---
                        📌 **التوزيع الميداني:**
                        * **لكل String:** ضع `{rec_string}` لوحاً على التوالي.
                        """)

                    with tab2:
                        st.warning(f"""
                        **القدرة الكلية للمنظومة:** `{min_total_panels}` لوحاً ({min_kw} kW)
                        * **عدد مدخلات MPPT:** {mppt_count}
                        * **عدد السلاسل (Strings) لكل MPPT:** {strings_per_mppt}
                        
                        ---
                        📌 **التوزيع الميداني:**
                        * **لكل String:** ضع `{min_string_safe}` ألواح على التوالي.
                        """)

                    with tab3:
                        st.success(f"""
                        **القدرة الكلية للمنظومة:** `{max_total_panels}` لوحاً ({max_kw} kW)
                        * **عدد مدخلات MPPT:** {mppt_count}
                        * **عدد السلاسل (Strings) لكل MPPT:** {strings_per_mppt}
                        
                        ---
                        📌 **التوزيع الميداني:**
                        * **لكل String:** ضع `{max_string_safe}` لوحاً على التوالي.
                        """)

                    # قسم فحص العدد المخصص
                    st.markdown("---")
                    st.subheader("🧮 فحص وتوزيع عدد ألواح مخصص (إدخال يدوي)")
                    st.write(f"الحدود الكهربائية المسموحة لهذا النظام هي ما بين **{min_total_panels}** إلى **{max_total_panels}** لوحاً كإجمالي للمنظومة:")

                    custom_panels_count = st.number_input(
                        "أدخل إجمالي عدد الألواح التي ترغب بتركيبها:",
                        min_value=1,
                        max_value=max_total_panels * 2,
                        value=int(rec_total_panels) if rec_total_panels > 0 else int(min_total_panels),
                        step=1,
                    )

                    if custom_panels_count > 0:
                        custom_kw = round((custom_panels_count * pmax) / 1000, 2)
                        st.markdown(f"#### 📊 النتائج للعدد المدخل ({custom_panels_count} لوحاً):")
                        st.write(f"- **إجمالي قدرة التوليد (Power):** `{custom_kw} kW` (محسوبة من بقدرة اللوح `{pmax}W` من الصورة)")

                        num_strings_used = min(total_strings, custom_panels_count)
                        panels_per_str = custom_panels_count // num_strings_used
                        remainder = custom_panels_count % num_strings_used

                        vmp_string = round(panels_per_str * vmp, 1)
                        voc_string_cold = round(panels_per_str * voc * 1.15, 1)

                        if panels_per_str < min_string_safe:
                            st.error(
                                f"❌ **العدد المدخل غير آمن (أقل من الحد الأدنى):**\n\n"
                                f"عند توزيع `{custom_panels_count}` لوحاً على السلاسل، سيكون هناك `{panels_per_str}` ألواح بالسلسلة الواحدة بجهد تشغيلي قدره `{vmp_string}V`.\n\n"
                                f"وهذا أقل من الحد الأدنى للتشغيل الآمن المكتشف من ملصق الإنفيرتر وهو `{min_string_safe}` ألواح (جهد MPPT الأدنى معدلاً = `{round(v_mppt_min_safe,1)}V`). لن يعمل الإنفيرتر بكفاءة."
                            )
                        elif panels_per_str > max_string_safe:
                            st.error(
                                f"⚠️ **العدد المدخل غير آمن (يتجاوز أقصى جهد):**\n\n"
                                f"عند توزيع `{custom_panels_count}` لوحاً، ستحتوي السلسلة على `{panels_per_str}` ألواح بجهد دارة مفتوحة في الشتاء يصل إلى `{voc_string_cold}V`.\n\n"
                                f"وهذا يتجاوز الحد الأقصى الآمن المسموح به في الإنفيرتر وهو `{max_string_safe}` لوحاً (أقصى جهد مستمر = `{round(v_max_safe,1)}V`). **خطر احتراق مدخل الإنفيرتر!**"
                            )
                        else:
                            st.success(
                                f"✅ **العدد المدخل متوافق تماماً وآمن كهربائياً:**\n\n"
                                f"جهد السلسلة التشغيلي سيكون حوالي `{vmp_string}V` وفي أقصى برودة سيعطي `{voc_string_cold}V`، وكلها تقع ضمن نطاق أمان الإنفيرتر المكتشف من الصورتين."
                            )

                            st.info(f"""
                            🔌 **خطة التوصيل الميدانية للعدد المدخل ({custom_panels_count} لوحاً):**
                            * **عدد السلاسل (Strings) المستخدمة:** `{num_strings_used}` من أصل `{total_strings}` المتاحة في الإنفيرتر.
                            * **توصيل كل سلسلة:** اربط `{panels_per_str}` ألواح على التوالي لكل سلسلة.
                            * **الجهد المتوقع لكل سلسلة (Vmp):** `{vmp_string} V`
                            * **الجهد الأقصى المتوقع في الشتاء (Voc Cold):** `{voc_string_cold} V`
                            """ + (f"\n⚠️ **ملاحظة:** يتبقى `{remainder}` ألواح غير موزعة. لضمان اتزان الجهد بين السلاسل، يفضل أن يكون إجمالي عدد الألواح يقبل القسمة بالتساوي على عدد السلاسل المستخدمة." if remainder > 0 else ""))

        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                st.error("⏳ **تم تجاوز عدد الطلبات المسموح به مجاناً في الدقيقة.** تم استخدام المحاولات المتاحة، يرجى الانتظار 30 ثانية ثم إعادة الضغط على الزر.")
            elif "404" in err_msg or "NOT_FOUND" in err_msg:
                st.error("⚠️ الموديل غير متوفر في حسابك الحالي، يرجى التبديل لـ `gemini-1.5-flash` من القائمة الجانبية.")
            else:
                st.error(f"حدث خطأ أثناء معالجة الحسابات: {e}")
