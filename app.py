import json
import math
import time
from google import genai
from google.genai import types
from PIL import Image
import streamlit as st

# 1. ضبط إعدادات الصفحة
st.set_page_config(
    page_title="حاسبة توافق الألواح والإنفيرتر المتقدمة",
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

    .stButton>button {
        width: 100%;
        background-color: #0284c7;
        color: white;
        border-radius: 8px;
        height: 3em;
        font-weight: bold;
        margin-top: 10px;
        transition: background-color 0.3s ease;
    }
    
    .stButton>button:hover {
        background-color: #0369a1;
    }

    .stAlert {
        direction: rtl;
        text-align: right;
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("☀️ حاسبة توافق الألواح والإنفيرتر المتقدمة")
st.caption("تحكم هندسي ديناميكي بمداخل الـ MPPT غير المحدودة، إيقاف العناصر غير المستخدمة، وتحليل السلاسل")

# 3. الشريط الجانبي
with st.sidebar:
    st.header("⚙️ الإعدادات والتحكم")
    api_key = st.text_input(
        "مفتاح Gemini API Key:",
        type="password",
        help="احصل عليه مجاناً من Google AI Studio (مطلوب فقط لخيار الصور والبحث النصي)",
    )
    st.info("💡 المفتاح مطلوب فقط لعمليات الذكاء الاصطناعي (الصور أو البحث النصي).")

# 4. خيارات تجاوز العناصر غير الموجودة
st.markdown("### 🎛️ خيارات تفعيل / إيقاف الأقسام (تجاوز العناصر غير الموجودة)")
col_opt1, col_opt2, col_opt3 = st.columns(3)
with col_opt1:
    enable_panel = st.checkbox("☀️ تفعيل اللوح الشمسي", value=True)
with col_opt2:
    enable_inverter = st.checkbox("⚡ تفعيل الإنفيرتر", value=True)
with col_opt3:
    enable_battery = st.checkbox("🔋 تفعيل البطارية الخارجية", value=False)

# 5. التبديل بين طرق الإدخال
search_mode = st.radio(
    "اختر طريقة إدخال البيانات للبحث والتحليل:",
    [
        "🔢 1. الإدخال اليدوي الكامل والتحكم الديناميكي بمداخل MPPT",
        "📸 2. البحث عن طريق الصور (إرفاق الملصقات)", 
        "✍️ 3. البحث عن طريق اسم الشركة والموديل (نصياً)"
    ],
    index=0,
)

uploaded_panel = None
uploaded_inverter = None
uploaded_battery = None
panel_text_query = ""
inverter_text_query = ""
battery_text_query = ""

# متغيرات الإدخال اليدوي
m_pmax, m_voc, m_vmp, m_isc, m_imp = 550.0, 49.6, 41.5, 14.0, 13.2
m_ac_power, m_v_max, m_v_mppt_min, m_v_mppt_max = 5000.0, 550.0, 125.0, 500.0
m_inv_type = "Hybrid"
m_phase_type = "Single-Phase"
m_b_volts, m_b_ah, m_b_kwh = 48.0, 100.0, 5.12
m_b_chem = "LiFePO4"

mppt_configs = []

if "🔢" in search_mode:
    st.markdown("---")
    if enable_panel:
        st.subheader("☀️ خصائص اللوح الشمسي")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            m_pmax = st.number_input("القدرة القصوى للوح (Pmax في Watts)", value=550.0, step=10.0)
            m_voc = st.number_input("جهد الدارة المفتوحة (Voc في Volts)", value=49.6, step=0.1)
            m_vmp = st.number_input("الجهد التشغيلي (Vmp في Volts)", value=41.5, step=0.1)
        with col_m2:
            m_isc = st.number_input("تيار القصر (Isc في Amps)", value=14.0, step=0.1)
            m_imp = st.number_input("التيار التشغيلي (Imp في Amps)", value=13.2, step=0.1)

    if enable_inverter:
        st.markdown("---")
        st.subheader("⚡ خصائص الإنفيرتر والتحكم الديناميكي بمداخل MPPT")
        col_i1, col_i2 = st.columns(2)
        with col_i1:
            m_ac_power = st.number_input("القدرة الاسمية للإنفيرتر (AC Watts)", value=5000.0, step=500.0)
            m_v_max = st.number_input("أقصى جهد مستمر مدخل (DC Max Volts)", value=550.0, step=10.0)
            m_v_mppt_min = st.number_input("أدنى جهد لنطاق MPPT", value=125.0, step=5.0)
            m_v_mppt_max = st.number_input("أقصى جهد لنطاق MPPT", value=500.0, step=5.0)
        with col_i2:
            m_inv_type = st.selectbox("نوع الإنفيرتر", ["Hybrid", "On-Grid", "Off-Grid"])
            m_phase_type = st.selectbox("نظام الفازات", ["Single-Phase", "Three-Phase"])
            m_mppt_count = st.number_input("عدد مداخل MPPT الكلي", min_value=1, max_value=10, value=2, step=1, help="حدد كم عدد مداخل الـ MPPT الموجودة في الإنفيرتر")

        st.markdown("#### 🎛️ تخصيص السلاسل (Strings) والتيار لكل مدخل MPPT على حدة:")
        for i in range(int(m_mppt_count)):
            st.markdown(f"**🔹 إعدادات مدخل MPPT رقم ({i+1}):**")
            c_s1, c_s2 = st.columns(2)
            with c_s1:
                strings_in_this_mppt = st.number_input(f"عدد السلاسل الموصولة بـ MPPT {i+1}", min_value=1, max_value=6, value=1, key=f"str_{i}")
            with c_s2:
                max_curr_this_mppt = st.number_input(f"أقصى تيار مسموح لـ MPPT {i+1} (Amps)", min_value=5.0, max_value=80.0, value=18.0, step=0.5, key=f"curr_{i}")
            mppt_configs.append({"mppt_id": i+1, "strings": strings_in_this_mppt, "max_current": max_curr_this_mppt})

    if enable_battery:
        st.markdown("---")
        st.subheader("🔋 خصائص البطارية الخارجية")
        col_mb1, col_mb2 = st.columns(2)
        with col_mb1:
            m_b_volts = st.number_input("الجهد الاسمي للبطارية (Volts)", value=48.0, step=2.4)
            m_b_ah = st.number_input("سعة البطارية (Ah)", value=100.0, step=10.0)
        with col_mb2:
            m_b_kwh = st.number_input("الطاقة الإجمالية (kWh)", value=5.12, step=0.5)
            m_b_chem = st.text_input("نوع الكيمياء", value="LiFePO4")

elif "📸" in search_mode:
    cols = st.columns(3)
    with cols[0]:
        if enable_panel: uploaded_panel = st.file_uploader("📸 صورة ملصق اللوح الشمسي", type=["jpg", "jpeg", "png", "webp"])
    with cols[1]:
        if enable_inverter: uploaded_inverter = st.file_uploader("📸 صورة ملصق الإنفيرتر", type=["jpg", "jpeg", "png", "webp"])
    with cols[2]:
        if enable_battery: uploaded_battery = st.file_uploader("📸 صورة ملصق البطارية", type=["jpg", "jpeg", "png", "webp"])

else:
    cols = st.columns(3)
    with cols[0]:
        if enable_panel: panel_text_query = st.text_input("☀️ اسم وموديل اللوح الشمسي:")
    with cols[1]:
        if enable_inverter: inverter_text_query = st.text_input("⚡ اسم وموديل الإنفيرتر:")
    with cols[2]:
        if enable_battery: battery_text_query = st.text_input("🔋 اسم وموديل البطارية:")


# 6. دوال مساعدة
def safe_float(val, default=0.0):
    try: return float(val)
    except: return default

def safe_int(val, default=1):
    try: return int(val)
    except: return default

JSON_STRUCTURE = """
{
  "panel": {"brand": "...", "model": "...", "pmax": 0, "voc": 0.0, "vmp": 0.0, "isc": 0.0, "imp": 0.0},
  "inverter": {
    "brand": "...", "model": "...", "type": "...", "ac_rated_power_w": 0.0, "v_max": 0.0, "v_mppt_min": 0.0, "v_mppt_max": 0.0, "mppt_count": 2
  }
}
"""

def extract_via_ai(p_img, i_img, p_txt, i_txt, key):
    client = genai.Client(api_key=key)
    contents = []
    if p_img: contents.append(p_img)
    if i_img: contents.append(i_img)
    prompt = f"استخرج المواصفات بصيغة JSON فقط حسب هذا الهيكل:\n{JSON_STRUCTURE}\nمعلومات نصية إن وجدت: لوح '{p_txt}', إنفيرتر '{i_txt}'"
    contents.append(prompt)
    
    # محاولة استخدام النموذج مع التعامل التلقائي مع أخطاء الضغط (503) وتجربة موديل بديل إذا لزم الأمر
    models_to_try = ["models/gemini-3.6-flash", "models/gemini-2.5-flash"]
    last_exception = None
    
    for mdl in models_to_try:
        try:
            response = client.models.generate_content(
                model=mdl, contents=contents,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
            )
            return json.loads(response.text)
        except Exception as e:
            last_exception = e
            continue
            
    raise last_exception


# 7. زر تنفيذ الحسابات
trigger_label = "🔢 تنفيذ الحسابات والتحليل الفوري" if "🔢" in search_mode else "⚡ تحليل السلاسل واستخراج التقرير"

if st.button(trigger_label):
    res = None
    if "🔢" in search_mode:
        res = {
            "panel": {"pmax": m_pmax if enable_panel else 0, "voc": m_voc if enable_panel else 0, "vmp": m_vmp if enable_panel else 0, "isc": m_isc if enable_panel else 0},
            "inverter": {
                "ac_rated_power_w": m_ac_power if enable_inverter else 0,
                "v_max": m_v_max if enable_inverter else 0,
                "v_mppt_min": m_v_mppt_min if enable_inverter else 0,
                "v_mppt_max": m_v_mppt_max if enable_inverter else 0,
                "mppt_count": int(m_mppt_count) if enable_inverter else 1,
                "mppt_configs": mppt_configs if mppt_configs else [{"mppt_id": 1, "strings": 1, "max_current": 18.0}]
            }
        }
    else:
        if not api_key:
            st.error("⚠️ يرجى إدخال مفتاح Gemini API Key في القائمة الجانبية.")
        else:
            try:
                p_i = Image.open(uploaded_panel) if uploaded_panel else None
                i_i = Image.open(uploaded_inverter) if uploaded_inverter else None
                res = extract_via_ai(p_i, i_i, panel_text_query, inverter_text_query, api_key)
                if "inverter" in res and "mppt_configs" not in res["inverter"]:
                    mc = res["inverter"].get("mppt_count", 2)
                    res["inverter"]["mppt_configs"] = [{"mppt_id": i+1, "strings": 1, "max_current": 18.0} for i in range(mc)]
            except Exception as e:
                st.error(f"حدث خطأ أثناء الاتصال بالخادم (قد يكون ضغط مؤقت): {e}")

    if res:
        st.session_state["analysis_result"] = res
        st.toast("🚀 تمت الحسابات بنجاح!", icon="⚡")


# 8. عرض النتائج والتحليل الفردي لكل MPPT
if "analysis_result" in st.session_state and st.session_state["analysis_result"]:
    res = st.session_state["analysis_result"]
    panel = res.get("panel", {})
    inv = res.get("inverter", {})

    pmax = safe_float(panel.get("pmax"))
    voc = safe_float(panel.get("voc"))
    vmp = safe_float(panel.get("vmp"))
    isc = safe_float(panel.get("isc"))

    v_max = safe_float(inv.get("v_max"))
    v_mppt_min = safe_float(inv.get("v_mppt_min"))
    v_mppt_max = safe_float(inv.get("v_mppt_max"))
    mppt_configs_res = inv.get("mppt_configs", [{"mppt_id": 1, "strings": 1, "max_current": 18.0}])

    st.markdown("---")
    st.subheader("📌 نتائج تحليل الجهد والسلاسل المستقلة لكل MPPT")

    if enable_panel and voc > 0 and vmp > 0 and enable_inverter and v_max > 0:
        v_mppt_min_safe = v_mppt_min * 1.10
        min_string_safe = math.ceil(v_mppt_min_safe / vmp) if vmp > 0 else 1

        voc_cold_safe = voc * 1.15
        v_max_safe = v_max * 0.95

        max_by_voc = math.floor(v_max_safe / voc_cold_safe) if voc_cold_safe > 0 else 1
        max_by_mppt = math.floor(v_mppt_max / vmp) if vmp > 0 and v_mppt_max > 0 else max_by_voc
        max_string_safe = min(max_by_voc, max_by_mppt) if max_by_mppt > 0 else max_by_voc
        if max_string_safe < min_string_safe: max_string_safe = min_string_safe
        rec_string = math.floor((min_string_safe + max_string_safe) / 2)

        st.success(f"""
        🛡️ **الحدود الآمنة للسلسلة الواحدة:**
        * الحد الأدنى: `{min_string_safe}` ألواح | الحد الأقصى: `{max_string_safe}` ألواح | الموصى به: `{rec_string}` ألواح.
        """)

        st.markdown("### 🎛️ التوزيع التفصيلي لكل مدخل MPPT على حدة:")
        total_global_panels = 0

        for cfg in mppt_configs_res:
            m_id = cfg.get("mppt_id", 1)
            str_count = cfg.get("strings", 1)
            m_curr = cfg.get("max_current", 18.0)

            st.markdown(f"**🔹 مدخل MPPT رقم ({m_id}):** يحتوي على `{str_count}` سلاسل | أقصى تيار مسموح: `{m_curr}A`")
            
            isc_safe = isc * 1.25
            if isc_safe > m_curr:
                st.warning(f"⚠️ تنبيه تيار في MPPT {m_id}: تيار اللوح المعدل ({isc_safe}A) أعلى من تيار المدخل المسموح ({m_curr}A).")

            panels_in_this_string = st.number_input(
                f"عدد الألواح لكل سلسلة في مدخل MPPT {m_id}",
                min_value=int(min_string_safe),
                max_value=int(max_string_safe),
                value=int(rec_string),
                step=1,
                key=f"panels_mppt_{m_id}"
            )

            branch_panels = panels_in_this_string * str_count
            total_global_panels += branch_panels
            
            vmp_str = round(panels_in_this_string * vmp, 1)
            voc_str = round(panels_in_this_string * voc * 1.15, 1)

            if panels_in_this_string < min_string_safe or panels_in_this_string > max_string_safe:
                st.error(f"❌ MPPT {m_id} غير آمن كهربائياً (الجهد التشغيلي: {vmp_str}V).")
            else:
                st.info(f"✅ مدخل MPPT {m_id} مستقر وآمن. إجمالي الألواح عليه: `{branch_panels}` لوحاً (جهد التشغيل: `{vmp_str}V`).")
            st.markdown("---")

        total_kw = round((total_global_panels * pmax) / 1000, 2)
        st.metric("☀️ إجمالي قدرة المنظومة الكلية للألواح", f"{total_kw} kW", f"{total_global_panels} لوحاً شمسياً")

    else:
        st.warning("⚠️ يرجى التأكد من تفعيل وإدخال بيانات اللوح الشمسي والإنفيرتر لإجراء الحسابات الدقيقة.")
