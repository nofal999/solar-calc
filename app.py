import os
import streamlit as st
import google.generativeai as genai
from PIL import Image
import io

# إعداد الصفحة وتكوينها
st.set_page_config(
    page_title="حاسبة الأنظمة الشمسية الذكية",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# تنسيق واجهة المستخدم واللغة العربية (RTL)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        direction: rtl;
        text-align: right;
    }
    .stTextInput, .stNumberInput, .stSelectbox {
        direction: rtl;
    }
    </style>
""", unsafe_allow_html=True)

# إعداد مفتاح API الخاص بـ Gemini (إن وجد)
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    pass

st.title("☀️ النظام الذكي لهندسة وتحليل الطاقة الشمسية")
st.markdown("أداة متكاملة لتحليل توافق الألواح، الإنفيرترات، والبطاريات، واستخراج البيانات عبر الذكاء الاصطناعي.")

# --- الشريط الجانبي للإعدادات ---
st.sidebar.header("⚙️ إعدادات النظام والمساعد الذكي")
user_api_key = st.sidebar.text_input("مفتاح Gemini API (اختياري)", type="password", value=api_key or "")

if user_api_key:
    genai.configure(api_key=user_api_key)

st.sidebar.markdown("---")
st.sidebar.subheader("📌 خيارات التحليل")
input_mode = st.sidebar.radio(
    "اختر طريقة إدخال البيانات:",
    ["إدخال يدوي مباشر", "استخراج البيانات من الصور (AI)"]
)

# --- القسم الأول: إدخال البيانات ---
panel_voc, panel_isc, panel_vmpp, panel_impp, panel_power = 41.5, 11.2, 34.5, 10.5, 450
inv_max_pv_w, inv_max_volt, inv_min_volt, inv_max_curr = 5000, 500, 120, 18

if input_mode == "استخراج البيانات من الصور (AI)":
    st.markdown("### 📸 رفع صور الملصقات الفنية (Datasheet)")
    col_img1, col_img2 = st.columns(2)
    
    with col_img1:
        panel_file = st.file_uploader("رفع صوره لوح الطاقة الشمسية (Panel)", type=["jpg", "png", "jpeg"])
    with col_img2:
        inv_file = st.file_uploader("رفع صورة الإنفيرتر (Inverter)", type=["jpg", "png", "jpeg"])
        
    if panel_file and user_api_key:
        try:
            image = Image.open(panel_file)
            st.image(image, caption="صورة اللوح الشمسي", width=250)
            # نموذج تحليل البيانات هنا إذا توفر المفتاح
        except Exception as e:
            st.error(f"حدث خطأ أثناء قراءة الصورة: {e}")
else:
    st.markdown("### 🎛️ بيانات الألواح والإنفيرتر اليدوية")
    c1, c2, c3 = st.columns(3)
    with c1:
        panel_power = st.number_input("قدرة اللوح الواحد (W):", value=450, step=10)
        panel_voc = st.number_input("جهد الدائرة المفتوحة Voc (V):", value=41.5, step=0.1)
    with c2:
        panel_vmpp = st.number_input("جهد العمل Vmpp (V):", value=34.5, step=0.1)
        panel_isc = st.number_input("تيار القصر Isc (A):", value=11.2, step=0.1)
    with c3:
        panel_impp = st.number_input("تيار العمل Impp (A):", value=10.5, step=0.1)

    st.markdown("---")
    i1, i2, i3, i4 = st.columns(4)
    with i1:
        inv_max_pv_w = st.number_input("القدرة القصوى للإنفيرتر (W):", value=5000, step=100)
    with i2:
        inv_max_volt = st.number_input("أقصى جهد مدخل Voc (V):", value=500.0, step=10.0)
    with i3:
        inv_min_volt = st.number_input("أقل جهد تشغيل MPPT (V):", value=120.0, step=5.0)
    with i4:
        inv_max_curr = st.number_input("أقصى تيار مدخل (A):", value=18.0, step=0.5)

# --- حساب النتائج التلقائية ---
st.markdown("---")
if st.button("⚡ تحليل سريع واستخراج التقرير والحسابات", type="primary"):
    st.success("تم إجراء التحليل الهندسي بنجاح!")
    
    max_panels_in_string = int((inv_max_volt * 0.85) / panel_voc)
    min_panels_in_string = int(inv_min_volt / panel_vmpp) + 1
    rec_total_panels = int(inv_max_pv_w / panel_power)
    
    st.markdown("### 📊 نتائج الحسابات الأولية:")
    r1, r2, r3 = st.columns(3)
    r1.metric("العدد الموصى به للألواح", f"{rec_total_panels} لوح")
    r2.metric("أقصى عدد في السلسلة الواحدة (String)", f"{max_panels_in_string} لوح")
    r3.metric("الحد الأدنى لعمل MPPT", f"{min_panels_in_string} لوح")

# --- خيار إدخال عدد الألواح المخصص ---
st.markdown("---")
st.subheader("⚙️ إدخال عدد الألواح اليدوي المخصص للفحص")
user_target_panels = st.number_input(
    "أدخل العدد المطلوب من الألواح الشمسية للفحص المباشر:",
    min_value=1,
    max_value=100,
    value=12,
    step=1,
    help="أدخل العدد الإجمالي للألواح المراد توزيعها على الإنفيرتر لفحص توافق الجهود والقدرات",
)

if user_target_panels > 0:
    total_system_power = user_target_panels * panel_power
    total_string_voc = user_target_panels * panel_voc
    
    st.info(f"💡 **معاينة النظام بالعدد المخصص ({user_target_panels} لوح):**")
    col_inf1, col_inf2 = st.columns(2)
    col_inf1.write(f"- إجمالي القدرة المتولدة: **{total_system_power} واط**")
    col_inf2.write(f"- إجمالي الجهد الأقصى (Voc متسلسل): **{total_string_voc:.1f} فولت**")
    
    if total_string_voc > inv_max_volt:
        st.error("⚠️ تحذير: الجهد الإجمالي للسلسلة يتجاوز الحد الأقصى المسموح به للإنفيرتر! خطر تلف الجهاز.")
    else:
        st.success("✅ الجهد الكهربائي ضمن الحدود الآمنة للإنفيرتر.")

st.markdown("---")
st.caption("برمجية هندسة الطاقة الشمسية - تم تطويرها لتناسب متطلبات العمل الفني والميداني.")
