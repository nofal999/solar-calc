import json
import math
import time
from typing import Any, Dict

from PIL import Image
import requests
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
st.caption("نسخة الويب المستقرة (الأتصال المباشر الآمن)")

# 3. الشريط الجانبي
with st.sidebar:
    st.header("⚙️ الإعدادات")
    api_key = st.text_input(
        "مفتاح Gemini API Key:",
        type="password",
        help="احصل عليه مجاناً من Google AI Studio",
    )
    st.info("💡 المفتاح مطلوب لعمليات التحليل والاستخراج.")

# 4. طرق البحث
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


def clean_json_response(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def process_extraction_via_rest(contents: list, key: str) -> dict:
    import base64
    import io

    # تنظيف المفتاح من أي مسافات مخفية قد تفسد الرابط
    clean_key = key.strip()
    
    # بناء الرابط بشكل آمن ومباشر
    url = f"[https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key=](https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key=){clean_key}"
    
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

    parts = [{"text": system_instruction}]
    
    for item in contents:
        if isinstance(item, Image.Image):
            buffered = io.BytesIO()
            item.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": img_str
                }
            })
        else:
            parts.append({"text": str(item)})

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1
        }
    }

    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
    except requests.exceptions.RequestException as e:
        raise Exception(f"فشل الاتصال بالإنترنت أو خطأ في الرابط: {str(e)}")
    
    if response.status_code != 200:
        error_text = response.text
        if "429" in error_text:
            raise Exception("تم استنفاد الحد الأقصى للطلبات المجانية (Quota Exceeded). يرجى الانتظار قليلاً أو إنشاء مفتاح جديد من مشروع جديد.")
        elif "404" in error_text:
            raise Exception("خطأ 404: النموذج غير متاح أو الرابط غير صحيح.")
        else:
            raise Exception(f"خطأ API ({response.status_code}): {error_text}")

    res_json = response.json()
    try:
        raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
        cleaned_json = clean_json_response(raw_text)
        return json.loads(cleaned_json)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise Exception(f"فشل في تحليل الاستجابة: {str(e)}")


# 5. زر التحليل الفوري
if st.button("⚡ تحليل فائق السرعة واستخراج التقرير"):
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
                    with st.spinner("⚡ جاري الاتصال ومعالجة البيانات..."):
                        contents = [prepare_image(p_img), prepare_image(i_img)]
                        if b_img:
                            contents.append(prepare_image(b_img))
                        contents.append("قم بتحليل الصور المرفقة واستخراج المواصفات الكهربائية الكاملة.")
                        res = process_extraction_via_rest(contents, api_key)
                except Exception as e:
                    st.error(f"❌ {e}")
        else:
            if not panel_text_query or not inverter_text_query:
                st.error("⚠️ يرجى كتابة اسم الشركة والموديل للوح والإنفيرتر معاً.")
            else:
                try:
                    with st.spinner("🔍 جاري جلب المواصفات والتحليل الفوري..."):
                        b_prompt = f'والبطارية الخارجية: "{battery_text_query}"' if enable_battery and battery_text_query else ""
                        prompt = f'استخرج مواصفات اللوح: "{panel_text_query}"، والإنفيرتر: "{inverter_text_query}" {b_prompt}.'
                        res = process_extraction_via_rest([prompt], api_key)
                except Exception as e:
                    st.error(f"❌ {e}")

        if res:
            st.session_state["analysis_result"] = res
            st.toast(f"🚀 تم التحليل بنجاح في {round(time.time() - start_t, 2)} ثوانٍ!", icon="⚡")

# 6. عرض النتائج والمخرجات
if "analysis_result" in st.session_state and st.session_state["analysis_result"]:
    res = st.session_state["analysis_result"]
    panel = res.get("panel", {})
    inv = res.get("inverter", {})

    p_brand = panel.get("brand", "غير معروف")
    p_model = panel.get("model", "غير معروف")
    pmax = safe_float(panel.get("pmax"))
    voc = safe_float(panel.get("voc"))
    vmp = safe_float(panel.get("vmp"))
    isc = safe_float(panel.get("isc"))

    i_brand = inv.get("brand", "غير معروف")
    i_model = inv.get("model", "غير معروف")
    ac_rated_power = safe_float(inv.get("ac_rated_power_w"))
    v_max = safe_float(inv.get("v_max"))
    v_mppt_min = safe_float(inv.get("v_mppt_min"))
    v_mppt_max = safe_float(inv.get("v_mppt_max"))
    mppt_count = safe_int(inv.get("mppt_count"), default=1)
    strings_per_mppt = safe_int(inv.get("strings_per_mppt"), default=1)

    st.subheader("📌 البيانات التعريفية والموديلات المكتشفة")
    col_p_info, col_i_info = st.columns(2)

    with col_p_info:
        st.markdown("### ☀️ اللوح الشمسي")
        st.write(f"**الشركة المصنعة:** {format_val(p_brand)}")
        st.write(f"**الموديل:** {format_val(p_model)}")
        st.write(f"- القدرة (Pmax): {format_val(pmax, 'W')}")
        st.write(f"- جهد الدارة المفتوحة (Voc): {format_val(voc, 'V')}")
        st.write(f"- الجهد التشغيلي (Vmp): {format_val(vmp, 'V')}")
        st.write(f"- تيار القصر (Isc): {format_val(isc, 'A')}")

    with col_i_info:
        st.markdown("### ⚡ الإنفيرتر")
        st.write(f"**الشركة المصنعة:** {format_val(i_brand)}")
        st.write(f"**الموديل:** {format_val(i_model)}")
        st.write(f"- القدرة الاسمية: {format_val(ac_rated_power, 'W')}")
        st.write(f"- أقصى جهد مستمر (DC Max): {format_val(v_max, 'V')}")
        st.write(f"- أدنى جهد MPPT: {format_val(v_mppt_min, 'V')}")
        st.write(f"- أقصى جهد MPPT: {format_val(v_mppt_max, 'V')}")

    if voc > 0 and vmp > 0 and v_max > 0:
        v_mppt_min_safe = v_mppt_min * 1.10
        min_string_safe = math.ceil(v_mppt_min_safe / vmp) if vmp > 0 else 1
        voc_cold_safe = voc * 1.15
        v_max_safe = v_max * 0.95

        max_by_voc = math.floor(v_max_safe / voc_cold_safe) if voc_cold_safe > 0 else 1
        max_by_mppt = math.floor(v_mppt_max / vmp) if vmp > 0 and v_mppt_max > 0 else max_by_voc
        max_string_safe = min(max_by_voc, max_by_mppt) if max_by_mppt > 0 else max_by_voc

        if max_string_safe < min_string_safe:
            max_string_safe = min_string_safe

        rec_string = math.floor((min_string_safe + max_string_safe) / 2)
        total_strings = mppt_count * strings_per_mppt
        rec_total_panels = rec_string * total_strings
        rec_kw = round((rec_total_panels * pmax) / 1000, 2)

        st.markdown("---")
        st.subheader("⚡ نتائج التوصيل وتوزيع السلاسل الآمن")
        st.success(f"""
        🛡️ **حدود الأمان بالسلسلة الواحدة:**
        * **أقل عدد ألواح آمن بالسلسلة:** `{min_string_safe}` ألواح.
        * **أكبر عدد ألواح آمن بالسلسلة:** `{max_string_safe}` لوحاً.
        * **العدد الموصى به مثالياً بالسلسلة:** `{rec_string}` ألواح.
        * **القدرة الكلية المقترحة:** `{rec_total_panels}` لوحاً (`{rec_kw} kW`)
        """)
