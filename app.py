import json
import math
import time
from google import genai
from google.genai import types
from PIL import Image
import streamlit as st

# 1. ضبط إعدادات الصفحة
st.set_page_config(
    page_title="حاسبة توافق الألواح والإنفيرتر والبطاريات الشاملة",
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

st.title("☀️ حاسبة توافق الألواح والإنفيرتر والبطاريات")
st.caption(
    "تحليل ذكي متكامل للمواصفات الكهربائية، نوع الجهد، نظام الفازات،"
    " البطاريات الخارجية، وتوزيع السلاسل الميدانية آلياً"
)

# 3. الشريط الجانبي
with st.sidebar:
    st.header("⚙️ الإعدادات والتحكم")
    api_key = st.text_input(
        "مفتاح Gemini API Key:",
        type="password",
        help="احصل عليه مجاناً من Google AI Studio (مطلوب فقط لخيار الصور والبحث النصي)",
    )
    st.info("💡 المفتاح مطلوب فقط لعمليات الذكاء الاصطناعي (الصور أو البحث النصي).")
    
    st.markdown("---")
    st.markdown("### 📌 معلومات الاستخدام")
    st.markdown("يمكنك اختيار طريقة الإدخال المناسبة لك (صور، بحث نصي، أو إدخال يدوي مباشر للقيم).")

# 4. التبديل بين طرق الإدخال الثلاثة
search_mode = st.radio(
    "اختر طريقة إدخال البيانات الحسابية:",
    [
        "📸 1. البحث عن طريق الصور (إرفاق الملصقات)", 
        "✍️ 2. البحث عن طريق اسم الشركة والموديل (نصياً)",
        "🔢 3. الإدخال اليدوي الكامل للقيم الرقمية (بدون ذكاء اصطناعي)"
    ],
    index=0,
)

enable_battery = st.toggle("🔋 تفعيل فحص وتحليل بطارية خارجية مخصصة", value=False)

uploaded_panel = None
uploaded_inverter = None
uploaded_battery = None
panel_text_query = ""
inverter_text_query = ""
battery_text_query = ""

# متغيرات الإدخال اليدوي
manual_data = {}

if "📸" in search_mode:
    cols = st.columns(3 if enable_battery else 2)
    with cols[0]:
        uploaded_panel = st.file_uploader("📸 صورة ملصق اللوح الشمسي", type=["jpg", "jpeg", "png", "webp"])
    with cols[1]:
        uploaded_inverter = st.file_uploader("📸 صورة ملصق الإنفيرتر", type=["jpg", "jpeg", "png", "webp"])
    if enable_battery:
        with cols[2]:
            uploaded_battery = st.file_uploader("📸 صورة ملصق البطارية", type=["jpg", "jpeg", "png", "webp"])

elif "✍️" in search_mode:
    cols = st.columns(3 if enable_battery else 2)
    with cols[0]:
        panel_text_query = st.text_input("☀️ اسم الشركة والموديل للوح الشمسي:", placeholder="مثال: Jinko 640W")
    with cols[1]:
        inverter_text_query = st.text_input("⚡ اسم الشركة والموديل للإنفيرتر:", placeholder="مثال: Deye SUN-5K-SG04LP1-EU")
    if enable_battery:
        with cols[2]:
            battery_text_query = st.text_input("🔋 اسم الشركة والموديل للبطارية:", placeholder="مثال: Pylontech US3000C")

else:
    st.markdown("---")
    st.subheader("🔢 إدخال القيم الفنية يدوياً بالكامل")
    
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.markdown("#### ☀️ خصائص اللوح الشمسي")
        m_pmax = st.number_input("القدرة القصوى للوح (Pmax في Watts)", value=550.0, step=10.0)
        m_voc = st.number_input("جهد الدارة المفتوحة (Voc في Volts)", value=49.6, step=0.1)
        m_vmp = st.number_input("الجهد التشغيلي (Vmp في Volts)", value=41.5, step=0.1)
        m_isc = st.number_input("تيار القصر (Isc في Amps)", value=14.0, step=0.1)
        m_imp = st.number_input("التيار التشغيلي (Imp في Amps)", value=13.2, step=0.1)

    with col_m2:
        st.markdown("#### ⚡ خصائص الإنفيرتر")
        m_ac_power = st.number_input("القدرة الاسمية للإنفيرتر (AC Watts)", value=5000.0, step=500.0)
        m_v_max = st.number_input("أقصى جهد مستمر مدخل (DC Max Volts)", value=550.0, step=10.0)
        m_v_mppt_min = st.number_input("أدنى جهد لنطاق MPPT", value=125.0, step=5.0)
        m_v_mppt_max = st.number_input("أقصى جهد لنطاق MPPT", value=500.0, step=5.0)
        m_mppt_count = st.number_input("عدد مداخل MPPT", value=2, step=1)
        m_max_mppt_curr = st.number_input("أقصى تيار لكل مدخل MPPT (Amps)", value=18.0, step=0.5)
        m_inv_type = st.selectbox("نوع الإنفيرتر", ["Hybrid", "On-Grid", "Off-Grid"])

    if enable_battery:
        st.markdown("#### 🔋 خصائص البطارية المرتبطة / الخارجية")
        col_mb1, col_mb2 = st.columns(2)
        with col_mb1:
            m_b_volts = st.number_input("الجهد الاسمي للبطارية (Volts)", value=48.0, step=2.4)
            m_b_ah = st.number_input("سعة البطارية (Ah)", value=100.0, step=10.0)
        with col_mb2:
            m_b_kwh = st.number_input("الطاقة الإجمالية (kWh)", value=5.12, step=0.5)
            m_b_chem = st.text_input("نوع الكيمياء", value="LiFePO4")

# 5. دالة الاستخراج بالصور
def extract_via_images(panel_img, inverter_img, battery_img, key):
    client = genai.Client(api_key=key)
    contents = [
        compress_image_for_speed(panel_img),
        compress_image_for_speed(inverter_img)
    ]
    if battery_img:
        contents.append(compress_image_for_speed(battery_img))

    prompt = f"""
    أنت مهندس طاقة شمسية خبير. قم بتحليل الصور المرفقة واستخرج البيانات التالية بدقة بصيغة JSON فقط دون أي نصوص إضافية:
    {{
      "panel": {{"brand": "...", "model": "...", "pmax": 0, "voc": 0.0, "vmp": 0.0, "isc": 0.0, "imp": 0.0}},
      "inverter": {{"brand": "...", "model": "...", "type": "...", "phase_type": "Single-Phase", "ac_rated_power_w": 0.0, "v_max": 0.0, "v_mppt_min": 0.0, "v_mppt_max": 0.0, "mppt_count": 1, "strings_per_mppt": 1, "max_mppt_current": 0.0, "battery": {{"supported": true, "nominal_voltage_v": 0.0}}}},
      "external_battery": {{"brand": "...", "model": "...", "capacity_ah": 0.0, "nominal_voltage_v": 0.0}}
    }}
    """
    contents.append(prompt)
    response = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
    )
    return json.loads(response.text)

# 6. دالة الاستخراج النصي
def extract_via_text(p_text, i_text, b_text, key):
    client = genai.Client(api_key=key)
    prompt = f"""
    اللوح: "{p_text}", الإنفيرتر: "{i_text}", البطارية: "{b_text}".
    أعطني البيانات بصيغة JSON بنفس الهيكل السابق بدقة تامة وبدون أي مقدمات.
    """
    response = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
    )
    return json.loads(response.text)

def compress_image_for_speed(pil_img, max_dim=1024):
    img_copy = pil_img.copy()
    img_copy.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    return img_copy

def safe_float(val, default=0.0):
    try: return float(val)
    except: return default

def safe_int(val, default=1):
    try: return int(val)
    except: return default

def format_val(value, unit=""):
    if value in [None, "", 0, 0.0, "غير محدد"]: return "`غير موجود`"
    return f"`{value} {unit}`".strip()

def is_battery_voltage_compatible(v1, v2):
    if v1 <= 0 or v2 <= 0: return True, "غير محدد بدقة."
    if abs(v1 - v2) <= 5.0 or (40 <= v1 <= 60 and 40 <= v2 <= 60):
        return True, f"الجهد متوافق ({v2}V مع نظام {v1}V)."
    return False, f"جهد البطارية ({v2}V) لا يتطابق مع نظام الإنفيرتر ({v1}V)."


# 7. زر التحليل وتنفيذ الحسابات
trigger_label = "🔢 تنفيذ الحسابات والتحليل الفوري" if "🔢" in search_mode else "⚡ تحليل سريع واستخراج التقرير والحسابات"

if st.button(trigger_label):
    res = None
    
    if "🔢" in search_mode:
        # بناء هيكل البيانات يدوياً مباشرة من المدخلات الحالية
        res = {
            "panel": {
                "brand": "إدخال يدوي", "model": "مخصص", "type": "Monocrystalline",
                "pmax": m_pmax, "voc": m_voc, "vmp": m_vmp, "isc": m_isc, "imp": m_imp
            },
            "inverter": {
                "brand": "إدخال يدوي", "model": "مخصص", "type": m_inv_type, "phase_type": "Single-Phase",
                "ac_rated_power_w": m_ac_power, "v_max": m_v_max, "v_mppt_min": m_v_mppt_min, 
                "v_mppt_max": m_v_mppt_max, "mppt_count": int(m_mppt_count), "strings_per_mppt": 1, 
                "max_mppt_current": m_max_mppt_curr,
                "battery": {"supported": m_inv_type != "On-Grid", "nominal_voltage_v": m_b_volts if enable_battery else 48.0}
            },
            "external_battery": {
                "brand": "إدخال يدوي", "model": "مخصص", "chemistry": m_b_chem if enable_battery else "N/A",
                "capacity_ah": m_b_ah if enable_battery else 0, "capacity_kwh": m_b_kwh if enable_battery else 0,
                "nominal_voltage_v": m_b_volts if enable_battery else 0
            }
        }
    else:
        if not api_key:
            st.error("⚠️ يرجى إدخال مفتاح Gemini API Key في القائمة الجانبية.")
        else:
            try:
                if "📸" in search_mode:
                    if not uploaded_panel or not uploaded_inverter:
                        st.error("⚠️ يرجى رفع صور اللوح والإنفيرتر.")
                    else:
                        p_img = Image.open(uploaded_panel)
                        i_img = Image.open(uploaded_inverter)
                        b_img = Image.open(uploaded_battery) if enable_battery and uploaded_battery else None
                        with st.spinner("⚡ جاري قراءة الصور..."):
                            res = extract_via_images(p_img, i_img, b_img, api_key)
                else:
                    if not panel_text_query or not inverter_text_query:
                        st.error("⚠️ يرجى كتابة اسم اللوح والإنفيرتر.")
                    else:
                        with st.spinner("🔍 جاري البحث والتحليل..."):
                            res = extract_via_text(panel_text_query, inverter_text_query, battery_text_query if enable_battery else "", api_key)
            except Exception as e:
                st.error(f"حدث خطأ أثناء الاتصال بالخادم: {e}")

    if res:
        st.session_state["analysis_result"] = res
        st.toast("🚀 تمت الحسابات بنجاح!", icon="⚡")


# 8. عرض النتائج والحسابات الهندسية
if "analysis_result" in st.session_state and st.session_state["analysis_result"]:
    res = st.session_state["analysis_result"]
    panel = res.get("panel", {})
    inv = res.get("inverter", {})
    ext_batt = res.get("external_battery", {})

    pmax = safe_float(panel.get("pmax"))
    voc = safe_float(panel.get("voc"))
    vmp = safe_float(panel.get("vmp"))
    isc = safe_float(panel.get("isc"))
    
    v_max = safe_float(inv.get("v_max"))
    v_mppt_min = safe_float(inv.get("v_mppt_min"))
    v_mppt_max = safe_float(inv.get("v_mppt_max"))
    mppt_count = safe_int(inv.get("mppt_count"), 1)
    strings_per_mppt = safe_int(inv.get("strings_per_mppt"), 1)
    max_mppt_current = safe_float(inv.get("max_mppt_current"))

    isc_safe = isc * 1.25
    system_warnings = []
    system_errors = []

    if max_mppt_current > 0 and isc_safe > max_mppt_current:
        system_warnings.append(f"⚠️ **تحذير تيار:** تيار اللوح المعدل ({round(isc_safe, 2)}A) أعلى من أقصى تيار لمدخل MPPT ({max_mppt_current}A).")

    if system_errors or system_warnings:
        st.markdown("---")
        for err in system_errors: st.error(err)
        for warn in system_warnings: st.warning(warn)

    st.markdown("---")
    st.subheader("📌 ملخص المواصفات الفعالة للمنظومة")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### ☀️ اللوح")
        st.write(f"- **القدرة (Pmax):** {format_val(pmax, 'W')}")
        st.write(f"- **Voc:** {format_val(voc, 'V')} | **Vmp:** {format_val(vmp, 'V')}")
        st.write(f"- **Isc:** {format_val(isc, 'A')}")
    with col2:
        st.markdown("### ⚡ الإنفيرتر")
        st.write(f"- **القدرة:** {format_val(safe_float(inv.get('ac_rated_power_w')), 'W')}")
        st.write(f"- **أقصى جهد DC:** {format_val(v_max, 'V')}")
        st.write(f"- **نطاق MPPT:** {format_val(v_mppt_min, 'V')} إلى {format_val(v_mppt_max, 'V')}")

    if voc > 0 and vmp > 0 and v_max > 0:
        v_mppt_min_safe = v_mppt_min * 1.10
        min_string_safe = math.ceil(v_mppt_min_safe / vmp) if vmp > 0 else 1

        voc_cold_safe = voc * 1.15
        v_max_safe = v_max * 0.95

        max_by_voc = math.floor(v_max_safe / voc_cold_safe) if voc_cold_safe > 0 else 1
        max_by_mppt = math.floor(v_mppt_max / vmp) if vmp > 0 and v_mppt_max > 0 else max_by_voc
        max_string_safe = min(max_by_voc, max_by_mppt) if max_by_mppt > 0 else max_by_voc

        if max_string_safe < min_string_safe: max_string_safe = min_string_safe
        rec_string = math.floor((min_string_safe + max_string_safe) / 2)
        total_strings = mppt_count * strings_per_mppt

        min_total_panels = min_string_safe * total_strings
        rec_total_panels = rec_string * total_strings
        max_total_panels = max_string_safe * total_strings

        st.markdown("---")
        st.subheader("⚡ نتائج التوصيل وتوزيع السلاسل الآمن")
        st.success(f"""
        🛡️ **حدود الأمان بالسلسلة الواحدة:**
        * **أقل عدد ألواح آمن بالسلسلة:** `{min_string_safe}` ألواح.
        * **أكبر عدد ألواح آمن بالسلسلة:** `{max_string_safe}` لوحاً.
        * **العدد الموصى به مثالياً بالسلسلة:** `{rec_string}` ألواح.
        """)

        st.markdown("---")
        st.subheader("🧮 فحص وتوزيع عدد ألواح مخصص")
        custom_panels_count = st.number_input(
            "أدخل إجمالي عدد الألواح التي ترغب بتركيبها:",
            min_value=max(1, int(min_total_panels)),
            max_value=max(10, int(max_total_panels * 3)),
            value=int(rec_total_panels),
            step=1
        )

        if custom_panels_count > 0:
            custom_kw = round((custom_panels_count * pmax) / 1000, 2)
            st.write(f"- **إجمالي قدرة التوليد:** `{custom_kw} kW`")
            num_strings_used = min(total_strings, custom_panels_count)
            panels_per_str = custom_panels_count // num_strings_used
            
            vmp_string = round(panels_per_str * vmp, 1)
            voc_string_cold = round(panels_per_str * voc * 1.15, 1)

            if panels_per_str < min_string_safe:
                st.error(f"❌ **العدد غير آمن:** الجهد التشغيلي `{vmp_string}V` أقل من الحد الأدنى للإنفيرتر.")
            elif panels_per_str > max_string_safe:
                st.error(f"⚠️ **العدد غير آمن:** جهد الشتاء `{voc_string_cold}V` يتجاوز أقصى جهد للإنفيرتر.")
            else:
                st.success("✅ **العدد المدخل متوافق تماماً وآمن كهربائياً.**")
                st.info(f"🔌 **خطة التوصيل المقترحة:** استخدم `{num_strings_used}` سلاسل، وكل سلسلة تضم `{panels_per_str}` ألواح.")
