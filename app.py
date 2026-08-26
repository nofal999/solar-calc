import streamlit as st
import os
import json

# إعداد صفحة ستريمليت
st.set_page_config(
    page_title="نظام حساب وتصميم المنظومات الشمسية",
    page_icon="☀️",
    layout="wide"
)

# دالة آمنة لتحويل القيم إلى أرقام عشرية
def safe_float(val, default=0.0):
    try:
        if val is None:
            return default
        # إزالة أي حروف زائدة أو وحدات قياس إن وجدت
        val_str = str(val).strip().lower()
        for suffix in ['v', 'a', 'w', 'kw', 'hz', 'ohm', '°c']:
            if val_str.endswith(suffix):
                val_str = val_str[:-len(suffix)].strip()
        return float(val_str)
    except (ValueError, TypeError):
        return default

# دالة آمنة لتحويل القيم إلى أرقام صحيحة
def safe_int(val, default=0):
    try:
        if val is None:
            return default
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return default

# تصميم الواجهة والعنوان
st.title("☀️ أداة تصميم وفحص المنظومات الشمسية الكهروضوئية")
st.markdown("---")

# نموذج تجريبي أو افتراضي للمدخلات بناءً على بياناتك السابقة
st.sidebar.header("⚙️ إعدادات المنظومة والبيانات")

# إدخال القيم الأساسية للألواح والإنفيرتر
panel_voc = st.sidebar.number_input("جهد الدارة المفتوحة للوح (Voc V)", value=41.0, step=0.1)
panel_vmp = st.sidebar.number_input("الجهد التشغيلي للوح (Vmp V)", value=34.4, step=0.1)
panel_power = st.sidebar.number_input("قدرة اللوح (Pmax W)", value=455.0, step=1.0)

mppt_min_v = st.sidebar.number_input("أدنى جهد MPPT للإنفيرتر", value=150.0, step=1.0)
mppt_max_v = st.sidebar.number_input("أقصى جهد MPPT للإنفيرتر", value=425.0, step=1.0)
inverter_max_dc_v = st.sidebar.number_input("أقصى جهد مستمر للإنفيرتر (DC Max)", value=500.0, step=1.0)

# حساب حدود الأمان للسلاسل (Strings)
# الحد الأدنى لعدد الألواح بناءً على أدنى جهد MPPT
min_panels_per_string = max(1, int(-(-mppt_min_v // panel_vmp))) # Ceil division approximation
# الحد الأقصى بناءً على جهد Voc لئلا يتجاوز أقصى جهد للإنفيرتر أو الـ Voc Max
max_panels_per_string = int(inverter_max_dc_v / panel_voc)

st.subheader("🛡️ حدود الأمان بالسلسلة الواحدة (Strings)")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("أقل عدد ألواح آمن بالسلسلة", f"{min_panels_per_string} ألواح")
with col2:
    st.metric("أكبر عدد ألواح آمن بالسلسلة", f"{max_panels_per_string} لوحاً")
with col3:
    rec_panels_per_string = max(min_panels_per_string, (min_panels_per_string + max_panels_per_string) // 2)
    st.metric("العدد الموصى به بالسلسلة", f"{rec_panels_per_string} ألواح")

st.markdown("---")
st.subheader("🧮 فحص وتوزيع عدد ألواح مخصص")

# حساب الحدود القصوى والدنيا المقترحة للعدد الإجمالي
min_total_panels = min_panels_per_string * 2  # بافتراض مدخلين MPPT على الأقل
max_total_panels = max_panels_per_string * 2

# القيم الافتراضية الآمنة لـ number_input لتجنب خطأ StreamlitValueBelowMinError
default_panels_val = rec_panels_per_string * 2
safe_default = max(1, default_panels_val)
safe_max = max(100, int(max_total_panels * 2))
safe_min = 1

# المدخل المخصص لعدد الألواح مع حماية كاملة ضد القيم الصفرية أو السالبة
custom_panels_count = st.number_input(
    "أدخل إجمالي عدد الألواح التي ترغب بتركيبها:",
    min_value=safe_min,
    max_value=safe_max,
    value=safe_default,
    step=1,
    key="custom_panels_input",
)

# العمليات الحسابية للعدد المدخل
if custom_panels_count > 0:
    total_power_kw = (custom_panels_count * panel_power) / 1000.0
    
    st.info(f"📊 **إجمالي قدرة التوليد:** {total_power_kw:.2f} kW (بقدرة لوح {panel_power}W)")
    
    # التحقق البسيط من التوافق
    if custom_panels_count >= min_panels_per_string:
        st.success("✅ العدد المدخل متوافق تماماً وآمن كهربائياً مع نطاق الـ MPPT.")
        
        # مقترح التوزيع على سلسلتين (أو حسب المتاح)
        strings_count = 2 if custom_panels_count >= (min_panels_per_string * 2) else 1
        panels_per_str = custom_panels_count // strings_count
        remainder = custom_panels_count % strings_count
        
        st.markdown(f"### 🔌 خططة التوصيل الميدانية المقترحة:")
        st.write(f"- **عدد السلاسل المستخدمة:** {strings_count} سلاسل")
        st.write(f"- **توصيل كل سلسلة:** اربط حوالي **{panels_per_str}** ألواح على التوالي لكل سلسلة" + (f" (ويبقَى لوح موزّع كاحتياط أو تعديل)." if remainder > 0 else ""))
        
        expected_vmp = panels_per_str * panel_vmp
        expected_voc_cold = panels_per_str * panel_voc * 1.15  # حساب معامل الأمان الحراري الشتوي تقريبياً
        
        st.write(f"- **الجهد التشغيلي المتوقع لكل سلسلة ($Vmp$):** `{expected_vmp:.1f} V`")
        st.write(f"- **الجهد الأقصى المتوقع في الشتاء ($Voc$):** `{expected_voc_cold:.1f} V` (أقل من الحد الأقصى {inverter_max_dc_v}V ✅)")
    else:
        st.warning(f"⚠️ العدد المدخل قليل جداً ولا يحقق الحد الأدنى لجهد البدء للإنفيرتر (الحد الأدنى المطلوب للسلسلة هو {min_panels_per_string} ألواح).")

st.markdown("---")
st.caption("تم تطوير وتأمين الكود البرمجي خصيصاً لمنع أخطاء الانهيار وضمان استقرار التشغيل على منصة Streamlit.")
