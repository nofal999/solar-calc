import json
import math
import time
from typing import Any, Dict

from PIL import Image
import google.generativeai as genai
import streamlit as st

# 1. إعداد الصفحة وتوجيه النصوص (RTL)
st.set_page_config(
    page_title="حاسبة توافق الألواح والإنفيرتر",
    page_icon="☀️",
    layout="centered",
)

st.markdown(
    """
    <style>
    [data-testid="stMainBlockContainer"], [data-testid="stSidebarContent"] {
        direction: rtl;
        text-align: right;
    }
    div[data-testid="stMarkdownContainer"] p, h1, h2, h3, h4, li {
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
    }
    </style>
""",
    unsafe_allow_html=True,
)

st.title("☀️ حاسبة توافق الألواح والإنفيرتر (النسخة المستقرة)")

# 2. إدخال المفتاح
with st.sidebar:
    st.header("⚙️ الإعدادات")
    api_key = st.text_input("مفتاح Gemini API Key:", type="password")

search_mode = st.radio(
    "طريقة الإدخال:",
    ["📸 صور الملصقات", "✍️ البحث النصي"],
)

uploaded_panel = st.file_uploader("صورة اللوح", type=["jpg", "jpeg", "png"]) if "📸" in search_mode else None
uploaded_inverter = st.file_uploader("صورة الإنفيرتر", type=["jpg", "jpeg", "png"]) if "📸" in search_mode else None

panel_text = st.text_input("اسم اللوح (مثال: Jinko 550W)") if "✍️" in search_mode else ""
inverter_text = st.text_input("اسم الإنفيرتر (مثال: Deye 5kW)") if "✍️" in search_mode else ""


def run_gemini_analysis(contents, key):
    genai.configure(api_key=key.strip())
    
    system_instruction = """
    أنت مهندس طاقة شمسية خبير. استخرج المواصفات وأعد الإجابة بصيغة JSON حصراً وحسب الهيكل التالي بدون أي نصوص إضافية:
    {
      "panel": {"brand": "", "model": "", "pmax": 0, "voc": 0, "vmp": 0, "isc": 0},
      "inverter": {"brand": "", "model": "", "ac_rated_power_w": 0, "v_max": 0, "v_mppt_min": 0, "v_mppt_max": 0, "mppt_count": 1, "strings_per_mppt": 1}
    }
    """

    # الحل الجذري لاختيار النموذج المتاح تلقائياً من حسابك لمنع خطأ 404 نهائياً
    available_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.5-flash", "gemini-pro"]
    selected_model = None

    for m in genai.list_models():
        if "generateContent" in m.supported_generation_methods:
            for target in available_models:
                if target in m.name:
                    selected_model = m.name
                    break
            if selected_model:
                break
    
    if not selected_model:
        selected_model = "models/gemini-1.5-flash"  # كاحتياطي أخير

    model = genai.GenerativeModel(
        model_name=selected_model,
        system_instruction=system_instruction,
        generation_config={"response_mime_type": "application/json", "temperature": 0.1}
    )
    
    response = model.generate_content(contents)
    
    # تنظيف وتفريغ الـ JSON
    text = response.text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text.strip())


if st.button("⚡ تحليل فوري"):
    if not api_key:
        st.error("⚠️ يرجى إدخال مفتاح الـ API.")
    else:
        try:
            with st.spinner("جاري التحليل..."):
                if "📸" in search_mode:
                    if not uploaded_panel or not uploaded_inverter:
                        st.error("يرجى رفع صور اللوح والإنفيرتر.")
                        res = None
                    else:
                        p_img = Image.open(uploaded_panel).convert("RGB")
                        i_img = Image.open(uploaded_inverter).convert("RGB")
                        res = run_gemini_analysis([p_img, i_img, "حلل الصور واستخرج البيانات."], api_key)
                else:
                    if not panel_text or not inverter_text:
                        st.error("يرجى إدخال بيانات اللوح والإنفيرتر.")
                        res = None
                    else:
                        prompt = f"استخرج مواصفات اللوح: {panel_text}، والإنفيرتر: {inverter_text}."
                        res = run_gemini_analysis([prompt], api_key)

            if res:
                st.session_state["result"] = res
                st.success("تم التحليل بنجاح!")
        except Exception as e:
            st.error(f"❌ خطأ تقني: {str(e)}")

if "result" in st.session_state:
    res = st.session_state["result"]
    panel = res.get("panel", {})
    inv = res.get("inverter", {})
    
    st.write("---")
    st.subheader("📊 النتائج المستخرجة:")
    col1, col2 = st.columns(2)
    with col1:
        st.json(panel)
    with col2:
        st.json(inv)
