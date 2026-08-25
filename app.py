import json
import math
import time
from typing import Any, Dict

from google import genai
from google.genai import types
from google.genai.errors import APIError
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


# 6. دالة الاستخراج الذكية مع تجربة النماذج المتاحة تلقائياً
def process_extraction(contents: list, key: str) -> dict:
    client = genai.Client(api_key=key.strip())

    response_schema = {
        "type": "OBJECT",
        "properties": {
            "panel": {
                "type": "OBJECT",
                "properties": {
                    "brand": {"type": "STRING"},
                    "model": {"type": "STRING"},
                    "part_number": {"type": "STRING"},
                    "type": {"type": "STRING"},
                    "pmax": {"type": "NUMBER"},
                    "voc": {"type": "NUMBER"},
                    "vmp": {"type": "NUMBER"},
                    "isc": {"type": "NUMBER"},
                    "imp": {"type": "NUMBER"},
                },
            },
            "inverter": {
                "type": "OBJECT",
                "properties": {
                    "brand": {"type": "STRING"},
                    "model": {"type": "STRING"},
                    "part_number": {"type": "STRING"},
                    "type": {"type": "STRING"},
                    "phase_type": {"type": "STRING"},
                    "voltage_architecture": {"type": "STRING"},
                    "ac_rated_power_w": {"type": "NUMBER"},
                    "v_max": {"type": "NUMBER"},
                    "v_mppt_min": {"type": "NUMBER"},
                    "v_mppt_max": {"type": "NUMBER"},
                    "v_start": {"type": "NUMBER"},
                    "mppt_count": {"type": "INTEGER"},
                    "strings_per_mppt": {"type": "INTEGER"},
                    "max_mppt_current": {"type": "NUMBER"},
                    "battery": {
                        "type": "OBJECT",
                        "properties": {
                            "supported": {"type": "BOOLEAN"},
                            "nominal_voltage_v": {"type": "NUMBER"},
                            "battery_type": {"type": "STRING"},
                            "max_charge_current_a": {"type": "NUMBER"},
                        },
                    },
                    "ac_input_output": {
                        "type": "OBJECT",
                        "properties": {
                            "nominal_ac_voltage_v": {"type": "STRING"},
                            "frequency_hz": {"type": "STRING"},
                            "max_ac_input_current_a": {"type": "NUMBER"},
                            "max_ac_output_current_a": {"type": "NUMBER"},
                        },
                    },
                    "startup_surge": {
                        "type": "OBJECT",
                        "properties": {
                            "surge_power_va": {"type": "NUMBER"},
                            "duration_seconds": {"type": "NUMBER"},
                        },
                    },
                },
            },
            "external_battery": {
                "type": "OBJECT",
                "properties": {
                    "brand": {"type": "STRING"},
                    "model": {"type": "STRING"},
                    "chemistry": {"type": "STRING"},
                    "capacity_ah": {"type": "NUMBER"},
                    "capacity_kwh": {"type": "NUMBER"},
                    "nominal_voltage_v": {"type": "NUMBER"},
                    "max_charge_current_a": {"type": "NUMBER"},
                    "max_discharge_current_a": {"type": "NUMBER"},
                },
            },
        },
    }

    # قائمة بالنماذج المتاحة مرتبة حسب الأفضلية والأحدث
    candidate_models = ["gemini-2.5-flash", "gemini-1.5-flash"]
    
    last_exception = None

    for model_name in candidate_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=0.1,
                ),
            )
            return json.loads(response.text)
        except APIError as e:
            last_exception = e
            # الانتقال للموديل التالي إذا كان الخطأ متعلقاً بالنموذج
            continue
        except Exception as e:
            raise Exception(f"تعذر معالجة البيانات: {str(e)}")

    if last_exception:
        raise Exception(f"خطأ من Google API: {last_exception.message}")


def extract_via_images(panel_img, inverter_img, battery_img, key):
    contents = []
    contents.append(prepare_image(panel_img))
    contents.append(prepare_image(inverter_img))

    if battery_img:
        contents.append(prepare_image(battery_img))

    prompt = """
    أنت مهندس طاقة شمسية خبير. قم بتحليل الصور المرفقة (لوح شمسي، إنفيرتر، وبطارية إن وجدت) واستخرج كافة المواصفات الكهربائية والبيانات الفنية بدقة وقم بملء الهيكل المحدد.
    إذا لم تكن صورة البطارية مرفقة، اجعل قيم external_battery تساوي 0 أو "غير معروف".
    """
    contents.append(prompt)
    return process_extraction(contents, key)


def extract_via_text(p_text, i_text, b_text, key):
    b_prompt = (
        f'والبطارية الخارجية المطلوبة: "{b_text}"'
        if b_text
        else "لا يوجد بطارية خارجية مخصصة."
    )
    prompt = f"""
    أنت خبير ومدرك لقواعد بيانات كتالوجات الألواح الشمسية والإنفيرترات والبطاريات (Datasheets).
    اللوح الشمسي المطلوب: "{p_text}"
    الإنفيرتر المطلوب: "{i_text}"
    {b_prompt}

    استخرج المواصفات الكهربائية القياسية لهذه الموديلات المحددة وقم بملء البيانات في الهيكل المحدد.
    إذا لم تطلب بطارية، اجعل قيم external_battery تساوي 0 أو "غير معروف".
    """
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
                    b_img = (
                        Image.open(uploaded_battery)
                        if enable_battery and uploaded_battery
                        else None
                    )
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
            st.toast(
                f"🚀 تم التحليل واستخرجت المواصفات في {round(time.time() - start_t, 2)} ثوانٍ!",
                icon="⚡",
            )


# 8. عرض النتائج والحسابات
if "analysis_result" in st.session_state and st.session_state["analysis_result"]:
    res = st.session_state["analysis_result"]
    panel = res.get("panel", {})
    inv = res.get("inverter", {})
    ext_batt = res.get("external_battery", {})

    p_brand = panel.get("brand", "غير معروف")
    p_model = panel.get("model", "غير معروف")
    p_part = panel.get("part_number", "غير معروف")
    p_type = panel.get("type", "غير معروف")

    pmax = safe_float(panel.get("pmax"))
    voc = safe_float(panel.get("voc"))
    vmp = safe_float(panel.get("vmp"))
    isc = safe_float(panel.get("isc"))
    imp = safe_float(panel.get("imp"))

    i_brand = inv.get("brand", "غير معروف")
    i_model = inv.get("model", "غير معروف")
    i_part = inv.get("part_number", "غير معروف")
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
        st.write(f"- التيار التشغيلي (Imp): {format_val(imp, 'A')}")

    with col_i_info:
        st.markdown("### ⚡ الإنفيرتر")
        st.write(f"**الشركة المصنعة:** {format_val(i_brand)}")
        st.write(f"**الموديل / الاسم:** {format_val(i_model)}")
        st.write(f"**نوع الإنفيرتر:** {format_val(i_type)}")
        st.write(f"**نظام الفازات (Phase):** {format_val(phase_type)}")
        st.write(f"**معمارية الجهد (DC Architecture):** {format_val(v_arch)}")
        st.write(f"- القدرة الاسمية: {format_val(ac_rated_power, 'W')}")
        st.write(f"- أقصى جهد مستمر (DC Max): {format_val(v_max, 'V')}")
        st.write(f"- أدنى جهد MPPT: {format_val(v_mppt_min, 'V')}")
        st.write(f"- أقصى جهد MPPT: {format_val(v_mppt_max, 'V')}")
        st.write(
            f"- عدد MPPT: `{mppt_count}` | عدد Strings/MPPT:"
            f" `{strings_per_mppt}`"
        )
        st.write(f"- أقصى تيار لكل MPPT: {format_val(max_mppt_current, 'A')}")

    st.markdown("---")

    st.subheader("🔋 مواصفات البطاريات، شبكة AC، وقدرة البدء (Startup)")
    c_batt, c_ac, c_surge = st.columns(3)

    with c_batt:
        st.markdown("#### 🔋 نظام بطاريات الإنفيرتر")
        batt_supported = batt_info.get("supported", False)
        batt_volts = safe_float(batt_info.get("nominal_voltage_v"))
        batt_type = batt_info.get("battery_type", "غير معروف")
        batt_charge = safe_float(batt_info.get("max_charge_current_a"))

        if not batt_supported and batt_volts == 0:
            st.write(
                "❌ **دعم البطاريات:** `لا يدعم بطاريات (On-Grid / Direct Solar)`"
            )
        else:
            st.write("- **يدعم بطاريات:** `نعم`")
            st.write(f"- **جهد البطارية الاسمي:** {format_val(batt_volts, 'V')}")
            st.write(f"- **أنواع البطاريات:** {format_val(batt_type)}")
            st.write(f"- **أقصى تيار شحن:** {format_val(batt_charge, 'A')}")

    with c_ac:
        st.markdown("#### 🔌 مدخل ومخرج AC")
        ac_v = ac_info.get("nominal_ac_voltage_v", "غير معروف")
        ac_freq = ac_info.get("frequency_hz", "غير معروف")
        ac_in_curr = safe_float(ac_info.get("max_ac_input_current_a"))
        ac_out_curr = safe_float(ac_info.get("max_ac_output_current_a"))

        st.write(f"- **نظام الفاز:** {format_val(phase_type)}")
        st.write(f"- **جهد AC الاسمي:** {format_val(ac_v)}")
        st.write(f"- **التردد:** {format_val(ac_freq)}")
        st.write(f"- **أقصى تيار مدخل AC:** {format_val(ac_in_curr, 'A')}")
        st.write(f"- **أقصى تيار مخرج AC:** {format_val(ac_out_curr, 'A')}")

    with c_surge:
        st.markdown("#### 🚀 قدرة البدء (Surge)")
        s_power = safe_float(surge_info.get("surge_power_va"))
        s_duration = safe_float(surge_info.get("duration_seconds"))

        st.write(f"- **قدرة البدء اللحظية:** {format_val(s_power, 'VA')}")
        st.write(f"- **مدة التحمل:** {format_val(s_duration, 'ثانية')}")

    if enable_battery or (ext_batt.get("nominal_voltage_v", 0) > 0):
        st.markdown("---")
        st.subheader("🛡️ تحليل مطابقة البطارية الخارجية وعوامل الأمان")

        b_brand = ext_batt.get("brand", "غير معروف")
        b_model = ext_batt.get("model", "غير معروف")
        b_chem = ext_batt.get("chemistry", "غير معروف")
        b_volts = safe_float(ext_batt.get("nominal_voltage_v"))
        b_ah = safe_float(ext_batt.get("capacity_ah"))
        b_kwh = safe_float(ext_batt.get("capacity_kwh"))
        b_max_chg = safe_float(ext_batt.get("max_charge_current_a"))
        b_max_dischg = safe_float(ext_batt.get("max_discharge_current_a"))

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.write(f"**الشركة المصنعة:** {format_val(b_brand)}")
            st.write(f"**الموديل:** {format_val(b_model)}")
            st.write(f"**نوع الكيمياء:** {format_val(b_chem)}")
            st.write(
                f"- **السعة الاسمية:** {format_val(b_ah, 'Ah')}"
                f" ({format_val(b_kwh, 'kWh')})"
            )
        with col_b2:
            st.write(f"- **الجهد الاسمي:** {format_val(b_volts, 'V')}")
            st.write(
                f"- **أقصى تيار شحن (Max Charge):**"
                f" {format_val(b_max_chg, 'A')}"
            )
            st.write(
                f"- **أقصى تيار تفريغ (Max Discharge):**"
                f" {format_val(b_max_dischg, 'A')}"
            )

        inv_batt_v = safe_float(batt_info.get("nominal_voltage_v"))
        inv_max_chg = safe_float(batt_info.get("max_charge_current_a"))

        batt_analysis = analyze_battery_safety_and_compatibility(
            inv_voltage=inv_batt_v,
            inv_max_charge=inv_max_chg,
            inv_ac_power=ac_rated_power,
            batt_voltage=b_volts,
            batt_max_charge=b_max_chg,
            batt_max_discharge=b_max_dischg,
            batt_ah=b_ah,
            batt_kwh=b_kwh,
        )

        st.markdown("#### ⚙️ نتائج الفحص وعوامل الأمان للبطارية:")

        if batt_analysis["voltage_match"]:
            st.success(f"✅ **مطابقة الجهد:** {batt_analysis['voltage_msg']}")
        else:
            st.error(f"❌ **عدم مطابقة الجهد:** {batt_analysis['voltage_msg']}")

        if (
            batt_analysis["safe_charge_current"] > 0
            or batt_analysis["safe_discharge_current"] > 0
        ):
            st.info(f"""
            🛡️ **حدود التشغيل الآمنة للبطارية (عامل أمان 80%):**
            * **تيار الشحن الآمن المستمر:** `{batt_analysis['safe_charge_current']}` أمبير (من أصل `{b_max_chg}`A).
            * **تيار التفريغ الآمن المستمر:** `{batt_analysis['safe_discharge_current']}` أمبير (من أصل `{b_max_dischg}`A).
            """)

        for rec in batt_analysis["recommendations"]:
            st.success(f"✔️ {rec}")
        for warn in batt_analysis["warnings"]:
            st.warning(f"⚠️ **تنبيه أمان:** {warn}")

    if voc == 0 or vmp == 0 or v_max == 0:
        st.error(
            "⚠️ البيانات الكهربائية الأساسية للجهد غير كافية لإجراء"
            " الحسابات (مثل Voc, Vmp, DC Max). يرجى التأكد من وضوح الصورة أو"
            " كتابة رقم الموديل بدقة."
        )
    else:
        v_mppt_min_safe = v_mppt_min * 1.10
        min_string_safe = math.ceil(v_mppt_min_safe / vmp) if vmp > 0 else 1

        voc_cold_safe = voc * 1.15
        v_max_safe = v_max * 0.95

        max_by_voc = math.floor(v_max_safe / voc_cold_safe) if voc_cold_safe > 0 else 1
        max_by_mppt = (
            math.floor(v_mppt_max / vmp)
            if vmp > 0 and v_mppt_max > 0
            else max_by_voc
        )
        max_string_safe = (
            min(max_by_voc, max_by_mppt) if max_by_mppt > 0 else max_by_voc
        )

        if max_string_safe < min_string_safe:
            max_string_safe = min_string_safe

        rec_string = math.floor((min_string_safe + max_string_safe) / 2)
        total_strings = mppt_count * strings_per_mppt

        min_total_panels = min_string_safe * total_strings
        rec_total_panels = rec_string * total_strings
        max_total_panels = max_string_safe * total_strings

        min_kw = round((min_total_panels * pmax) / 1000, 2)
        rec_kw = round((rec_total_panels * pmax) / 1000, 2)
        max_kw = round((max_total_panels * pmax) / 1000, 2)

        isc_safe = isc * 1.25

        st.markdown("---")
        st.subheader("⚡ نتائج التوصيل وتوزيع السلاسل الآمن")

        if max_mppt_current > 0 and isc_safe > max_mppt_current:
            st.warning(
                f"⚠️ **تنبيه مطابقة التيار:** تيار القصر المعدل للوح"
                f" ({round(isc_safe, 2)} A) أكبر من أقصى تيار يتحمله مدخل MPPT في"
                f" الإنفيرتر ({max_mppt_current} A). قد يحدث قص للتيار"
                " (Clipping) عند الذروة."
            )
        elif max_mppt_current > 0:
            st.success(
                f"✅ **توافق التيار:** تيار اللوح المعدل ({round(isc_safe, 2)} A)"
                " متوافق تماماً مع مدخل الإنفيرتر."
            )

        st.success(f"""
        🛡️ **حدود الأمان بالسلسلة الواحدة:**
        * **أقل عدد ألواح آمن بالسلسلة:** `{min_string_safe}` ألواح.
        * **أكبر عدد ألواح آمن بالسلسلة:** `{max_string_safe}` لوحاً.
        * **العدد الموصى به مثالياً بالسلسلة:** `{rec_string}` ألواح.
        """)

        st.markdown("### 🔀 تفاصيل التوزيع المقترح من النظام")

        tab1, tab2, tab3 = st.tabs(
            ["⭐ التوزيع المثالي", "🔴 الحد الأدنى", "🟢 الحد الأقصى"]
        )

        with tab1:
            st.info(f"""
            **القدرة الكلية للمنظومة:** `{rec_total_panels}` لوحاً ({rec_kw} kW)
            * **عدد مدخلات MPPT:** {mppt_count} | **عدد السلاسل لكل MPPT:** {strings_per_mppt}
            
            ---
            📌 **التوزيع الميداني:**
            * **لكل String:** ضع `{rec_string}` ألواح على التوالي.
            """)

        with tab2:
            st.warning(f"""
            **القدرة الكلية للمنظومة:** `{min_total_panels}` لوحاً ({min_kw} kW)
            * **عدد مدخلات MPPT:** {mppt_count} | **عدد السلاسل لكل MPPT:** {strings_per_mppt}
            
            ---
            📌 **التوزيع الميداني:**
            * **لكل String:** ضع `{min_string_safe}` ألواح على التوالي.
            """)

        with tab3:
            st.success(f"""
            **القدرة الكلية للمنظومة:** `{max_total_panels}` لوحاً ({max_kw} kW)
            * **عدد مدخلات MPPT:** {mppt_count} | **عدد السلاسل لكل MPPT:** {strings_per_mppt}
            
            ---
            📌 **التوزيع الميداني:**
            * **لكل String:** ضع `{max_string_safe}` لوحاً على التوالي.
            """)

        st.markdown("---")
        st.subheader("🧮 فحص وتوزيع عدد ألواح مخصص")

        initial_custom_value = max(
            1, int(rec_total_panels if rec_total_panels > 0 else min_total_panels)
        )
        max_custom_value = max(1, int(max_total_panels * 2))

        custom_panels_count = st.number_input(
            "أدخل إجمالي عدد الألواح التي ترغب بتركيبها:",
            min_value=1,
            max_value=max_custom_value,
            value=initial_custom_value,
            step=1,
            key="custom_panels_input",
        )

        if custom_panels_count > 0:
            custom_kw = round((custom_panels_count * pmax) / 1000, 2)
            st.markdown(
                f"#### 📊 النتائج للعدد المدخل ({custom_panels_count} لوحاً):"
            )
            st.write(
                f"- **إجمالي قدرة التوليد:** `{custom_kw} kW` (بقدرة اللوح"
                f" `{pmax}W`)"
            )

            num_strings_used = min(total_strings, custom_panels_count)
            panels_per_str = custom_panels_count // num_strings_used
            remainder = custom_panels_count % num_strings_used

            vmp_string = round(panels_per_str * vmp, 1)
            voc_string_cold = round(panels_per_str * voc * 1.15, 1)

            if panels_per_str < min_string_safe:
                st.error(
                    f"❌ **العدد المدخل غير آمن (أقل من الحد الأدنى):**\n\n"
                    f"الجهد التشغيلي المتوقع `{vmp_string}V` أقل من جهد MPPT"
                    f" الأدنى الآمن (`{round(v_mppt_min_safe,1)}V`)."
                )
            elif panels_per_str > max_string_safe:
                st.error(
                    f"⚠️ **العدد المدخل غير آمن (يتجاوز أقصى جهد):**\n\n"
                    f"جهد الدارة المفتوحة في الشتاء يصل إلى `{voc_string_cold}V`"
                    " مما يتجاوز الحد الأقصى الآمن المسموح للإنفيرتر"
                    f" (`{round(v_max_safe,1)}V`). **خطر تلف مدخل"
                    " الإنفيرتر!**"
                )
            else:
                st.success(
                    "✅ **العدد المدخل متوافق تماماً وآمن كهربائياً.**"
                )
                st.info(
                    f"""
                🔌 **خطة التوصيل الميدانية للعدد المدخل ({custom_panels_count} لوحاً):**
                * **عدد السلاسل (Strings) المستخدمة:** `{num_strings_used}` من أصل `{total_strings}`
                * **توصيل كل سلسلة:** اربط `{panels_per_str}` ألواح على التوالي لكل سلسلة.
                * **الجهد المتوقع لكل سلسلة (Vmp):** `{vmp_string} V`
                * **الجهد الأقصى المتوقع في الشتاء (Voc Cold):** `{voc_string_cold} V`
                """
                    + (
                        f"\n⚠️ **ملاحظة:** يتبقى `{remainder}` ألواح غير"
                        " موزعة."
                        if remainder > 0
                        else ""
                    )
                )
