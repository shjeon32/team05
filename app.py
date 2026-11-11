from datetime import date
import io
import os
import re
import matplotlib.pyplot as plt
import pandas as pd
import requests
import seaborn as sns
import streamlit as st

API_BASE_URL = "https://apihub.kma.go.kr/api/typ01/url/kma_sfcdd3.php"
DEFAULT_CSV_PATH = "keyword_폭염.csv"


def get_api_key() -> str:
    """Streamlit Secrets 또는 사이드바 입력창에서 API 키를 안전하게 획득합니다."""
    # 1. secrets 파일이 존재하고 키가 있는지 안전하게 확인
    try:
        if "KMA_AUTH_KEY" in st.secrets:
            return st.secrets["KMA_AUTH_KEY"]
    except Exception:
        pass

    # 2. 로컬 컴퓨터에 secrets.toml이 없으면 사이드바 입력창 제공
    return st.sidebar.text_input(
        "기상청 API 키 입력 (선택)",
        type="password",
        help="Secrets 설정이 없을 때 직접 입력할 수 있습니다.",
    )


def load_kma_data(
    start_date: date, end_date: date, auth_key: str, stn: int = 108
) -> pd.DataFrame:
    """기상청 일 관측 API를 단일 호출하여 최고기온(TA_MAX)과 평균습도(HM_AVG)를 수집합니다."""
    if not auth_key:
        return pd.DataFrame()

    params = {
        "tm1": start_date.strftime("%Y%m%d"),
        "tm2": end_date.strftime("%Y%m%d"),
        "stn": stn,
        "help": 0,
        "authKey": auth_key,
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

                if line_str.startswith("#") and "TM" in line_str:
                    clean_header = line_str.lstrip("#").strip()
                    header_cols = re.split(r"\s+", clean_header)
                    continue

                if not line_str.startswith("#"):
                    cols = re.split(r"\s+", line_str)

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
                        len(cols) > max(tm_idx, ta_max_idx, hm_avg_idx)
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
    except Exception as e:
        st.error(f"기상청 API 수신 중 오류 발생: {e}")

    if not records:
        return pd.DataFrame(columns=["date", "TA_MAX", "HM_AVG"])

    return pd.DataFrame(records)


def load_google_trend_csv(source) -> pd.DataFrame:
    """업로드된 파일 객체 또는 파일 경로를 입력받아 데이터를 정제합니다."""
    if hasattr(source, "read"):
        file_bytes = source.read()
    else:
        with open(source, "rb") as f:
            file_bytes = f.read()

    df = None
    for encoding in ["utf-8-sig", "utf-8", "cp949", "euc-kr"]:
        try:
            content = file_bytes.decode(encoding)
            temp_df = pd.read_csv(io.StringIO(content), skiprows=1)
            if len(temp_df.columns) >= 2:
                df = temp_df
                break
        except UnicodeDecodeError:
            continue

    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "search_volume"])

    df = df.iloc[:, :2]
    df.columns = ["date", "search_volume"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["search_volume"] = (
        df["search_volume"].astype(str).str.replace("<", "").astype(float)
    )

    return df.dropna(subset=["date"])


def display_kpi_metrics(df: pd.DataFrame):
    """주요 지표 3가지를 상단에 표시합니다."""
    total_days = len(df)
    avg_ta_max = df["TA_MAX"].mean() if total_days > 0 else 0.0
    heatwave_days = (df["TA_MAX"] >= 33.0).sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("분석 일수", f"{total_days}일")
    col2.metric("최고 기온 평균", f"{avg_ta_max:.1f} °C")
    col3.metric("폭염일 수 (33°C 이상)", f"{heatwave_days}일")


def render_heatmap(merged_df: pd.DataFrame):
    """기온-습도별 검색량 히트맵을 생성합니다."""
    pivot_table = merged_df.pivot_table(
        index="TA_MAX",
        columns="HM_AVG",
        values="search_volume",
        aggfunc="mean",
    )
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
    st.set_page_config(page_title="기온과 습도에 따른 키워드 검색량 분석", layout="wide")
    st.title("기온과 습도에 따른 키워드 검색량 분석")

    st.sidebar.header("설정 및 파일 업로드")

    auth_key = get_api_key()

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

    start_date, end_date = selected_dates

    # 1. 트렌드 데이터 취득 (업로드 파일 우선, 미업로드 시 저장소 기본 CSV 자동 로드)
    trend_df = pd.DataFrame()
    if uploaded_file is not None:
        trend_df = load_google_trend_csv(uploaded_file)
    elif os.path.exists(DEFAULT_CSV_PATH):
        st.info(f"별도 파일이 업로드되지 않아 저장소 내 기본 데이터('{DEFAULT_CSV_PATH}')를 표시합니다.")
        trend_df = load_google_trend_csv(DEFAULT_CSV_PATH)
    else:
        st.info("왼쪽 사이드바에서 구글 트렌드 CSV 파일을 업로드해 주세요.")
        return

    # 2. 기상청 API 데이터 호출
    with st.spinner("기상 데이터 수신 중..."):
        weather_df = load_kma_data(start_date, end_date, auth_key=auth_key, stn=108)

    if weather_df.empty:
        st.warning("기상 데이터를 불러오지 못했습니다. API 키 및 기간 설정을 확인해 주세요.")
        st.subheader("업로드된 트렌드 데이터 샘플")
        st.dataframe(trend_df.head(10))
        return

    # 3. 데이터 결합 및 대시보드 렌더링
    merged_df = pd.merge(weather_df, trend_df, on="date", how="inner")

    if not merged_df.empty:
        display_kpi_metrics(merged_df)
        st.write("---")
        st.subheader("기온 및 습도별 검색량 히트맵")
        render_heatmap(merged_df)

        with st.expander("결합 데이터 전체 보기"):
            st.dataframe(merged_df)
    else:
        st.warning("선택한 기간의 기상 데이터 날짜와 트렌드 CSV의 날짜가 일치하지 않습니다. 기간 설정을 조정해 주세요.")


if __name__ == "__main__":
    main()
