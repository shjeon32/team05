from datetime import date
import io
import re
import matplotlib.pyplot as plt
import pandas as pd
import requests
import seaborn as sns
import streamlit as st

# 기상청 API 엔드포인트 및 인증키
API_BASE_URL = "https://apihub.kma.go.kr/api/typ01/url/kma_sfcdd.php"
AUTH_KEY = "cDzxUQ5sScu88VEObKnLyA"


def load_kma_data(
    start_date: date, end_date: date, stn: int = 108
) -> pd.DataFrame:
    """지정된 기간 동안 기상청 일 관측 API를 조회하여 최고기온(TA_MAX)과 평균습도(HM_AVG)를 추출하는 함수"""
    date_list = pd.date_range(start=start_date, end=end_date).strftime("%Y%m%d")
    records = []

    for tm in date_list:
        params = {"tm": tm, "stn": stn, "help": 0, "authKey": AUTH_KEY}
        try:
            response = requests.get(API_BASE_URL, params=params, timeout=5)
            if response.status_code == 200:
                for line in response.text.strip().split("\n"):
                    # 주석(#) 제외 및 데이터 행 추출
                    if not line.startswith("#"):
                        cols = re.split(r"\s+", line.strip())
                        # cols[0]: TM, cols[1]: STN, cols[11]: TA_MAX, cols[13]: HM_AVG
                        if len(cols) >= 15 and cols[1] == str(stn):
                            records.append(
                                {
                                    "date": pd.to_datetime(cols[0]),
                                    "TA_MAX": float(cols[11]),
                                    "HM_AVG": float(cols[13]),
                                }
                            )
        except Exception:
            continue

    return pd.DataFrame(records)


def load_google_trend_csv(uploaded_file) -> pd.DataFrame:
    """업로드된 구글 트렌드 CSV 파일의 다중 인코딩을 처리하고 일자 및 검색량을 정제하는 함수"""
    file_bytes = uploaded_file.read()

    # 한글 깨짐 방지를 위한 인코딩 순차 시도
    for encoding in ["utf-8-sig", "utf-8", "cp949", "euc-kr"]:
        try:
            content = file_bytes.decode(encoding)
            # 구글 트렌드 상단 제목행 제외(skiprows=1) 후 로드
            df = pd.read_csv(io.StringIO(content), skiprows=1)
            break
        except UnicodeDecodeError:
            continue

    df.columns = ["date", "search_volume"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    # 검색량 내 '<1' 같은 텍스트 기호 처리 및 결측치 제거
    df["search_volume"] = (
        df["search_volume"].astype(str).str.replace("<", "").astype(float)
    )
    return df.dropna(subset=["date"])


def display_kpi_metrics(df: pd.DataFrame):
    """분석 일수, 최고 기온 평균, 폭염일수(33도 이상) 통표를 계산하여 출력하는 함수"""
    total_days = len(df)
    avg_ta_max = df["TA_MAX"].mean() if total_days > 0 else 0.0
    heatwave_days = (df["TA_MAX"] >= 33.0).sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("분석 일수", f"{total_days}일")
    col2.metric("최고 기온 평균", f"{avg_ta_max:.1f} °C")
    col3.metric("폭염일 수 (33°C 이상)", f"{heatwave_days}일")


def render_heatmap(merged_df: pd.DataFrame):
    """가로축을 습도, 세로축을 최고 기온으로 두고 검색량에 따라 색상이 진해지는 히트맵 생성 함수"""
    # 습도(HM_AVG)와 기온(TA_MAX) 기준 검색량 집계
    pivot_table = merged_df.pivot_table(
        index="TA_MAX",
        columns="HM_AVG",
        values="search_volume",
        aggfunc="mean",
    )
    # 고온이 위로 가도록 정렬
    pivot_table = pivot_table.sort_index(ascending=False)

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.heatmap(
        pivot_table,
        cmap="YlOrRd",
        annot=True,
        fmt=".0f",
        cbar_kws={"label": "Search Volume"},
        ax=ax,
    )

    ax.set_title("Keyword Search Volume by Temperature and Humidity")
    ax.set_xlabel("Humidity (%)")
    ax.set_ylabel("Maximum Temperature (C)")

    st.pyplot(fig)


def main():
    """Streamlit 메인 대시보드 구동 함수"""
    st.set_page_config(page_title="기온과 습도에 따른 키워드 검색량 분석", layout="wide")
    st.title("기온과 습도에 따른 키워드 검색량 분석")

    # 사이드바: 관측 기간 슬라이더 및 CSV 업로드 창
    st.sidebar.header("설정 및 파일 업로드")

    selected_dates = st.sidebar.slider(
        "분석 기간 선택",
        min_value=date(2026, 1, 1),
        max_value=date(2026, 11, 11),
        value=(date(2026, 8, 1), date(2026, 8, 31)),
        format="YYYY-MM-DD",
    )

    uploaded_file = st.sidebar.file_uploader(
        "구글 트렌드 CSV 파일 업로드", type=["csv"]
    )

    if uploaded_file is not None:
        start_date, end_date = selected_dates
        with st.spinner("데이터 처리 중..."):
            # 1. 기상청 API 데이터 수집 (서울 지점 108 기준)
            weather_df = load_kma_data(start_date, end_date, stn=108)

            # 2. 구글 트렌드 CSV 데이터 처리
            trend_df = load_google_trend_csv(uploaded_file)

            # 3. 날짜 기준 결합
            merged_df = pd.merge(weather_df, trend_df, on="date", how="inner")

        if not merged_df.empty:
            # 주요 통계 지표 표시
            display_kpi_metrics(merged_df)

            st.write("---")

            # 히트맵 시각화
            st.subheader("기온 및 습도별 검색량 히트맵")
            render_heatmap(merged_df)

            # 결합 데이터 테이블 표시
            with st.expander("결합 데이터 상세 보기"):
                st.dataframe(merged_df)
        else:
            st.warning(
                "선택한 기간에 일치하는 데이터가 CSV 파일에 없습니다. 기간 또는 파일을 확인하세요."
            )
    else:
        st.info("왼쪽 사이드바에서 구글 트렌드 CSV 파일을 업로드해 주세요.")


if __name__ == "__main__":
    main()
