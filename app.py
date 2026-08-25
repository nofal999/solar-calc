import json
import math
import time
from google import genai
from google.genai import types
from PIL import Image
import streamlit as st

# ضبط إعدادات الصفحة
st.set_page_config(
    page_title="حاسبة توافق الألواح والإنفيرتر الشاملة",
    page_icon="☀️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    [data-testid="stMainBlockContainer"], 
    [data-testid="stSidebarContent"] {
        direction: rtl;
        text-align: right;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
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

st.title("☀️ حاسبة توافق الألواح والإنفيرتر الفائقة")

with st.sidebar:
    st.header("⚙️ الإعدادات")
    api_key = st.text_input(
        "مفتاح Gemini API Key:",
        type="password",
    )

uploaded_panel = st.file_uploader(
    "📸 صورة ملصق اللوح الشمسي", type=["jpg", "jpeg", "png"]
)
uploaded_inverter = st.file_uploader(
    "📸 صورة ملصق الإنفيرتر", type=["jpg", "jpeg", "png"]
)


def safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=1):
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def format_val(value, unit=""):
    if (
        value is None
        or value == ""
        or value == 0
        or value == 0.0
        or value == "غير محدد"
    ):
        return "`غير موجود على الملصق`"
    return f"`{value} {unit}`".strip()


# ⚡ 1. دالة لضغط الصور لتسريع السرعة بشكل ملحوظ عند الرفع
def compress_image_for_speed(pil_img, max_dim=1024):
    """تصغير أبعاد الصورة وتقليل حجمها لسرعة الإرسال دون التأثير على وضوح النص"""
    img_copy = pil_img.copy()
    img_copy.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    return img_copy


# ⚡ 2. دالة الاستخراج السريعة جداً
def extract_data_via_gemini_fast(panel_img, inverter_img, key):
    client = genai.Client(api_key=key)

    # ضغط الصور في الذاكرة لتسريع رفع البيانات للـ API
    p_img_small = compress_image_for_speed(panel_img)
    i_img_small = compress_image_for_speed(inverter_img)

    prompt = """
    أنت مهندس طاقة شمسية خبير. قم بتحليل الصورتين المرفقتين واستخرج البيانات التالية بأسلوب JSON فقط بدون أي نصوص أو مقدمات:

    {
      "panel": {
        "brand": "الشركة",
        "model": "الموديل",
        "part_number": "الرقم التسلسلي",
        "type": "النوع",
        "pmax": 0,
        "voc": 0.0,
        "vmp": 0.0,
        "isc": 0.0,
        "imp": 0.0
      },
      "inverter": {
        "brand": "الشركة",
        "model": "الموديل",
        "part_number": "الرقم التسلسلي",
        "type": "النوع",
        "phase_type": "عدد الفازات",
        "voltage_architecture": "نوع الجهد",
        "ac_rated_power_w": 0.0,
        "v_max": 0.0,
        "v_mppt_min": 0.0,
        "v_mppt_max": 0.0,
        "v_start": 0.0,
        "mppt_count": 1,
        "strings_per_mppt": 1,
        "max_mppt_current": 0.0,
        "battery": {
          "supported": true,
          "nominal_voltage_v": 0.0,
          "battery_type": "النوع",
          "max_charge_current_a": 0.0
        },
        "ac_input_output": {
          "nominal_ac_voltage_v": "جهد AC",
          "frequency_hz": "التردد",
          "max_ac_input_current_a": 0.0,
          "max_ac_output_current_a": 0.0
        },
        "startup_surge": {
          "surge_power_va": 0.0,
          "duration_seconds": 0.0
        }
      }
    }
    تنبيه: أعد أرقاماً فقط للقيم الرقمية دون وحدات، واستخدم 0 للقيم المفقودة.
    """

    # استخدام النماذج السريعة فقط بالترتيب (Fast Models Priority)
    fast_models = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-3.5-flash"]

    for model_name in fast_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[p_img_small, i_img_small, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,  # درجة سرعة وتحديد أعلى
                ),
            )
            return json.loads(response.text)
        except Exception:
            continue

    raise Exception("عذراً، متعذر الاتصال بالنموذج السريع حالياً.")


# زر التحليل
if st.button("⚡ تحليل سريع واستخراج التقرير"):
    if not api_key:
        st.error("⚠️ يرجى إدخال مفتاح Gemini API Key.")
    elif not uploaded_panel or not uploaded_inverter:
        st.error("⚠️ يرجى تحميل الصورتين معاً.")
    else:
        try:
            p_img = Image.open(uploaded_panel)
            i_img = Image.open(uploaded_inverter)

            with st.spinner("⚡ جاري الضغط والتحليل السريع جداً..."):
                start_time = time.time()
                res = extract_data_via_gemini_fast(p_img, i_img, api_key)
                st.session_state["analysis_result"] = res
                st.toast(
                    f"⚡ تم التحليل في {round(time.time() - start_time, 2)} ثوانٍ!",
                    icon="🚀",
                )
        except Exception as e:
            st.error(f"حدث خطأ: {e}")

# عرض النتائج... (نفس الجزء السابق للتخزين في session_state)
if "analysis_result" in st.session_state and st.session_state["analysis_result"]:
    res = st.session_state["analysis_result"]
    # ... باقي الكود للعرض كالمعتاد
