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

    button[data-baseweb="tab"] {
        direction: rtl !important;
    }
    div[data-baseweb="tab-list"] {
        flex-direction: row-reverse !important;
        justify-content: flex-end !important;
    }

    section[data-testid="stFileUploadDropzone"] {
        direction: rtl;
        text-align: right;
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
    "تحليل ذكي متكامل للمواصفات الكهربائية، مع إدراج عوامل الأمان للبطاريات وسلاسل الألواح"
)

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

# تفعيل أو إيقاف تحليل البطارية الخارجية
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
        uploaded_panel = st.file_uploader(
            "📸 صورة ملصق اللوح الشمسي", type=["jpg", "jpeg", "png"]
        )
    with cols[1]:
        uploaded_inverter = st.file_uploader(
            "📸 صورة ملصق الإنفيرتر", type=["jpg", "jpeg", "png"]
        )
    if enable_battery:
        with cols[2]:
            uploaded_battery = st.file_uploader(
                "📸 صورة ملصق البطارية", type=["jpg", "jpeg", "png"]
            )
else:
    cols = st.columns(3 if enable_battery else 2)
    with cols[0]:
        panel_text_query = st.text_input(
            "☀️ اسم الشركة والموديل للوح الشمسي:",
            placeholder="مثال: Jinko Solar JKMM550M-72HL4-V",
        )
    with cols[1]:
        inverter_text_query = st.text_input(
            "⚡ اسم الشركة والموديل للإنفيرتر:",
            placeholder="مثال: Deye SUN-5K-SG04LP1-EU أو Growatt 5000ES",
        )
    if enable_battery:
        with cols[2]:
            battery_text_query = st.text_input(
                "🔋 اسم الشركة والموديل للبطارية:",
                placeholder="مثال: Felicity solar LPBF48300 أو Pylontech US3000C",
            )


# 5. دوال مساعدة وتحضير الصور
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
    if (
        value is None
        or value == ""
        or value == 0
        or value == 0.0
        or value == "غير محدد"
        or value == "غير معروف"
    ):
        return "`غير موجود في البيانات`"
    return f"`{value} {unit}`".strip()


def prepare_image(pil_img: Image.Image, max_dim: int = 1024) -> Image.Image:
    """تحضير الصورة: تحويلها لـ RGB وتصغير أبعادها لضمان التوافق وحجم البيانات."""
    img_copy = pil_img.copy()
    if img_copy.mode != "RGB":
        img_copy = img_copy.convert("RGB")
    img_copy.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    return img_copy


def analyze_battery_safety_and_compatibility(
    inv_voltage: float,
    inv_max_charge: float,
    inv_ac_power: float,
    batt_voltage: float,
    batt_max_charge: float,
    batt_max_discharge: float,
    batt_ah: float,
    batt_kwh: float,
) -> Dict[str, Any]:
    results = {
        "voltage_match": False,
        "voltage_msg": "",
        "warnings": [],
        "recommendations": [],
        "safe_charge_current": 0.0,
        "safe_discharge_current": 0.0,
    }

    if inv_voltage <= 0 or batt_voltage <= 0:
        results["voltage_msg"] = "تعذر الجزم بتوافق الجهد لعدم توفر قراءة دقيقة."
    elif (40.0 <= inv_voltage <= 60.0) and (40.0 <= batt_voltage <= 60.0):
        results["voltage_match"] = True
        results["voltage_msg"] = (
            f"جهد البطارية ({batt_voltage}V) متوافق تماماً مع نظام الإنفيرتر"
            f" ({inv_voltage}V) ضمن فئة 48V/51.2V القياسية."
        )
    elif (20.0 <= inv_voltage <= 30.0) and (20.0 <= batt_voltage <= 30.0):
        results["voltage_match"] = True
        results["voltage_msg"] = (
            f"جهد البطارية ({batt_voltage}V) متوافق مع نظام الإنفيرتر"
            f" ({inv_voltage}V) ضمن فئة 24V."
        )
    elif (10.0 <= inv_voltage <= 15.0) and (10.0 <= batt_voltage <= 15.0):
        results["voltage_match"] = True
        results["voltage_msg"] = (
            f"جهد البطارية ({batt_voltage}V) متوافق مع نظام الإنفيرتر"
            f" ({inv_voltage}V) ضمن فئة 12V."
        )
    elif (
        inv_voltage >= 100.0
        and batt_voltage >= 100.0
        and abs(inv_voltage - batt_voltage) <= 60.0
    ):
        results["voltage_match"] = True
        results["voltage_msg"] = (
            f"جهد البطارية العالي HV ({batt_voltage}V) متوافق مع نطاق الإنفيرتر"
            f" ({inv_voltage}V)."
        )
    elif abs(inv_voltage - batt_voltage) <= 5.0:
        results["voltage_match"] = True
        results["voltage_msg"] = (
            f"الجهد متوافق تقريباً بين الإنفيرتر ({inv_voltage}V) والبطارية"
            f" ({batt_voltage}V)."
        )
    else:
        results["voltage_match"] = False
        results["voltage_msg"] = (
            f"غير متوافق! جهد البطارية ({batt_voltage}V) يختلف جوهرياً عن جهد"
            f" الإنفيرتر المطلوب ({inv_voltage}V)."
        )

    SAFETY_FACTOR = 0.80
    if batt_max_charge > 0:
        results["safe_charge_current"] = round(batt_max_charge * SAFETY_FACTOR, 1)
    if batt_max_discharge > 0:
        results["safe_discharge_current"] = round(batt_max_discharge * SAFETY_FACTOR, 1)

    if inv_max_charge > 0 and batt_max_charge > 0:
        if inv_max_charge > results["safe_charge_current"]:
            results["warnings"].append(
                f"أقصى تيار شحن للإنفيرتر ({inv_max_charge}A) أعلى من تيار الشحن"
                f" الآمن للبطارية بعامل الأمان"
                f" ({results['safe_charge_current']}A). يجب ضبط أقصى تيار شحن"
                " في إعدادات الإنفيرتر (Max Charge Current) على"
                f" `{results['safe_charge_current']} A` لحماية خلايا البطارية."
            )
        else:
            results["recommendations"].append(
                f"تيار شحن الإنفيرتر ({inv_max_charge}A) آمن وضمن الحدود المسموحة"
                " للبطارية."
            )

    if inv_ac_power > 0 and batt_voltage > 0 and batt_max_discharge > 0:
        max_inverter_dc_current = round(inv_ac_power / (batt_voltage * 0.90), 1)
        if max_inverter_dc_current > results["safe_discharge_current"]:
            results["warnings"].append(
                f"عند تشغيل الإنفيرتر بالكامل ({inv_ac_power}W)، يسحب تيار مستمر"
                f" يصل إلى ~`{max_inverter_dc_current}A` وهو أكبر من تيار"
                " التفريغ الآمن لبطارية واحدة"
                f" (`{results['safe_discharge_current']}A`). ينصح بالتوازي مع"
                " بطارية إضافية لتقسيم الحمل وتجنب فصل الـ BMS."
            )
        else:
            results["recommendations"].append(
                f"تيار التفريغ الآمن للبطارية ({results['safe_discharge_current']}A)"
                " يكفي لتشغيل قدرة الإنفيرتر الكاملة بحماية وأمان."
            )

    if batt_ah > 0 and inv_ac_power > 0 and batt_voltage > 0:
        recommended_min_ah = round((inv_ac_power / batt_voltage) * 1.5, 0)
        if batt_ah < (inv_ac_power / batt_voltage):
            results["warnings"].append(
                f"سعة البطارية ({batt_ah}Ah) تعتبر صغيرة نسبياً على إنفيرتر بقدرة"
                f" {inv_ac_power}W. يُفضل ألا تقل السعة الكلية عن"
                f" `{recommended_min_ah}Ah` لمطابقة أحمال الذروة ولتوفير ساعات"
                " تشغيل معقولة."
            )

    return results


def clean_json_response(text: str) -> str:
    """تنظيف نص الاستجابة من رموز Markdown مثل ```json ... ```"""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


# 6. دالة الاستخراج المباشرة من Gemini API
def process_extraction(contents: list, key: str) -> dict:
    genai.configure(api_key=key.strip())
    
    # استخدام النموذج المعتمد الأحدث والمستقر
    model_name = "gemini-2.5-flash"

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
    
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            all_inputs,
            generation_config={"response_mime_type": "application/json", "temperature": 0.1}
        )
        cleaned_json = clean_json_response(response.text)
        return json.loads(cleaned_json)
    except Exception as e:
        # محاولة احتياطية باستكشاف نموذج متاح بحساب المستخدم
        try:
            available_models = [
                m.name for m in genai.list_models() 
                if 'generateContent' in m.supported_generation_methods
            ]
            if available_models:
                fallback_model = genai.GenerativeModel(available_models[0])
                response = fallback_model.generate_content(
                    all_inputs,
                    generation_config={"response_mime_type": "application/json", "temperature": 0.1}
                )
                cleaned_json = clean_json_response(response.text)
                return json.loads(cleaned_json)
        except Exception:
            pass
        raise Exception(f"تعذر استخراج البيانات من API: {str(e)}")


def extract_via_images(panel_img, inverter_img, battery_img, key):
    contents = [prepare_image(panel_img), prepare_image(inverter_img)]
    if battery_img:
        contents.append(prepare_image(battery_img))

    prompt = "قم بتحليل الصور المرفقة واستخراج المواصفات الكهربائية الكاملة."
    contents.append(prompt)
    return process_extraction(contents, key)


def extract_via_text(p_text, i_text, b_text, key):
    b_prompt = f'والبطارية الخارجية: "{b_text}"' if b_text else "لا يوجد بطارية خارجية."
    prompt = f'استخرج مواصفات اللوح: "{p_text}"، والإنفيرتر: "{i_text}" {b_prompt}.'
    return process_extraction([prompt], key)


# 7. زر التفعيل والتحليل
if st.button("⚡ تحليل سريع واستخرج التقرير والحسابات"):
    if not api_key:
        st.error("⚠️ يرجى إدخال مفتاح Gemini API Key في القائمة الجانبية.")
    else:
        res = None
        start_t = time.time()

        if "📸" in search_mode:
            if not uploaded_panel or not uploaded_inverter:
                st.error("⚠️ يرجى تحميل صورة اللوح والإنفيرتر معاً لمتابعة الحسابات.")
            elif enable_battery and not uploaded_battery:
                st.error("⚠️ لقد قمت بتفعيل فحص البطارية، يرجى رفع صورة ملصق البطارية أيضاً.")
            else:
                try:
                    p_img = Image.open(uploaded_panel)
                    i_img = Image.open(uploaded_inverter)
                    b_img = Image.open(uploaded_battery) if enable_battery and uploaded_battery else None
                    with st.spinner("⚡ جاري قراءة الملصقات وتحليل الصور وحساب الأمان تلقائياً..."):
                        res = extract_via_images(p_img, i_img, b_img, api_key)
                except Exception as e:
                    st.error(f"❌ {e}")
        else:
            if not panel_text_query or not inverter_text_query:
                st.error("⚠️ يرجى كتابة اسم الشركة والموديل للوح والإنفيرتر معاً.")
            elif enable_battery and not battery_text_query:
                st.error("⚠️ لقد قمت بتفعيل فحص البطارية، يرجى كتابة اسم وموديل البطارية أيضاً.")
            else:
                try:
                    with st.spinner("🔍 جاري البحث عن مواصفات الكتالوج والتحليل..."):
                        res = extract_via_text(
                            panel_text_query,
                            inverter_text_query,
                            battery_text_query if enable_battery else "",
                            api_key,
                        )
                except Exception as e:
                    st.error(f"❌ {e}")

        if res:
            st.session_state["analysis_result"] = res
            st.toast(f"🚀 تم التحليل بنجاح في {round(time.time() - start_t, 2)} ثوانٍ!", icon="⚡")


# 8. عرض النتائج والحسابات
if "analysis_result" in st.session_state and st.session_state["analysis_result"]:
    res = st.session_state["analysis_result"]
    panel = res.get("panel", {})
    inv = res.get("inverter", {})
    ext_batt = res.get("external_battery", {})

    p_brand = panel.get("brand", "غير معروف")
    p_model = panel.get("model", "غير معروف")
    p_type = panel.get("type", "غير معروف")

    pmax = safe_float(panel.get("pmax"))
    voc = safe_float(panel.get("voc"))
    vmp = safe_float(panel.get("vmp"))
    isc = safe_float(panel.get("isc"))
    imp = safe_float(panel.get("imp"))

    i_brand = inv.get("brand", "غير معروف")
    i_model = inv.get("model", "غير معروف")
    i_type = inv.get("type", "غير معروف")
    phase_type = inv.get("phase_type", "غير معروف")
    v_arch = inv.get("voltage_architecture", "غير معروف")
    ac_rated_power = safe_float(inv.get("ac_rated_power_w"))

    v_max = safe_float(inv.get("v_max"))
    v_mppt_min = safe_float(inv.get("v_mppt_min"))
    v_mppt_max = safe_float(inv.get("v_mppt_max"))
    mppt_count = safe_int(inv.get("mppt_count"), default=1)
    strings_per_mppt = safe_int(inv.get("strings_per_mppt"), default=1)
    max_mppt_current = safe_float(inv.get("max_mppt_current"))

    batt_info = inv.get("battery", {})
    ac_info = inv.get("ac_input_output", {})
    surge_info = inv.get("startup_surge", {})

    st.subheader("📌 البيانات التعريفية والموديلات المكتشفة")
    col_p_info, col_i_info = st.columns(2)

    with col_p_info:
        st.markdown("### ☀️ اللوح الشمسي")
        st.write(f"**الشركة المصنعة:** {format_val(p_brand)}")
        st.write(f"**الموديل / الاسم:** {format_val(p_model)}")
        st.write(f"**نوع اللوح:** {format_val(p_type)}")
        st.write(f"- القدرة (Pmax): {format_val(pmax, 'W')}")
        st.write(f"- جهد الدارة المفتوحة (Voc): {format_val(voc, 'V')}")
        st.write(f"- الجهد التشغيلي (Vmp): {format_val(vmp, 'V')}")
        st.write(f"- تيار القصر (Isc): {format_val(isc, 'A')}")
        st.write(f"- التيار التشغيلي (Imp
