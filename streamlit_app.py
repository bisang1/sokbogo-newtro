import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import requests
import streamlit as st
from openai import OpenAI
import os


import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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


# =========================================================
# App Config
# =========================================================
st.set_page_config(page_title="속보고-뉴트로-김앤리 (콘텐츠 공장)", page_icon="🔬", layout="centered")
st.title("🔬 속보고-뉴트로-김앤리")
st.caption("채널 선택(뉴트로/속보고/김앤리) + 최근 근거(PubMed) + 8컷(LLM 4 + 고정 4) + 약한 움직임 영상 4컷 + 업로드 패키지까지 자동 생성합니다.")

# =========================================================
# Secrets / Client
# =========================================================
api_key = st.secrets.get("OPENAI_API_KEY", "")
model = st.secrets.get("OPENAI_MODEL", "gpt-4.1-mini")

if not api_key:
    st.warning("OPENAI_API_KEY가 필요합니다.")
    st.stop()

client = OpenAI(api_key=api_key)

# =========================================================
# 채널
# =========================================================
CHANNELS = [
    "뉴트로(과거vs현재)",
    "속보고(장기-몸속-일상-희망)",
    "김앤리(연구소)",
    "트렌드 탐색"
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

    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": instruction + "\n\n" + user},
        ],
        temperature=0.6,
    )

    text = getattr(resp, "output_text", "") or ""
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

    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
    )
    text = getattr(resp, "output_text", "") or ""
    return text.strip()

# =========================
# Sokbogo output package
# =========================


from pathlib import Path
from datetime import datetime
import re

BASE_OUTPUT_DIR = Path("outputs")

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






# =========================================================
# 앱 시작 시 마지막 결과 복구
# =========================================================
if "last_output" not in st.session_state:
    st.session_state["last_output"] = load_last_result()

# =========================================================
# UI (입력)
# =========================================================
if "channel" not in st.session_state:
    st.session_state["channel"] = CHANNELS[0]
if "selected_category" not in st.session_state:
    st.session_state["selected_category"] = list(PRESETS.keys())[0]
if "preset_idx" not in st.session_state:
    st.session_state["preset_idx"] = 0

if st.session_state["preset_idx"] is None:
    st.session_state["preset_idx"] = 0


with st.expander("🧩 입력", expanded=True):
    st.session_state["channel"] = st.selectbox("채널", CHANNELS, index=CHANNELS.index(st.session_state["channel"]))

if st.session_state["channel"] == "트렌드 탐색":
    render_topic_explorer(client=client, model=model)
    st.stop()

left, right = st.columns(2)

with left:
    input_method = st.radio("주제 입력 방식", ["프리셋 선택", "직접 입력", "트렌드 키워드 기반"], horizontal=True)

    topic = None

    if input_method == "트렌드 키워드 기반":
        trend_input = st.text_input("트렌드 키워드 (예: 미세먼지, 수면부족)")
        if trend_input:
            trend_info = get_llm_trend_pick(trend_input, client, model)

            if trend_info.get("reason"):
                st.info(f"트렌드 이유: {trend_info['reason']}")

            if trend_info.get("health_angle"):
                st.success(f"건강 연결: {trend_info['health_angle']}")

            if trend_info.get("converted_topic"):
                st.session_state["selected_topic"] = trend_info["converted_topic"]
                st.session_state["trend_reason"] = trend_info.get("reason", "")
                st.session_state["trend_insight"] = trend_info.get("insight", "")
                st.session_state["trend_health_angle"] = trend_info.get("health_angle", "")
                st.success(f"최종 주제: {trend_info['converted_topic']}")
                topic = trend_info["converted_topic"]
            else:
                st.warning("❌ 건강 연결 불가 → 주제 제외됨")
    
    elif input_method == "직접 입력":
        custom_topic = st.text_input("주제를 자유롭게 입력하세요", placeholder="예: 봄철 알레르기 비염 예방법")
        if custom_topic:
            st.session_state["selected_topic"] = custom_topic
            # 직접 입력 모드에서는 트렌드 관련 정보를 비웁니다
            st.session_state["trend_reason"] = ""
            st.session_state["trend_insight"] = ""
            st.session_state["trend_health_angle"] = ""
            topic = custom_topic

    else:
        # 프리셋 선택 (선택된 주제 초기화)
        st.session_state["selected_topic"] = ""
        topic = None

if st.session_state.get("selected_topic"):
    topic = st.session_state["selected_topic"]

    if st.session_state.get("trend_reason"):
        st.info(f"이슈 이유: {st.session_state['trend_reason']}")

    if st.session_state.get("trend_insight"):
        st.info(f"사람들이 궁금해하는 이유: {st.session_state['trend_insight']}")

    if st.session_state.get("trend_health_angle"):
        st.info(f"건강 연결: {st.session_state['trend_health_angle']}")

    st.success(f"선택된 주제: {topic}")

    recommended_cats = recommend_categories(topic) if topic else []

    available_categories = [
        c for c in recommended_cats
        if c in PRESETS and PRESETS.get(c)
    ]

    if not available_categories:
        available_categories = [
            c for c in PRESETS.keys()
            if PRESETS.get(c)
        ]

    saved_category = st.session_state.get("selected_category")
    default_idx = (
        available_categories.index(saved_category)
        if saved_category in available_categories else 0
    )

    category = st.selectbox(
        "설명 영역",
        available_categories,
        index=default_idx,
        key="selected_category"
    )

    preset_list = PRESETS.get(category, [])



    available_categories = [
        c for c in PRESETS.keys()
        if PRESETS.get(c)
    ]

    

is_trend_mode = bool(st.session_state.get("selected_topic"))

preset_list = PRESETS.get(category, []) if 'category' in locals() else []

# 프리셋 모드일 때만 프리셋 검사
if not preset_list and not is_trend_mode:
    st.warning("현재 설명 영역에 연결된 질환 프리셋이 없습니다.")
    st.stop()

# -----------------------------
# 프리셋 모드 / 트렌드 모드 분기
# -----------------------------
if not is_trend_mode:
    if st.session_state.get("preset_idx") is None:
        st.session_state["preset_idx"] = 0

    if st.session_state["preset_idx"] >= len(preset_list):
        st.session_state["preset_idx"] = 0

    disease_options = [p["disease"] for p in preset_list]
    preset_idx = st.selectbox(
        "질환명(추천)",
        range(len(disease_options)),
        format_func=lambda i: disease_options[i],
        index=st.session_state["preset_idx"],
    )
    st.session_state["preset_idx"] = preset_idx

    selected_preset = preset_list[preset_idx]
    keywords_ko_default = selected_preset.get("keywords_ko", "")
    pubmed_query = selected_preset.get("pubmed_query", "")

else:
    preset_idx = 0
    selected_preset = {}

    trend_topic = st.session_state.get("selected_topic", "").strip()
    trend_reason = st.session_state.get("trend_reason", "").strip()
    trend_health_angle = st.session_state.get("trend_health_angle", "").strip()

    keywords_ko_default = trend_topic

    pubmed_parts = [trend_topic]
    if trend_health_angle:
        pubmed_parts.append(trend_health_angle)

    pubmed_query = " ".join([p for p in pubmed_parts if p]).strip()

# -----------------------------
# 공통 UI
# -----------------------------
if st.session_state["channel"].startswith("뉴트로"):
    base_year = st.selectbox("비교 기준 연도(뉴트로용)", BASE_YEARS, index=0)
else:
    base_year = BASE_YEARS[0]

st.session_state["base_year"] = base_year

tone = st.selectbox("영상 톤", TONES, index=TONES.index("다큐"))
st.session_state["tone"] = tone

years_back = st.slider("최근 근거 범위(년)", min_value=1, max_value=15, value=5)
max_papers = st.slider("자동 참고 논문 수(PubMed)", min_value=1, max_value=8, value=5)
use_pubmed = st.toggle("최근 건강정보 자동 검색(PubMed) 사용", value=True)

with right:
    keywords_ko = st.text_input(
        "최근 건강 키워드(쉬운 한글)",
        value=keywords_ko_default,
        help="대본/출력은 한글로만 생성됩니다.",
    )
    st.session_state["keywords_ko"] = keywords_ko

    show_pubmed_query = st.toggle("고급: PubMed 검색 쿼리 보기(영문)")

    if show_pubmed_query:
        st.code(pubmed_query)


st.divider()

# 🔥 오늘 건강 트렌드
if st.session_state.get("trend_topics"):
    st.subheader("🔥 오늘 건강 트렌드")

    for i, topic in enumerate(st.session_state["trend_topics"][:5], 1):
        st.write(f"{i}. {topic}")

    # 트렌드 주제 선택
    if "selected_topic" not in st.session_state:
        st.session_state["selected_topic"] = None

    trend_choice = st.selectbox(
        "트렌드 주제 사용",
        ["선택 안함"] + st.session_state["trend_topics"],
        index=0,
        key="trend_choice_selectbox"
    )

    if trend_choice != "선택 안함":
        st.session_state["selected_topic"] = trend_choice
        st.success(f"선택된 트렌드 주제: {trend_choice}")
# =========================================================
# 다음 주제 / 리셋 버튼
# =========================================================
c1, c2 = st.columns(2)

with c1:
    if st.button("🔄 다음 주제(새로 시작)", use_container_width=True):
        youtube_api_key = st.secrets.get("YOUTUBE_API_KEY", "")
        trend_data = get_health_trends(youtube_api_key)
        st.session_state["trend_topics"] = trend_data.get("topics", [])

        st.session_state["last_output"] = None
        delete_last_result()





        for k in ["channel", "organ", "preset_idx"]:
            if k in st.session_state:
                del st.session_state[k]

        st.rerun()

# =========================================================
# Generate
# =========================================================
if st.button("✅ 쇼츠 패키지 생성", use_container_width=True):

   


        # UI 값 다시 읽기 (Generate 실행 시 안전하게 사용)
    base_year = st.session_state.get("base_year", 2000) or 2000
    years_back = st.session_state.get("years_back", 5) or 5
    max_papers = st.session_state.get("max_papers", 8) or 8
    use_pubmed = st.session_state.get("use_pubmed", True)
    tone = st.session_state.get("tone", "다큐")
    keywords_ko = st.session_state.get("keywords_ko", "")
    st.session_state["keywords_ko"] = keywords_ko

    channel = st.session_state.get("channel", "")
    preset_idx = st.session_state.get("preset_idx", 0) or 0

    evidence_articles: List[Dict[str, str]] = []
    evidence_err: Optional[str] = None

   



    if not is_trend_mode:
        disease_options = [p["disease"] for p in preset_list]

        idx = st.session_state.get("preset_idx", 0) or 0
        if idx >= len(disease_options):
            idx = 0

        visual_topic = disease_options[idx]
    else:
        # 트렌드 모드에서는 선택된 주제를 그대로 사용
        visual_topic = st.session_state.get("selected_topic", "").strip()

    # 먼저 기본값을 무조건 만든다
    script_topic = visual_topic

    # 트렌드가 있으면 대본/제목용 주제로 덮어쓴다
    selected_topic_value = st.session_state.get("selected_topic", "")
    if selected_topic_value:
        script_topic = selected_topic_value

    # 기존 아래 코드 호환용
    disease = script_topic

    channel = st.session_state.get("channel", "")
    




preset_idx = st.session_state.get("preset_idx", 0) or 0
years_back = st.session_state.get("years_back", 5) or 5
max_papers = st.session_state.get("max_papers", 8) or 8



# PubMed 검색어 결정
current_selected_topic = st.session_state.get("selected_topic", "").strip()
is_trend_mode = bool(current_selected_topic)

if is_trend_mode:
    pubmed_query = current_selected_topic
else:
    selected_preset = preset_list[preset_idx] if 0 <= preset_idx < len(preset_list) else {}
    pubmed_query = selected_preset.get("pubmed_query", "")

    if st.session_state.get("use_pubmed", True):
        with st.spinner("최근 근거(PubMed) 수집 중..."):
            evidence_articles, evidence_err = get_recent_evidence(
                pubmed_query=pubmed_query,
                years_back=years_back,
                max_papers=max_papers,
            )


    evidence_material = ""
    evidence_lines = []
    if evidence_articles:
        for a in evidence_articles:
            abs_snip = a.get("abstract", "") or ""
            if len(abs_snip) > 900:
                abs_snip = abs_snip[:900] + "..."
            evidence_lines.append(f"- PMID:{a.get('pmid')} | {a.get('title')} ({a.get('pubdate')})\n  초록재료: {abs_snip}")
    evidence_material = "\n".join(evidence_lines)

    # 채널별 프롬프트


    channel = st.session_state.get("channel", "")
    base_year = st.session_state.get("base_year", 2000) or 2000
    disease = st.session_state.get("selected_topic", "")
    tone = st.session_state.get("tone", "다큐")
    years_back = st.session_state.get("years_back", 5)
    keywords_ko = st.session_state.get("keywords_ko", "")
    


    system_prompt = ""
    thumb_rules = ""


    if channel and channel.startswith("뉴트로"):
        thumb_rules = THUMBNAIL_STYLE_RULES_NEWTRO
        system_prompt = f"""
너는 '뉴트로 칠공' 채널의 건강 다큐 쇼츠 제작 AI다.

[전체 출력 규칙]
- 출력은 전부 한국어.
- 대본은 반드시 60초를 넘지 말 것.
- 구조: 과거({base_year}년대) → 현재(2026년) → 최근 건강정보 2문장 → 행동 팁 3개 → 질문형 마무리.
- 너무 전문적으로 쓰지 말고 쉽게 설명.
- 과장/공포/단정 금지. "가능성/경향" 수준.

{EASY_SCRIPT_RULES}
{INFOGRAPHIC_5CUT_RULES}
{VIDEO_MOTION_RULES}
{thumb_rules}
""".strip()



disease = category
base_year = st.session_state.get("base_year", BASE_YEARS[0])
tone = st.session_state.get("tone", "다큐")
keywords_ko = st.session_state.get("keywords_ko", "")   # ⭐ 이 줄 추가
years_back = st.session_state.get("years_back", 5)      # ⭐ 이것도 같이 추가

user_prompt = f"""
너는 조회수 높은 유튜브 쇼츠 대본 전문가다.

다음 조건을 반드시 지켜라:

1. 첫 문장은 반드시 강한 경고 또는 궁금증 유발 문장
2. 3초 안에 시청자가 멈추게 만들어라
3. 절대 “오늘 ~입니다” 같은 설명형 시작 금지
4. 감정 + 위험 + 궁금증 구조로 작성
5. 전체 길이는 30~40초
6. 문장은 짧고 강하게
7. 한국어로 자연스럽게
8. 마지막에 행동 유도 포함

구조:
- hook (강한 첫 문장)
- 공감 상황
- 핵심 정보
- 행동 유도

예시 스타일:
“이 증상, 그냥 넘기면 위험합니다”
“아침에 일어나기 힘들다면…”
“몸이 보내는 신호일 수 있습니다”

[주제]
{disease}

[설명 영역]
{category}

[최근 키워드]
{keywords_ko}
"""


channel = st.session_state.get("channel", "")
if channel and channel.startswith("속보고"):
        thumb_rules = THUMBNAIL_STYLE_RULES_SOKBOGO if 'THUMBNAIL_STYLE_RULES_SOKBOGO' in globals() else ""
        system_prompt = f"""
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
{thumb_rules}
""".strip()

channel = st.session_state.get("channel", "")
base_year = st.session_state.get("base_year", 2000)
disease = st.session_state.get("selected_topic", "") or category
tone = st.session_state.get("tone", "다큐")
keywords_ko = st.session_state.get("keywords_ko", "")   
years_back = st.session_state.get("years_back", 5)      

user_prompt = f"""
너는 조회수 높은 유튜브 쇼츠 대본 전문가다.

다음 조건을 반드시 지켜라:

1. 첫 문장은 반드시 강한 경고, 놀람, 궁금증 중 하나로 시작
2. 3초 안에 시청자가 멈추게 만들어라
3. 절대 “오늘 ~입니다”, “이번 주제는” 같은 설명형 시작 금지
4. 문장은 짧고 강하게 써라
5. 전체 대본은 30~40초 분량으로 작성
6. 너무 전문적인 말 대신 쉬운 한국어를 사용
7. 구조는 “증상/느낌 → 몸속 변화 → 일상 변화 → 지금 할 행동” 순서
8. 마지막은 바로 따라할 수 있는 행동 유도로 끝내라
9. 사람 이름, 팀 이름, 트렌드 원문은 제목/첫 문장에 직접 넣지 말고 건강 상황으로 번역해라

출력 형식:
1) hook: 0~3초 후킹 1문장
2) script_30s: 30~40초 나레이션
3) sokbogo_image_prompts_5cuts: 대본 흐름에 맞춘 5개의 씬 객체 배열
4) thumbnail_text: 썸네일용 짧은 문구 1개
5) hashtags: 해시태그 5개

좋은 예시 톤:
- “이 증상, 그냥 넘기면 위험합니다”
- “배가 자주 아프다면 몸이 보내는 신호일 수 있습니다”
- “운동 후 이런 변화가 반복되면 꼭 보세요”

[주제]
{disease}

[설명 영역]
{category}

[최근 키워드]
{keywords_ko}

[참고]
- 영상 톤: {tone}
- 최근 {years_back}년 범위 참고
"""


channel = st.session_state.get("channel", "")
selected_topic = st.session_state.get("selected_topic", "")
tone = st.session_state.get("tone", "다큐")
keywords_ko = st.session_state.get("keywords_ko", "")
years_back = st.session_state.get("years_back", 5)

user_prompt = f"""
너는 조회수 높은 유튜브 쇼츠 대본 전문가다.

다음 조건을 반드시 지켜라:

1. 첫 문장은 강한 경고, 반전, 궁금증 중 하나로 시작
2. 절대 “오늘 연구한 주제는”, “이번 영상은” 같은 설명형 시작 금지
3. 3초 안에 시청자가 멈추게 만들어라
4. 전체 대본은 30~40초 분량으로 작성
5. 문장은 짧고 강하게, 쉬운 한국어로 써라
6. 구조는 “hook → 공감 상황 → 핵심 정보 → 행동 유도” 순서
7. 연구소 채널 톤은 유지하되 딱딱하지 않게
8. 사람 이름, 팀 이름, 트렌드 원문은 제목/첫 문장에 직접 넣지 말고 건강 상황으로 번역해라
9. 마지막은 지금 바로 해볼 행동이나 체크 포인트로 끝내라

출력 형식:
1) hook: 0~3초 후킹 1문장
2) script_30s: 30~40초 나레이션
3) infographic_scene_concepts_5cuts: 대본 흐름에 맞춘 5개의 씬 객체 배열
4) evidence_summary_2lines: 쉬운 말 2문장
5) action_tips: 짧은 실전 팁 3개
6) upload:
- 제목 후보 4개
- 설명 2줄
- 해시태그 5개
- 고정댓글 1개
- 썸네일 문구 4개
7) sources: PubMed 자료가 있으면 PMID/제목/연도 포함

좋은 예시 톤:
- “이 신호, 그냥 넘기면 늦을 수 있습니다”
- “아침에 유독 힘들다면 몸이 보내는 신호일 수 있습니다”
- “이런 변화가 반복되면 꼭 체크해보세요”

[주제]
{selected_topic}

[설명 영역]
{category}

[최근 건강 키워드]
{keywords_ko}

[참고]
- 영상 톤: {tone}
- 최근 {years_back}년 범위 참고

[PubMed 재료]
{locals().get("evidence_material", "") or "(없음)"}
"""

try:

    system_prompt = """
너는 조회수 높은 건강 쇼츠 콘텐츠 전문가다.

규칙:
- 한국어로 작성
- 짧고 강한 문장 사용
- 설명형 시작 금지
- 감정 + 궁금증 유도
- 클릭하고 싶은 구조로 작성
- 과장/공포는 피하고 자연스럽게 설득력 있게 작성
"""
    data = call_openai_json(system_prompt, user_prompt)

    evidence_err = locals().get("evidence_err", None)
    if evidence_err and use_pubmed:
        st.warning(evidence_err)

    raw_topic = selected_topic or disease or category

    bad_topic_words = ["BTS", "방탄", "롯데", "자이언츠", "공연", "중계", "연예인", "경기", "이슈"]
    if any(w.lower() in raw_topic.lower() for w in bad_topic_words):
        raw_topic = category


        # 이미지 프롬프트용 고정 주제 다시 계산
    preset_idx_safe = st.session_state.get("preset_idx", 0) or 0
    if preset_idx_safe >= len(preset_list):
        preset_idx_safe = 0

    visual_topic_for_image = disease
    if preset_list and 0 <= preset_idx_safe < len(preset_list):
        visual_topic_for_image = preset_list[preset_idx_safe].get("disease", disease)

    if channel and channel.startswith("김앤리"):
        data["kimlee_image_prompt"] = KIMLEE_COVER_PROMPT_TEMPLATE.format(
            topic=visual_topic_for_image
        )

        data["kimlee_sora2_video_prompts_4cuts"] = {
            "cut1": KIMLEE_SORA2_VIDEO_4CUT_TEMPLATE["cut1"].format(topic=visual_topic_for_image),
            "cut2": KIMLEE_SORA2_VIDEO_4CUT_TEMPLATE["cut2"].format(topic=visual_topic_for_image),
            "cut3": KIMLEE_SORA2_VIDEO_4CUT_TEMPLATE["cut3"].format(topic=visual_topic_for_image),
            "cut4": KIMLEE_SORA2_VIDEO_4CUT_TEMPLATE["cut4"].format(topic=visual_topic_for_image),
        }

    script = (data.get("script_30s") or "").strip()
    secs = estimate_speech_seconds_korean(script)

    if secs > 60:
        with st.spinner(f"대본이 {secs:.0f}초로 추정되어 60초 이내로 자동 축약 중..."):
            data["script_30s"] = shorten_script_to_60s_easy(
                script,
                channel=channel,
            )



    final_script = (data.get("script_30s") or "").strip()

    if channel and channel.startswith("속보") and final_script:
        try:
            package_result = build_sokbogo_output_package(
                topic=(
                    st.session_state.get("selected_topic")
                    or topic
                    or st.session_state.get("keywords_ko", "")
                    or "뇌 건강 경고 신호"
                ),
                script_text=final_script,
            )

            st.session_state["sokbogo_output_dir"] = package_result["output_dir"]
            st.success(f"속보고 결과물 저장 완료: {package_result['output_dir']}")

        except Exception as e:
            st.error(f"속보고 결과물 저장 실패: {e}")

    final_topic_for_images = (
        st.session_state.get("selected_topic")
        or topic
        or st.session_state.get("keywords_ko", "")
        or "뇌 건강 경고 신호"
    )

    custom_image_prompts = []
    
    if channel and channel.startswith("속보고"):
        sokbogo_prompts = data.get("sokbogo_image_prompts_5cuts", [])
        for i, p in enumerate(sokbogo_prompts[:5], 1):
            if p.get("type", "").lower() == "diorama":
                organ_en = p.get("organ_en", "Brain")
                direction = p.get("scene_direction_en", "researching")
                prompt = f'''Input Variable: [{final_topic_for_images}]
System Instruction: Generate a hyper-realistic "Biological Autopsy" diorama.

Layout:
- 9:16 vertical
- a giant {organ_en} placed on a white medical operating table
- photorealistic surgical theater environment
- cinematic surgical lighting
- no text, no letters, no subtitles, no watermark

Core Visual Style:
- miniature 1:87 scale scientists researching the organ
- yellow safety suits
- small cranes, scaffold lifts, surgical tools, diagnostic monitors
- glowing magenta scan lines tracing the organ structure
- ultra-detailed diorama realism

Scene Goal: Scene {i}
{direction}
'''
                custom_image_prompts.append(prompt.strip())
            else:
                direction = p.get("scene_direction_en", "Korean person looking at camera")
                prompt = f'''Vertical 9:16 aspect ratio, hyper-realistic photography, high-end commercial style.
Subject: Korean people (South Korean).
Scene: {direction}
No text, no letters, cinematic lighting, highly detailed everyday life scene.
'''
                custom_image_prompts.append(prompt.strip())
    else:
        scene_concepts = data.get("infographic_scene_concepts_5cuts", [])
        for concept in scene_concepts[:5]:
            org = concept.get("organ_ko", "뇌")
            inferred_org = infer_target_organ(org)
            
            prompt = build_infographic_scene_prompt(
                organ=inferred_org,
                topic=final_topic_for_images,
                scene_title=concept.get("scene_title", "Scene"),
                scene_direction=concept.get("scene_direction_en", "show the internal structure"),
            )
            custom_image_prompts.append(prompt)

    if len(custom_image_prompts) < 5:
        fixed = generate_fixed_infographic_prompts(topic=final_topic_for_images)
        for i in range(len(custom_image_prompts), 5):
            if i < len(fixed):
                custom_image_prompts.append(fixed[i])

    data["image_prompts"] = custom_image_prompts
    data["scene_prompts"] = custom_image_prompts



    st.session_state["last_output"] = data
    save_last_result(data)
    st.success("생성 완료 (앱을 껐다 켜도 마지막 결과가 남습니다.)")

except Exception as e:
        st.error("생성 중 오류 발생")
        st.exception(e)





# =========================================================
# 마지막 결과 출력
# =========================================================
data_to_show = st.session_state.get("last_output")

if data_to_show:
    st.subheader("🎙️ 대본(60초 이내, 쉬운 한국어)")
    st.code(data_to_show.get("script_30s", ""))
    est = estimate_speech_seconds_korean(data_to_show.get("script_30s", ""))
    st.caption(f"⏱️ 말하기 시간 추정: 약 {est:.0f}초 (목표: 60초 이내)")

    # 김앤리 cover prompt
    if data_to_show.get("kimlee_image_prompt"):
        st.subheader("🐾 김앤리 썸네일 이미지 프롬프트(고정 템플릿)")
        st.code(data_to_show.get("kimlee_image_prompt", ""))

    # 김앤리 연구실 4컷
    kimlee4 = data_to_show.get("kimlee_lab_image_prompts_4cuts")
    if kimlee4:
        st.subheader("🐾 김앤리 연구실 4컷 이미지 프롬프트")
        st.markdown("**컷 1**"); st.code(kimlee4.get("cut1", ""))
        st.markdown("**컷 2**"); st.code(kimlee4.get("cut2", ""))
        st.markdown("**컷 3**"); st.code(kimlee4.get("cut3", ""))
        st.markdown("**컷 4**"); st.code(kimlee4.get("cut4", ""))

    # 김앤리 소라2 4컷
    sora4 = data_to_show.get("kimlee_sora2_video_prompts_4cuts")
    if sora4:
        st.subheader("🎥 김앤리 소라2 4컷 영상 프롬프트(약한 움직임)")
        st.markdown("**영상 1**"); st.code(sora4.get("cut1", ""))
        st.markdown("**영상 2**"); st.code(sora4.get("cut2", ""))
        st.markdown("**영상 3**"); st.code(sora4.get("cut3", ""))
        st.markdown("**영상 4**"); st.code(sora4.get("cut4", ""))


    st.subheader("🧠 최근 건강정보 근거(2문장)")
    st.code(data_to_show.get("evidence_summary_2lines", ""))

    st.subheader("✅ 행동 예방 팁 (3개)")
    tips = data_to_show.get("action_tips", []) or []
    for t in tips:
        st.write(f"- {t}")

    st.subheader("행동 예방 팁 (3개)")

    if data_to_show.get("image_prompts"):
        st.subheader("🧠 장기 연구형 인포그래피 5장")

    for i, prompt in enumerate(data_to_show.get("image_prompts", [])[:5], 1):
        st.markdown(f"**씬 {i}**")
        st.code(prompt)

    st.subheader("🚀 업로드 최적화")
    up = data_to_show.get("upload", {}) or {}
    st.code(up.get("title", ""))
    st.code(up.get("description2lines", ""))
    st.code(up.get("hashtags", ""))
    st.code(up.get("pinned_comment", ""))

    st.subheader("🧷 썸네일 문구 후보")
    thumbs = (up.get("thumbnail_text_candidates", []) or [])[:4]
    if thumbs:
        for t in thumbs:
            st.write(f"- {t}")
    else:
        st.write("- (없음)")

    st.subheader("📚 Sources (클릭해서 PubMed 열기)")
    sources = data_to_show.get("sources", []) or []
    if sources:
        for s in sources:
            pmid = str(s.get("id", "")).strip()
            title = s.get("title", "")
            year = s.get("year", "")
            if pmid:
                st.markdown(f"- [PubMed {pmid} ({year})](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)  \n  {title}")
            else:
                st.write(f"- (PMID 없음) {title}")
    else:
        st.write("- (sources 없음)")

    with st.expander("🧾 전체 JSON 보기"):
        st.json(data_to_show)
else:
    st.info("아직 생성된 결과가 없습니다. 위에서 생성 버튼을 눌러주세요.")
