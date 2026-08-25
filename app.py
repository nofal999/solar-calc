import json
import math
from google import genai
from google.genai import types
from PIL import Image
import streamlit as st

# ضبط إعدادات الصفحة
st.set_page_config(
    page_title="حاسبة الألواح والإنفيرتر",
    page_icon="☀️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# تخصيص واجهة المستخدم باللغة العربية واختيار ألوان متناسقة
st.markdown(
    """
    <style>
    .main { text-align: right; direction: rtl; }
    div[data-testid="stMarkdownContainer"] { text-align: right; }
    .stButton>button { width: 100%; background-color: #0284c7; color: white; border-radius: 8px; height: 3em; font-weight: bold; }
    .metric-card { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 15px; margin-bottom: 10px; }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("☀️ حاسبة توافق الألواح والإنفيرتر")
st.caption("حلل ملصقات البيانات واستخرج النتائج الكهربائية ومجالات التوصيل فوراً")

# إدخال مفتاح API في الشريط الجانبي أو الواجهة الرئيسية
with st.sidebar:
    st.header("⚙️ الإعدادات")
    api_key = st.text_input(
        "مفتاح Gemini API Key:",
        type="password",
        help="احصل عليه مجاناً من Google AI Studio",
    )
    st.info("💡 يمكنك حفظ المفتاح هنا لتسهيل الاستخدام اليومي من الجوال.")

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
    ملاحظة: تأكد أن القيم العددية تعود بأرقام فقط (Numbers) بدون كتابة أصل الوحدات (مثل V أو A أو W) لضمان نجاح الحسابات.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[panel_img, inverter_img, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        ),
    )
    return json.loads(response.text)


if st.button("🔍 تحليل واستخراج الحسابات"):
    if not api_key:
        st.error("⚠️ يرجى إدخال مفتاح Gemini API Key في القائمة الجانبية.")
    elif not uploaded_panel or not uploaded_inverter:
        st.error("⚠️ يرجى تحميل الصورتين معاً لمتابعة الحسابات.")
    else:
        try:
            p_img = Image.open(uploaded_panel)
            i_img = Image.open(uploaded_inverter)

            with st.spinner("جاري قراءة الملصقات وتطبيق الحسابات الهندسية..."):
                res = extract_data_via_gemini(p_img, i_img, api_key)

                panel = res.get("panel", {})
                inv = res.get("inverter", {})

                # تحويل القيم لضمان سلامة العمليات الحسابية
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
                    st.write(
                        f"- نطاق MPPT: `{v_mppt_min} V` - `{v_mppt_max} V`"
                    )
                    st.write(f"- عدد MPPT: `{mppt_count}`")
                    st.write(f"- عدد Strings / MPPT: `{strings_per_mppt}`")

                # الحسابات الكهربائية
                # 1. أدنى عدد ألواح لتشغيل الـ MPPT
                min_string = math.ceil(v_mppt_min / vmp) if vmp > 0 else 0

                # 2. أقصى عدد ألواح بالسلسلة (مع معامل أمان برودة الطقس 1.12 لـ Voc)
                voc_cold = voc * 1.12
                max_by_voc = (
                    math.floor(v_max / voc_cold) if voc_cold > 0 else 0
                )
                max_by_mppt = (
                    math.floor(v_mppt_max / vmp) if vmp > 0 else max_by_voc
                )
                max_string = min(max_by_voc, max_by_mppt)

                total_strings = mppt_count * strings_per_mppt

                # عرض النتائج النهائية
                st.markdown("---")
                st.subheader("⚡ نتائج التوصيل والتدقيق الفني")

                st.success(f"""
                * **عدد تتبعات MPPT:** {mppt_count}
                * **إجمالي السلاسل (Total Strings):** {total_strings} سلاسل (بواقع {strings_per_mppt} لكل MPPT).
                * **أقل عدد ألواح في السلسلة الواحدة (String Min):** `{min_string}` ألواح.
                * **أكبر عدد ألواح في السلسلة الواحدة (String Max):** `{max_string}` لوحاً.
                """)

                # السعة الإجمالية
                min_total_panels = min_string * total_strings
                max_total_panels = max_string * total_strings

                min_kw = round((min_total_panels * pmax) / 1000, 2)
                max_kw = round((max_total_panels * pmax) / 1000, 2)

                st.info(f"""
                **📊 القدرة السعوية الكاملة للمنظومة:**
                * **الحد الأدنى للتشغيل:** {min_total_panels} لوحاً ({min_kw} kW).
                * **الحد الأقصى المسموح:** {max_total_panels} لوحاً ({max_kw} kW).
                """)

        except Exception as e:
            st.error(f"حدث خطأ أثناء معالجة الصور: {e}")
