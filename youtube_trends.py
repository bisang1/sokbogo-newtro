import requests
import xml.etree.ElementTree as ET


# 유튜브 인기 영상
def fetch_youtube_trends(api_key, region="KR", max_results=10):

    url = "https://www.googleapis.com/youtube/v3/videos"

    params = {
        "part": "snippet,statistics",
        "chart": "mostPopular",
        "regionCode": region,
        "maxResults": max_results,
        "key": api_key
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()

        videos = []

        for item in data.get("items", []):
            videos.append({
                "title": item["snippet"]["title"],
                "channel": item["snippet"]["channelTitle"]
            })

        return videos

    except:
        return []


# 실시간 검색 트렌드
def fetch_realtime_trends():

    url = "https://trends.google.com/trending/rss?geo=KR"

    try:
        r = requests.get(url, timeout=10)

        root = ET.fromstring(r.text)

        trends = []

        for item in root.findall(".//item"):
            trends.append(item.find("title").text)

        return trends[:20]

    except:
        return []


# 건강 주제 생성
def generate_health_topics(trends):

    topics = []

    for t in trends:

        topics.append(f"{t} 이슈로 보는 건강 영향")
        topics.append(f"{t} 시즌 건강 관리 방법")
        topics.append(f"{t} 때 조심해야 할 건강 신호")

    # 기본 주제 fallback
    fallback = [
        "신장이 망가지기 전에 오는 변화",
        "심장이 보내는 위험 신호",
        "혈압이 높아질 때 몸의 변화",
        "간이 나빠질 때 나타나는 증상",
        "혈당이 올라갈 때 몸의 변화",
        "가슴 답답함 위험 신호",
        "피곤이 계속될 때 의심 질환",
        "손발 저림 건강 신호",
        "어지럼증 위험 신호",
        "몸이 붓는 이유"
    ]

    topics.extend(fallback)

    # 중복 제거
    topics = list(dict.fromkeys(topics))

    return topics[:20]


# 전체 실행
def get_health_trends(youtube_api_key):

    youtube = fetch_youtube_trends(youtube_api_key)

    realtime = fetch_realtime_trends()

    keywords = realtime + [v["title"] for v in youtube]

    topics = generate_health_topics(keywords)

    return {
        "youtube": youtube,
        "realtime": realtime,
        "topics": topics
    }