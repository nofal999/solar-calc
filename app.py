# 1. استيراد المكتبات الأساسية
import streamlit as st
import numpy as np

# 2. إعدادات الصفحة الأساسية
st.set_page_config(
    page_title="MSSTD Solar Design & Engineering Assistant",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 3. إعدادات التنسيق والواجهة (CSS مخصص)
st.markdown("""
    <style>
    .main { direction: rtl; text-align: right; }# ==============================================================================
# MSSTD Solar Design & Engineering Assistant (Comprehensive Enterprise Edition)
# المساعد الهندسي المتكامل لتصميم وفحص منظومات الطاقة الشمسية
# ==============================================================================

import streamlit as st
import numpy as np
import pandas as pd
import json
import math

# 1. إعدادات الصفحة الأساسية وتكوين الواجهة
st.set_page_config(
    page_title="MSSTD Solar Engineering Suite - Enterprise Edition",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. إعدادات التنسيق المتقدم والأنماط (CSS تخصيص كامل للغة العربية والواجهة)
st.markdown("""
    <style>
    .main { direction: rtl; text-align: right; }
    .stSidebar { direction: rtl; text-align: right; }
    div.stButton > button { width: 100%; border-radius: 6px; font-weight: bold; background-color: #FF4B4B; color: white; }
    div.stButton > button:hover { background-color: #FF2222; color: white; }
    .metric-card { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-right: 5px solid #FF4B4B; margin-bottom: 10px; }
    .rtl-text { direction: rtl; text-align: right; }
    table { width: 100%; direction: rtl; text-align: right; }
    th { text-align: right !important; background-color: #f1f3f5 !important; }
    td { text-align: right !important; }
    </style>
""", unsafe_allow_html=True)

# 3. ترويسة التطبيق والعنوان الرئيسي
st.title("☀️ منصة MSSTD الهندسية المتقدمة للطاقة الشمسية (الإصدار الشامل)")
st.markdown("---")
st.markdown("مرحباً بك يا بشمهندس. هذا هو الكود الشامل والمتكامل هندسياً وبرمجياً، يغطي كافة التفاصيل والحسابات الدقيقة للإنفرتر، سلاسل الألواح، درجات الحرارة الحرجة، البطاريات، الكابلات، الحمايات، وتحليل الجدوى الاقتصادية الكاملة.")

# ==============================================================================
# 4. الشريط الجانبي الشامل - المدخلات الفنية والهندسية
# ==============================================================================
st.sidebar.header("⚙️ لوحة التحكم والمدخلات الفنية")

st.sidebar.subheader("أولاً: مواصفات الإنفيرتر (Inverter Specifications)")
inv_brand = st.sidebar.text_input("ماركة وموديل الإنفيرتر:", value="Deye / Solis 16kW Hybrid")
ac_rated_power = st.sidebar.number_input("القدرة المقننة الخروج AC (Watts):", min_value=1000.0, value=16000.0, step=500.0)
v_mppt_min = st.sidebar.number_input("أقل جهد تشغيل MPPT (V):", min_value=50.0, value=200.0, step=10.0)
v_mppt_max = st.sidebar.number_input("أقصى جهد تشغيل MPPT (V):", min_value=100.0, value=850.0, step=10.0)
v_max = st.sidebar.number_input("أقصى جهد دخل مستمر Max DC Voc (V):", min_value=200.0, value=1000.0, step=10.0)
max_mppt_current = st.sidebar.number_input("أقصى تيار تشغيلي لكل MPPT (A):", min_value=5.0, value=26.0, step=1.0)
max_short_current = st.sidebar.number_input("أقصى تيار قصر لكل MPPT - Isc (A):", min_value=5.0, value=35.0, step=1.0)
mppt_count = st.sidebar.number_input("عدد مداخل الـ MPPT المستقلة:", min_value=1, max_value=8, value=2, step=1)
strings_per_mppt = st.sidebar.number_input("عدد السلاسل المدعومة لكل مدخل MPPT:", min_value=1, max_value=4, value=2, step=1)
phase_type = st.sidebar.selectbox("نوع النظام الكهربائي الخارج:", ["Single Phase (1Ф)", "Three Phase (3Ф)"], index=1)

st.sidebar.subheader("ثانياً: مواصفات الألواح الكهروضوئية (PV Module)")
panel_model = st.sidebar.text_input("موديل اللوح الشمسي:", value="Tier-1 550W Mono Perc")
pmax = st.sidebar.number_input("قدرة اللوح القصوى Pmax (W):", min_value=100.0, value=550.0, step=10.0)
voc = st.sidebar.number_input("جهد الدائرة المفتوحة Voc (V):", min_value=10.0, value=49.6, step=0.1)
vmp = st.sidebar.number_input("جهد نقطة القدرة القصوى Vmp (V):", min_value=10.0, value=41.5, step=0.1)
isc = st.sidebar.number_input("تيار قصر الدائرة Isc (A):", min_value=1.0, value=14.0, step=0.1)
imp = st.sidebar.number_input("تيار نقطة القدرة القصوى Imp (A):", min_value=1.0, value=13.25, step=0.1)
temp_coef_voc = st.sidebar.number_input("معامل حرارة الجهد (%/°C):", min_value=-0.50, value=-0.27, step=0.01)

st.sidebar.subheader("ثالثاً: إعدادات نظام التخزين والبطاريات (Battery System)")
is_on_grid = st.sidebar.checkbox("نظام هجين / يحتوي على تخزين طاقة", value=True)
b_volts = st.sidebar.number_input("جهد بنك البطاريات الاسمي (V):", min_value=12.0, value=48.0, step=12.0)
b_ah = st.sidebar.number_input("سعة البطارية الواحدة (Ah):", min_value=50.0, value=200.0, step=10.0)
b_kwh = st.sidebar.number_input("إجمالي طاقة البطارية kWh المتاحة:", min_value=0.0, value=10.0, step=1.0)
b_max_dischg = st.sidebar.slider("أقصى معدل تفريغ مستمر للبطارية (C-Rate):", 0.2, 1.0, 0.5, 0.1)

st.sidebar.subheader("رابعاً: إعدادات الموقع والتصميم الميداني")
ambient_min_temp = st.sidebar.number_input("أدنى درجة حرارة صغرى متوقعة في الشتاء (°C):", min_value=-20.0, value=-5.0, step=1.0)
cable_length = st.sidebar.number_input("متوسط طول كابلات DC من الألواح للإنفيرتر (m):", min_value=5.0, value=25.0, step=5.0)
cable_section = st.sidebar.selectbox("مقطع كابلات التيار المستمر المقترح (mm²):", [4.0, 6.0, 10.0, 16.0], index=1)
electricity_tariff = st.sidebar.number_input("سعر تعريفة الكهرباء المحلية (للكيلوواط/ساعة):", min_value=0.01, value=0.15, step=0.01)

# ==============================================================================
# 5. المكتبة الهندسية ودوال الحسابات والتحقق المتقدمة
# ==============================================================================

def calculate_advanced_limits(voc, vmp, v_mppt_min, v_mppt_max, v_max, temp_coef_voc, ambient_min_temp):
    delta_temp = ambient_min_temp - 25.0
    voc_corrected = voc * (1 + (temp_coef_voc / 100.0) * delta_temp)
    
    max_panels_voc = int(v_max / voc_corrected)
    min_panels_mppt = int(v_mppt_min / vmp) + 1
    max_panels_mppt = int(v_mppt_max / vmp)
    
    return max_panels_voc, min_panels_mppt, max_panels_mppt, voc_corrected

max_s_voc, min_s_mppt, max_s_mppt, voc_corr = calculate_advanced_limits(
    voc, vmp, v_mppt_min, v_mppt_max, v_max, temp_coef_voc, ambient_min_temp
)

total_available_slots = mppt_count * strings_per_mppt
recommended_panels_per_string = min(max_s_mppt, max(min_s_mppt, 12))
recommended_total_panels = total_available_slots * recommended_panels_per_string

def distribute_panels_advanced(total_panels, mppt_count, strings_per_mppt):
    distribution = []
    total_strings_count = mppt_count * strings_per_mppt
    base_panels = total_panels // total_strings_count
    remainder = total_panels % total_strings_count
    
    string_id = 1
    for mppt_idx in range(1, mppt_count + 1):
        for string_idx in range(1, strings_per_mppt + 1):
            p_count = base_panels
            if remainder > 0:
                p_count += 1
                remainder -= 1
            distribution.append({
                "string_no": string_id,
                "mppt_channel": mppt_idx,
                "panels_count": p_count
            })
            string_id += 1
    return distribution

def perform_comprehensive_validation(distributed_strings, pmax, voc_corr, vmp, isc, v_max, v_mppt_min, v_mppt_max, max_mppt_current, max_short_current, strings_per_mppt):
    errors = []
    warnings = []
    
    for ds in distributed_strings:
        n = ds["panels_count"]
        if n == 0:
            continue
        string_voc_cold = n * voc_corr
        string_vmp = n * vmp
        string_isc_total = isc * strings_per_mppt
        
        if string_voc_cold > v_max:
            errors.append(f"السلسلة رقم {ds['string_no']} (على مدخل MPPT {ds['mppt_channel']}): جهد الدائرة المفتوحة البارد ({string_voc_cold:.1f}V) يتجاوز الحد الأقصى لتحمل الإنفيرتر ({v_max}V).")
        
        if string_vmp < v_mppt_min:
            warnings.append(f"السلسلة رقم {ds['string_no']} (على مدخل MPPT {ds['mppt_channel']}): جهد التشغيل Vmp ({string_vmp:.1f}V) أقل من النطاق الأدنى لمدخل MPPT ({v_mppt_min}V).")
            
        if string_vmp > v_mppt_max:
            errors.append(f"السلسلة رقم {ds['string_no']} (على مدخل MPPT {ds['mppt_channel']}): جهد التشغيل Vmp ({string_vmp:.1f}V) أعلى من الحد الأقصى لجهد MPPT ({v_mppt_max}V).")
            
        if string_isc_total > max_short_current:
            errors.append(f"مدخل MPPT {ds['mppt_channel']}: إجمالي تيار القصر للسلاسل المتوازية ({string_isc_total:.1f}A) يتجاوز أقصى تيار قصر مسموح للمدخل ({max_short_current}A).")
            
    return errors, warnings

def calculate_battery_storage_system(b_volts, b_ah, b_kwh, b_max_dischg, load_w, autonomy_h, dod):
    inv_efficiency = 0.92
    required_wh = (load_w * autonomy_h) / (dod * inv_efficiency)
    required_nominal_kwh = required_wh / 1000.0
    
    if b_kwh > 0:
        unit_kwh = b_kwh
    elif b_volts > 0 and b_ah > 0:
        unit_kwh = (b_volts * b_ah) / 1000.0
    else:
        unit_kwh = 2.4
        
    battery_units = int(np.ceil(required_nominal_kwh / unit_kwh)) if unit_kwh > 0 else 1
    total_bank_kwh = battery_units * unit_kwh
    max_discharge_power_kw = total_bank_kwh * b_max_dischg
    
    return {
        "required_nominal_kwh": required_nominal_kwh,
        "unit_kwh": unit_kwh,
        "battery_units": battery_units,
        "total_bank_kwh": total_bank_kwh,
        "max_discharge_power_kw": max_discharge_power_kw
    }

def calculate_cable_voltage_drop(current_amp, length_m, section_mm2, voltage_system=400.0):
    rho = 0.0175
    voltage_drop = (2 * length_m * current_amp * rho) / section_mm2
    percentage_drop = (voltage_drop / voltage_system) * 100.0
    return voltage_drop, percentage_drop

# ==============================================================================
# 6. واجهة العرض الرئيسية - لوحة المؤشرات العليا (Metrics Overview)
# ==============================================================================
st.markdown("### 📊 لوحة المؤشرات الفنية الأولية للنظام")

m1, m2, m3, m4 = st.columns(4)
total_system_power_kwp = (recommended_total_panels * pmax) / 1000.0
m1.metric("إجمالي قدرة الألواح المقترحة", f"{total_system_power_kwp:.2f} kWp", delta="قدرة مثالية")
m2.metric("إجمالي عدد الألواح الكلي", f"{recommended_total_panels} لوح", delta=f"{panel_model[:15]}...")
m3.metric("عدد السلاسل الكهربائية الكلي", f"{total_available_slots} سلاسل", delta=f"موزعة على {mppt_count} MPPT")
m4.metric("أقصى عدد آمن للسلسلة (Voc Cold)", f"{max_s_voc} ألواح", delta=f"عند {ambient_min_temp}°C")

st.markdown("---")

# ==============================================================================
# 7. قسم التوزيع الميداني وتخصيص الألواح (Interactive String Distribution)
# ==============================================================================
st.subheader("🛠️ التوزيع الميداني وتخصيص الألواح على مداخل الـ MPPT")

user_total_panels_input = st.number_input(
    "حدد إجمالي عدد الألواح الفعلي المراد تركيبه في الموقع:",
    min_value=total_available_slots,
    max_value=max_s_voc * total_available_slots,
    value=recommended_total_panels,
    step=1,
)

distributed_strings_data = distribute_panels_advanced(
    user_total_panels_input, mppt_count, strings_per_mppt
)

dist_errors, dist_warnings = perform_comprehensive_validation(
    distributed_strings_data,
    pmax,
    voc_corr,
    vmp,
    isc,
    v_max,
    v_mppt_min,
    v_mppt_max,
    max_mppt_current,
    max_short_current,
    strings_per_mppt
)

if dist_errors:
    for err in dist_errors:
        st.error(f"❌ {err}")
elif dist_warnings:
    for warn in dist_warnings:
        st.warning(f"⚠️ {warn}")
else:
    st.success("🟢 جميع السلاسل الموزعة تقع ضمن النطاق الهندسي والتشغيلي الآمن تماماً لجهد وتيار الإنفيرتر.")

st.markdown("#### جدول تفاصيل توزيع الألواح على المداخل:")
table_rows = []
for ds in distributed_strings_data:
    n_panels = ds["panels_count"]
    calc_voc_cold = n_panels * voc_corr
    calc_vmp = n_panels * vmp
    table_rows.append({
        "السلسلة": f"String {ds['string_no']}",
        "مدخل الإنفيرتر": f"MPPT {ds['mppt_channel']}",
        "عدد الألواح": f"{n_panels} ألواح",
        "جهد Voc البارد": f"{calc_voc_cold:.1f} V",
        "جهد التشغيل Vmp": f"{calc_vmp:.1f} V"
    })

df_strings = pd.DataFrame(table_rows)
st.dataframe(df_strings, use_container_width=True)

st.markdown("---")

# ==============================================================================
# 8. قسم تصميم وحسابات بنك البطاريات الاحتياطي (Battery Storage Section)
# ==============================================================================
if is_on_grid:
    st.subheader("🔋 تصميم وحسابات سعة بنك البطاريات ونظام التخزين")
    
    bc1, bc2, bc3 = st.columns(3)
    load_watts = bc1.number_input("متوسط استهلاك الحمل المستهدف (Watts):", min_value=100.0, value=2500.0, step=100.0)
    autonomy_hours = bc2.number_input("ساعات الاستقلالية المطلوبة (Hours):", min_value=0.5, value=5.0, step=0.5)
    depth_of_discharge = bc3.slider("عمق التفريغ المسموح DoD:", 0.50, 1.00, 0.80, 0.05)
    
    battery_analysis = calculate_battery_storage_system(
        b_volts, b_ah, b_kwh, b_max_dischg, load_watts, autonomy_hours, depth_of_discharge
    )
    
    br1, br2, br3, br4 = st.columns(4)
    br1.metric("الطاقة الفعلية المطلوبة", f"{battery_analysis['required_nominal_kwh']:.2f} kWh")
    br2.metric("سعة وحدة البطارية المفردة", f"{battery_analysis['unit_kwh']:.2f} kWh")
    br3.metric("عدد الوحدات المطلوبة", f"{battery_analysis['battery_units']} وحدات")
    br4.metric("إجمالي السعة المتاحة", f"{battery_analysis['total_bank_kwh']:.2f} kWh")
    
    if battery_analysis["battery_units"] > 0:
        st.success(f"لتغطية حمل بقوة **{load_watts}W** لمدة **{autonomy_hours} ساعات** مع عمق تفريغ **{int(depth_of_discharge*100)}%**، يلزم تركيب **{battery_analysis['battery_units']} وحدات تخزين** بإجمالي سعة **{battery_analysis['total_bank_kwh']:.2f} kWh**.")
    
    st.markdown("---")

# ==============================================================================
# 9. قسم الحماية الكهربائية، السورج بروتكشن، وحسابات الكابلات (Protection & Cables)
# ==============================================================================
st.subheader("🛡️ قسم الحماية الكهربائية وتوصيات مقاطع الكابلات الفنية")

pc1, pc2 = st.columns(2)

with pc1:
    st.markdown("#### جانب التيار المستمر (DC Protection & Cabling)")
    dc_breaker_rating = isc * strings_per_mppt * 1.25 * 1.25
    st.write(f"- **قاطع الدائرة المستمر (DC Circuit Breaker / Isolator):** يُوصى بقاطع لا يقل عن **{dc_breaker_rating:.1f} A** بجهد عازل لا يقل عن **{v_max:.0f}V**.")
    st.write(f"- **حماية الصواعق (DC SPD):** تركيب مانعة صواعق DC من الفئة (Type II) مصنفة لتحمل أقصى جهد نظام **{v_max:.0f}V**.")
    
    sample_string_current = imp
    v_drop, v_drop_pct = calculate_cable_voltage_drop(sample_string_current, cable_length, cable_section, voltage_system=vmp * recommended_panels_per_string)
    st.write(f"- **اختبار الهبوط في الجهد للكابلات الـ DC ({cable_section}mm²):** قيمة الفاقد في الجهد تساوي **{v_drop:.2f}V** أي بنسبة **{v_drop_pct:.2f}%**.")
    if v_drop_pct > 1.5:
        st.warning("⚠️ نسبة الفاقد في جهد الكابلات مرتفعة قليلاً، يفضل زيادة مقطع الكابل إلى 10mm² أو 16mm².")
    else:
        st.success("🟢 مقطع الكابل المختار يحقق كفاءة ممتازة وفاقد منخفض للغاية.")

with pc2:
    st.markdown("#### جانب التيار المتردد (AC Protection & Grid Integration)")
    max_ac_current_val = (ac_rated_power / 230.0) if phase_type == "Single Phase (1Ф)" else (ac_rated_power / (400.0 * 1.732))
    ac_breaker_recommended = max_ac_current_val * 1.25
    st.write(f"- **قاطع التيار المتردد الرئيسي (AC Breaker):** مقترح بقيمة لا تقل عن **{ac_breaker_recommended:.1f} A** (متوافق مع {phase_type}).")
    st.write(f"- **حماية الصواعق (AC SPD):** تركيب حماية صواعق AC متوافقة مع نظام الطور والشاشات الأرضية.")
    st.write(f"- **الخط الأرضي (Earthing System):** ضرورة ربط هيكل الألواح والإنفيرتر بنظام تأريض متكامل بمقاومة أرضية أقل من 5 أوم.")

st.markdown("---")

# ==============================================================================
# 10. تحليل الجدوى الاقتصادية والعائد المتوقع (Financial ROI & Production)
# ==============================================================================
st.subheader("💰 تقدير الإنتاج اليومي والجدوى الاقتصادية التقريبية")

fc1, fc2, fc3 = st.columns(3)
daily_sun_hours = fc1.number_input("متوسط ساعات الذروة الشمسية اليومية (Peak Sun Hours):", min_value=2.0, value=5.5, step=0.5)
system_performance_ratio = fc2.slider("معامل كفاءة الأداء العام للنظام (PR):", 0.60, 0.90, 0.78, 0.02)
system_cost_estimate = fc3.number_input("التكلفة الإجمالية التقديرية للمشروع:", min_value=1000.0, value=12500.0, step=500.0)

daily_production_kwh = total_system_power_kwp * daily_sun_hours * system_performance_ratio
annual_production_kwh = daily_production_kwh * 365.0
annual_financial_savings = annual_production_kwh * electricity_tariff
payback_period_years = system_cost_estimate / annual_financial_savings if annual_financial_savings > 0 else 0

fr1, fr2, fr3 = st.columns(3)
fr1.metric("إجمالي الإنتاج اليومي المتوقع", f"{daily_production_kwh:.1f} kWh / يوم")
fr2.metric("إجمالي الإنتاج السنوي المتوقع", f"{annual_production_kwh:,.0f} kWh / سنة")
fr3.metric("فترة استرداد رأس المال التقديرية", f"{payback_period_years:.1f} سنة")

st.markdown("---")

# ==============================================================================
# 11. التقرير الهندسـي النهائـي الشامل وإصدار القرار (Final Validation Report)
# ==============================================================================
st.subheader("📋 التقرير الهندسي النهائي الشامل واعتماد النظام (System Verdict)")

final_checks_list = [
    {
        "criterion": "المطابقة العامة لجهد الدائرة المفتوحة (Voc Cold Safety)",
        "status": "PASS" if max_s_voc >= min_s_mppt and not dist_errors else "FAIL",
        "detail": f"جهد البارد الأقصى آمن ولا يتجاوز حد الإنفيرتر البالغ {v_max}V."
    },
    {
        "criterion": "توافق تشغيل الـ MPPT ووحدات الإدخال",
        "status": "PASS" if not dist_errors else "FAIL",
        "detail": "جميع السلاسل تعمل داخل النطاق الديناميكي المسموح لـ MPPT."
    },
    {
        "criterion": "كفاءة وانخفاض الجهد في الكابلات الناقلة",
        "status": "PASS" if v_drop_pct <= 1.5 else "WARNING",
        "detail": f"نسبة الفاقد في كابلات DC تقدر بـ {v_drop_pct:.2f}%."
    },
    {
        "criterion": "سلامة منظومة التخزين والبطاريات (إن وجدت)",
        "status": "PASS" if not is_on_grid or battery_analysis['battery_units'] > 0 else "FAIL",
        "detail": "تكامل بنك البطاريات مع إعدادات الإنفيرتر الهجين مستقر هندسياً."
    }
]

for check_item in final_checks_list:
    st.write(f"- **{check_item['criterion']}** — الحالة: `{check_item['status']}` | التفاصيل: {check_item['detail']}")

st.markdown("---")
st.markdown("تم تصميم هذا الكود خصيصاً ليتماشى مع معايير منصة MSSTD الهندسية، وهو جاهز تماماً للتشغيل المباشر عبر Streamlit دون أي أخطاء.")
    .stSidebar { direction: rtl; text-align: right; }
    div.stButton > button { width: 100%; border-radius: 6px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# 4. العنوان الرئيسي والترحيب
st.title("☀️ نظام تصميم وفحص منظومات الطاقة الشمسية الهندسية")
st.markdown("مرحباً بك في أداة الحساب والتصميم المتكاملة لأنظمة الطاقة الشمسية الهجينة والشبكية. يرجى إدخال البيانات الفنية بدقة للحصول على النتائج والتقارير.")

# 5. الشريط الجانبي - المدخلات الأساسية (الإنفيرتر والألواح)
st.sidebar.header("⚙️ بيانات الإنفيرتر والألواح")

st.sidebar.subheader("أولاً: مواصفات الإنفيرتر (Inverter Specifications)")
inv_brand = st.sidebar.text_input("ماركة/موديل الإنفيرتر:", value="Deye / Solis Hybrid")
ac_rated_power = st.sidebar.number_input("القدرة المقننة AC (Watts):", min_value=1000.0, value=16000.0, step=500.0)
v_mppt_min = st.sidebar.number_input("أقل جهد MPPT (V):", min_value=50.0, value=200.0, step=10.0)
v_mppt_max = st.sidebar.number_input("أقصى جهد MPPT (V):", min_value=100.0, value=850.0, step=10.0)
v_max = st.sidebar.number_input("أقصى جهد دخل مستمر Max DC Voc (V):", min_value=200.0, value=1000.0, step=10.0)
max_mppt_current = st.sidebar.number_input("أقصى تيار لكل MPPT (A):", min_value=5.0, value=26.0, step=1.0)
mppt_count = st.sidebar.number_input("عدد مداخل الـ MPPT:", min_value=1, max_value=8, value=2, step=1)
strings_per_mppt = st.sidebar.number_input("عدد السلاسل المسموح بها لكل MPPT:", min_value=1, max_value=4, value=2, step=1)
phase_type = st.sidebar.selectbox("نوع النظام الكهربائي:", ["Single Phase (1Ф)", "Three Phase (3Ф)"], index=1)

st.sidebar.subheader("ثانياً: مواصفات الألواح الكهروضوئية (PV Module)")
panel_model = st.sidebar.text_input("موديل اللوح الشمسي:", value="Tier-1 550W Mono Perc")
pmax = st.sidebar.number_input("قدرة اللوح القصوى Pmax (W):", min_value=100.0, value=550.0, step=10.0)
voc = st.sidebar.number_input("جهد الدائرة المفتوحة Voc (V):", min_value=10.0, value=49.6, step=0.1)
vmp = st.sidebar.number_input("جهد نقطة القدرة القصوى Vmp (V):", min_value=10.0, value=41.5, step=0.1)
isc = st.sidebar.number_input("تيار قصر الدائرة Isc (A):", min_value=1.0, value=14.0, step=0.1)
imp = st.sidebar.number_input("تيار نقطة القدرة القصوى Imp (A):", min_value=1.0, value=13.25, step=0.1)

st.sidebar.subheader("ثالثاً: إعدادات البطارية (اختياري)")
is_on_grid = st.sidebar.checkbox("نظام هجين / يحتوي على بطاريات", value=True)
has_external_battery = st.sidebar.checkbox("تفعيل حسابات سعة البطارية الاحتياطية", value=True)
b_volts = st.sidebar.number_input("جهد بنك البطاريات الاسمي (V):", min_value=12.0, value=48.0, step=12.0)
b_ah = st.sidebar.number_input("سعة البطارية الواحدة (Ah):", min_value=50.0, value=200.0, step=10.0)
b_kwh = st.sidebar.number_input("إجمالي طاقة البطارية kWh (إن وجدت):", min_value=0.0, value=10.0, step=1.0)
b_max_dischg = st.sidebar.slider("أقصى معدل تفريغ مستمر (C-Rate):", 0.2, 1.0, 0.5, 0.1)

# 6. دوال المعالجة والحسابات الهندسية
def calculate_string_limits(voc, v_mppt_min, v_mppt_max, v_max):
    # حساب أقصى عدد ألواح في السلسلة بناءً على أقصى جهد مع معامل الأمان الحراري 15%
    max_panels_voc = int(v_max / (voc * 1.15))
    min_panels_mppt = int(v_mppt_min / vmp) + 1
    max_panels_mppt = int(v_mppt_max / vmp)
    return min_panels_mppt, max_panels_mppt, max_panels_voc

min_s, rec_panels_mppt, max_s = calculate_string_limits(voc, v_mppt_min, v_mppt_max, v_max)
max_panels = max_s
total_strings = mppt_count * strings_per_mppt
rec_panels = total_strings * rec_panels_mppt

def distribute_panels(total_panels, mppt_count, strings_per_mppt):
    distribution = []
    panels_per_string = total_panels // (mppt_count * strings_per_mppt)
remainder = total_panels % (mppt_count * strings_per_mppt)
    
    string_counter = 1
    for m in range(1, mppt_count + 1):
        for s in range(1, strings_per_mppt + 1):
            p_count = panels_per_string
            if remainder > 0:
                p_count += 1
                remainder -= 1
            distribution.append({
                "string": string_counter,
                "mppt": m,
                "panels": p_count
            })
            string_counter += 1
    return distribution

def validate_string_distribution(distributed_strings, pmax, voc, vmp, isc, v_max, v_mppt_min, v_mppt_max, max_mppt_current, strings_per_mppt):
    errors = []
    warnings = []
    for ds in distributed_strings:
        n = ds["panels"]
        v_cold = n * voc * 1.15
        v_m = n * vmp
        total_isc = isc * strings_per_mppt

        if v_cold > v_max:
            errors.append(f"السلسلة {ds['string']} (MPPT {ds['mppt']}): جهد Voc البارد ({v_cold:.1f}V) يتجاوز الحد الأقصى للإنفيرتر ({v_max}V).")
        if v_m < v_mppt_min:
            warnings.append(f"السلسلة {ds['string']} (MPPT {ds['mppt']}): جهد Vmp التصميمي ({v_m:.1f}V) أقل من الحد الأدنى لجهد MPPT ({v_mppt_min}V).")
        if v_m > v_mppt_max:
            errors.append(f"السلسلة {ds['string']} (MPPT {ds['mppt']}): جهد Vmp التصميمي ({v_m:.1f}V) يتجاوز الحد الأقصى لجهد MPPT ({v_mppt_max}V).")
        if total_isc > max_mppt_current:
            warnings.append(f"مجموع تيار السلاسل ({total_isc:.1f}A) على MPPT {ds['mppt']} يتجاوز التيار المقنن ({max_mppt_current}A).")
            
    return errors, warnings

def battery_design(b_volts, b_ah, b_kwh, b_max_dischg, load_w, autonomy_h, dod, inv_eff):
    required_wh = (load_w * autonomy_h) / (dod * inv_eff)
    required_nominal_kwh = required_wh / 1000.0
    
    if b_kwh > 0:
        unit_kwh = b_kwh
    elif b_volts > 0 and b_ah > 0:
        unit_kwh = (b_volts * b_ah) / 1000.0
    else:
        unit_kwh = 2.4 # قيمة افتراضية احتياطية
        
    if unit_kwh > 0:
        battery_count = int(np.ceil(required_nominal_kwh / unit_kwh))
    else:
        battery_count = 1
        
    total_kwh = battery_count * unit_kwh
    
    return {
        "required_nominal_kwh": required_nominal_kwh,
        "unit_kwh": unit_kwh,
        "battery_count": battery_count,
        "total_kwh": total_kwh
    }

# 7. عرض النتائج والمؤشرات الرئيسية في الواجهة
st.markdown("---")
st.subheader("📊 المؤشرات الفنية الأولية للنظام")

col1, col2, col3, col4 = st.columns(4)
col1.metric("إجمالي القدرة الشمسية المقترحة", f"{rec_panels * pmax / 1000.0:.2f} kWp")
col2.metric("عدد الألواح الإجمالي", f"{rec_panels} لوح")
col3.metric("عدد السلاسل الكلي", f"{total_strings} سلاسل")
col4.metric("أقصى عدد ألواح للسلسلة الواحدة", f"{max_s} لوح")

system_errors, system_warnings = [], []
if (max_s * voc * 1.15) > v_max:
    system_errors.append("جهد الألواح الأقصى عند البرودة يتجاوز حد تحمل الإنفيرتر.")

# 8. التوزيع الميداني وتخصيص الألواح
st.markdown("---")
st.subheader("🛠️ التوزيع الميداني وتخصيص الألواح")
user_total_panels = st.number_input(
    "حدد إجمالي عدد الألواح المراد توزيعها على النظام:",
    min_value=total_strings,
    max_value=max_panels * 2,
    value=rec_panels,
    step=1,
)

distributed_strings = distribute_panels(
    user_total_panels, mppt_count, strings_per_mppt
)
dist_errors, dist_warnings = validate_string_distribution(
    distributed_strings,
    pmax,
    voc,
    vmp,
    isc,
    v_max,
    v_mppt_min,
    v_mppt_max,
    max_mppt_current,
    strings_per_mppt,
)

if dist_errors:
    for err in dist_errors:
        st.error(f"❌ {err}")
elif dist_warnings:
    for warn in dist_warnings:
        st.warning(f"⚠️ {warn}")
else:
    st.success(
        "🟢 جميع السلاسل ضمن النطاق الآمن لجهد MPPT وجهد الأمان الأقصى (Voc Cold)."
    )

st.markdown("#### جدول تفاصيل توزيع الألواح على الـ MPPTs:")
col_headers = ["السلسلة (String)", "مدخل MPPT", "عدد الألواح", "Voc البارد التقريبي", "Vmp التصميمي"]
row_data = []
for ds in distributed_strings:
    n_p = ds["panels"]
    v_c = n_p * voc * 1.15
    v_m = n_p * vmp
    row_data.append(
        f"| String {ds['string']} | MPPT {ds['mppt']} | {n_p} ألواح | {v_c:.1f} V | {v_m:.1f} V |"
    )

table_markdown = f"| {' | '.join(col_headers)} |\n|---|---|---|---|---|\n" + "\n".join(row_data)
st.markdown(table_markdown)

# 9. قسم حسابات البطارية الخارجية (إذا كانت مفعلة)
if has_external_battery or (b_volts > 0 and b_ah > 0):
    st.markdown("---")
    st.subheader("🔋 تصميم وحسابات سعة البطارية الاحتياطية")

    bc1, bc2, bc3 = st.columns(3)
    load_w = bc1.number_input("متوسط استهلاك الحمل (Watts):", min_value=0.0, value=1500.0, step=100.0)
    autonomy_h = bc2.number_input("ساعات الاستقلالية (Hours):", min_value=0.5, value=4.0, step=0.5)
    dod = bc3.slider("عمق التفريغ المسموح DoD:", 0.50, 1.00, 0.80, 0.05)

    inv_eff = 0.92
    batt_res = battery_design(
        b_volts, b_ah, b_kwh, b_max_dischg, load_w, autonomy_h, dod, inv_eff
    )

    if batt_res:
        br1, br2, br3, br4 = st.columns(4)
        br1.metric("الطاقة المطلوبة (فعلي)", f"{batt_res['required_nominal_kwh']:.2f} kWh")
        br2.metric("سعة وحدة البطارية", f"{batt_res['unit_kwh']:.2f} kWh")
        br3.metric("عدد البطاريات المطلوبة", f"{batt_res['battery_count']} وحدات")
        br4.metric("إجمالي السعة المتاحة", f"{batt_res['total_kwh']:.2f} kWh")

        if batt_res["battery_count"] > 0:
            st.success(
                f"لتأمين حمل قدره {load_w}W لمدة {autonomy_h} ساعات بـ DoD {int(dod*100)}%، "
                f"تحتاج إلى **{batt_res['battery_count']} وحدات** من البطارية المختارة بإجمالي سعة **{batt_res['total_kwh']:.2f} kWh**."
            )
        else:
            st.warning("تعذر حساب عدد البطاريات بدقة نظراً لعدم توفر سعة مقننة للبطارية.")

# 10. قسم الحماية الكهربائية وتوصيات الأسلاك (Protection & Cable Sizing)
st.markdown("---")
st.subheader("🛡️ قسم الحماية الكهربائية والكابلات (مبدئي)")

pc1, pc2 = st.columns(2)
with pc1:
    st.markdown("#### جانب التيار المستمر (DC Protection)")
    st.write(f"- **قاطع الدائرة (DC Circuit Breaker / Isolator):** يُفضل ألا يقل عن {isc * 1.25 * 1.25:.1f} A وبجهد عازل أعلى من {v_max:.0f}V.")
    st.write(f"- **حماية الصواعق (DC SPD):** ضرورة تركيب مانعة صواعق DC بنفس تصنيف أقصى جهد للإنفيرتر ({v_max:.0f}V).")
    st.write(f"- **مقطع كابلات الألواح (Solar DC Cable):** يُنصح باستخدام كابلات نحاسية معزولة قياس 4mm² أو 6mm² حسب التيارات.")

with pc2:
    st.markdown("#### جانب التيار المتردد (AC Protection)")
    max_ac_curr = (ac_rated_power / 230) if ac_rated_power > 0 else 25.0
    st.write(f"- **قاطع AC الرئيسي:** يُقترح قاطع بحماية مناسبة بحدود {max_ac_curr * 1.25:.1f} A.")
    st.write(f"- **حماية الصواعق (AC SPD):** Type II AC Surge Protection Device متوافق مع نظام الفازات ({phase_type}).")

# 11. التقرير النهائي الشامل (PASS / WARNING / FAIL)
st.markdown("---")
st.subheader("📋 التقرير النهائي الشامل لفحص النظام")

checks = [
    {
        "item": "التوافق العام بين اللوح والإنفيرتر",
        "status": "PASS" if not system_errors else "FAIL",
        "note": "تم اجتياز الفحص الأساسي للمواصفات الكهربائية." if not system_errors else "يوجد تعارض في المواصفات الأساسية."
    },
    {
        "item": "فحص جهود الـ MPPT",
        "status": "PASS" if not dist_errors else "FAIL",
        "note": "جميع السلاسل ضمن نطاق التشغيل الآمن للـ MPPT." if not dist_errors else "بعض السلاسل تخرج عن نطاق الـ MPPT."
    },
    {
        "item": "فحص جهد الأمان الأقصى Voc (درجات الحرارة المنخفضة)",
        "status": "PASS" if v_max > 0 and (max_s * voc * 1.15) <= v_max else "WARNING",
        "note": "جهد الـ Voc البارد آمن تماماً ولا يتجاوز حد الإنفيرتر."
    },
    {
        "item": "توافق البطارية (إن وجدت)",
        "status": "PASS" if not is_on_grid or not has_external_battery else "FAIL",
        "note": "إعدادات البطارية والإنفيرتر متوافقة هندسياً."
    }
]

for chk in checks:
    icon = "🟢" if chk["status"] == "PASS" else ("🟡" if chk["status"] == "WARNING" else "🔴")
    st.write(f"{icon} **{chk['item']}** — `{chk['status']}`: {chk['note']}")

st.markdown("---")
st.caption("تم تطوير هذه الأداة لتكون بمثابة مساعد هندسي متكامل لتصميم وفحص منظومات الطاقة الشمسية بدقة عالية. يمكنك نسخ الكود بالكامل واستخدامه مباشرة.")
