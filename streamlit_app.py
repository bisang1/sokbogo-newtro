# deploy refresh
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import requests
import streamlit as st
from openai import OpenAI

# =========================================================
# 마지막 결과 저장 (로컬 실행 기준: 앱 껐다 켜도 남김)
# =========================================================
LAST_RESULT_PATH = Path("last_result.json")

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
CHANNELS = ["뉴트로(과거vs현재)", "속보고(증상→몸속→일상→희망)", "김앤리(연구소)"]

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
EIGHT_CUT_RULES = """
==============================
[8컷 인포그래피 생성 규칙]
==============================
총 8개의 인포그래피 프롬프트를 생성하라.

1) infographic_prompts_llm_4cuts
- 장기와 질환 특성에 맞게 자유롭게 구성하되
- 반드시 디오라마 스타일 강제 규칙을 따를 것.

2) infographic_prompts_fixed_4cuts
- 동일 구조를 유지하되
- 장기명과 질환명(필요시)만 바꿔서 출력.

디오라마 강제:
- "Biological Autopsy diorama"로 시작
- 1:87 miniature scientists 포함 (ladders/ropes/catwalks)
- subtle magenta MRI scan lines 포함
- hyper realistic, cinematic medical lighting 포함
- vertical 9:16, no text overlay 포함
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
  "infographic_prompts_llm_4cuts": {
    "past_cut1": "...",
    "past_cut2": "...",
    "present_cut1": "...",
    "present_cut2": "..."
  },
  "infographic_prompts_fixed_4cuts": {
    "past_cut1": "...",
    "past_cut2": "...",
    "present_cut1": "...",
    "present_cut2": "..."
  },
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
if "organ" not in st.session_state:
    st.session_state["organ"] = "심장"
if "preset_idx" not in st.session_state:
    st.session_state["preset_idx"] = 0

with st.expander("🧩 입력", expanded=True):
    st.session_state["channel"] = st.selectbox("채널", CHANNELS, index=CHANNELS.index(st.session_state["channel"]))

    left, right = st.columns(2)

    with left:
        organ = st.selectbox("장기", list(PRESETS.keys()), index=list(PRESETS.keys()).index(st.session_state["organ"]))
        if organ != st.session_state["organ"]:
            st.session_state["organ"] = organ
            st.session_state["preset_idx"] = 0

        preset_list = PRESETS[organ]
        disease_options = [p["disease"] for p in preset_list]
        preset_idx = st.selectbox(
            "질환명(추천)",
            range(len(disease_options)),
            format_func=lambda i: disease_options[i],
            index=st.session_state["preset_idx"],
        )
        st.session_state["preset_idx"] = preset_idx

        # 뉴트로일 때만 비교연도 의미 있음
        if st.session_state["channel"].startswith("뉴트로"):
            base_year = st.selectbox("비교 기준 연도(뉴트로용)", BASE_YEARS, index=0)
        else:
            base_year = BASE_YEARS[0]

        tone = st.selectbox("영상 톤", TONES, index=TONES.index("다큐"))

    with right:
        keywords_ko = st.text_input(
            "최근 건강 키워드(쉬운 한국어)",
            value=preset_list[preset_idx]["keywords_ko"],
            help="대본/출력은 한국어로만 생성됩니다.",
        )

        years_back = st.slider("최근 근거 범위(년)", min_value=1, max_value=15, value=5)
        max_papers = st.slider("자동 참고 논문 수(PubMed)", min_value=1, max_value=5, value=3)
        use_pubmed = st.toggle("최근 건강정보 자동 검색(PubMed) 사용", value=True)

        show_pubmed_query = st.toggle("고급: PubMed 검색 쿼리 보기(영문)", value=False)
        pubmed_query = preset_list[preset_idx]["pubmed_query"]
        if show_pubmed_query:
            st.code(pubmed_query)

st.divider()

# =========================================================
# 다음 주제 / 리셋 버튼
# =========================================================
c1, c2 = st.columns(2)

with c1:
    if st.button("🔄 다음 주제(새로 시작)", use_container_width=True):
        st.session_state["last_output"] = None
        delete_last_result()
        for k in ["channel", "organ", "preset_idx"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

with c2:
    if st.button("📌 마지막 결과 유지 + 입력만 리셋", use_container_width=True):
        for k in ["channel", "organ", "preset_idx"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

# =========================================================
# Generate
# =========================================================
if st.button("✅ 쇼츠 패키지 생성", use_container_width=True):
    evidence_articles: List[Dict[str, str]] = []
    evidence_err: Optional[str] = None

    preset_list = PRESETS[st.session_state["organ"]]
    disease_options = [p["disease"] for p in preset_list]
    disease = disease_options[st.session_state["preset_idx"]]
    channel = st.session_state["channel"]
    organ = st.session_state["organ"]

    if use_pubmed:
        with st.spinner("최근 근거(PubMed) 수집 중..."):
            evidence_articles, evidence_err = get_recent_evidence(
                pubmed_query=pubmed_query,
                years_back=years_back,
                max_papers=max_papers,
            )

    evidence_lines = []
    if evidence_articles:
        for a in evidence_articles:
            abs_snip = a.get("abstract", "") or ""
            if len(abs_snip) > 900:
                abs_snip = abs_snip[:900] + "..."
            evidence_lines.append(f"- PMID:{a.get('pmid')} | {a.get('title')} ({a.get('pubdate')})\n  초록재료: {abs_snip}")
    evidence_material = "\n".join(evidence_lines)

    # 채널별 프롬프트
    if channel.startswith("뉴트로"):
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
{EIGHT_CUT_RULES}
{VIDEO_MOTION_RULES}
{thumb_rules}
""".strip()

        user_prompt = f"""
[입력]
채널: 뉴트로(과거vs현재)
장기: {organ}
질환: {disease}
비교 기준 연도: {base_year}년대
영상 톤: {tone}
최근 건강 키워드(한국어): {keywords_ko}
근거 범위: 최근 {years_back}년

[요청 출력]
1) hook: 0~3초 후킹 1문장
2) script_30s: 60초 이내 쉬운 한국어 나레이션 (과거→현재→근거2문장→행동팁→질문형 엔딩)

3) infographic_prompts_llm_4cuts:
- past_cut1: {base_year}년대 레트로 디오라마 + {organ} 전체 샷
- past_cut2: {base_year}년대 레트로 디오라마 + {organ} 표면/장벽/외곽 구조 근접 샷
- present_cut1: 2026 현대 디오라마 + {organ} 기능 조직 단면 샷
- present_cut2: 2026 현대 디오라마 + {organ} 혈관/염증 메커니즘 매크로 단면 샷

4) infographic_prompts_fixed_4cuts:
- 동일 고정 구조 유지 + {organ}/{disease}에 맞게 표현만 미세 조정.

5) video_prompts_4cuts:
- infographic_prompts_llm_4cuts와 동일 장면 기반 8초 영상 4개
- 아주 약한 움직임만 포함

6) evidence_summary_2lines: 쉬운 말 2문장(과장 금지)
7) action_tips: 실천 팁 3개(짧게, 쉬운 말)
8) upload: 제목/설명2줄/해시태그/고정댓글/썸네일문구 후보 4개(뉴트로 스타일)
9) sources: PubMed 재료가 있으면 PMID/제목/연도 포함

[PubMed 재료]
{evidence_material if evidence_material else "(없음)"}
""".strip()

    elif channel.startswith("속보고"):
        thumb_rules = THUMBNAIL_STYLE_RULES_SOKBOGO
        system_prompt = f"""
너는 '속보고' 채널의 건강 쇼츠 제작 AI다.

[전체 출력 규칙]
- 출력은 전부 한국어.
- 대본은 반드시 60초를 넘지 말 것.
- 구조: (증상/느낌) → (몸속에서 벌어질 수 있는 일) → (일상 변화 2~3개) → (희망)
- 공포팔이/단정 금지. "가능성/신호" 수준.
- 너무 전문인처럼 말하지 말고 쉽게.

{EASY_SCRIPT_RULES}
{EIGHT_CUT_RULES}
{VIDEO_MOTION_RULES}
{thumb_rules}
""".strip()

        user_prompt = f"""
[입력]
채널: 속보고(증상→몸속→일상→희망)
장기: {organ}
주제(질환/키워드): {disease}
영상 톤: {tone}
최근 건강 키워드(한국어): {keywords_ko}
근거 범위: 최근 {years_back}년

[요청 출력]
1) hook: 0~3초 후킹 1문장(증상/호기심)
2) script_30s: 60초 이내 쉬운 한국어 나레이션
   - 증상/느낌 → 몸속 변화 → 일상 변화 2~3개 → 희망

3) infographic_prompts_llm_4cuts:
- 컷1: 증상 신호를 암시하는 {organ} 디오라마
- 컷2: 몸속 변화 시작 {organ} 근접/단면 디오라마
- 컷3: 관리/생활 변화가 연결되는 {organ} 디오라마(현대)
- 컷4: 안정/회복 방향을 암시하는 {organ} 디오라마(현대)

4) infographic_prompts_fixed_4cuts: 고정 구조 유지
5) video_prompts_4cuts: 약한 움직임
6) evidence_summary_2lines: 쉬운 말 2문장
7) action_tips 3개
8) upload(속보고 스타일)
9) sources(PubMed 있으면 포함)

[PubMed 재료]
{evidence_material if evidence_material else "(없음)"}
""".strip()

    else:
        # 김앤리(연구소)
        thumb_rules = THUMBNAIL_STYLE_RULES_KIMLEE
        system_prompt = f"""
너는 '김앤리 연구소' 채널의 건강 쇼츠 제작 AI다.

[전체 출력 규칙]
- 출력은 전부 한국어.
- 대본은 반드시 60초를 넘지 말 것.
- 너무 전문인처럼 말하지 말고 쉽게.
- 구조:
  1) 김/리 사원이 오늘 연구한 주제 소개
  2) 몸속 변화 2~3단계(아주 쉽게)
  3) 결론 1줄
  4) 오늘 당장 할 행동 1가지(또는 2가지)

- 공포팔이/단정 금지. "가능성/신호" 수준.
- 귀엽지만 신뢰감 있는 톤.

{EASY_SCRIPT_RULES}
{EIGHT_CUT_RULES}
{VIDEO_MOTION_RULES}
{thumb_rules}
""".strip()

        user_prompt = f"""
[입력]
채널: 김앤리(연구소)
장기: {organ}
주제(질환/키워드): {disease}
영상 톤: {tone}
최근 건강 키워드(한국어): {keywords_ko}
근거 범위: 최근 {years_back}년

[요청 출력]
1) hook: "김 사원이 오늘 연구한 건..." 같은 연구소 톤 1문장
2) script_30s: 60초 이내 쉬운 한국어 나레이션 (연구→메커니즘→결론→행동)
3) infographic_prompts_llm_4cuts / fixed_4cuts / video_prompts_4cuts: 기존 구조 유지(내용은 연구소 톤으로)
4) evidence_summary_2lines: 쉬운 말 2문장
5) action_tips: 실천 팁 3개(짧게)
6) upload: 제목/설명2줄/해시태그/고정댓글/썸네일문구 후보 4개(김앤리 스타일)
7) sources: PubMed 재료가 있으면 PMID/제목/연도 포함

[PubMed 재료]
{evidence_material if evidence_material else "(없음)"}
""".strip()

    try:
        data = call_openai_json(system_prompt, user_prompt)

        if evidence_err and use_pubmed:
            st.warning(evidence_err)

        # 김앤리: 사용자 템플릿 기반 cover prompt 추가
        if channel.startswith("김앤리"):
            data["kimlee_image_prompt"] = KIMLEE_COVER_PROMPT_TEMPLATE.format(topic=disease)
        # 김앤리: 연구실 4컷 + 소라2 4컷도 고정 템플릿으로 추가
        if channel.startswith("김앤리"):
            topic_for_kimlee = build_kimlee_topic(disease, keywords_ko, max_keywords=3)   # 필요하면 keywords_ko로 바꿔도 됨
            data["kimlee_image_prompt"] = KIMLEE_COVER_PROMPT_TEMPLATE.format(topic=topic_for_kimlee)

            data["kimlee_lab_image_prompts_4cuts"] = {
                "cut1": KIMLEE_LAB_4CUT_TEMPLATE["cut1"].format(topic=topic_for_kimlee),
                "cut2": KIMLEE_LAB_4CUT_TEMPLATE["cut2"].format(topic=topic_for_kimlee),
                "cut3": KIMLEE_LAB_4CUT_TEMPLATE["cut3"].format(topic=topic_for_kimlee),
                "cut4": KIMLEE_LAB_4CUT_TEMPLATE["cut4"].format(topic=topic_for_kimlee),
            }

            data["kimlee_sora2_video_prompts_4cuts"] = {
                "cut1": KIMLEE_SORA2_VIDEO_4CUT_TEMPLATE["cut1"].format(topic=topic_for_kimlee),
                "cut2": KIMLEE_SORA2_VIDEO_4CUT_TEMPLATE["cut2"].format(topic=topic_for_kimlee),
                "cut3": KIMLEE_SORA2_VIDEO_4CUT_TEMPLATE["cut3"].format(topic=topic_for_kimlee),
                "cut4": KIMLEE_SORA2_VIDEO_4CUT_TEMPLATE["cut4"].format(topic=topic_for_kimlee),
            }



        # 60초 초과하면 자동 축약
        script = (data.get("script_30s") or "").strip()
        secs = estimate_speech_seconds_korean(script)
        if secs > 60:
            with st.spinner(f"대본이 {secs:.0f}초로 추정되어 60초 이내로 자동 축약 중..."):
                data["script_30s"] = shorten_script_to_60s_easy(script, channel=channel)

        st.session_state["last_output"] = data
        save_last_result(data)
        st.success("생성 완료! (앱을 껐다 켜도 마지막 결과가 남습니다.)")

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

    st.subheader("🖼 LLM 생성 4컷 인포그래피")
    ip_llm = data_to_show.get("infographic_prompts_llm_4cuts", {}) or {}
    st.markdown("**컷 1**"); st.code(ip_llm.get("past_cut1", ""))
    st.markdown("**컷 2**"); st.code(ip_llm.get("past_cut2", ""))
    st.markdown("**컷 3**"); st.code(ip_llm.get("present_cut1", ""))
    st.markdown("**컷 4**"); st.code(ip_llm.get("present_cut2", ""))

    st.subheader("🧱 고정 4컷 인포그래피 (템플릿)")
    st.markdown("**고정 컷 1**"); st.code(FIXED_4CUT_TEMPLATE["past_cut1"].format(organ=st.session_state.get("organ", "심장")))
    st.markdown("**고정 컷 2**"); st.code(FIXED_4CUT_TEMPLATE["past_cut2"].format(organ=st.session_state.get("organ", "심장")))
    st.markdown("**고정 컷 3**"); st.code(FIXED_4CUT_TEMPLATE["present_cut1"].format(organ=st.session_state.get("organ", "심장")))
    st.markdown("**고정 컷 4**"); st.code(FIXED_4CUT_TEMPLATE["present_cut2"].format(organ=st.session_state.get("organ", "심장")))

    st.subheader("🎥 영상 프롬프트 4컷 (약한 움직임)")
    vp4 = data_to_show.get("video_prompts_4cuts", {}) or {}
    st.markdown("**영상 1**"); st.code(vp4.get("past_cut1", ""))
    st.markdown("**영상 2**"); st.code(vp4.get("past_cut2", ""))
    st.markdown("**영상 3**"); st.code(vp4.get("present_cut1", ""))
    st.markdown("**영상 4**"); st.code(vp4.get("present_cut2", ""))

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
