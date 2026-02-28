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
st.set_page_config(page_title="속보고-뉴트로 (질환 진화 공장)", page_icon="🔬", layout="centered")
st.title("🔬 속보고-뉴트로")
st.caption("1980년대 vs 현재 질환 관리의 진화 + 최근 근거(PubMed) + 8컷(LLM 4 + 고정 4) + 약한 움직임 영상 4컷까지 자동 생성합니다.")

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
# 고정 4컷 템플릿 (완전 고정)
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
# Prompt snippets (문자열 깨짐 방지)
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

THUMBNAIL_STYLE_RULES = """
==============================
[썸네일 문구 스타일 - 뉴트로 칠공 고정]
==============================
- 10~14자 내외 권장
- "1980 vs 지금" 대비 느낌 포함
- 짧고 강하게
- 질문형/반전형/충격형 섞어서 4개
- 질환명 또는 장기 키워드 1개 포함
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
# 앱 시작 시 마지막 결과 복구
# =========================================================
if "last_output" not in st.session_state:
    st.session_state["last_output"] = load_last_result()

# =========================================================
# UI (입력)
# =========================================================
if "organ" not in st.session_state:
    st.session_state["organ"] = "심장"
if "preset_idx" not in st.session_state:
    st.session_state["preset_idx"] = 0

with st.expander("🧩 입력", expanded=True):
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

        base_year = st.selectbox("비교 기준 연도", BASE_YEARS, index=0)
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
        for k in ["organ", "preset_idx"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

with c2:
    if st.button("📌 마지막 결과 유지 + 입력만 리셋", use_container_width=True):
        for k in ["organ", "preset_idx"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

# =========================================================
# Generate
# =========================================================
if st.button("✅ 30초 쇼츠 패키지 생성", use_container_width=True):
    evidence_articles: List[Dict[str, str]] = []
    evidence_err: Optional[str] = None

    if use_pubmed:
        with st.spinner("최근 근거(PubMed) 수집 중..."):
            evidence_articles, evidence_err = get_recent_evidence(
                pubmed_query=pubmed_query,
                years_back=years_back,
                max_papers=max_papers,
            )

    # 프롬프트에 넣을 근거 재료(짧게)
    evidence_lines = []
    if evidence_articles:
        for a in evidence_articles:
            abs_snip = a.get("abstract", "") or ""
            if len(abs_snip) > 900:
                abs_snip = abs_snip[:900] + "..."
            evidence_lines.append(f"- PMID:{a.get('pmid')} | {a.get('title')} ({a.get('pubdate')})\n  초록재료: {abs_snip}")
    evidence_material = "\n".join(evidence_lines)

    disease = disease_options[preset_idx]

    system_prompt = f"""
너는 '뉴트로 칠공' 채널의 건강 다큐 쇼츠 제작 AI다.

[전체 출력 규칙]
- 출력(대본, 제목, 설명, 해시태그, 팁)은 전부 한국어로만 작성.
- 30초 분량.
- 구조: 과거({base_year}년대) → 현재(2026년) → 최근 건강정보 2문장 → 행동 팁 3개 → 질문형 마무리.
- 과장, 공포 조장, 단정적 표현 금지.
- "연관성", "경향", "관련 가능성" 수준으로 표현.

{EIGHT_CUT_RULES}

{VIDEO_MOTION_RULES}

{THUMBNAIL_STYLE_RULES}
""".strip()

    user_prompt = f"""
[입력]
장기: {organ}
질환: {disease}
비교 기준 연도: {base_year}년대
영상 톤: {tone}
최근 건강 키워드(한국어): {keywords_ko}
근거 범위: 최근 {years_back}년

[요청 출력]
1) hook: 0~3초 후킹 1문장
2) script_30s: 30초 나레이션 (과거→현재→근거2문장→행동팁→질문형 엔딩)

3) infographic_prompts_llm_4cuts:
- past_cut1: {base_year}년대 레트로 디오라마(병리 테이블/아날로그 소품) + {organ} 전체 샷
- past_cut2: {base_year}년대 레트로 디오라마 + {organ} 표면/장벽/외곽 구조 근접 샷
- present_cut1: 2026 현대 디오라마(디지털 장비/클린 랩) + {organ} 기능 조직 단면 샷
- present_cut2: 2026 현대 디오라마 + {organ} 혈관/염증 메커니즘 매크로 단면 샷
* 상황 디테일은 장기/질환 특성에 맞게 더 구체화.

4) infographic_prompts_fixed_4cuts:
- 동일 고정 구조 유지 + {organ}/{disease}에 맞게 표현만 미세 조정.

5) video_prompts_4cuts:
- infographic_prompts_llm_4cuts와 동일 장면 기반 8초 영상 4개
- 아주 약한 움직임만 포함(느린 줌 1회 또는 미세 패닝 1회)

6) evidence_summary_2lines: "최근 건강정보에 의하면" 형식 2문장(한국어만, 과장 금지)
7) action_tips: 실천 팁 3개(짧게, 한국어만)
8) upload: 제목/설명2줄/해시태그/고정댓글/썸네일문구 후보 4개(뉴트로 칠공 스타일)
9) sources: PubMed 재료가 있으면 PMID/제목/연도 포함

[PubMed 재료]
{evidence_material if evidence_material else "(없음)"}
""".strip()

    try:
        data = call_openai_json(system_prompt, user_prompt)

        if evidence_err and use_pubmed:
            st.warning(evidence_err)

        # ✅ 생성 성공 시 "마지막 결과"로 저장 + 파일 저장
        st.session_state["last_output"] = data
        save_last_result(data)

        st.success("생성 완료! (앱을 껐다 켜도 마지막 결과가 남습니다.)")

    except Exception as e:
        st.error("생성 중 오류 발생")
        st.exception(e)

# =========================================================
# 마지막 결과 출력 (앱을 다시 열어도 계속 보이게)
# =========================================================
data_to_show = st.session_state.get("last_output")

if data_to_show:
    st.subheader("🎙️ 30초 대본(한국어)")
    st.code(data_to_show.get("script_30s", ""))

    st.subheader("🧠 최근 건강정보 근거(2문장)")
    st.code(data_to_show.get("evidence_summary_2lines", ""))

    st.subheader("✅ 행동 예방 팁 (3개)")
    tips = data_to_show.get("action_tips", []) or []
    for t in tips:
        st.write(f"- {t}")

    st.subheader("🖼 LLM 생성 4컷 인포그래피 (과거 2 + 현재 2)")
    ip_llm = data_to_show.get("infographic_prompts_llm_4cuts", {}) or {}
    st.markdown("**LLM 과거 컷 1**"); st.code(ip_llm.get("past_cut1", ""))
    st.markdown("**LLM 과거 컷 2**"); st.code(ip_llm.get("past_cut2", ""))
    st.markdown("**LLM 현재 컷 1**"); st.code(ip_llm.get("present_cut1", ""))
    st.markdown("**LLM 현재 컷 2**"); st.code(ip_llm.get("present_cut2", ""))

    st.subheader("🧱 고정 4컷 인포그래피 (완전 고정)")
    ip_fixed_from_llm = data_to_show.get("infographic_prompts_fixed_4cuts", {}) or {}
    if ip_fixed_from_llm:
        st.caption("아래는 모델이 '고정 구조'로 출력한 버전입니다.")
        st.markdown("**고정 과거 컷 1 (LLM)**"); st.code(ip_fixed_from_llm.get("past_cut1", ""))
        st.markdown("**고정 과거 컷 2 (LLM)**"); st.code(ip_fixed_from_llm.get("past_cut2", ""))
        st.markdown("**고정 현재 컷 1 (LLM)**"); st.code(ip_fixed_from_llm.get("present_cut1", ""))
        st.markdown("**고정 현재 컷 2 (LLM)**"); st.code(ip_fixed_from_llm.get("present_cut2", ""))

    st.caption("아래는 코드에 박아둔 '완전 고정 템플릿' 버전입니다.")
    st.markdown("**고정 과거 컷 1 (템플릿)**"); st.code(FIXED_4CUT_TEMPLATE["past_cut1"].format(organ=organ))
    st.markdown("**고정 과거 컷 2 (템플릿)**"); st.code(FIXED_4CUT_TEMPLATE["past_cut2"].format(organ=organ))
    st.markdown("**고정 현재 컷 1 (템플릿)**"); st.code(FIXED_4CUT_TEMPLATE["present_cut1"].format(organ=organ))
    st.markdown("**고정 현재 컷 2 (템플릿)**"); st.code(FIXED_4CUT_TEMPLATE["present_cut2"].format(organ=organ))

    st.subheader("🎥 영상 프롬프트 4컷 (약한 움직임)")
    vp4 = data_to_show.get("video_prompts_4cuts", {}) or {}
    st.markdown("**영상 1 (과거 컷 1)**"); st.code(vp4.get("past_cut1", ""))
    st.markdown("**영상 2 (과거 컷 2)**"); st.code(vp4.get("past_cut2", ""))
    st.markdown("**영상 3 (현재 컷 1)**"); st.code(vp4.get("present_cut1", ""))
    st.markdown("**영상 4 (현재 컷 2)**"); st.code(vp4.get("present_cut2", ""))

    st.subheader("🚀 업로드 최적화")
    up = data_to_show.get("upload", {}) or {}
    st.code(up.get("title", ""))
    st.code(up.get("description2lines", ""))
    st.code(up.get("hashtags", ""))
    st.code(up.get("pinned_comment", ""))

    st.subheader("🧷 썸네일 문구 후보(뉴트로 칠공 스타일)")
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