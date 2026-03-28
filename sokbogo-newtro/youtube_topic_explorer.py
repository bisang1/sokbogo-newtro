import json
import time
import requests

def score_topic(topic: str) -> int:
    score = 50
    t = (topic or "").strip()

    strong_patterns = [
        "이유", "신호", "증상", "습관", "경고", "위험", "전조",
        "하면 안", "주의", "체크", "확인", "진짜", "왜", "원인"
    ]
    curiosity_patterns = [
        "밤에", "아침에", "식후", "자꾸", "갑자기", "모르면", "놓치면", "의외로"
    ]
    health_patterns = [
        "수면", "혈당", "심장", "간", "위", "장", "신장", "콜레스테롤",
        "염증", "피로", "두통", "어지럼", "혈압", "당뇨", "스트레스", "기관지", "호흡"
    ]

    for kw in strong_patterns:
        if kw in t:
            score += 10

    for kw in curiosity_patterns:
        if kw in t:
            score += 7

    for kw in health_patterns:
        if kw in t:
            score += 8

    if len(t) <= 22:
        score += 5

    return min(score, 100)


def fetch_google_trends_keywords():
    url = "https://trends.google.com/trending/rss?geo=KR"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        text = response.text

        keywords = []
        for chunk in text.split("<item>")[1:]:
            if "<title>" in chunk and "</title>" in chunk:
                title = chunk.split("<title>")[1].split("</title>")[0].strip()
                if title:
                    keywords.append(title)

        return keywords[:10]
    except Exception:
        return [
            "수면 부족",
            "혈당",
            "미세먼지",
            "두통",
            "스트레스",
        ]


def _extract_json_object(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {}

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        chunk = text[start:end + 1]
        try:
            return json.loads(chunk)
        except Exception:
            return {}

    return {}


def interpret_trend_with_llm(keyword: str, client, model: str) -> dict:
    keyword = (keyword or "").strip()

    if not keyword:
        return {
            "keyword": "",
            "reason": "",
            "insight": "",
            "health_angle": "",
            "converted_topic": "",
            "topics": [],
        }

    system_prompt = """
너는 한국어 쇼츠 기획 전문가다.
역할:
- 트렌드 키워드의 맥락을 자연스럽게 해석한다.
- 억지 연결은 하지 않는다.
- 건강 연결이 가능하면 흥미롭고 사람다운 방식으로 연결한다.
- 건강 연결이 약하면 생활 리듬, 감정, 스트레스, 수면, 몸의 변화 같은 넓은 인간 경험으로 해석한다.
- 기계적으로 "위험", "경고", "체크"만 반복하지 않는다.
- 뻔한 문장을 피하고, 실제 쇼츠에서 클릭하고 싶을 만한 주제로 만든다.

반드시 JSON만 출력:
{
  "reason": "왜 이 키워드가 관심을 받는지 한 문장",
  "insight": "사람들이 왜 이걸 궁금해하는지 한 문장",
  "health_angle": "건강과 연결 가능하면 한 문장, 어렵다면 빈 문자열",
  "converted_topic": "최종 쇼츠 주제 한 문장",
  "topics": ["대안 주제1", "대안 주제2", "대안 주제3"]
}
"""

    user_prompt = f"""
트렌드 키워드: {keyword}

조건:
- reason은 현재 왜 관심을 받는지 추론
- insight는 사람 심리나 상황 중심
- health_angle은 가능할 때만 자연스럽게
- converted_topic은 건강 또는 몸의 변화, 생활 리듬, 감정, 수면, 피로, 식습관 등과 자연스럽게 연결한 쇼츠 주제
- topics는 3개
- 전부 한국어
- 제목처럼 짧고 강하게
- 억지 의료 단정 금지
"""

    try:
        resp = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        text = getattr(resp, "output_text", "") or ""
        data = _extract_json_object(text)

        reason = (data.get("reason") or "").strip()
        insight = (data.get("insight") or "").strip()
        health_angle = (data.get("health_angle") or "").strip()
        converted_topic = (data.get("converted_topic") or "").strip()
        topics = data.get("topics") or []

        clean_topics = []
        for item in topics:
            s = str(item).strip()
            if s:
                clean_topics.append(s)

        if converted_topic and converted_topic not in clean_topics:
            clean_topics.insert(0, converted_topic)

        if not clean_topics and converted_topic:
            clean_topics = [
                converted_topic,
                f"{converted_topic} 왜 더 피곤하게 느껴질까?",
                f"{converted_topic} 몸이 먼저 보내는 신호",
            ]

        return {
            "keyword": keyword,
            "reason": reason,
            "insight": insight,
            "health_angle": health_angle,
            "converted_topic": converted_topic,
            "topics": clean_topics[:3],
        }

    except Exception:
        fallback_topic = f"{keyword} 이슈가 사람 몸과 일상에 주는 변화"
        return {
            "keyword": keyword,
            "reason": f"{keyword} 관련 관심이 높아지며 검색량이 증가했습니다.",
            "insight": "사람들은 지금 이 키워드가 자신의 일상과 어떤 관련이 있는지 궁금해합니다.",
            "health_angle": "이슈가 직접 건강 키워드가 아니어도 스트레스, 수면, 피로, 생활 리듬 변화와 연결해 볼 수 있습니다.",
            "converted_topic": fallback_topic,
            "topics": [
                fallback_topic,
                f"{keyword} 때문에 요즘 더 피곤한 이유",
                f"{keyword} 같은 이슈가 반복될 때 몸이 받는 부담",
            ],
        }

TREND_LLM_CACHE = {}
TREND_LLM_CACHE_TTL = 60 * 30  # 30분


def get_cached_trend_interpretation(keyword: str, client, model: str) -> dict:
    now = time.time()
    cache_key = f"{model}::{(keyword or '').strip()}"

    cached = TREND_LLM_CACHE.get(cache_key)
    if cached and (now - cached["ts"] < TREND_LLM_CACHE_TTL):
        return cached["data"]

    data = interpret_trend_with_llm(keyword, client=client, model=model)
    TREND_LLM_CACHE[cache_key] = {
        "ts": now,
        "data": data,
    }
    return data


def get_topic_trends(client, model: str):
    keywords = fetch_google_trends_keywords()[:5]

    results = []
    for kw in keywords:
        info = get_cached_trend_interpretation(kw, client=client, model=model)
        topics = info.get("topics") or []

        if not topics:
            topics = [info.get("converted_topic") or kw]

        best_score = max(score_topic(topic) for topic in topics)

        results.append(
            {
                "keyword": kw,
                "topics": topics,
                "score": best_score,
                "reason": info.get("reason", ""),
                "insight": info.get("insight", ""),
                "health_angle": info.get("health_angle", ""),
                "converted_topic": info.get("converted_topic", ""),
            }
        )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results