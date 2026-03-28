from openai import OpenAI


# 사람 이름 필터
INVALID_KEYWORDS = ["장동민", "최민정", "리그", "유나", "news"]

def is_invalid_topic(text: str) -> bool:
    return any(name in text for name in INVALID_KEYWORDS)

client = OpenAI()





def generate_topics_from_trend(trend_keyword: str, n: int = 3):
    """
    트렌드 키워드를 쇼츠 주제로 변환
    """

    prompt = f"""
너는 조회수 높은 한국어 건강 쇼츠 주제 기획자다.

트렌드 키워드:
{trend_keyword}

목표:
트렌드 키워드를 건강 쇼츠 주제로 자연스럽게 변환하라.

반드시 지킬 규칙:
1. 트렌드 키워드를 제목에 직접 반복하지 말 것
2. 사람 이름, 팀 이름, 공연명, 사건명, 브랜드명, 연예인 이름은 제목에 넣지 말 것
3. 트렌드에서 느껴지는 상황/감정/행동을 건강 주제로 번역할 것
4. 제목은 건강 정보 쇼츠에 맞게 "증상", "몸의 신호", "피로", "회복", "수면", "염증", "습관", "장", "위", "면역", "통증" 같은 언어로 바꿀 것
5. 자극적이되 이상하지 않게, 클릭하고 싶게 만들 것
6. 짧고 자연스러운 한국어 제목으로 만들 것
7. 결과는 반드시 5개
8. 제목만 출력할 것, 번호만 붙일 것
9. 설명 문장, 해설, 괄호, 영어 문구 넣지 말 것
10. 제목은 반드시 클릭 유도형으로 작성할 것
11. "이유", "신호", "위험", "경고", "지금", "절대", "반드시" 같은 단어를 적극 사용할 것
12. 궁금증을 유발하는 문장으로 만들 것
13. 평범한 설명형 제목은 금지
14. 사람 이름, 팀 이름 대신 상황과 증상 중심으로 표현할 것




좋은 예시:
1. 아침에 일어나기 힘들다면 봐야 할 신호
2. 운동 후 몸이 보내는 위험 신호
3. 자꾸 피곤한 사람에게 흔한 원인
4. 배가 자주 아프다면 체크할 것
5. 잠을 자도 피곤한 진짜 이유




나쁜 예시:
1. {trend_keyword} 이슈로 보는 건강 영향
2. {trend_keyword} 시즌 건강 관리법
3. {trend_keyword} 때문에 조심해야 할 건강 신호
4. 연예인 이름 + 건강 제목
5. 팀 이름 + 증상 제목

출력 형식 예시:
1. 제목
2. 제목
3. 제목
4. 제목
5. 제목
"""

    res = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {
            "role": "system",
            "content": "너는 조회수 높은 한국어 건강 쇼츠 주제 전문가다. 트렌드 키워드를 건강 주제로 자연스럽게 변환하는 역할이다."
        },
        {
            "role": "user",
            "content": prompt
        }
    ],
    temperature=0.9
)

    text = res.choices[0].message.content

    topics = [t.strip("- ").strip() for t in text.split("\n") if t.strip()]
    topics = [t for t in topics if not is_invalid_topic(t)]

    

    return topics[:n]