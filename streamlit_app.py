import json
import re
import base64
import subprocess
import shutil
import traceback
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import requests
import streamlit as st
from openai import AuthenticationError, OpenAI
import os


import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR_PATH = Path(BASE_DIR)
SUBAPP_DIR = os.path.join(BASE_DIR, "sokbogo-newtro")

if SUBAPP_DIR not in sys.path:
    sys.path.insert(0, SUBAPP_DIR)


from youtube_trends import get_health_trends
from youtube_topic_explorer_page import render_topic_explorer
from category_mapper import recommend_categories
from youtube_topic_explorer import get_topic_trends, interpret_trend_with_llm


st.success("YouTubeFactory 앱 정상 실행 중")

# =========================================================
# 마지막 결과 저장 (로컬 실행 기준: 앱 껐다 켜도 남김)
# =========================================================
LAST_RESULT_PATH = Path("last_result.json")
LOCAL_SETTINGS_PATH = Path(".streamlit/local_settings.json")


def load_local_settings() -> Dict[str, Any]:
    try:
        if LOCAL_SETTINGS_PATH.exists():
            return json.loads(LOCAL_SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}


def save_local_settings(data: Dict[str, Any]) -> None:
    try:
        LOCAL_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def get_effective_api_key() -> str:
    local_settings = load_local_settings()
    return (local_settings.get("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", "")).strip()


def rebuild_openai_client() -> tuple[str, OpenAI | None]:
    current_api_key = get_effective_api_key()
    return current_api_key, OpenAI(api_key=current_api_key) if current_api_key else None


def desktop_video_tools_enabled() -> bool:
    env_value = os.getenv("ENABLE_DESKTOP_VIDEO_TOOLS", "").strip().lower()
    if env_value:
        return env_value in {"1", "true", "yes", "on"}

    secret_value = str(st.secrets.get("ENABLE_DESKTOP_VIDEO_TOOLS", "1")).strip().lower()
    return secret_value in {"1", "true", "yes", "on"}


def get_llm_trend_pick(trend_text: str, client, model: str) -> dict:
    trend_text = (trend_text or "").strip()

    if not trend_text:
        return {
            "reason": "",
            "insight": "",
            "health_angle": "",
            "converted_topic": "",
            "usable": False,
        }

    try:
        data = interpret_trend_with_llm(
            trend_text,
            client=client,
            model=model,
        )

        converted_topic = (data.get("converted_topic") or "").strip()

        return {
            "reason": (data.get("reason") or "").strip(),
            "insight": (data.get("insight") or "").strip(),
            "health_angle": (data.get("health_angle") or "").strip(),
            "converted_topic": converted_topic,
            "usable": bool(converted_topic),
        }
    except Exception:
        return {
            "reason": "",
            "insight": "",
            "health_angle": "",
            "converted_topic": "",
            "usable": False,
        }


def load_last_result() -> dict | None:
    try:
        if LAST_RESULT_PATH.exists():
            return json.loads(LAST_RESULT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None

def save_last_result(data: dict) -> None:
    try:
        LAST_RESULT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def delete_last_result() -> None:
    try:
        if LAST_RESULT_PATH.exists():
            LAST_RESULT_PATH.unlink()
    except Exception:
        pass

def infer_target_organ(topic: str) -> str:
    t = (topic or "").strip()

    organ_map = {
        "뇌": ["뇌", "기억", "집중", "불안", "우울", "스트레스", "수면", "잠", "두통", "어지럼", "멘탈", "신경"],
        "심장": ["심장", "혈압", "맥박", "두근", "부정맥", "혈관", "순환", "가슴"],
        "폐": ["폐", "호흡", "기관지", "기침", "천식", "미세먼지", "황사", "산소"],
        "간": ["간", "해독", "피로", "음주", "지방간", "독소"],
        "위": ["위", "속쓰림", "위산", "소화", "메스꺼움", "야식", "식후", "폭식"],
        "장": ["장", "변비", "설사", "장염", "복부", "배", "유산균", "가스", "식습관"],
        "신장": ["신장", "콩팥", "붓기", "소변"],
        "혈관": ["혈당", "당뇨", "인슐린", "콜레스테롤", "중성지방", "대사", "배달", "간식"],
    }

    for organ, keywords in organ_map.items():
        if any(k in t for k in keywords):
            return organ

    return "뇌"


def organ_english_name(organ: str) -> str:
    mapping = {
        "뇌": "Massive Human Brain",
        "심장": "Massive Human Heart",
        "폐": "Massive Human Lungs",
        "간": "Massive Human Liver",
        "위": "Massive Human Stomach",
        "장": "Massive Human Intestines",
        "신장": "Massive Human Kidney",
        "혈관": "Massive Human Blood Vessel Network",
    }
    return mapping.get(organ, "Massive Human Brain")


def organ_damage_signal(organ: str) -> str:
    mapping = {
        "뇌": "glowing magenta neural scan lines and black micro-particles infiltrating the cortex",
        "심장": "glowing magenta vascular lines and dark stress clusters spreading across the muscle tissue",
        "폐": "glowing magenta airway lines with black dust particles clogging alveoli and bronchi",
        "간": "glowing magenta metabolic pathways with dark toxin clusters spreading across the liver surface",
        "위": "glowing magenta digestive lines with acidic dark contamination spreading through the stomach wall",
        "장": "glowing magenta intestinal pathways with dark inflammatory particles spreading through the gut",
        "신장": "glowing magenta filtration lines with dark waste particles blocking kidney channels",
        "혈관": "glowing magenta vessel pathways with dark metabolic particles building up inside the circulation",
    }
    return mapping.get(organ, "glowing magenta neural scan lines and black micro-particles infiltrating the tissue")


def organ_lab_action(organ: str) -> str:
    mapping = {
        "뇌": "tiny 1:87 scale scientists using cranes and lifts to inspect the lobes and neural pathways",
        "심장": "tiny 1:87 scale scientists using cranes and surgical lifts to inspect the chambers and vessels",
        "폐": "tiny 1:87 scale scientists using cranes and scaffold lifts to inspect airway branches and alveoli",
        "간": "tiny 1:87 scale scientists using cranes and micro-platforms to inspect liver lobes and toxic zones",
        "위": "tiny 1:87 scale scientists using scaffold lifts to inspect the stomach folds and acidic damage zones",
        "장": "tiny 1:87 scale scientists using scaffold lifts and cranes to inspect intestinal folds and inflamed regions",
        "신장": "tiny 1:87 scale scientists using cranes and lift platforms to inspect kidney filtration structures",
        "혈관": "tiny 1:87 scale scientists using cranes and lifts to inspect vessel walls and metabolic buildup",
    }
    return mapping.get(organ, "tiny 1:87 scale scientists using cranes and lifts to inspect the organ structure")


def build_infographic_scene_prompt(
    organ: str,
    topic: str,
    scene_title: str,
    scene_direction: str,
) -> str:
    organ_en = organ_english_name(organ)
    damage_signal = organ_damage_signal(organ)
    lab_action = organ_lab_action(organ)

    return f"""
Input Variable: [{topic}]
System Instruction: Generate a hyper-realistic "Biological Autopsy" diorama.

Layout:
- 9:16 vertical
- a giant {organ_en} placed on a white medical operating table
- photorealistic surgical theater environment
- cinematic surgical lighting
- highly detailed realistic tissue texture
- no text, no letters, no subtitles, no watermark

Core Visual Style:
- miniature 1:87 scale scientists researching the organ
- yellow safety suits
- small cranes, scaffold lifts, surgical tools, diagnostic monitors
- glowing magenta scan lines tracing the organ structure
- dramatic medical-laboratory atmosphere
- ultra-detailed diorama realism
- clean composition for short-form vertical video

Scene Goal:
- {scene_title}
- {scene_direction}

Required Elements:
- {lab_action}
- {damage_signal}

Topic Context:
- The scene should visually express this topic: {topic}

Visual Rule:
- show the process through research, contamination, infiltration, damage progression, and warning
- focus on visual storytelling only
- no text inside image
- no infographic labels
- no UI overlay
- no logo
""".strip()


def generate_fixed_infographic_prompts(topic: str, channel: str = "") -> list[str]:
    organ = infer_target_organ(topic)

    scenes = [
        (
            "Scene 1 - baseline inspection",
            f"show the {organ} in a relatively stable condition while miniature scientists begin investigation and scanning",
        ),
        (
            "Scene 2 - early anomaly detection",
            f"show early contamination or stress signals first appearing on the {organ}, with scientists reacting and diagnostic cranes moving into position",
        ),
        (
            "Scene 3 - infiltration and spread",
            f"show harmful particles, stress signals, or damage factors spreading deeper through the {organ}, with magenta scan lines revealing the internal pathway",
        ),
        (
            "Scene 4 - visible damage escalation",
            f"show the {organ} under heavier damage, inflammation, or overload, with scientists trying to contain the affected zones in a tense medical scene",
        ),
        (
            "Scene 5 - warning stage",
            f"show the {organ} at the warning stage, emphasizing the final danger signal clearly through lighting, contamination density, and urgent scientific intervention",
        ),
    ]

    return [
        build_infographic_scene_prompt(organ, topic, scene_title, scene_direction)
        for scene_title, scene_direction in scenes
    ]


def build_lifestyle_scene_prompt(topic: str, scene_text: str, scene_index: int, scene_count: int) -> str:
    return f"""
Create a photorealistic vertical 9:16 image for a Korean health shorts video.

Topic: {topic}
Scene text: {scene_text}
Scene order: {scene_index} of {scene_count}

Requirements:
- Show Korean women or men in their 40s
- One or two people are allowed, and more than one person may appear if it improves the scene
- Real human lifestyle scene only
- Focus on insomnia, smartphone use at night, checking sleep environment, bedtime routine, fatigue, late-night wakefulness, or using an AI prompt on a phone or laptop to solve a sleep-related problem
- Use realistic Korean home interiors, especially bedroom, bedside table, blanket, pillow, dim lamp, apartment bedroom, living room, or small desk setup
- If a device appears, show realistic smartphone or laptop use in a natural Korean daily-life context
- Natural body language, believable tired emotion, cinematic but realistic
- Health-related situation should be implied through behavior, facial expression, sleep routine, light, posture, or environment
- People-centered composition
- modern Korean lifestyle photography
- relatable everyday moment
- no hospital operating room
- no medical lab
- no surgery
- no giant organ
- no giant brain
- no medical brain diorama
- no organ cutaway
- no miniature
- no autopsy table
- no surgical theater
- no infographic
- no text inside image
- no letters
- no watermark
- no split screen

Visual direction:
- Use this scene text as the visual situation: {scene_text}
- Prefer insomnia-related daily life moments over abstract medical visuals
- Show realistic Korean 40s adults rather than models with exaggerated fashion styling
- Keep the image grounded, relatable, and emotionally clear
- Prefer subtle storytelling over abstract symbolism
""".strip()


def build_fixed_lifestyle_scene_prompts(topic: str, script_text: str) -> List[str]:
    scene_texts = split_script_into_scene_texts(script_text, 3)
    fallback_text = topic or "불면증과 수면 습관"

    scenes = [
        (
            1,
            scene_texts[0] if len(scene_texts) > 0 and scene_texts[0] else fallback_text,
            "밤에 잠들지 못하고 침대에서 스마트폰을 보는 한국 40대 남녀, 불면증에 공감되는 현실적인 장면",
        ),
        (
            2,
            scene_texts[1] if len(scene_texts) > 1 and scene_texts[1] else fallback_text,
            "한국 40대 사용자가 스마트폰 AI 입력창에 프롬프트를 입력하는 장면, 손과 폰 화면과 집중하는 표정이 잘 보이는 행동 유도 핵심 장면",
        ),
        (
            3,
            scene_texts[2] if len(scene_texts) > 2 and scene_texts[2] else fallback_text,
            "수면 환경을 점검하거나 편안하게 쉬는 한국 40대의 장면, 안정감과 개선 가능성, 실천 유도 느낌",
        ),
    ]

    return [
        build_lifestyle_scene_prompt(
            topic=topic,
            scene_text=f"{fixed_direction}. Narrative context: {scene_text}",
            scene_index=index,
            scene_count=3,
        )
        for index, scene_text, fixed_direction in scenes
    ]


def generate_lifestyle_image_prompts(topic: str, script_text: str, scene_count: int = 5) -> List[str]:
    return build_fixed_lifestyle_scene_prompts(topic, script_text)


# =========================================================
# App Config
# =========================================================
st.set_page_config(
    page_title="속보고-뉴트로-김앤리 (콘텐츠 공장)",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.title("🔬 속보고-뉴트로-김앤리")
st.caption("채널 선택(속보고/뉴트로/김앤리) + 최근 근거(PubMed) + 이미지/영상 프롬프트 + 업로드 패키지 자동 생성 워크스페이스입니다.")

# =========================================================
# Secrets / Client
# =========================================================
api_key = get_effective_api_key()
model = st.secrets.get("OPENAI_MODEL", "gpt-4o-mini")
client = OpenAI(api_key=api_key) if api_key else None

# =========================================================
# 채널
# =========================================================
CHANNELS = [
    "속보고",
    "뉴트로",
    "김앤리",
]

# =========================================================
# 김앤리 썸네일(커버) 이미지 프롬프트 템플릿 (사용자 제공 고정)
# =========================================================
KIMLEE_COVER_PROMPT_TEMPLATE = """
Create a vertical 9:16 YouTube Shorts cover image for the Kim & Lee Health Lab series.

Topic: {topic}

=== Core Identity (DO NOT CHANGE STYLE) ===
Two white fluffy cat characters representing Kim employee and Lee employee.
They are professional health lab researchers in a modern medical laboratory.

Kim employee:
- White fluffy fur
- Pastel blue knit sweater
- Soft blue beanie
- Looking into microscope seriously

Lee employee:
- White fluffy fur
- Pastel pink knit sweater
- Soft pink beanie
- Holding clipboard and analyzing notes

=== Fur & Character Rendering (MANDATORY) ===
Ultra realistic fluffy white fur
Soft volumetric fur strands
Highly detailed whiskers
Natural paw texture
Photoreal fur simulation
Gentle rim lighting enhancing fur edges
NOT clay
NOT toy
NOT miniature
NOT diorama

=== Lab Environment (Series Signature) ===
Clean modern medical laboratory interior
Realistic microscope
Test tube rack with colorful samples
Glass beakers with subtle reflections
Small medical chart or organ illustration related to the topic
Digital lab monitor in background
Clinical white surfaces

=== Kim & Lee Shorts Visual Signature ===
Foreground: lab samples connected visually to the topic
Background: slightly blurred lab environment
Tone: cute but scientifically trustworthy
Mood: educational, credible, warm

=== Lighting & Quality ===
Cinematic studio lighting
Macro photography depth of field
Physically based rendering
High detail 8k
Professional health documentary realism
""".strip()
# =========================================================
# 김앤리 연구실 4컷 이미지 프롬프트 (고정 템플릿)
# =========================================================
KIMLEE_LAB_4CUT_TEMPLATE = {
    "cut1": """
Ultra realistic vertical 9:16 scene in a clean modern medical laboratory.
Two white fluffy cat researchers (Kim=blue sweater+blue beanie, Lee=pink sweater+pink beanie).
Topic board in background shows simple organ sketch related to: {topic} (no readable text, just illustration).
Kim is looking into a microscope seriously, Lee is holding a clipboard and pointing to a lab monitor.
Photoreal fluffy fur strands, detailed whiskers, gentle rim light, macro depth of field.
Cute but scientifically trustworthy mood, no text overlay.
""".strip(),
    "cut2": """
Ultra realistic vertical 9:16 close-up.
Kim cat hands adjusting microscope focus knob, extreme detail on paw texture and fur.
On the lab desk: test tubes with colorful samples, glass beakers with subtle reflections.
A small organ model (matching topic: {topic}) sits near the microscope.
Clean clinical white surfaces, cinematic studio lighting, shallow depth of field, no text overlay.
""".strip(),
    "cut3": """
Ultra realistic vertical 9:16 mid-shot.
Lee cat analyzing a digital lab monitor showing abstract medical charts (no readable text),
while Kim cat gestures toward a transparent specimen container.
Foreground: lab samples visually connected to {topic} with simple icon-like shapes (no text).
Warm educational documentary realism, photoreal fur simulation, gentle rim lighting, no text overlay.
""".strip(),
    "cut4": """
Ultra realistic vertical 9:16 hopeful conclusion scene.
Both cats side-by-side, Kim points at a simplified 'good trend' style chart on a board (no readable text),
Lee stamps a clipboard as “research complete” vibe (no text).
Background: modern lab, microscope and organ illustration related to {topic}.
Cinematic lighting, macro DOF, credible and warm, no text overlay.
""".strip(),
}

# =========================================================
# 소라2(약한 움직임) 김앤리 4컷 영상 프롬프트 (고정 템플릿)
# =========================================================
KIMLEE_SORA2_VIDEO_4CUT_TEMPLATE = {
    "cut1": """
Sora2 video, 8 seconds, vertical 9:16.
Scene: modern medical lab with two ultra-realistic fluffy white cat researchers (Kim blue, Lee pink).
Action: very subtle slow zoom-in (single gentle zoom), faint monitor glow, no fast motion.
Mood: warm, credible health documentary. No text. No shaky cam.
Topic visual: simple organ illustration linked to {topic} in background (no readable text).
""".strip(),
    "cut2": """
Sora2 video, 8 seconds, vertical 9:16.
Close-up: Kim cat adjusting microscope focus knob, lab glassware and test tubes in frame.
Motion: gentle micro pan left-to-right (slow, minimal), no orbit, no dramatic effects.
Photoreal fur strands and paw texture, cinematic lighting, no text.
Topic: small organ model hinting {topic}.
""".strip(),
    "cut3": """
Sora2 video, 8 seconds, vertical 9:16.
Mid-shot: Lee cat holds clipboard, looks at lab monitor with abstract charts (no readable text),
Kim cat points to specimen container.
Motion: slow subtle zoom-out (single gentle move), soft depth of field, no fast transitions.
Clean clinical lab, credible warm tone, no text.
Topic: {topic} suggested via organ illustration.
""".strip(),
    "cut4": """
Sora2 video, 8 seconds, vertical 9:16.
Both cats together, confident ending pose in lab.
Motion: faint MRI-like line sweep effect in the background only (very subtle), or gentle micro pan.
No explosive effects, no dramatic camera movement, no text.
Hopeful educational ending, topic: {topic}.
""".strip(),
}

# =========================================================
# 프리셋: 장기 → 질환/키워드(한국어) + PubMed 검색용 영문쿼리(내부용)
# =========================================================
PRESETS: Dict[str, List[Dict[str, str]]] = {
    "수면": [
            {
                "disease": "불면증",
                "keywords_ko": "잠들기 전 스마트폰 불면증 수면 습관",
                "pubmed_query": "insomnia sleep hygiene smartphone"
            },
            {
                "disease": "수면 부족",
                "keywords_ko": "수면 부족 건강 영향 피로 집중력 저하",
                "pubmed_query": "sleep deprivation health"
            }
        ],

"대사": [
    {
        "disease": "대사증후군",
        "keywords_ko": "복부비만 인슐린 저항성 혈당 상승 건강 영향",
        "pubmed_query": "metabolic syndrome insulin resistance health risk"
    },
    {
        "disease": "인슐린 저항성",
        "keywords_ko": "혈당 스파이크 피로 졸림 식후 혈당",
        "pubmed_query": "insulin resistance blood sugar spike"
    }
],

"피부": [
    {
        "disease": "피부염",
        "keywords_ko": "미세먼지 피부 트러블 염증 피부 장벽",
        "pubmed_query": "air pollution skin inflammation barrier"
    },
    {
        "disease": "피부 장벽 손상",
        "keywords_ko": "건조 가려움 피부 보호막 손상",
        "pubmed_query": "skin barrier damage pollution"
    }
],

"염증": [
    {
        "disease": "만성 염증",
        "keywords_ko": "미세먼지 염증 반응 산화 스트레스",
        "pubmed_query": "chronic inflammation oxidative stress pollution"
    }
],


    "심장": [
        {
            "disease": "관상동맥질환(협심증)",
            "keywords_ko": "동맥경화, LDL, 염증, 플라크, 스타틴, 스텐트",
            "pubmed_query": "coronary artery disease AND (atherosclerosis OR LDL OR inflammation OR plaque OR statin OR stent)",
        },
        {
            "disease": "심근경색(급성 심근경색)",
            "keywords_ko": "혈전, 재관류, 트로포닌, 스텐트, 염증",
            "pubmed_query": "myocardial infarction AND (thrombosis OR reperfusion OR troponin OR stent OR inflammation)",
        },
        {
            "disease": "심부전(HFpEF/HFrEF)",
            "keywords_ko": "심장 리모델링, 울혈, BNP, SGLT2 억제제, 염증",
            "pubmed_query": "heart failure AND (HFpEF OR HFrEF OR SGLT2 inhibitor OR BNP OR remodeling)",
        },
        {
            "disease": "심방세동",
            "keywords_ko": "뇌졸중 예방, 항응고제(DOAC), 카테터 절제술, 심박수 조절",
            "pubmed_query": "atrial fibrillation AND (DOAC OR anticoagulation OR stroke prevention OR catheter ablation)",
        },
        {
            "disease": "고혈압(심혈관 위험)",
            "keywords_ko": "혈압 변동성, 염분, 혈관 탄성, 심혈관 위험, 생활습관",
            "pubmed_query": "hypertension AND (blood pressure variability OR salt intake OR arterial stiffness OR cardiovascular risk)",
        },
        {
            "disease": "심근염",
            "keywords_ko": "바이러스, 심장 MRI, 염증, 흉통, 트로포닌",
            "pubmed_query": "myocarditis AND (cardiac MRI OR inflammation OR troponin OR viral)",
        },
    ],
    "신장": [
        {
            "disease": "만성 신장질환(CKD)",
            "keywords_ko": "단백뇨, 혈압, 미세혈관 손상, 염증, 당뇨",
            "pubmed_query": "chronic kidney disease AND (proteinuria OR blood pressure OR microvascular OR inflammation OR diabetes)",
        },
        {
            "disease": "신부전(말기 신부전)",
            "keywords_ko": "투석, 체액 과다, 빈혈, 칼륨, 인 조절",
            "pubmed_query": "end stage renal disease AND (dialysis OR fluid overload OR anemia OR potassium OR phosphate)",
        },
        {
            "disease": "당뇨병성 신증",
            "keywords_ko": "혈당, 알부민뇨, 사구체, RAAS, SGLT2 억제제",
            "pubmed_query": "diabetic nephropathy AND (albuminuria OR glomerular OR RAAS OR SGLT2 inhibitor)",
        },
    ],
    "간": [
        {
            "disease": "지방간(NAFLD/MASLD)",
            "keywords_ko": "인슐린 저항성, 체중, 중성지방, 염증, 섬유화",
            "pubmed_query": "fatty liver AND (NAFLD OR MASLD OR insulin resistance OR fibrosis OR inflammation)",
        },
        {
            "disease": "간염(만성 B/C형 간염)",
            "keywords_ko": "바이러스, 항바이러스 치료, 간암 위험, 섬유화",
            "pubmed_query": "chronic hepatitis AND (antiviral therapy OR fibrosis OR hepatocellular carcinoma risk)",
        },
    ],
    "폐": [
        {
            "disease": "천식",
            "keywords_ko": "기관지 염증, 알레르기, 흡입 스테로이드, 트리거 관리",
            "pubmed_query": "asthma AND (airway inflammation OR inhaled corticosteroid OR trigger management)",
        },
        {
            "disease": "COPD(만성폐쇄성폐질환)",
            "keywords_ko": "흡연, 호흡곤란, 폐기능, 재활, 악화 예방",
            "pubmed_query": "COPD AND (smoking OR pulmonary rehabilitation OR exacerbation prevention OR lung function)",
        },
    ],
}

TONES = ["다큐", "설명형", "반전형"]
BASE_YEARS = [1980, 1990, 2000]

# =========================================================
# 고정 4컷 템플릿 (완전 고정) - 기존 유지
# =========================================================
FIXED_4CUT_TEMPLATE = {
    "past_cut1": """
Biological Autopsy diorama of {organ} displayed on a stainless pathology table,
retro 1985 newspaper aesthetic lighting and props (old lab clipboard, analog instruments),
1:87 miniature scientists observing with ladders and ropes,
subtle magenta MRI scan lines faintly sweeping across the scene,
hyper realistic, cinematic medical lighting,
vertical 9:16, shallow depth of field, no text overlay
""".strip(),
    "past_cut2": """
Biological Autopsy diorama close-up of the outer structural barrier of the {organ},
tactile micro-structure terrain representation,
1:87 miniature scientists climbing ladders and using ropes to inspect the surface,
retro 1985 lab mood with analog tools,
subtle magenta MRI scan lines,
hyper realistic, cinematic medical lighting,
vertical 9:16, no text overlay
""".strip(),
    "present_cut1": """
Biological Autopsy diorama cross-section of functional tissue inside the {organ} like a cutaway model,
clean modern pathology lab, digital instruments, sterile premium medical lighting,
1:87 miniature scientists walking on catwalks examining micro-structures with tiny instruments,
subtle magenta MRI scan lines highlighting key pathways,
hyper realistic, cinematic medical lighting,
vertical 9:16, no text overlay
""".strip(),
    "present_cut2": """
Biological Autopsy diorama macro cutaway of microvascular network around the {organ},
mild inflammation indicated by subtle redness and immune-cell-like forms,
1:87 miniature scientists using ropes to traverse vessel ridges,
clean modern medical environment,
subtle magenta MRI scan lines tracing perfusion,
hyper realistic, cinematic medical lighting,
vertical 9:16, no text overlay
""".strip(),
}

# =========================================================
# Prompt snippets
# =========================================================
INFOGRAPHIC_5CUT_RULES = """
==============================
[5컷 인포그래피 생성 규칙]
==============================
대본의 흐름(시간적 변화, 증상 악화, 완화 등)에 맞춰 몸속 내부 구조의 변화를 시각적으로 보여주는 5개의 씬을 기획하라.
반드시 대본 내용과 일치해야 하며, 몸 속 장기에서 일어나는 현상으로 번역하여 표현한다. (설명이나 텍스트 불포함)

JSON 배열 `infographic_scene_concepts_5cuts` 를 리턴할 것.
배열 속 각 객체는 다음과 같이 구성된다:
- organ_ko: 타겟 장기명 (뇌, 심장, 폐, 간, 위, 장, 신장, 혈관 등 1단어 한글)
- scene_title: 해당 장면의 시각적 초점이나 단계 (한글)
- scene_direction_en: 장기 표면에 일어나는 오염, 입자, 색상 변화 등 시각적 묘사를 '영어로' 작성
""".strip()

SOKBOGO_5CUT_RULES = """
==============================
[속보고 5컷 이미지 프롬프트 생성 규칙]
==============================
대본의 흐름에 맞춰 5개의 이미지 씬을 기획하라. 배열 `sokbogo_image_prompts_5cuts` 를 리턴할 것.

- 컷 1~2: [내부 장기 디오라마]
  대본에 등장하는 핵심 신체 내부/장기(예: 콧속 비강, 피부 장벽, 위장, 간, 탈모 두피 등 대본에 맞는 정확한 명칭)를 배경으로 한 1:87 스케일 미니어처 과학자 생물학 연구 디오라마.
  컷 1은 '증상이 좋을 때/평상시', 컷 2는 '증상이 나빠졌을 때/오염/손상된 상태'.
  *주의: 무작정 Brain(뇌)라고 쓰지 말고, 대본의 타겟 장기를 정확히 영어로 특정할 것!
  -> JSON 형태: {"type": "diorama", "organ_en": "Nasal cavity / Stomach / Hair follicle / Skin barrier 등 영어 장기명", "scene_direction_en": "영어 시각적 묘사"}

- 컷 3~5: [실제 한국인 일상]
  대본 시나리오 내용(증상 발현, 고통, 해결책 등)에 맞는 실제 한국인(Korean people)의 실사 이미지. (디오라마/미니어처 절대 금지)
  등장인물은 반드시 한국 사람이어야 한다.
  -> JSON 형태: {"type": "real_human", "scene_direction_en": "Korean person experiencing the symptom..."}
""".strip()

VIDEO_MOTION_RULES = """
==============================
[영상 프롬프트(4컷) 규칙]
==============================
- 4컷 영상 프롬프트는 인포그래피 4컷(LLM)과 동일 장면을 기반으로 8초 구성.
- 과한 움직임 금지.
- 허용: slow subtle zoom in OR gentle micro pan OR faint MRI line sweep
- 금지: 빠른 줌, 급격한 오비트, 흔들림, 과한 광원/폭발/변형 효과
""".strip()

THUMBNAIL_STYLE_RULES_NEWTRO = """
==============================
[썸네일 문구 스타일 - 뉴트로 칠공]
==============================
- 10~14자 내외 권장
- "1980 vs 지금" 대비 느낌 포함
- 짧고 강하게
- 질문형/반전형/충격형 섞어서 4개
- 질환명 또는 장기 키워드 1개 포함
""".strip()

THUMBNAIL_STYLE_RULES_SOKBOGO = """
==============================
[썸네일 문구 스타일 - 속보고]
==============================
- 10~14자 내외 권장
- 증상/몸속/개선(희망) 느낌
- 공포팔이 금지(단정/협박 표현 금지)
- 질문형/호기심형 섞어서 4개
- 장기 키워드 1개 포함
""".strip()

THUMBNAIL_STYLE_RULES_KIMLEE = """
==============================
[썸네일 문구 스타일 - 김앤리(연구소)]
==============================
- 4~8글자 강한 단어(실험/보고서/혈관/간/당뇨/수면 등)
- 귀엽지만 신뢰감
- 과장/공포 금지
- 4개
""".strip()

EASY_SCRIPT_RULES = """
==============================
[대본 규칙: 60초 이내 + 쉬운 말]
==============================
- 대본은 반드시 60초를 넘지 말 것.
- 어려운 의학용어 최소화. 꼭 필요하면 1번만 쓰고 바로 쉬운 말로 풀기.
- 문장 짧게, 대화체.
- 숫자/수치/약물명 과다 금지(필요하면 1개만).
- 공포 조장/단정 금지. "가능성/경향" 수준으로 표현.
""".strip()

# =========================================================
# PubMed (NCBI E-utilities)
# =========================================================
NCBI_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
UA_HEADERS = {"User-Agent": "sokbogo-newtro/1.0 (streamlit app)"}

@st.cache_data(ttl=60 * 60, show_spinner=False)
def pubmed_search_pmids(query: str, years_back: int = 5, retmax: int = 3) -> List[str]:
    now = datetime.now(timezone.utc)
    start_year = now.year - max(1, int(years_back))
    mindate = f"{start_year}/01/01"
    maxdate = f"{now.year}/12/31"

    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": str(retmax),
        "sort": "pub+date",
        "mindate": mindate,
        "maxdate": maxdate,
        "datetype": "pdat",
    }
    r = requests.get(f"{NCBI_EUTILS}/esearch.fcgi", params=params, headers=UA_HEADERS, timeout=10)
    r.raise_for_status()
    j = r.json()
    pmids = j.get("esearchresult", {}).get("idlist", []) or []
    return [str(x) for x in pmids]

@st.cache_data(ttl=60 * 60, show_spinner=False)
def pubmed_fetch_abstracts(pmids: List[str]) -> List[Dict[str, str]]:
    if not pmids:
        return []

    ids = ",".join(pmids)
    params = {"db": "pubmed", "id": ids, "retmode": "xml"}
    r = requests.get(f"{NCBI_EUTILS}/efetch.fcgi", params=params, headers=UA_HEADERS, timeout=15)
    r.raise_for_status()
    xml = r.text

    articles: List[Dict[str, str]] = []
    blocks = re.split(r"</PubmedArticle>", xml)
    for b in blocks:
        if "<PubmedArticle>" not in b:
            continue

        def pick(tag: str) -> str:
            m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", b, flags=re.DOTALL)
            if not m:
                return ""
            t = re.sub(r"<[^>]+>", " ", m.group(1))
            t = re.sub(r"\s+", " ", t).strip()
            return t

        pmid = pick("PMID")
        title = pick("ArticleTitle")
        abs_parts = re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>", b, flags=re.DOTALL)
        abstract = " ".join([re.sub(r"<[^>]+>", " ", x) for x in abs_parts])
        abstract = re.sub(r"\s+", " ", abstract).strip()

        year = pick("Year")
        month = pick("Month")
        day = pick("Day")
        pubdate = " ".join([x for x in [year, month, day] if x]).strip()

        if pmid and (title or abstract):
            articles.append({"pmid": pmid.strip(), "title": title.strip(), "pubdate": pubdate.strip(), "abstract": abstract.strip()})

    pmid_index = {p: i for i, p in enumerate(pmids)}
    articles.sort(key=lambda x: pmid_index.get(x["pmid"], 9999))
    return articles

def get_recent_evidence(pubmed_query: str, years_back: int, max_papers: int) -> Tuple[List[Dict[str, str]], Optional[str]]:
    try:
        pmids = pubmed_search_pmids(pubmed_query, years_back=years_back, retmax=max_papers)
        if not pmids:
            return [], "최근 PubMed 검색 결과가 없습니다. (프리셋을 바꾸거나 범위를 늘려보세요.)"
        articles = pubmed_fetch_abstracts(pmids)
        if not articles:
            return [], "최근 논문 정보를 가져왔지만 초록(abstract) 파싱에 실패했습니다."
        return articles[:max_papers], None
    except Exception as e:
        return [], f"최근 건강정보 자동 검색 실패: {e}"

# =========================================================
# OpenAI JSON Call
# =========================================================
def call_openai_json(system: str, user: str) -> Dict[str, Any]:
    instruction = """
반드시 JSON만 출력하라.
아래 구조의 JSON 객체 1개만 반환하라. 추가 텍스트 금지.

{
  "topic": "...",
  "hook": "...",
  "script_30s": "...",
  "infographic_scene_concepts_5cuts": [
    {
      "organ_ko": "한글 장기명(예: 뇌, 심장, 혈관)",
      "scene_title": "장면 목적",
      "scene_direction_en": "English description of organ's condition and changes"
    }
  ],
  "sokbogo_image_prompts_5cuts": [
    {
      "type": "diorama 또는 real_human",
      "organ_en": "Target Organ in English (디오라마일 경우 필수, 사람일 경우 빈칸)",
      "scene_direction_en": "Detailed english visual prompt"
    }
  ],
  "video_prompts_4cuts": {
    "past_cut1": "...",
    "past_cut2": "...",
    "present_cut1": "...",
    "present_cut2": "..."
  },
  "evidence_summary_2lines": "...",
  "action_tips": ["...", "...", "..."],
  "upload": {
    "title": "...",
    "description2lines": "...",
    "hashtags": "...",
    "pinned_comment": "...",
    "thumbnail_text_candidates": ["...", "...", "...", "..."]
  },
  "sources": [
    {"type": "pubmed", "id": "PMID", "title": "...", "year": "..."}
  ]
}
""".strip()

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": instruction + "\n\n" + user},
        ],
        temperature=0.6,
    )

    text = resp.choices[0].message.content or ""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError("JSON 응답을 찾지 못했습니다. (모델 출력 확인 필요)")
    return json.loads(text[start : end + 1])

# =========================================================
# 60초 초과 방지: 간단 추정 + 자동 축약
# =========================================================
def estimate_speech_seconds_korean(text: str) -> float:
    if not text:
        return 0.0
    t = re.sub(r"\s+", "", text)
    chars = len(t)
    return chars / 6.0  # 6자/초 보수 추정

def build_kimlee_topic(disease: str, keywords_ko: str, max_keywords: int = 3) -> str:
    # 쉼표 기준으로 키워드 추출
    kws = [k.strip() for k in (keywords_ko or "").split(",") if k.strip()]
    kws = kws[:max_keywords]
    if kws:
        return f"{disease} — " + ", ".join(kws)
    return disease


def shorten_script_to_60s_easy(original_script: str, channel: str) -> str:
    system = f"""
너는 건강 쇼츠 나레이션 편집자다.
{EASY_SCRIPT_RULES}
- 원문 의미는 유지하되 더 짧고 더 쉬운 말로 고쳐라.
- 반드시 60초 이내가 되도록 분량을 줄여라.
- 채널 톤: {channel}
출력은 오직 '수정된 대본 텍스트'만.
""".strip()

    user = f"""
[원문 대본]
{original_script}

[요청]
- 60초를 넘지 않게 줄여줘.
- 전문용어 줄이고 초등학생도 이해할 만큼 쉽게.
- 마지막은 희망/실천으로 끝내기(공포 금지).
""".strip()

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
    )
    text = resp.choices[0].message.content or ""
    return text.strip()

# =========================
# Sokbogo output package
# =========================


from pathlib import Path
from datetime import datetime
import re

BASE_OUTPUT_DIR = Path("outputs")
REMOTION_PROJECT_DIR = Path(os.getenv("REMOTION_PROJECT_DIR", str(BASE_DIR_PATH))).resolve()


def resolve_remotion_cli() -> Optional[Path]:
    candidates = [
        REMOTION_PROJECT_DIR / "node_modules" / ".bin" / "remotion.cmd",
        REMOTION_PROJECT_DIR / "node_modules" / ".bin" / "remotion",
        REMOTION_PROJECT_DIR / "node_modules" / ".bin" / "remotion.ps1",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    global_cli = shutil.which("remotion")
    if global_cli:
        return Path(global_cli).resolve()

    return None


def quote_shell_arg(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def run_remotion_cli(args: List[str], check: bool) -> subprocess.CompletedProcess:
    remotion_cli = resolve_remotion_cli()
    if remotion_cli is None:
        raise FileNotFoundError("Remotion CLI executable was not found.")

    if os.name == "nt" and remotion_cli.suffix.lower() in {".cmd", ".bat"}:
        command = " ".join([quote_shell_arg(str(remotion_cli))] + [quote_shell_arg(arg) for arg in args])
        return subprocess.run(
            command,
            cwd=str(REMOTION_PROJECT_DIR),
            capture_output=True,
            text=True,
            check=check,
            shell=True,
        )

    return subprocess.run(
        [str(remotion_cli), *args],
        cwd=str(REMOTION_PROJECT_DIR),
        capture_output=True,
        text=True,
        check=check,
    )

def safe_name(text: str):
    return re.sub(r"\W+", "_", text)[:40]

def make_output_dir(channel: str, topic: str):
    folder = BASE_OUTPUT_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name(channel)}_{safe_name(topic)}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder

def save_text(path, text):
    path.write_text(text, encoding="utf-8")

def build_sokbogo_output_package(topic: str, script_text: str):
    output_dir = make_output_dir("sokbogo", topic)
    script_path = output_dir / "script.txt"
    save_text(script_path, script_text)

    return {
        "output_dir": str(output_dir),
        "script_path": str(script_path),
    }


def split_script_into_scene_texts(script_text: str, scene_count: int) -> List[str]:
    cleaned = re.sub(r"\s+", " ", (script_text or "").strip())
    if not cleaned:
        return [""] * scene_count

    sentences = [s.strip() for s in re.split(r"(?<=[.!?。！？])\s+|(?<=다\.)\s+|(?<=요\.)\s+", cleaned) if s.strip()]
    if not sentences:
        sentences = [cleaned]

    buckets: List[List[str]] = [[] for _ in range(scene_count)]
    for index, sentence in enumerate(sentences):
        buckets[index % scene_count].append(sentence)

    return [" ".join(bucket).strip() for bucket in buckets]


def split_scene_text_to_lines(scene_text: str, max_lines: int = 3) -> List[str]:
    text = re.sub(r"\s+", " ", (scene_text or "").strip())
    if not text:
        return []

    sentence_parts = [part.strip() for part in re.split(r"(?<=[.!?。！？])\s+", text) if part.strip()]
    if len(sentence_parts) >= 2:
        return sentence_parts[:max_lines]

    chunks = [part.strip() for part in re.split(r",\s*| 그리고 | 하지만 | 그래서 | 혹시 | 또는 ", text) if part.strip()]
    if len(chunks) >= 2:
        return chunks[:max_lines]

    words = text.split()
    if len(words) <= 4:
        return [text]

    chunk_size = max(2, len(words) // max_lines)
    lines: List[str] = []
    for index in range(0, len(words), chunk_size):
        lines.append(" ".join(words[index:index + chunk_size]).strip())
        if len(lines) == max_lines:
            break

    return [line for line in lines if line]


def estimate_scene_duration_frames(text: str, fps: int = 30) -> int:
    seconds = estimate_speech_seconds_korean(text or "")
    estimated = int(round(max(2.5, min(5.5, seconds)) * fps))
    return max(75, estimated)


def generate_images_from_prompts(output_dir: Path, image_prompts: List[str]) -> List[str]:
    images_dir = output_dir / "public" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    generated_paths: List[str] = []
    for index, prompt in enumerate(image_prompts, start=1):
        response = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1536",
        )
        image_base64 = response.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)
        image_path = images_dir / f"scene{index}.png"
        image_path.write_bytes(image_bytes)
        generated_paths.append(str(image_path.resolve()))

    return generated_paths


def build_storyboard_manifest(
    output_dir: Path,
    topic: str,
    script_text: str,
    image_prompts: List[str],
    image_paths: List[str],
) -> Dict[str, Any]:
    scenes_text = split_script_into_scene_texts(script_text, max(len(image_paths), 1))
    scenes: List[Dict[str, Any]] = []

    for index, image_path in enumerate(image_paths):
        scenes.append(
            {
                "id": index + 1,
                "imagePath": image_path,
                "prompt": image_prompts[index] if index < len(image_prompts) else "",
                "caption": scenes_text[index] if index < len(scenes_text) else "",
                "durationInFrames": 90,
            }
        )

    manifest = {
        "topic": topic,
        "script": script_text,
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "scenes": scenes,
    }

    manifest_path = output_dir / "storyboard.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"manifest": manifest, "manifest_path": str(manifest_path.resolve())}


def sync_with_remotion_project(output_dir: Path, topic: str, image_paths: List[str], script_text: str) -> Dict[str, Any]:
    images_dir = REMOTION_PROJECT_DIR / "public" / "images"
    data_dir = REMOTION_PROJECT_DIR / "src" / "data"
    images_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    scenes_text = split_script_into_scene_texts(script_text, max(len(image_paths), 1))
    scenes: List[Dict[str, Any]] = []

    for index, source_image in enumerate(image_paths, start=1):
        target_image = images_dir / f"scene{index}.png"
        shutil.copyfile(source_image, target_image)
        caption = scenes_text[index - 1] if index - 1 < len(scenes_text) else ""
        scenes.append(
            {
                "id": index,
                "type": "hook" if index == 1 else "ending" if index == len(image_paths) else "body",
                "text": caption,
                "image": f"/images/scene{index}.png",
            }
        )

    script_json = {
        "title": topic,
        "scenes": [
            {
                "image": scene["image"],
                "text": split_scene_text_to_lines(scene["text"]),
            }
            for scene in scenes
        ],
    }
    script_json_path = data_dir / "script.json"
    script_json_path.write_text(json.dumps(script_json, ensure_ascii=False, indent=2), encoding="utf-8")

    remotion_root_path = REMOTION_PROJECT_DIR / "src" / "RemotionRoot.tsx"
    generated_index_path = REMOTION_PROJECT_DIR / "src" / "generated-index.ts"
    main_video_path = REMOTION_PROJECT_DIR / "src" / "MainVideo.tsx"
    scene_component_dir = REMOTION_PROJECT_DIR / "src" / "components"
    scene_component_dir.mkdir(parents=True, exist_ok=True)
    scene_component_path = scene_component_dir / "Scene.tsx"
    scene_component_path.write_text(
        """import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from "remotion";

export type ScriptScene = {
  image: string;
  text: string[];
};

type SceneProps = {
  scene: ScriptScene;
  sceneIndex: number;
};

const lineEnterFrame = (lineIndex: number) => 12 + lineIndex * 18;

const lineStyle = (frame: number, fps: number, lineIndex: number) => {
  const enterAt = lineEnterFrame(lineIndex);
  const progress = spring({
    fps,
    frame: Math.max(0, frame - enterAt),
    config: {damping: 170, stiffness: 140, mass: 0.9},
  });

  return {
    opacity: interpolate(frame, [enterAt - 4, enterAt + 12], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
    transform: `translateY(${interpolate(progress, [0, 1], [34, 0])}px)`,
  };
};

const TextBlock = ({scene}: {scene: ScriptScene}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 16,
        width: "100%",
      }}
    >
      {scene.text.map((line, index) => (
        <div
          key={index}
          style={{
            color: "white",
            fontSize: 54,
            fontWeight: 800,
            lineHeight: 1.2,
            letterSpacing: "-0.025em",
            textShadow: "0 6px 24px rgba(0,0,0,0.55)",
            ...lineStyle(frame, fps, index),
          }}
        >
          {line}
        </div>
      ))}
    </div>
  );
};

export const Scene = ({scene, sceneIndex}: SceneProps) => {
  const isHowToScene = sceneIndex === 1;

  return (
    <AbsoluteFill>
      <Img
        src={staticFile(scene.image.replace(/^\\/+/, ""))}
        style={{width: "100%", height: "100%", objectFit: "cover"}}
      />
      <AbsoluteFill
        style={{
          background: "linear-gradient(180deg, rgba(4,10,18,0.06) 0%, rgba(4,10,18,0.24) 50%, rgba(4,10,18,0.82) 100%)",
          padding: 52,
        }}
      >
        {isHowToScene ? (
          <div
            style={{
              minHeight: "100%",
              display: "grid",
              gridTemplateColumns: "1.2fr 0.9fr",
              gap: 24,
              alignItems: "center",
              alignContent: "center",
              width: "100%",
              maxWidth: 960,
              margin: "0 auto",
            }}
          >
            <div
              style={{
                backgroundColor: "rgba(7,12,20,0.62)",
                backdropFilter: "blur(14px)",
                border: "1px solid rgba(255,255,255,0.12)",
                borderRadius: 28,
                padding: "28px 30px",
                boxShadow: "0 12px 40px rgba(0,0,0,0.28)",
              }}
            >
              <TextBlock scene={scene} />
            </div>
            <div
              style={{
                backgroundColor: "rgba(255,255,255,0.12)",
                border: "1px solid rgba(255,255,255,0.2)",
                borderRadius: 28,
                padding: "22px 22px 26px 22px",
                alignSelf: "center",
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                minHeight: 300,
                marginTop: -40,
              }}
            >
              <div
                style={{
                  color: "rgba(255,255,255,0.82)",
                  fontSize: 26,
                  fontWeight: 700,
                  marginBottom: 12,
                  letterSpacing: "-0.03em",
                }}
              >
                사용 순서
              </div>
              <div
                style={{
                  color: "white",
                  fontSize: 34,
                  fontWeight: 800,
                  lineHeight: 1.35,
                  whiteSpace: "pre-wrap",
                }}
              >
                프롬프트 복사
                {"\\n"}AI에 붙여넣기
                {"\\n"}수면 상태 확인
              </div>
            </div>
          </div>
        ) : (
          <div
            style={{
              marginTop: "auto",
              marginBottom: 240,
              width: "100%",
              maxWidth: 920,
            }}
          >
            <div
              style={{
                backgroundColor: "rgba(7,12,20,0.56)",
                backdropFilter: "blur(12px)",
                borderRadius: 28,
                padding: "28px 30px",
                border: "1px solid rgba(255,255,255,0.1)",
              }}
            >
              <TextBlock scene={scene} />
            </div>
          </div>
        )}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
""",
        encoding="utf-8",
    )
    main_video_path.write_text(
        """import {AbsoluteFill, Sequence} from "remotion";
import scriptData from "./data/script.json";
import {Scene, ScriptScene} from "./components/Scene";

type ScriptData = {
  title: string;
  scenes: ScriptScene[];
};

const data = scriptData as ScriptData;
const scenes = data.scenes ?? [];
const FRAMES_PER_SCENE = 150;

export const MainVideo = () => {
  return (
    <AbsoluteFill style={{backgroundColor: "#050b14"}}>
      {scenes.map((scene, index) => (
        <Sequence
          key={index}
          from={index * FRAMES_PER_SCENE}
          durationInFrames={FRAMES_PER_SCENE}
        >
          <Scene scene={scene} sceneIndex={index} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
""",
        encoding="utf-8",
    )
    remotion_root_path.write_text(
        """import {Composition} from "remotion";
import scriptData from "./data/script.json";
import {MainVideo} from "./MainVideo";

export const GeneratedRoot = () => {
  const fps = 30;
  const minFramesPerScene = 150;
  const totalFrames = Math.max(
    minFramesPerScene,
    (scriptData.scenes?.length ?? 1) * minFramesPerScene
  );

  return (
    <Composition
      id="GeneratedShorts"
      component={MainVideo}
      durationInFrames={totalFrames}
      fps={fps}
      width={1080}
      height={1920}
    />
  );
};
""",
        encoding="utf-8",
    )
    generated_index_path.write_text(
        """import {registerRoot} from "remotion";
import {GeneratedRoot} from "./RemotionRoot";

registerRoot(GeneratedRoot);
""",
        encoding="utf-8",
    )

    project_storyboard_path = images_dir.parent / "storyboard.json"
    project_storyboard_path.write_text(
        json.dumps(
            {
                "topic": topic,
                "script": script_text,
                "scenes": scenes,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    local_data_dir = output_dir / "data"
    local_data_dir.mkdir(parents=True, exist_ok=True)
    local_sync_path = local_data_dir / "script.json"
    local_sync_path.write_text(json.dumps(script_json, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "project_dir": str(REMOTION_PROJECT_DIR.resolve()),
        "generated_dir": str(images_dir.resolve()),
        "video_meta_path": str(script_json_path.resolve()),
        "script_json": script_json,
        "generated_entry_path": str(generated_index_path.resolve()),
        "remotion_root_path": str(remotion_root_path.resolve()),
        "main_video_path": str(main_video_path.resolve()),
        "scene_component_path": str(scene_component_path.resolve()),
        "project_storyboard_path": str(project_storyboard_path.resolve()),
        "scenes": scenes,
    }


def render_remotion_video(output_dir: Path) -> Dict[str, Any]:
    video_dir = output_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    output_file = video_dir / "shorts.mp4"

    required_paths = [
        REMOTION_PROJECT_DIR,
        REMOTION_PROJECT_DIR / "package.json",
        REMOTION_PROJECT_DIR / "src" / "generated-index.ts",
        REMOTION_PROJECT_DIR / "src" / "RemotionRoot.tsx",
        REMOTION_PROJECT_DIR / "src" / "MainVideo.tsx",
        REMOTION_PROJECT_DIR / "src" / "components" / "Scene.tsx",
        REMOTION_PROJECT_DIR / "src" / "data" / "script.json",
    ]
    missing_paths = [str(path) for path in required_paths if not path.exists()]
    if missing_paths:
        return {
            "ok": False,
            "reason": f"missing_required_files: {', '.join(missing_paths)}",
            "output_path": str(output_file.resolve()),
            "stdout": "",
            "stderr": "",
        }

    remotion_cli = resolve_remotion_cli()
    if remotion_cli is None:
        return {
            "ok": False,
            "reason": "remotion_cli_missing",
            "output_path": str(output_file.resolve()),
            "stdout": "",
            "stderr": "",
        }

    try:
        completed = run_remotion_cli(
            ["render", "src/generated-index.ts", "GeneratedShorts", str(output_file.resolve())],
            check=True,
        )
        return {
            "ok": True,
            "output_path": str(output_file.resolve()),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except subprocess.CalledProcessError as exc:
        return {
            "ok": False,
            "reason": "render_failed",
            "output_path": str(output_file.resolve()),
            "stdout": exc.stdout,
            "stderr": exc.stderr,
        }
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "reason": f"command_not_found: {exc}",
            "output_path": str(output_file.resolve()),
            "stdout": "",
            "stderr": str(exc),
        }


def preflight_visual_pipeline() -> Tuple[bool, str]:
    required_paths = [
        REMOTION_PROJECT_DIR,
        REMOTION_PROJECT_DIR / "package.json",
    ]
    missing_paths = [str(path) for path in required_paths if not path.exists()]
    if missing_paths:
        return False, f"missing_required_paths: {', '.join(missing_paths)}"

    remotion_cli = resolve_remotion_cli()
    if remotion_cli is None:
        return False, "remotion_cli_missing"

    try:
        completed = run_remotion_cli(["versions"], check=False)
        detail = "\n".join(
            part.strip()
            for part in [completed.stdout or "", completed.stderr or ""]
            if part and part.strip()
        ).strip()
        if completed.returncode == 0:
            return True, detail or "remotion_ok"

        relaxed_success_markers = [
            "@remotion/cli",
            "Available commands:",
            "remotion render",
        ]
        if any(marker in detail for marker in relaxed_success_markers):
            return True, detail or "remotion_cli_available"

        return False, f"remotion_cli_check_failed: {detail or f'returncode={completed.returncode}'}"
    except FileNotFoundError as exc:
        return False, f"command_not_found: {exc}"


def build_visual_video_package(topic: str, script_text: str, image_prompts: List[str], render_video: bool = False) -> Dict[str, Any]:
    output_dir = make_output_dir("shorts", topic)
    script_path = output_dir / "script.txt"
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    local_script_json_path = data_dir / "script.json"
    save_text(script_path, script_text)

    visual_package: Dict[str, Any] = {
        "output_dir": str(output_dir.resolve()),
        "script_path": str(script_path.resolve()),
        "local_script_json_path": str(local_script_json_path.resolve()),
        "image_paths": [],
        "storyboard_path": "",
        "remotion_project_dir": str(REMOTION_PROJECT_DIR),
        "remotion_generated_dir": "",
        "remotion_video_meta_path": "",
        "video_path": str((output_dir / "video" / "shorts.mp4").resolve()),
        "render_ok": False,
        "render_reason": "",
        "render_stdout": "",
        "render_stderr": "",
        "preflight_status": "",
        "debug_traceback": "",
        "failure_stage": "",
    }

    try:
        preflight_ok, preflight_reason = preflight_visual_pipeline()
        visual_package["preflight_status"] = preflight_reason
        if not preflight_ok:
            visual_package["failure_stage"] = "preflight"
            visual_package["render_reason"] = f"preflight_failed: {preflight_reason}"
            local_script_json_path.write_text(
                json.dumps({"title": topic, "scenes": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return visual_package

        try:
            image_paths = generate_images_from_prompts(output_dir, image_prompts)
            visual_package["image_paths"] = image_paths
        except Exception as exc:
            visual_package["failure_stage"] = "image_generation"
            visual_package["render_reason"] = f"image_generation_failed: {exc}"
            visual_package["debug_traceback"] = traceback.format_exc()
            local_script_json_path.write_text(
                json.dumps({"title": topic, "scenes": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return visual_package

        try:
            manifest_info = build_storyboard_manifest(output_dir, topic, script_text, image_prompts, image_paths)
            visual_package["storyboard_path"] = manifest_info["manifest_path"]
        except Exception as exc:
            visual_package["failure_stage"] = "storyboard"
            visual_package["render_reason"] = f"storyboard_failed: {exc}"
            visual_package["debug_traceback"] = traceback.format_exc()
            return visual_package

        try:
            remotion_sync_info = sync_with_remotion_project(output_dir, topic, image_paths, script_text)
            visual_package["remotion_project_dir"] = remotion_sync_info.get("project_dir", visual_package["remotion_project_dir"])
            visual_package["remotion_generated_dir"] = remotion_sync_info.get("generated_dir", "")
            visual_package["remotion_video_meta_path"] = remotion_sync_info.get("video_meta_path", "")
            visual_package["remotion_root_path"] = remotion_sync_info.get("remotion_root_path", "")
            visual_package["main_video_path"] = remotion_sync_info.get("main_video_path", "")
            visual_package["scene_component_path"] = remotion_sync_info.get("scene_component_path", "")
            local_script_json_path.write_text(
                json.dumps(
                    remotion_sync_info.get("script_json", {"title": topic, "scenes": []}),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            visual_package["failure_stage"] = "remotion_sync"
            visual_package["render_reason"] = f"remotion_sync_failed: {exc}"
            visual_package["debug_traceback"] = traceback.format_exc()
            return visual_package

        if not render_video:
            visual_package["failure_stage"] = "ready_for_manual_render"
            visual_package["render_reason"] = "manual_render_pending"
            return visual_package

        try:
            render_info = render_remotion_video(output_dir)
        except Exception as exc:
            visual_package["failure_stage"] = "render_invocation"
            visual_package["render_reason"] = f"render_invocation_failed: {exc}"
            visual_package["debug_traceback"] = traceback.format_exc()
            return visual_package

        visual_package["failure_stage"] = "render"
        visual_package["video_path"] = render_info.get("output_path", visual_package["video_path"])
        visual_package["render_ok"] = render_info.get("ok", False)
        visual_package["render_reason"] = render_info.get("reason", "")
        visual_package["render_stdout"] = render_info.get("stdout", "")
        visual_package["render_stderr"] = render_info.get("stderr", "")
        return visual_package
    except Exception as exc:
        visual_package["failure_stage"] = "unexpected"
        visual_package["render_reason"] = f"unexpected_pipeline_error: {exc}"
        visual_package["debug_traceback"] = traceback.format_exc()
        return visual_package

# =========================================================
# Workspace UI
# =========================================================
RESULTS_PATH = Path("results.json")


def load_saved_results() -> List[Dict[str, Any]]:
    try:
        if RESULTS_PATH.exists():
            data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
            return data.get("results", [])
    except Exception:
        return []
    return []


def save_saved_results() -> None:
    try:
        RESULTS_PATH.write_text(
            json.dumps({"results": st.session_state.get("results", [])}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def init_session_state() -> None:
    st.session_state.setdefault("results", load_saved_results())
    st.session_state.setdefault("selected_result_index", 0)
    st.session_state.setdefault("api_key_input", get_effective_api_key())
    st.session_state.setdefault("channel", CHANNELS[0])
    st.session_state.setdefault("input_method", "프리셋 선택")
    st.session_state.setdefault("selected_category", list(PRESETS.keys())[0] if PRESETS else "")
    st.session_state.setdefault("preset_idx", 0)
    st.session_state.setdefault("custom_topic", "")
    st.session_state.setdefault("trend_input", "")
    st.session_state.setdefault("selected_topic", "")
    st.session_state.setdefault("trend_reason", "")
    st.session_state.setdefault("trend_insight", "")
    st.session_state.setdefault("trend_health_angle", "")
    st.session_state.setdefault("keywords_ko", "")
    st.session_state.setdefault("style_type", "정보형")
    st.session_state.setdefault("cut_count", 5)
    st.session_state.setdefault("output_count", 1)
    st.session_state.setdefault("tone", "다큐")
    st.session_state.setdefault("base_year", BASE_YEARS[0] if BASE_YEARS else 2000)
    st.session_state.setdefault("years_back", 5)
    st.session_state.setdefault("max_papers", 5)
    st.session_state.setdefault("use_pubmed", True)


def render_page_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1rem;
            padding-left: 1rem;
            padding-right: 1rem;
            color: #e5e7eb;
        }
        .stApp {
            background-color: #0f1720;
            color: #e5e7eb;
        }
        .stApp, .stApp p, .stApp span, .stApp label, .stApp div {
            color: #f8fafc;
        }
        .workspace-card, .result-card {
            background: #111827;
            border: 1px solid #334155;
            border-radius: 18px;
            padding: 18px;
            margin-bottom: 18px;
            box-shadow: 0 16px 40px rgba(15, 23, 42, 0.35);
        }
        .workspace-card-title, .result-card-title {
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 10px;
            color: #f8fafc;
        }
        .result-card.selected {
            border-color: #38bdf8;
            background: #0f1720;
        }
        .result-status {
            display: inline-flex;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 0.81rem;
            font-weight: 700;
            color: #f8fafc;
            margin-top: 6px;
        }
        .status-complete { background: #16a34a; }
        .status-pending { background: #f59e0b; }
        .status-error { background: #dc2626; }
        .workspace-section-label {
            color: #cbd5e1;
            margin-bottom: 8px;
            font-size: 0.94rem;
        }
        .workbench-header {
            background: linear-gradient(180deg, rgba(14, 165, 233, 0.16), transparent);
            padding: 16px;
            border-radius: 18px;
            border: 1px solid #334155;
            margin-bottom: 18px;
        }
        .stButton > button {
            border-radius: 14px;
            color: #f8fafc !important;
            background: #1f2937 !important;
            border: 1px solid #475569;
        }
        .stButton > button p,
        .stButton > button span {
            color: #f8fafc !important;
        }
        .stButton button[kind="secondary"],
        .stButton button[data-testid="baseButton-secondary"] {
            background: #1f2937 !important;
            color: #f8fafc !important;
        }
        .stTextInput label,
        .stTextInput p,
        .stSelectbox label,
        .stSelectbox p,
        .stNumberInput label,
        .stNumberInput p,
        .stSlider label,
        .stSlider p,
        .stRadio label,
        .stRadio p,
        .stCheckbox label,
        .stCheckbox p {
            color: #f8fafc !important;
        }
        .stTextInput input,
        .stNumberInput input,
        .stTextArea textarea {
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            background-color: #f8fafc !important;
            caret-color: #0f172a !important;
        }
        .stTextInput input::placeholder,
        .stTextArea textarea::placeholder {
            color: #64748b !important;
            -webkit-text-fill-color: #64748b !important;
        }
        .stNumberInput button,
        .stNumberInput button span {
            color: #0f172a !important;
        }
        .stSelectbox [data-baseweb="select"] > div,
        .stMultiSelect [data-baseweb="select"] > div {
            color: #0f172a !important;
            background-color: #f8fafc !important;
        }
        .stSelectbox [data-baseweb="select"] span,
        .stMultiSelect [data-baseweb="select"] span {
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
        }
        .stSelectbox svg,
        .stMultiSelect svg {
            fill: #0f172a !important;
        }
        .stExpander summary,
        .stExpander summary span,
        .stExpander details summary p {
            color: #f8fafc !important;
        }
        [data-testid="stExpander"] details summary {
            background: #111827 !important;
            border-radius: 12px;
        }
        .stMarkdown, .stMarkdown p, .stMarkdown li, .stCaption, .stCode {
            color: #f8fafc !important;
        }
        .stCode,
        .stCode pre,
        .stCode code,
        [data-testid="stCodeBlock"],
        [data-testid="stCodeBlock"] pre,
        [data-testid="stCodeBlock"] code {
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            background: #f8fafc !important;
        }
        [data-testid="stWidgetLabel"],
        [data-testid="stMarkdownContainer"],
        [data-testid="stExpander"] summary {
            color: #f8fafc !important;
        }
        [data-baseweb="popover"] *,
        ul[role="listbox"] *,
        li[role="option"] * {
            color: #0f172a !important;
        }
        [data-baseweb="popover"],
        ul[role="listbox"] {
            background: #f8fafc !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_selected_preset() -> Tuple[Dict[str, str], List[Dict[str, str]]]:
    category = st.session_state.get("selected_category", "")
    preset_list = PRESETS.get(category, [])
    preset_idx = st.session_state.get("preset_idx", 0)
    if preset_idx >= len(preset_list):
        st.session_state["preset_idx"] = 0
        preset_idx = 0
    selected_preset = preset_list[preset_idx] if preset_list else {}
    return selected_preset, preset_list


def build_topic_context() -> Dict[str, Any]:
    method = st.session_state["input_method"]
    category = st.session_state.get("selected_category", "")
    custom_topic = st.session_state.get("custom_topic", "").strip()
    selected_topic = st.session_state.get("selected_topic", "").strip()
    keywords_ko = st.session_state.get("keywords_ko", "")
    selected_preset, _ = get_selected_preset()

    topic = ""
    pubmed_query = ""
    keywords = keywords_ko

    if method == "프리셋 선택":
        topic = selected_preset.get("disease", "")
        keywords = selected_preset.get("keywords_ko", "")
        pubmed_query = selected_preset.get("pubmed_query", "")
    elif method == "직접 입력":
        topic = custom_topic
        pubmed_query = custom_topic
    else:
        topic = selected_topic or custom_topic
        pubmed_query = topic

    if not keywords and topic:
        keywords = topic

    return {
        "method": method,
        "channel": st.session_state.get("channel", ""),
        "category": category,
        "topic": topic,
        "keywords_ko": keywords,
        "pubmed_query": pubmed_query,
        "style_type": st.session_state.get("style_type", "정보형"),
        "cut_count": st.session_state.get("cut_count", 5),
        "output_count": st.session_state.get("output_count", 1),
        "tone": st.session_state.get("tone", "다큐"),
        "base_year": st.session_state.get("base_year", BASE_YEARS[0] if BASE_YEARS else 2000),
        "years_back": st.session_state.get("years_back", 5),
        "max_papers": st.session_state.get("max_papers", 5),
        "use_pubmed": st.session_state.get("use_pubmed", True),
        "selected_topic": selected_topic,
    }


def build_system_prompt(context: Dict[str, Any]) -> str:
    channel = context["channel"]
    base_year = context["base_year"]
    if channel == "속보고":
        return f"""
너는 '속보고' 채널의 건강 쇼츠 제작 AI다.
[전체 출력 규칙]
- 출력은 전부 한국어.
- 대본은 반드시 60초를 넘지 말 것.
- 구조: (증상/느낌) → (몸속에서 벌어질 수 있는 일) → (일상 변화 2~3개) → (희망)
- 공포팔이/단정 금지. "가능성/신호" 수준.
- 너무 전문인처럼 말하지 말고 쉽게.
{EASY_SCRIPT_RULES}
{SOKBOGO_5CUT_RULES}
{VIDEO_MOTION_RULES}
{THUMBNAIL_STYLE_RULES_SOKBOGO}
""".strip()
    if channel == "뉴트로":
        return f"""
너는 '뉴트로' 채널의 건강 쇼츠 제작 AI다.
[전체 출력 규칙]
- 출력은 전부 한국어.
- 대본은 반드시 60초를 넘지 말 것.
- 구조: 과거({base_year}년대) → 현재(2026년) → 최근 건강정보 2문장 → 행동 팁 3개 → 질문형 마무리.
- 너무 전문적으로 쓰지 말고 쉽게 설명.
- 과장/공포/단정 금지. "가능성/경향" 수준.
{EASY_SCRIPT_RULES}
{INFOGRAPHIC_5CUT_RULES}
{VIDEO_MOTION_RULES}
{THUMBNAIL_STYLE_RULES_NEWTRO}
""".strip()
    if channel == "김앤리":
        return f"""
너는 '김앤리' 연구소 채널의 건강 쇼츠 제작 AI다.
[전체 출력 규칙]
- 출력은 전부 한국어.
- 대본은 반드시 60초를 넘지 말 것.
- 연구소 채널 톤을 유지하되 딱딱하지 않게.
- 공포팔이/과장 금지.
{EASY_SCRIPT_RULES}
{INFOGRAPHIC_5CUT_RULES}
{VIDEO_MOTION_RULES}
{THUMBNAIL_STYLE_RULES_KIMLEE}
""".strip()
    return f"""
너는 건강 쇼츠 제작 AI다.
{EASY_SCRIPT_RULES}
{INFOGRAPHIC_5CUT_RULES}
{VIDEO_MOTION_RULES}
""".strip()


def build_user_prompt(context: Dict[str, Any], evidence_material: str) -> str:
    return f"""
너는 조회수 높은 유튜브 쇼츠 대본 전문가다.

다음 조건을 반드시 지켜라:
1. 첫 문장은 강한 경고, 반전, 궁금증 중 하나로 시작
2. 3초 안에 시청자가 멈추게 만들어라
3. 절대 “오늘 ~입니다”, “이번 영상은” 같은 설명형 시작 금지
4. 문장은 짧고 강하게, 쉬운 한국어로 작성
5. 전체 대본은 30~40초 분량 중심
6. 마지막은 바로 따라할 수 있는 행동 유도로 마무리

[주제]
{context["topic"]}

[설명 영역]
{context["category"]}

[최근 키워드]
{context["keywords_ko"]}

[생성 옵션]
- 컷 수: {context["cut_count"]}
- 출력 개수: {context["output_count"]}
- 톤: {context["tone"]}
- 스타일: {context["style_type"]}
- 최근 근거 범위: {context["years_back"]}년

[PubMed 재료]
{evidence_material or '(없음)'}
""".strip()


def create_result_record(context: Dict[str, Any], data: Dict[str, Any], evidence_err: Optional[str]) -> Dict[str, Any]:
    result = {
        "id": f"{int(datetime.now().timestamp())}",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "완료",
        "channel": context["channel"],
        "topic": context["topic"],
        "category": context["category"],
        "style_type": context["style_type"],
        "tone": context["tone"],
        "cut_count": context["cut_count"],
        "output_count": context["output_count"],
        "keywords_ko": context["keywords_ko"],
        "pubmed_query": context["pubmed_query"],
        "input_method": context["method"],
        "hook": data.get("hook", ""),
        "script_30s": data.get("script_30s", ""),
        "image_prompts": data.get("image_prompts", []) or [],
        "video_prompts": data.get("video_prompts_4cuts") or data.get("kimlee_sora2_video_prompts_4cuts") or {},
        "upload": data.get("upload", {}) or {},
        "visual_package": data.get("visual_package", {}) or {},
        "evidence_summary_2lines": data.get("evidence_summary_2lines", ""),
        "action_tips": data.get("action_tips", []) or [],
        "sources": data.get("sources", []) or [],
        "raw_data": data,
        "warnings": evidence_err or "",
    }
    if context["channel"] == "김앤리":
        result["kimlee_image_prompt"] = data.get("kimlee_image_prompt", "")
    return result


def ensure_openai_ready() -> bool:
    if client is not None:
        return True
    st.error("OpenAI API 키가 없습니다. 왼쪽 설정 패널에서 키를 입력하고 저장해주세요.")
    return False


def generate_new_result() -> None:
    if not ensure_openai_ready():
        return

    context = build_topic_context()
    if not context["topic"]:
        st.warning("생성할 주제를 먼저 입력하거나 프리셋을 선택하세요.")
        return

    if context["method"] == "트렌드 키워드 기반" and not context["selected_topic"]:
        st.warning("트렌드 키워드를 먼저 변환해서 주제를 확정하세요.")
        return

    evidence_err = None
    evidence_articles = []
    if context["use_pubmed"]:
        with st.spinner("최근 근거(PubMed)를 수집 중입니다..."):
            evidence_articles, evidence_err = get_recent_evidence(
                pubmed_query=context["pubmed_query"],
                years_back=context["years_back"],
                max_papers=context["max_papers"],
            )

    evidence_material = []
    for article in evidence_articles:
        abstract = article.get("abstract", "") or ""
        if len(abstract) > 350:
            abstract = abstract[:350] + "..."
        evidence_material.append(
            f"- PMID:{article.get('pmid', '')} | {article.get('title', '')} ({article.get('pubdate', '')})\n  초록: {abstract}"
        )

    system_prompt = build_system_prompt(context)
    user_prompt = build_user_prompt(context, "\n".join(evidence_material))

    with st.spinner("쇼츠 패키지를 생성 중입니다. 잠시만 기다려주세요..."):
        try:
            raw_data = call_openai_json(system_prompt, user_prompt)
        except AuthenticationError:
            st.error("OpenAI API 키 인증에 실패했습니다. `.streamlit/secrets.toml`의 `OPENAI_API_KEY`를 새 키로 바꿔주세요.")
            st.info("새 키 발급: https://platform.openai.com/api-keys")
            return
        except Exception as e:
            st.error("생성 중 오류가 발생했습니다.")
            st.exception(e)
            return

    script = (raw_data.get("script_30s") or "").strip()
    if script:
        secs = estimate_speech_seconds_korean(script)
        if secs > 60:
            with st.spinner(f"대본이 {secs:.0f}초로 추정되어 60초 이내로 자동 축약 중..."):
                raw_data["script_30s"] = shorten_script_to_60s_easy(script, context["channel"])

    final_topic = context["topic"] or context["keywords_ko"] or "건강 쇼츠 주제"
    if context["channel"] == "김앤리":
        raw_data["kimlee_image_prompt"] = KIMLEE_COVER_PROMPT_TEMPLATE.format(topic=final_topic)
        raw_data["kimlee_sora2_video_prompts_4cuts"] = {
            key: template.format(topic=final_topic)
            for key, template in KIMLEE_SORA2_VIDEO_4CUT_TEMPLATE.items()
        }

    if context["channel"] == "속보고":
        final_script = (raw_data.get("script_30s") or "").strip()
        if final_script:
            try:
                package_result = build_sokbogo_output_package(topic=final_topic, script_text=final_script)
                st.session_state["sokbogo_output_dir"] = package_result["output_dir"]
            except Exception as e:
                st.warning(f"속보고 결과물 저장 실패: {e}")

    raw_data["image_prompts"] = generate_lifestyle_image_prompts(
        topic=final_topic,
        script_text=raw_data.get("script_30s", ""),
        scene_count=3,
    )

    raw_data["visual_package"] = {
        "output_dir": "",
        "script_path": "",
        "local_script_json_path": "",
        "image_paths": [],
        "storyboard_path": "",
        "remotion_project_dir": str(REMOTION_PROJECT_DIR),
        "remotion_generated_dir": "",
        "remotion_video_meta_path": "",
        "video_path": "",
        "render_ok": False,
        "render_reason": "manual_image_generation_pending",
        "failure_stage": "waiting_for_manual_image_generation",
        "render_stdout": "",
        "render_stderr": "",
        "debug_traceback": "",
        "preflight_status": "",
    }

    result = create_result_record(context, raw_data, evidence_err)
    st.session_state["results"].append(result)
    st.session_state["selected_result_index"] = len(st.session_state["results"]) - 1
    save_saved_results()
    save_last_result(raw_data)
    st.success("생성 완료. 오른쪽 목록에서 결과를 선택할 수 있습니다.")


def delete_selected_result() -> None:
    results = st.session_state.get("results", [])
    idx = st.session_state.get("selected_result_index", 0)
    if not results:
        return
    results.pop(idx)
    if idx >= len(results):
        st.session_state["selected_result_index"] = max(0, len(results) - 1)
    save_saved_results()
    st.success("선택된 결과를 삭제했습니다.")


def get_selected_result_for_action() -> Optional[Tuple[List[Dict[str, Any]], int, Dict[str, Any]]]:
    results = st.session_state.get("results", [])
    if not results:
        st.warning("먼저 소스 패키지를 생성해 주세요.")
        return None

    idx = st.session_state.get("selected_result_index", 0)
    if idx >= len(results):
        idx = max(0, len(results) - 1)
        st.session_state["selected_result_index"] = idx

    return results, idx, results[idx]


def generate_images_for_selected_result() -> None:
    if not ensure_openai_ready():
        return

    selected = get_selected_result_for_action()
    if not selected:
        return

    results, idx, result = selected
    topic = (result.get("topic") or "").strip()
    script_text = (result.get("script_30s") or "").strip()
    image_prompts = result.get("image_prompts", []) or []

    if not topic or not script_text:
        st.warning("선택한 결과에 주제 또는 대본이 없습니다. 먼저 소스 패키지를 다시 생성해 주세요.")
        return

    if not image_prompts:
        image_prompts = generate_lifestyle_image_prompts(topic=topic, script_text=script_text, scene_count=3)
        result["image_prompts"] = image_prompts
        result.setdefault("raw_data", {})["image_prompts"] = image_prompts

    with st.spinner("이미지를 생성하고 Remotion 프로젝트와 동기화하는 중입니다..."):
        visual_package = build_visual_video_package(
            topic=topic,
            script_text=script_text,
            image_prompts=image_prompts,
            render_video=False,
        )

    result["visual_package"] = visual_package
    result.setdefault("raw_data", {})["visual_package"] = visual_package
    results[idx] = result
    save_saved_results()
    save_last_result(result.get("raw_data", {}))

    if visual_package.get("image_paths"):
        st.success("이미지 생성과 파일 저장이 완료되었습니다. 필요한 파일을 채운 뒤 렌더링 버튼을 눌러주세요.")
    else:
        st.warning(f"이미지 생성 단계가 완료되지 않았습니다: {visual_package.get('render_reason', 'unknown')}")


def render_selected_result_video() -> None:
    selected = get_selected_result_for_action()
    if not selected:
        return

    results, idx, result = selected
    visual_package = result.get("visual_package", {}) or {}
    output_dir_str = (visual_package.get("output_dir") or "").strip()

    if not output_dir_str or not visual_package.get("image_paths"):
        st.warning("먼저 이미지 생성 버튼으로 이미지와 script.json을 준비해 주세요.")
        return

    output_dir = Path(output_dir_str)
    with st.spinner("현재 준비된 파일 기준으로 영상을 렌더링하는 중입니다..."):
        preflight_ok, preflight_reason = preflight_visual_pipeline()
        visual_package["preflight_status"] = preflight_reason
        if not preflight_ok:
            visual_package["render_ok"] = False
            visual_package["failure_stage"] = "preflight"
            visual_package["render_reason"] = f"preflight_failed: {preflight_reason}"
        else:
            render_info = render_remotion_video(output_dir)
            visual_package["video_path"] = render_info.get("output_path", visual_package.get("video_path", ""))
            visual_package["render_ok"] = render_info.get("ok", False)
            visual_package["failure_stage"] = "render"
            visual_package["render_reason"] = render_info.get("reason", "")
            visual_package["render_stdout"] = render_info.get("stdout", "")
            visual_package["render_stderr"] = render_info.get("stderr", "")
            visual_package["debug_traceback"] = ""

    result["visual_package"] = visual_package
    result.setdefault("raw_data", {})["visual_package"] = visual_package
    results[idx] = result
    save_saved_results()
    save_last_result(result.get("raw_data", {}))

    if visual_package.get("render_ok"):
        st.success(f"영상 렌더 완료: {visual_package.get('video_path', '')}")
    else:
        st.warning(f"영상 렌더가 완료되지 않았습니다: {visual_package.get('render_reason', 'unknown')}")


def render_sidebar_settings() -> None:
    global api_key, client

    st.markdown("<div class='workspace-card'>", unsafe_allow_html=True)
    st.markdown("<div class='workspace-card-title'>설정 패널</div>", unsafe_allow_html=True)

    st.markdown("<div class='workspace-section-label'>0. OpenAI API 키</div>", unsafe_allow_html=True)
    st.session_state["api_key_input"] = st.text_input(
        "OPENAI_API_KEY",
        value=st.session_state.get("api_key_input", ""),
        type="password",
        placeholder="sk-proj-...",
        help="여기에 저장하면 `.streamlit/local_settings.json`에 유지됩니다.",
    )
    if api_key:
        masked = f"{api_key[:7]}...{api_key[-4:]}" if len(api_key) > 12 else "저장됨"
        st.caption(f"현재 적용된 키: {masked}")
    else:
        st.caption("현재 적용된 키가 없습니다.")
    if st.button("API 키 저장", use_container_width=True):
        new_key = st.session_state.get("api_key_input", "").strip()
        if new_key:
            save_local_settings({"OPENAI_API_KEY": new_key})
            api_key, client = rebuild_openai_client()
            st.session_state["api_key_input"] = api_key
            st.success("API 키를 로컬에 저장했습니다.")
            st.rerun()
        else:
            st.warning("저장할 API 키를 입력해주세요.")
    if st.button("저장된 API 키 삭제", use_container_width=True):
        save_local_settings({})
        api_key, client = rebuild_openai_client()
        st.session_state["api_key_input"] = api_key
        st.success("로컬에 저장된 API 키를 삭제했습니다.")
        st.rerun()

    st.markdown("<div class='workspace-section-label'>1. 채널 & 입력 방식</div>", unsafe_allow_html=True)
    st.session_state["channel"] = st.selectbox("채널", CHANNELS, index=CHANNELS.index(st.session_state["channel"]))
    st.session_state["input_method"] = st.radio(
        "주제 입력 방식",
        ["프리셋 선택", "직접 입력", "트렌드 키워드 기반"],
        index=["프리셋 선택", "직접 입력", "트렌드 키워드 기반"].index(st.session_state["input_method"]),
        horizontal=True,
    )

    st.markdown("<div class='workspace-section-label'>2. 설명 · 주제 · 키워드</div>", unsafe_allow_html=True)
    if st.session_state["input_method"] == "프리셋 선택":
        category_keys = list(PRESETS.keys())
        selected_category = st.session_state.get("selected_category", category_keys[0] if category_keys else "")
        st.session_state["selected_category"] = st.selectbox(
            "설명 영역(카테고리)",
            category_keys,
            index=category_keys.index(selected_category) if selected_category in category_keys else 0,
        )
        _, preset_list = get_selected_preset()
        if preset_list:
            st.session_state["preset_idx"] = st.selectbox(
                "질환명(추천)",
                range(len(preset_list)),
                format_func=lambda i: preset_list[i].get("disease", ""),
                index=st.session_state.get("preset_idx", 0),
            )
        else:
            st.warning("현재 선택된 카테고리에 등록된 프리셋이 없습니다.")
    elif st.session_state["input_method"] == "직접 입력":
        st.session_state["custom_topic"] = st.text_input(
            "직접 입력 주제",
            value=st.session_state.get("custom_topic", ""),
            placeholder="예: 봄철 알레르기 비염 예방법",
        )
        st.session_state["keywords_ko"] = st.text_input(
            "최근 건강 키워드",
            value=st.session_state.get("keywords_ko", ""),
            placeholder="예: 비염, 알레르기, 코 건강",
        )
    else:
        st.session_state["trend_input"] = st.text_input(
            "트렌드 키워드 입력",
            value=st.session_state.get("trend_input", ""),
            placeholder="예: 미세먼지, 수면부족",
        )
        if st.button("트렌드 주제 변환", use_container_width=True):
            if not st.session_state["trend_input"]:
                st.warning("트렌드 키워드를 먼저 입력하세요.")
            elif not ensure_openai_ready():
                pass
            else:
                with st.spinner("트렌드 키워드를 쇼츠 주제로 변환 중..."):
                    trend_info = get_llm_trend_pick(st.session_state["trend_input"], client, model)
                if trend_info.get("usable"):
                    st.session_state["selected_topic"] = trend_info.get("converted_topic", "")
                    st.session_state["trend_reason"] = trend_info.get("reason", "")
                    st.session_state["trend_insight"] = trend_info.get("insight", "")
                    st.session_state["trend_health_angle"] = trend_info.get("health_angle", "")
                    st.success(f"변환된 주제: {st.session_state['selected_topic']}")
                else:
                    st.warning("트렌드 키워드 변환에 실패했습니다. 다른 키워드를 시도하세요.")

    st.markdown("<div class='workspace-section-label'>3. 생성 옵션</div>", unsafe_allow_html=True)
    st.session_state["cut_count"] = st.select_slider("컷 수", options=[4, 5, 6], value=st.session_state.get("cut_count", 5))
    st.session_state["output_count"] = st.number_input("출력 개수", min_value=1, max_value=3, value=st.session_state.get("output_count", 1))
    st.session_state["style_type"] = st.selectbox(
        "톤앤매너",
        ["정보형", "공감형", "경고형"],
        index=["정보형", "공감형", "경고형"].index(st.session_state.get("style_type", "정보형")),
    )
    st.session_state["tone"] = st.selectbox(
        "영상 톤",
        TONES,
        index=TONES.index(st.session_state.get("tone", "다큐") if st.session_state.get("tone", "다큐") in TONES else "다큐"),
    )
    st.session_state["base_year"] = st.selectbox(
        "비교 기준 연도(뉴트로용)",
        BASE_YEARS,
        index=BASE_YEARS.index(st.session_state.get("base_year", BASE_YEARS[0])),
    )
    st.session_state["years_back"] = st.slider("최근 근거 범위(년)", min_value=1, max_value=15, value=st.session_state.get("years_back", 5))
    st.session_state["max_papers"] = st.slider("자동 참고 논문 수(PubMed)", min_value=1, max_value=8, value=st.session_state.get("max_papers", 5))
    st.session_state["use_pubmed"] = st.checkbox("최근 건강정보 자동 검색(PubMed) 사용", value=st.session_state.get("use_pubmed", True))

    st.markdown("<div class='workspace-section-label'>4. 실행 버튼</div>", unsafe_allow_html=True)
    if st.button("📦 소스 패키지 생성", type="primary", use_container_width=True):
        generate_new_result()

    st.write(" ")
    if desktop_video_tools_enabled():
        if st.button("🖼️ 선택 결과 이미지 생성", use_container_width=True):
            generate_images_for_selected_result()

        if st.button("🎬 선택 결과 렌더링", use_container_width=True):
            render_selected_result_video()
    else:
        st.caption("현재 배포 모드에서는 PC 전용 기능인 이미지 생성/렌더링 버튼이 숨겨집니다.")

    if st.button("🗑️ 선택 결과 삭제", use_container_width=True):
        delete_selected_result()

    st.markdown("</div>", unsafe_allow_html=True)


def render_main_result() -> None:
    results = st.session_state.get("results", [])
    selected_index = st.session_state.get("selected_result_index", 0)

    if not results:
        st.markdown("<div class='workspace-card'>", unsafe_allow_html=True)
        st.subheader("현재 선택된 결과가 없습니다.")
        st.write("왼쪽 설정에서 값을 입력한 뒤 '쇼츠 패키지 생성' 버튼을 눌러주세요.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if selected_index >= len(results):
        st.session_state["selected_result_index"] = 0
        selected_index = 0

    result = results[selected_index]
    st.markdown("<div class='workspace-card'>", unsafe_allow_html=True)
    st.markdown(f"<div class='workspace-card-title'>{result.get('topic', '결과 없음')}</div>", unsafe_allow_html=True)
    st.write(f"**상태**: {result.get('status', '완료')}")
    st.write(f"**채널**: {result.get('channel', '')}")
    st.write(f"**입력 방식**: {result.get('input_method', '')}")
    st.write(f"**키워드**: {result.get('keywords_ko', '')}")
    st.write(f"**생성일**: {result.get('created_at', '')}")
    st.divider()

    with st.expander("핵심 정보", expanded=True):
        st.write(f"**주제**: {result.get('topic', '')}")
        st.write(f"**설명 영역**: {result.get('category', '')}")
        st.write(f"**톤/매너**: {result.get('style_type', '')} / {result.get('tone', '')}")
        if result.get("warnings"):
            st.warning(result["warnings"])

    with st.expander("훅 / 스크립트", expanded=True):
        st.write(f"**훅:** {result.get('hook', '')}")
        st.code(result.get('script_30s', ''))

    with st.expander("이미지 프롬프트", expanded=False):
        if result.get("kimlee_image_prompt"):
            st.markdown("**커버 프롬프트**")
            st.code(result.get("kimlee_image_prompt", ""))
        for i, prompt in enumerate(result.get('image_prompts', [])[:5], 1):
            st.markdown(f"**씬 {i}**")
            st.code(prompt)

    with st.expander("영상 프롬프트", expanded=False):
        video_prompts = result.get('video_prompts', {}) or {}
        if video_prompts:
            for key, prompt in video_prompts.items():
                st.markdown(f"**{key}**")
                st.code(prompt)
        else:
            st.write("영상 프롬프트가 없습니다.")

    with st.expander("업로드 패키지", expanded=False):
        upload = result.get('upload', {}) or {}
        st.write(f"**제목 후보**: {upload.get('title', '')}")
        st.write(f"**설명(2줄)**: {upload.get('description2lines', '')}")
        st.write(f"**해시태그**: {upload.get('hashtags', '')}")
        st.write(f"**고정댓글**: {upload.get('pinned_comment', '')}")
        thumbs = upload.get('thumbnail_text_candidates', []) or []
        if thumbs:
            st.write("**썸네일 후보**")
            for t in thumbs:
                st.write(f"- {t}")

    with st.expander("이미지 / 영상 산출물", expanded=False):
        visual_package = result.get("visual_package", {}) or {}
        if not desktop_video_tools_enabled():
            st.info("이 배포 모드에서는 PC 전용 기능인 이미지 생성과 Remotion 렌더링을 숨겨두었습니다.")
        st.write(f"**출력 폴더**: {visual_package.get('output_dir', '')}")
        st.write(f"**로컬 script.json**: {visual_package.get('local_script_json_path', '')}")
        st.write(f"**Remotion 프로젝트**: {visual_package.get('remotion_project_dir', '')}")
        st.write(f"**Remotion generated 폴더**: {visual_package.get('remotion_generated_dir', '')}")
        st.write(f"**Remotion script.json**: {visual_package.get('remotion_video_meta_path', '')}")
        st.write(f"**RemotionRoot.tsx**: {visual_package.get('remotion_root_path', '')}")
        st.write(f"**MainVideo.tsx**: {visual_package.get('main_video_path', '')}")
        st.write(f"**components/Scene.tsx**: {visual_package.get('scene_component_path', '')}")
        st.write(f"**스토리보드 JSON**: {visual_package.get('storyboard_path', '')}")
        st.write(f"**영상 파일**: {visual_package.get('video_path', '')}")
        st.write(f"**렌더 상태**: {'완료' if visual_package.get('render_ok') else '미완료'}")
        if visual_package.get("preflight_status"):
            st.write(f"**사전 점검 결과**: {visual_package.get('preflight_status')}")
        if visual_package.get("failure_stage"):
            st.write(f"**실패 단계**: {visual_package.get('failure_stage')}")
        if visual_package.get("render_reason"):
            st.write(f"**렌더 사유**: {visual_package.get('render_reason')}")
        if visual_package.get("render_stderr"):
            st.code(visual_package.get("render_stderr", ""), language="text")
        if visual_package.get("debug_traceback"):
            st.write("**디버그 상세**")
            st.code(visual_package.get("debug_traceback", ""), language="text")
        image_paths = visual_package.get("image_paths", []) or []
        if image_paths:
            st.write("**생성된 이미지 파일**")
            for image_path in image_paths:
                st.write(f"- {image_path}")

    with st.expander("참고 근거 / 소스", expanded=False):
        st.write(f"**Evidence 요약**: {result.get('evidence_summary_2lines', '')}")
        sources = result.get('sources', []) or []
        if sources:
            for s in sources:
                pmid = str(s.get('id', '')).strip()
                title = s.get('title', '')
                year = s.get('year', '')
                if pmid:
                    st.markdown(f"- [PubMed {pmid} ({year})](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)  {title}")
                else:
                    st.write(f"- {title}")
        else:
            st.write("참고 소스가 없습니다.")

    st.markdown("</div>", unsafe_allow_html=True)


def render_result_list() -> None:
    results = st.session_state.get("results", [])
    selected_index = st.session_state.get("selected_result_index", 0)

    st.markdown("<div class='workspace-card'>", unsafe_allow_html=True)
    st.markdown("<div class='workspace-card-title'>생성물 목록</div>", unsafe_allow_html=True)
    st.write(f"총 {len(results)}개 결과 저장됨")

    if not results:
        st.info("아직 생성된 쇼츠 결과가 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    for idx, item in enumerate(results):
        selected = idx == selected_index
        status = item.get('status', '완료')
        status_class = 'status-complete' if status == '완료' else 'status-pending' if status == '생성중' else 'status-error'
        st.markdown(
            f"<div class='result-card {'selected' if selected else ''}>"
            f"<div class='result-card-title'>{idx + 1}. {item.get('topic', '무제')}</div>"
            f"<div class='result-status {status_class}'>{status}</div>"
            f"<div style='margin-top: 8px; color: #cbd5e1; font-size:0.9rem;'>{item.get('created_at', '')}</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("선택하기", key=f"select_{idx}", use_container_width=True):
            st.session_state["selected_result_index"] = idx
            st.rerun()
        if st.button("삭제", key=f"delete_{idx}", use_container_width=True):
            st.session_state["selected_result_index"] = max(0, len(results) - 2)
            results.pop(idx)
            save_saved_results()
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    render_page_style()
    init_session_state()

    st.markdown("<div class='workbench-header'><strong>PLIX 스타일 쇼츠 제작 작업장</strong> - 왼쪽 설정 / 가운데 결과 / 오른쪽 목록</div>", unsafe_allow_html=True)
    left_col, middle_col, right_col = st.columns([2, 5, 3], gap="large")

    with left_col:
        render_sidebar_settings()

    with middle_col:
        render_main_result()

    with right_col:
        render_result_list()


main()
