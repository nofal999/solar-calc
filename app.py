import os
import streamlit as st
import google.generativeai as genai
from PIL import Image
import io

# إعداد الصفحة وتكوينها
st.set_page_config(
    page_title="حاسبة الأنظمة الشمسية الذكية المتقدمة",
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

# العنوان الرئيسي
st.title("☀️ النظام الذكي لهندسة وتحليل الطاقة الشمسية")
st.markdown("أداة هندسية متكاملة لتحليل توافق الألواح، الإنفيرترات، والبطاريات، واستخراج البيانات تلقائياً عبر الذكاء الاصطناعي (Gemini AI) أو الإدخال اليدوي.")

# --- الشريط الجانبي للإعدادات ---
st.sidebar.header("⚙️ إعدادات النظام والذكاء الاصطناعي")
user_api_key = st.sidebar.text_input("أدخل مفتاح Gemini API:", type="password", value=os.environ.get("GEMINI_API_KEY", ""))

if user_api_key:
    genai.configure(api_key=user_api_key)

st.sidebar.markdown("---")
st.sidebar.subheader("📌 طريقة إدخال البيانات الفنية")
input_mode = st.sidebar.radio(
    "اختر الآلية المفضلة:",
    ["استخراج البيانات من الصور (AI Datasheet)", "إدخال يدوي مباشر"]
)

# القيم الافتراضية
panel_voc, panel_isc, panel_vmpp, panel_impp, panel_power = 41.5, 11.2, 34.5, 10.5, 450
inv_max_pv_w, inv_max_volt, inv_min_volt, inv_max_curr = 5000, 500, 120, 18
battery_volt, battery_ah = 48, 100

# --- قسم استخراج البيانات من الصور باستخدام الذكاء الاصطناعي ---
if input_mode == "استخراج البيانات من الصور (AI Datasheet)":
    st.markdown("### 📸 تحليل الملصقات الفنية (Datasheet) بالذكاء الاصطناعي")
    
    col_img1, col_img2 = st.columns(2)
    
    with col_img1:
        st.subheader("1️⃣ لوح الطاقة الشمسية (Panel)")
        panel_file = st.file_uploader("رفـع صورة ملصق اللوح الشمسي", type=["jpg", "png", "jpeg"], key="panel_img")
        if panel_file:
            image_p = Image.open(panel_file)
            st.image(image_p, caption="صورة اللوح الشمسي المرفوعة", width=250)

    with col_img2:
        st.subheader("2️⃣ إنفيرتر الطاقة الشمسية (Inverter)")
        inv_file = st.file_uploader("رفـع صورة ملصق الإنفيرتر", type=["jpg", "png", "jpeg"], key="inv_img")
        if inv_file:
            image_i = Image.open(inv_file)
            st.image(image_i, caption="صورة الإنفيرتر المرفوعة", width=250)

    # زر معالجة الصور عبر Gemini API
    if st.button("🤖 تحليل الصور واستخراج البيانات الفنية تلقائياً", type="primary"):
        if not user_api_key:
            st.error("⚠️ الرجاء إدخال مفتاح Gemini API في الشريط الجانبي لتفعيل ميزة الذكاء الاصطناعي.")
        elif not panel_file and not inv_file:
            st.warning("⚠️ الرجاء رفع صورة واحدة على الأقل (لوح أو إنفيرتر) للتحليل.")
        else:
            with st.spinner("جاري تحليل الصور واستخراج الخصائص الكهربائية..."):
                try:
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    prompt = "استخرج من هذه الصورة البيانات الفنية بدقة وأرجعها بأرقام واضحة مثل: Voc, Vmpp, Isc, Impp, Power."
                    
                    if panel_file:
                        # إرسال صورة اللوح
                        img_bytes = panel_file.getvalue()
                        response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": img_bytes}])
                        st.success("✅ تم تحليل لوح الطاقة بنجاح:")
                        st.write(response.text)
                        
                    if inv_file:
                        # إرسال صورة الإنفيرتر
                        img_bytes_inv = inv_file.getvalue()
                        response_inv = model.generate_content(["استخرج قدرة الإنفيرتر القصوى، أقصى جهد مدخل Voc، وأقل جهد MPPT.", {"mime_type": "image/jpeg", "data": img_bytes_inv}])
                        st.success("✅ تم تحليل الإنفيرتر بنجاح:")
                        st.write(response_inv.text)
                        
                except Exception as e:
                    st.error(f"حدث خطأ أثناء الاتصال بـ Gemini API: {e}")

    st.markdown("---")
    st.info("💡 يمكنك الاعتماد على القيم الافتراضية أدناه أو تعديلها بناءً على النتائج المستخرجة:")

# --- القسم الثاني: الإدخال اليدوي وتعديل المعلمات ---
st.markdown("### 🎛️ ضبط الخصائص والبيانات الكهربائية")

col_p1, col_p2, col_p3 = st.columns(3)
with col_p1:
    panel_power = st.number_input("قدرة اللوح الواحد (W):", value=panel_power, step=10)
    panel_voc = st.number_input("جهد الدائرة المفتوحة Voc (V):", value=panel_voc, step=0.1)
with col_p2:
    panel_vmpp = st.number_input("جهد العمل Vmpp (V):", value=panel_vmpp, step=0.1)
    panel_isc = st.number_input("تيار القصر Isc (A):", value=panel_isc, step=0.1)
with col_p3:
    panel_impp = st.number_input("تيار العمل Impp (A):", value=panel_impp, step=0.1)

st.markdown("---")
col_i1, col_i2, col_i3, col_i4 = st.columns(4)
with col_i1:
    inv_max_pv_w = st.number_input("القدرة القصوى للإنفيرتر (W):", value=inv_max_pv_w, step=100)
with col_i2:
    inv_max_volt = st.number_input("أقصى جهد مدخل Voc (V):", value=inv_max_volt, step=10.0)
with col_i3:
    inv_min_volt = st.number_input("أقل جهد تشغيل MPPT (V):", value=inv_min_volt, step=5.0)
with col_i4:
    inv_max_curr = st.number_input("أقصى تيار مدخل (A):", value=inv_max_curr, step=0.5)

# --- القسم الثالث: حساب النتائج التلقائية والتوزيع ---
st.markdown("---")
if st.button("⚡ تشغيل التحليل الهندسي واستخراج الحسابات", type="primary"):
    st.success("تم إجراء التحليل الهندسي بنجاح!")
    
    max_panels_in_string = int((inv_max_volt * 0.85) / panel_voc)
    min_panels_in_string = int(inv_min_volt / panel_vmpp) + 1
    rec_total_panels = int(inv_max_pv_w / panel_power)
    
    st.markdown("### 📊 نتائج الحسابات والتوصيات:")
    r1, r2, r3 = st.columns(3)
    r1.metric("العدد الموصى به للألواح", f"{rec_total_panels} لوح")
    r2.metric("أقصى عدد في السلسلة (String)", f"{max_panels_in_string} لوح")
    r3.metric("الحد الأدنى لعمل MPPT", f"{min_panels_in_string} لوح")

# --- القسم الرابع: إدخال عدد الألواح المخصص والفحص المباشر ---
st.markdown("---")
st.subheader("⚙️ فحص توزيع عدد الألواح المخصص")
user_target_panels = st.number_input(
    "أدخل العدد الإجمالي المطلوب للألواح المراد تركيبها:",
    min_value=1,
    max_value=100,
    value=12,
    step=1,
    help="أدخل العدد المرغوب لفحص تطابقه مع حدود الإنفيرتر الكهربائية",
)

if user_target_panels > 0:
    total_system_power = user_target_panels * panel_power
    total_string_voc = user_target_panels * panel_voc
    
    st.info(f"💡 **مراجعة النظام للعدد المحدد ({user_target_panels} لوح):**")
    inf_c1, inf_c2 = st.columns(2)
    inf_c1.write(- f"إجمالي القدرة المتولدة: **{total_system_power} واط**")
    inf_c2.write(- f"إجمالي الجهد (Voc متسلسل افتراضي): **{total_string_voc:.1f} فولت**")
    
    if total_string_voc > inv_max_volt:
        st.error("⚠️ تحذير خطير: الجهد الإجمالي للسلسلة يتجاوز الحد الأقصى المسموح به للإنفيرتر! خطر احتراق الجهاز.")
    else:
        st.success("✅ الجهد الكهربائي للسلسلة ضمن النطاق الآمن للإنفيرتر.")

st.markdown("---")
st.caption("برمجية هندسة الطاقة الشمسية الذكية - الإصدار المتكامل والمحدث.")
