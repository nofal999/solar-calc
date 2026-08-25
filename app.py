import json
import math
from google import genai
from google.genai import types
from PIL import Image
import streamlit as st

# ضبط إعدادات الصفحة
st.set_page_config(
    page_title="حاسبة الألواح والإنفيرتر - المتقدمة",
    page_icon="☀️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# تخصيص واجهة المستخدم لدعم اللغة العربية بالكامل من اليمين إلى اليسار (RTL)
st.markdown(
    """
    <style>
    /* الاتجاه العام للصفحة والنصوص */
    html, body, [data-testid="stAppViewContainer"], .main {
        direction: rtl;
        text-align: right;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* ضبط محاذاة كافة نصوص Markdown والأشرطة الجانبية */
    div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stMarkdownContainer"] h1,
    div[data-testid="stMarkdownContainer"] h2,
    div[data-testid="stMarkdownContainer"] h3,
    div[data-testid="stMarkdownContainer"] h4,
    div[data-testid="stMarkdownContainer"] li {
        text-align: right !important;
        direction: rtl !important;
    }

    /* ضبط اتجاه القوائم النقطية */
    ul, ol {
        padding-right: 1.5rem !important;
        padding-left: 0rem !important;
    }

    /* ضبط اتجاه علامات التبويب Tabs */
    button[data-baseweb="tab"] {
        direction: rtl !important;
    }
    div[data-baseweb="tab-list"] {
        flex-direction: row-reverse !important;
        justify-content: flex-end !important;
    }

    /* ضبط صندوق رفع الملفات */
    section[data-testid="stFileUploadDropzone"] {
        direction: rtl;
        text-align: right;
    }

    /* تنسيق الأزرار */
    .stButton>button {
        width: 100%;
        background-color: #0284c7;
        color: white;
        border-radius: 8px;
        height: 3em;
        font-weight: bold;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("☀️ حاسبة توافق الألواح والإنفيرتر")
st.caption("تحليل ذكي بمعاملات أمان هندسية آمنة 100% للتوصيل الميداني")

# الشريط الجانبي
with st.sidebar:
    st.header("⚙️ الإعدادات")
    api_key = st.text_input(
        "مفتاح Gemini API Key:",
        type="password",
        help="احصل عليه مجاناً من Google AI Studio",
    )
    st.info("💡 يتم حفظ المفتاح هنا لتسهيل الاستخدام اليومي.")

col_panel, col_inv = st.columns(2)
with col_panel:
    uploaded_panel = st.file_uploader(
        "📸 صورة ملصق اللوح الشمسي", type=["jpg", "jpeg", "png"]
    )
with col_inv:
    uploaded_inverter = st.file_uploader(
        "📸 صورة ملصق الإنفيرتر", type=["jpg", "jpeg", "png"]
    )


def extract_data_via_gemini(panel_img, inverter_img, key):
    client = genai.Client(api_key=key)

    prompt = """
    أنت مهندس طاقة شمسية خبير. قم بتحليل الصورتين المرفقتين (الأولى للوح الشمسي والثانية للإنفيرتر).
    استخرج القيم الفنية الكهربائية بدقة مطلقة وعد بتقرير بأسلوب JSON فقط بالهيكل التالي بدون أي مقدمات أو مشروحات:

    {
      "panel": {
        "model": "اسم الطراز إن وجد",
        "pmax": 0,
        "voc": 0.0,
        "vmp": 0.0,
        "isc": 0.0,
        "imp": 0.0
      },
      "inverter": {
        "model": "اسم الطراز إن وجد",
        "v_max": 0.0,
        "v_mppt_min": 0.0,
        "v_mppt_max": 0.0,
        "v_start": 0.0,
        "mppt_count": 1,
        "strings_per_mppt": 1,
        "max_mppt_current": 0.0
      }
    }
    ملاحظة: تأكد أن القيم العددية تعود بأرقام فقط (Numbers) بدون كتابة أصل الوحدات (مثل V أو A أو W).
    """

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=[panel_img, inverter_img, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        ),
    )
    return json.loads(response.text)


if st.button("🔍 تحليل واستخرج الحسابات الأمنيّة"):
    if not api_key:
        st.error("⚠️ يرجى إدخال مفتاح Gemini API Key في القائمة الجانبية.")
    elif not uploaded_panel or not uploaded_inverter:
        st.error("⚠️ يرجى تحميل الصورتين معاً لمتابعة الحسابات.")
    else:
        try:
            p_img = Image.open(uploaded_panel)
            i_img = Image.open(uploaded_inverter)

            with st.spinner("جاري قراءة الملصقات وتطبيق الحسابات بـ معاملات الأمان..."):
                res = extract_data_via_gemini(p_img, i_img, api_key)

                panel = res.get("panel", {})
                inv = res.get("inverter", {})

                pmax = float(panel.get("pmax", 0))
                voc = float(panel.get("voc", 0))
                vmp = float(panel.get("vmp", 0))
                isc = float(panel.get("isc", 0))

                v_max = float(inv.get("v_max", 0))
                v_mppt_min = float(inv.get("v_mppt_min", 0))
                v_mppt_max = float(inv.get("v_mppt_max", 0))
                mppt_count = int(inv.get("mppt_count", 1))
                strings_per_mppt = int(inv.get("strings_per_mppt", 1))

                # عرض البيانات المستخرجة
                st.subheader("📋 المواصفات المستخرجة")

                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**🔹 اللوح الشمسي**")
                    st.write(f"- القدرة (Pmax): `{pmax} W`")
                    st.write(f"- جهد الدارة المفتوحة (Voc): `{voc} V`")
                    st.write(f"- الجهد التشغيلي (Vmp): `{vmp} V`")
                    st.write(f"- تيار القصر (Isc): `{isc} A`")

                with c2:
                    st.markdown("**🔹 الإنفيرتر**")
                    st.write(f"- أقصى جهد مستمر (DC Max): `{v_max} V`")
                    st.write(f"- نطاق MPPT: `{v_mppt_min} V` - `{v_mppt_max} V`")
                    st.write(f"- عدد MPPT: `{mppt_count}`")
                    st.write(f"- عدد Strings / MPPT: `{strings_per_mppt}`")

                # ==========================================
                # 🛡️ الحسابات بـ معاملات الأمان
                # ==========================================

                # 1. الحد الأدنى الآمن للألواح في السلسلة (Safety Margin +10% للحرارة العالية)
                v_mppt_min_safe = v_mppt_min * 1.10
                min_string_safe = math.ceil(v_mppt_min_safe / vmp) if vmp > 0 else 0

                # 2. الحد الأقصى الآمن للألواح في السلسلة (Safety Margin 1.15 للبرودة + 5% هامش أمان)
                voc_cold_safe = voc * 1.15
                v_max_safe = v_max * 0.95
                
                max_by_voc = math.floor(v_max_safe / voc_cold_safe) if voc_cold_safe > 0 else 0
                max_by_mppt = math.floor(v_mppt_max / vmp) if vmp > 0 else max_by_voc
                max_string_safe = min(max_by_voc, max_by_mppt)

                # العدد الموصى به للسلسلة الواحدة
                rec_string = math.floor((min_string_safe + max_string_safe) / 2)

                # إجمالي السلاسل
                total_strings = mppt_count * strings_per_mppt

                # حسابات الإجمالي لكل MPPT ولكل خيار
                panels_per_mppt_min = min_string_safe * strings_per_mppt
                panels_per_mppt_rec = rec_string * strings_per_mppt
                panels_per_mppt_max = max_string_safe * strings_per_mppt

                min_total_panels = min_string_safe * total_strings
                rec_total_panels = rec_string * total_strings
                max_total_panels = max_string_safe * total_strings

                min_kw = round((min_total_panels * pmax) / 1000, 2)
                rec_kw = round((rec_total_panels * pmax) / 1000, 2)
                max_kw = round((max_total_panels * pmax) / 1000, 2)

                # عرض النتائج النهائية
                st.markdown("---")
                st.subheader("⚡ نتائج التوصيل وتوزيع السلاسل الآمن")

                st.success(f"""
                🛡️ **حدود الأمان للسلسلة الواحدة (String Limits):**
                * **أقل عدد ألواح آمن بالسلسلة:** `{min_string_safe}` ألواح.
                * **أكبر عدد ألواح آمن بالسلسلة:** `{max_string_safe}` لوحاً.
                * **العدد الموصى به مثالياً بالسلسلة:** `{rec_string}` ألواح.
                """)

                st.markdown("### 🔀 تفاصيل توزيع الألواح على MPPT و String")

                tab1, tab2, tab3 = st.tabs(["⭐ التوزيع المثالي (الموصى به)", "🔴 الحد الأدنى (الحد الأدنى للتشغيل)", "🟢 الحد الأقصى (السعة القصوى)"])

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
