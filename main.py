import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.caption("KOBIS 영화관입장권통합전산망 일일 박스오피스")


# --------------------------------------------------
# 한국 시간 기준으로 '어제' 날짜 계산
# --------------------------------------------------

# 배포 서버의 시간이 한국 시간이 아닐 수 있으므로
# 반드시 Asia/Seoul 시간대를 사용합니다.
KST = ZoneInfo("Asia/Seoul")

now_kst = datetime.now(KST)
yesterday = now_kst.date() - timedelta(days=1)

# KOBIS API가 요구하는 날짜 형식: YYYYMMDD
target_date = yesterday.strftime("%Y%m%d")

# 화면에 보여줄 날짜
display_date = yesterday.strftime("%Y년 %m월 %d일")


# --------------------------------------------------
# KOBIS API 주소
# --------------------------------------------------

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# --------------------------------------------------
# KOBIS API 호출 함수
# --------------------------------------------------

# 같은 날짜에 API를 계속 호출하지 않도록
# 결과를 1시간 동안 캐시합니다.
@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    """
    KOBIS에서 특정 날짜의 일일 박스오피스 정보를 가져옵니다.

    ttl=3600
    → 한 번 가져온 결과를 약 1시간 동안 기억합니다.
    """

    # Streamlit Cloud의 Secrets에서 인증키를 가져옵니다.
    # 실제 인증키는 코드에 작성하지 않습니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except Exception:
        return {
            "success": False,
            "error": "KOBIS_KEY를 Streamlit Secrets에서 찾을 수 없습니다.",
            "data": None
        }

    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        response = requests.get(
            API_URL,
            params=params,
            timeout=10
        )

        # HTTP 오류가 발생하면 예외를 발생시킵니다.
        response.raise_for_status()

        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"KOBIS API 요청에 실패했습니다.\n\n{e}",
            "data": None
        }

    except ValueError:
        return {
            "success": False,
            "error": "KOBIS API의 응답을 JSON으로 읽을 수 없습니다.",
            "data": None
        }

    # --------------------------------------------------
    # KOBIS는 인증키가 틀려도 HTTP 상태코드가 200일 수 있습니다.
    # 따라서 faultInfo가 있는지 반드시 확인합니다.
    # --------------------------------------------------

    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        return {
            "success": False,
            "error": f"KOBIS API 오류가 발생했습니다.\n\n{fault_info}",
            "data": None
        }

    # 정상적인 응답인지 확인합니다.
    if "boxOfficeResult" not in data:
        return {
            "success": False,
            "error": "KOBIS 응답에 boxOfficeResult가 없습니다.",
            "data": None
        }

    box_office_result = data["boxOfficeResult"]

    movie_list = box_office_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "error": (
                "해당 날짜의 영화 목록이 비어 있습니다.\n\n"
                "조회 날짜가 올바른지, KOBIS에서 해당 날짜의 "
                "박스오피스 자료가 집계되었는지 확인해 주세요."
            ),
            "data": None
        }

    return {
        "success": True,
        "error": None,
        "data": movie_list
    }


# --------------------------------------------------
# 데이터 가져오기
# --------------------------------------------------

result = get_boxoffice(target_date)


# --------------------------------------------------
# API 요청 실패 시 안내
# --------------------------------------------------

if not result["success"]:
    st.error("박스오피스 정보를 가져오지 못했습니다.")

    st.warning(
        "다음 항목을 확인해 주세요.\n\n"
        "1. Streamlit Cloud의 Secrets에 `KOBIS_KEY`가 등록되어 있는지\n"
        "2. KOBIS 인증키가 정확한지\n"
        "3. 인터넷 연결 및 KOBIS API가 정상적으로 동작하는지\n"
        "4. 조회 날짜에 박스오피스 자료가 집계되어 있는지"
    )

    st.code(result["error"], language="text")

    st.stop()


# --------------------------------------------------
# DataFrame으로 변환
# --------------------------------------------------

movies = result["data"]

df = pd.DataFrame(movies)


# --------------------------------------------------
# 숫자로 사용할 컬럼을 숫자형으로 변환
# --------------------------------------------------

# KOBIS API에서는 숫자도 문자열로 전달됩니다.
# 따라서 그래프와 정렬에 사용할 수 있도록 숫자로 변환합니다.

numeric_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt"
]

for column in numeric_columns:
    if column in df.columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )


# --------------------------------------------------
# 순위 기준으로 정렬
# --------------------------------------------------

df = df.sort_values("rank").reset_index(drop=True)


# --------------------------------------------------
# 조회 날짜 표시
# --------------------------------------------------

st.subheader(f"📅 {display_date} 박스오피스")

st.write(
    f"한국 시간 기준 **어제({display_date})**의 "
    "일일 박스오피스입니다."
)


# --------------------------------------------------
# 1위 영화 정보
# --------------------------------------------------

if len(df) > 0:

    first_movie = df.iloc[0]

    movie_name = first_movie["movieNm"]
    audience = int(first_movie["audiCnt"])
    accumulated = int(first_movie["audiAcc"])
    screens = int(first_movie["scrnCnt"])

    st.markdown(f"## 🥇 1위: {movie_name}")

    # 1위 영화의 주요 지표 3개를 크게 보여줍니다.
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "어제 관객수",
            f"{audience:,}명"
        )

    with col2:
        st.metric(
            "누적 관객수",
            f"{accumulated:,}명"
        )

    with col3:
        st.metric(
            "스크린수",
            f"{screens:,}개"
        )


# --------------------------------------------------
# 전체 박스오피스 표
# --------------------------------------------------

st.subheader("📊 전체 박스오피스")

# 화면에 보여줄 컬럼과 한글 이름을 정합니다.
table_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()

table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]

# 숫자를 보기 편하게 표시합니다.
table_df["관객수"] = table_df["관객수"].apply(
    lambda x: f"{int(x):,}명" if pd.notna(x) else "-"
)

table_df["누적관객"] = table_df["누적관객"].apply(
    lambda x: f"{int(x):,}명" if pd.notna(x) else "-"
)

table_df["스크린수"] = table_df["스크린수"].apply(
    lambda x: f"{int(x):,}개" if pd.notna(x) else "-"
)

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# 관객수 상위 5편 막대그래프
# --------------------------------------------------

st.subheader("🎟️ 관객수 상위 5편")

# 그래프용 데이터는 숫자형인 원본 df에서 가져옵니다.
top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)

# 영화명을 인덱스로 지정합니다.
chart_df = top5[
    ["movieNm", "audiCnt"]
].set_index("movieNm")

# Streamlit의 기본 막대그래프를 사용합니다.
st.bar_chart(
    chart_df,
    y="audiCnt",
    use_container_width=True
)

st.caption(
    "※ 관객수는 해당 날짜의 일일 관객수입니다."
)
