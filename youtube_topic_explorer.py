# youtube_topic_explorer.py

from typing import List, Dict


def get_topic_trends(limit: int = 20) -> List[Dict]:
    """
    기존 건강 트렌드와 별개로
    콘텐츠 아이디어용 확장 트렌드
    """

    trends = [
        {
            "keyword": "수면 부족",
            "topics": [
                "밤에 자꾸 깨는 이유",
                "잠들기 전에 하면 안 되는 행동",
                "아침에 피곤한 진짜 이유"
            ],
            "score": 98
        },
        {
            "keyword": "혈당 스파이크",
            "topics": [
                "식후 졸림이 오는 이유",
                "혈당이 갑자기 오르는 습관",
                "혈당 급상승 신호"
            ],
            "score": 97
        },
        {
            "keyword": "미세먼지",
            "topics": [
                "미세먼지 심한 날 몸의 변화",
                "폐가 예민해지는 이유",
                "목이 칼칼한 이유"
            ],
            "score": 95
        },
        {
            "keyword": "야식",
            "topics": [
                "야식이 수면을 망치는 이유",
                "밤에 배고픈 진짜 이유",
                "야식 때문에 혈당이 오르는 이유"
            ],
            "score": 96
        },
        {
            "keyword": "카페인",
            "topics": [
                "커피가 수면을 깨는 이유",
                "카페인에 예민한 사람 특징",
                "오후 커피가 위험한 이유"
            ],
            "score": 92
        },
    ]

    # 부족하면 filler 채우기
    index = 6
    while len(trends) < limit:
        trends.append({
            "keyword": f"트렌드 주제 {index}",
            "topics": [f"건강 정보 {index}"],
            "score": 70
        })
        index += 1

    return trends[:limit]