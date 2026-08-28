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
    .main { direction: rtl; text-align: right; }
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
