from datetime import date
import io
import re
import matplotlib.pyplot as plt
import pandas as pd
import requests
import seaborn as sns
import streamlit as st

# 기상청 기간 일 관측 API 엔드포인트 및 인증키
API_BASE_URL = "https://apihub.kma.go.kr/api/typ01/url/kma_sfcdd3.php"
AUTH_KEY = st.secrets.get("AUTH_KEY", "cDzxUQ5sScu88VEObKnLyA")


def load_kma_data(
    start_date: date, end_date: date, stn: int = 108
) -> pd.DataFrame:
    """기상청 기간 일 관측 API(kma_sfcdd3)를 단일 호출하여 TA_MAX(최고기온), HM_AVG(평균습도)를 추출하는 함수"""
    params = {
        "tm1": start_date.strftime("%Y%m%d"),
        "tm2": end_date.strftime("%Y%m%d"),
        "stn": stn,
        "help": 0,
        "authKey": AUTH_KEY,
    }

    records = []
    try:
        response = requests.get(API_BASE_URL, params=params, timeout=10)
        if response.status_code == 200:
            lines = response.text.strip().split("\n")
            header_cols = []

            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue

                # 헤더 라인 탐색 (컬럼 위치 매핑용)
                if line_str.startswith("#") and "TM" in line_str:
                    clean_header = line_str.lstrip("#").strip()
                    header_cols = re.split(r"\s+", clean_header)
                    continue

                # 주석 제외 실제 데이터 처리
                if not line_str.startswith("#"):
                    cols = re.split(r"\s+", line_str)

                    # 헤더 탐색 성공 시 이름 기반 인덱싱, 실패 시 기본 인덱스 매핑
                    if (
                        header_cols
                        and "TM" in header_cols
                        and "TA_MAX" in header_cols
                        and "HM_AVG" in header_cols
                    ):
                        tm_idx = header_cols.index("TM")
                        ta_max_idx = header_cols.index("TA_MAX")
                        hm_avg_idx = header_cols.index("HM_AVG")
                    else:
                        tm_idx, ta_max_idx, hm_avg_idx = 0, 11, 13

                    if (
                        len(cols)
                        > max(tm_idx, ta_max_idx, hm_avg_idx)
                        and cols[tm_idx].isdigit()
                        and len(cols[tm_idx]) == 8
                    ):
                        try:
                            records.append(
                                {
                                    "date": pd.to_datetime(
                                        cols[tm_idx], format="%Y%m%d"
                                    ),
                                    "TA_MAX": float(cols[ta_max_idx]),
                                    "HM_AVG": float(cols[hm_avg_idx]),
                                }
                            )
                        except ValueError:
                            continue
    except Exception:
        pass

    # 결합 실패 및 KeyError 방지 기본 DataFrame
    if not records:
        return pd.DataFrame(columns=["date", "TA_MAX", "HM_AVG"])

    return pd.DataFrame(records)


def load_google_trend_csv(uploaded_file) -> pd.DataFrame:
    """업로드된 구글 트렌드 CSV 파일의 다중 인코딩을 처리하고 날짜와 검색량을 추출하는 함수"""
    file_bytes = uploaded_file.read()
    df = None

    # 한글 깨짐 방지 인코딩 순차 시도
    for encoding in ["utf-8-sig", "utf-8", "cp949", "euc-kr"]:
        try:
            content = file_bytes.decode(encoding)
            # 구글 트렌드 상단 주석 제외 로드
            temp_df = pd.read_csv(io.StringIO(content), skiprows=1)
            if len(temp_df.columns) >= 2:
                df = temp_df
                break
        except UnicodeDecodeError:
            continue

    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "search_volume"])

    # 앞의 두 열을 날짜, 검색량으로 지정
    df = df.iloc[:, :2]
    df.columns = ["date", "search_volume"]

    # 날짜 정제 및 검색량 기호 제거
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["search_volume"] = (
        df["search_volume"].astype(str).str.replace("<", "").astype(float)
    )

    return df.dropna(subset=["date"])


def display_kpi_metrics(df: pd.DataFrame):
    """분석 일수, 최고 기온 평균, 폭염일수(33도 이상) 통계를 출력하는 함수"""
    total_days = len(df)
    avg_ta_max = df["TA_MAX"].mean() if total_days > 0 else 0.0
    heatwave_days = (df["TA_MAX"] >= 33.0).sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("분석 일수", f"{total_days}일")
    col2.metric("최고 기온 평균", f"{avg_ta_max:.1f} °C")
    col3.metric("폭염일 수 (33°C 이상)", f"{heatwave_days}일")


def render_heatmap(merged_df: pd.DataFrame):
    """가로축 습도, 세로축 최고 기온으로 두고 검색량에 따라 색상이 진해지는 히트맵 생성 함수"""
    pivot_table = merged_df.pivot_table(
        index="TA_MAX",
        columns="HM_AVG",
        values="search_volume",
        aggfunc="mean",
    )
    # 높은 기온이 위로 가도록 정렬
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

    st.sidebar.header("설정 및 파일 업로드")

    # 2026년 1월 1일 ~ 2026년 11월 11일 슬라이더
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
            # 1. 기상청 API 데이터 일괄 수신 (서울 지점 108)
            weather_df = load_kma_data(start_date, end_date, stn=108)

            # 2. 구글 트렌드 CSV 데이터 처리
            trend_df = load_google_trend_csv(uploaded_file)

        # 유효성 검사
        if weather_df.empty:
            st.error(
                "기상청 API로부터 데이터를 불러오지 못했습니다. 인증키, 지점번호 또는 일자를 확인하세요."
            )
            return

        if trend_df.empty:
            st.error("구글 트렌드 CSV 파일의 데이터를 정상적으로 읽지 못했습니다.")
            return

        # 3. 날짜 기준 결합
        merged_df = pd.merge(weather_df, trend_df, on="date", how="inner")

        if not merged_df.empty:
            display_kpi_metrics(merged_df)
            st.write("---")
            st.subheader("기온 및 습도별 검색량 히트맵")
            render_heatmap(merged_df)

            with st.expander("결합 데이터 상세 보기"):
                st.dataframe(merged_df)
        else:
            st.warning(
                "선택한 기간의 기상 데이터와 CSV 파일 내 날짜가 일치하지 않습니다. 기간 설정을 확인해 주세요."
            )
    else:
        st.info("왼쪽 사이드바에서 구글 트렌드 CSV 파일을 업로드해 주세요.")


if __name__ == "__main__":
    main()
