import json
import math
import time
from typing import Any, Dict

import google.generativeai as genai
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
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("☀️ حاسبة توافق الألواح والإنفيرتر والبطاريات")
st.caption("تحليل ذكي متكامل للمواصفات الكهربائية، مع إدراج عوامل الأمان للبطاريات وسلاسل الألواح")

# 3. الشريط الجانبي
with st.sidebar:
    st.header("⚙️ الإعدادات")
    api_key = st.text_input(
        "مفتاح Gemini API Key:",
        type="password",
        help="احصل عليه مجاناً من Google AI Studio",
    )
    st.info("💡 المفتاح مطلوب لعمليات التحليل والاستخراج.")

# 4. التبديل بين طريقتي البحث
search_mode = st.radio(
    "اختر طريقة إدخال البيانات للبحث والتحليل:",
    ["📸 1. البحث عن طريق الصور (إرفاق الملصقات)", "✍️ 2. البحث عن طريق اسم الشركة والموديل (نصياً)"],
    index=0,
)

enable_battery = st.toggle("🔋 تفعيل فحص وتحليل بطارية خارجية مخصصة", value=False)

uploaded_panel = None
uploaded_inverter = None
uploaded_battery = None
panel_text_query = ""
inverter_text_query = ""
battery_text_query = ""

if "📸" in search_mode:
    cols = st.columns(3 if enable_battery else 2)
    with cols[0]:
        uploaded_panel = st.file_uploader("📸 صورة ملصق اللوح الشمسي", type=["jpg", "jpeg", "png"])
    with cols[1]:
        uploaded_inverter = st.file_uploader("📸 صورة ملصق الإنفيرتر", type=["jpg", "jpeg", "png"])
    if enable_battery:
        with cols[2]:
            uploaded_battery = st.file_uploader("📸 صورة ملصق البطارية", type=["jpg", "jpeg", "png"])
else:
    cols = st.columns(3 if enable_battery else 2)
    with cols[0]:
        panel_text_query = st.text_input("☀️ اسم الشركة والموديل للوح الشمسي:", placeholder="مثال: Jinko Solar JKMM550M-72HL4-V")
    with cols[1]:
        inverter_text_query = st.text_input("⚡ اسم الشركة والموديل للإنفيرتر:", placeholder="مثال: Deye SUN-5K-SG04LP1-EU")
    if enable_battery:
        with cols[2]:
            battery_text_query = st.text_input("🔋 اسم الشركة والموديل للبطارية:", placeholder="مثال: Felicity solar LPBF48300")


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 1) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def format_val(value: Any, unit: str = "") -> str:
    if value is None or value == "" or value == 0 or value == 0.0 or value == "غير محدد" or value == "غير معروف":
        return "`غير موجود في البيانات`"
    return f"`{value} {unit}`".strip()


def prepare_image(pil_img: Image.Image, max_dim: int = 1024) -> Image.Image:
    img_copy = pil_img.copy()
    if img_copy.mode != "RGB":
        img_copy = img_copy.convert("RGB")
    img_copy.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    return img_copy


def analyze_battery_safety_and_compatibility(
    inv_voltage: float, inv_max_charge: float, inv_ac_power: float,
    batt_voltage: float, batt_max_charge: float, batt_max_discharge: float,
    batt_ah: float, batt_kwh: float,
) -> Dict[str, Any]:
    results = {
        "voltage_match": False, "voltage_msg": "", "warnings": [], "recommendations": [],
        "safe_charge_current": 0.0, "safe_discharge_current": 0.0,
    }

    if inv_voltage <= 0 or batt_voltage <= 0:
        results["voltage_msg"] = "تعذر الجزم بتوافق الجهد لعدم توفر قراءة دقيقة."
    elif abs(inv_voltage - batt_voltage) <= 5.0 or (40.0 <= inv_voltage <= 60.0 and 40.0 <= batt_voltage <= 60.0):
        results["voltage_match"] = True
        results["voltage_msg"] = f"جهد البطارية ({batt_voltage}V) متوافق تماماً مع نظام الإنفيرتر ({inv_voltage}V)."
    else:
        results["voltage_match"] = False
        results["voltage_msg"] = f"غير متوافق! جهد البطارية ({batt_voltage}V) يختلف عن جهد الإنفيرتر المطلوبة ({inv_voltage}V)."

    SAFETY_FACTOR = 0.80
    if batt_max_charge > 0:
        results["safe_charge_current"] = round(batt_max_charge * SAFETY_FACTOR, 1)
    if batt_max_discharge > 0:
        results["safe_discharge_current"] = round(batt_max_discharge * SAFETY_FACTOR, 1)

    return results


def clean_json_response(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def process_extraction(contents: list, key: str) -> dict:
    genai.configure(api_key=key.strip())
    
    system_instruction = """
    أنت مهندس طاقة شمسية خبير. استخرج المواصفات وأعد الإجابة بصيغة JSON حصراً وحسب الهيكل التالي بدون أي نصوص إضافية:
    {
      "panel": {"brand": "", "model": "", "part_number": "", "type": "", "pmax": 0, "voc": 0, "vmp": 0, "isc": 0, "imp": 0},
      "inverter": {
        "brand": "", "model": "", "part_number": "", "type": "", "phase_type": "", "voltage_architecture": "", "ac_rated_power_w": 0,
        "v_max": 0, "v_mppt_min": 0, "v_mppt_max": 0, "v_start": 0, "mppt_count": 1, "strings_per_mppt": 1, "max_mppt_current": 0,
        "battery": {"supported": true, "nominal_voltage_v": 0, "battery_type": "", "max_charge_current_a": 0},
        "ac_input_output": {"nominal_ac_voltage_v": "", "frequency_hz": "", "max_ac_input_current_a": 0, "max_ac_output_current_a": 0},
        "startup_surge": {"surge_power_va": 0, "duration_seconds": 0}
      },
      "external_battery": {"brand": "", "model": "", "chemistry": "", "capacity_ah": 0, "capacity_kwh": 0, "nominal_voltage_v": 0, "max_charge_current_a": 0, "max_discharge_current_a": 0}
    }
    """

    all_inputs = [system_instruction] + contents
    last_exception = None

    # جلب النماذج المتاحة ديناميكياً من حساب الـ API وتصفيتها لتجنب خطأ 404
    valid_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                valid_models.append(m.name)
    except Exception:
        pass

    # إضافة النماذج الاحتياطية القياسية الموثوقة
    fallback_candidates = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
    for model_name in fallback_candidates:
        if model_name not in valid_models:
            valid_models.append(model_name)

    for m_name in valid_models:
        try:
            clean_name = m_name.replace("models/", "")
            model = genai.GenerativeModel(clean_name)
            response = model.generate_content(
                all_inputs,
                generation_config={"response_mime_type": "application/json", "temperature": 0.1}
            )
            cleaned_json = clean_json_response(response.text)
            return json.loads(cleaned_json)
        except Exception as e:
            last_exception = e
            continue

    raise Exception(f"تعذر استخراج البيانات من API: {str(last_exception)}")


# 5. زر التحليل
if st.button("⚡ تحليل سريع واستخرج التقرير والحسابات"):
    if not api_key:
        st.error("⚠️ يرجى إدخال مفتاح Gemini API Key في القائمة الجانبية.")
    else:
        res = None
        start_t = time.time()

        if "📸" in search_mode:
            if not uploaded_panel or not uploaded_inverter:
                st.error("⚠️ يرجى تحميل صورة اللوح والإنفيرتر معاً لمتابعة الحسابات.")
            else:
                try:
                    p_img = Image.open(uploaded_panel)
                    i_img = Image.open(uploaded_inverter)
                    b_img = Image.open(uploaded_battery) if enable_battery and uploaded_battery else None
                    with st.spinner("⚡ جاري قراءة الملصقات وتحليل الصور تلقائياً..."):
                        contents = [prepare_image(p_img), prepare_image(i_img)]
                        if b_img:
                            contents.append(prepare_image(b_img))
                        contents.append("قم بتحليل الصور المرفقة واستخراج المواصفات الكهربائية الكاملة.")
                        res = process_extraction(contents, api_key)
                except Exception as e:
                    st.error(f"❌ {e}")
        else:
            if not panel_text_query or not inverter_text_query:
                st.error("⚠️ يرجى كتابة اسم الشركة والموديل للوح والإنفيرتر معاً.")
            else:
                try:
                    with st.spinner("🔍 جاري البحث عن مواصفات الكتالوج والتحليل..."):
                        b_prompt = f'والبطارية الخارجية: "{battery_text_query}"' if enable_battery and battery_text_query else ""
                        prompt = f'استخرج مواصفات اللوح: "{panel_text_query}"، والإنفيرتر: "{inverter_text_query}" {b_prompt}.'
                        res = process_extraction([prompt], api_key)
                except Exception as e:
                    st.error(f"❌ {e}")

        if res:
            st.session_state["analysis_result"] = res
            st.toast(f"🚀 تم التحليل بنجاح في {round(time.time() - start_t, 2)} ثوانٍ!", icon="⚡")

# 6. عرض النتائج
if "analysis_result" in st.session_state and st.session_state["analysis_result"]:
    res = st.session_state["analysis_result"]
    panel = res.get("panel", {})
    inv = res.get("inverter", {})
    
    st.success("✅ تم استلام وتحليل البيانات بنجاح! راجع التفاصيل أدناه.")
    st.write(panel)
    st.write(inv)
