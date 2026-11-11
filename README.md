# 폭염과 습도에 따른 키워드 검색량 분석
본 프로젝트는 기상청 종관기상관측(ASOS) 데이터와 구글 트렌드 검색어 데이터를 융합하여 기상 요소(최고기온, 평균습도)가 특정 키워드('폭염', '날씨') 검색량 변화에 미치는 영향을 분석하는 Streamlit 기반 웹 대시보드입니다.

## 앱 바로가기
https://team05-9vnswd6v3mquusikp5vogd.streamlit.app/

## team05 팀원
- 한치영
- 전서현

## 실행 방법


1. 저장소 복제 (GitHub에 업로드된 프로젝트 코드를 로컬 컴퓨터로 내려받습니다)

git clone https://github.com/shjeon32/team05.git


2. 프로젝트 디렉토리 이동 (다운로드한 프로젝트 폴더 내부로 진입합니다)

cd team05


3. 필수 라이브러리 설치 (실행에 필요한 외부 패키지들을 일괄 설치합니다)

pip install -r requirements.txt


4. Streamlit 웹 애플리케이션 실행 (로컬 웹 서버를 구동하여 브라우저에서 대시보드를 엽니다)

streamlit run app.py

5. 구글 트렌드 검색량 CSV 파일 업로드

대시보드 왼쪽 사이드바의 구글 트렌드 CSV 파일 업로드 영역에서 Browse files 버튼을 클릭합니다.

분석하고자 하는 구글 트렌드 일별 검색량 CSV 파일(예: 저장소 내의 keyword_날씨.csv 또는 신규 다운로드 파일)을 선택하여 업로드합니다.

파일이 업로드되면 사이드바의 기간 슬라이더와 연동되어 해당 파일의 날짜 및 검색량 데이터가 기상 관측 데이터와 자동으로 결합·시각화됩니다.

별도의 파일을 업로드하지 않은 상태에서는 저장소의 기본 데이터('keyword_폭염.csv')가 자동으로 적용됩니다.

참고) 기상청 API 키 직접 입력 방법

- 로컬 환경 실행 시 기상청 API 키가 사전에 설정되어 있지 않은 경우, 왼쪽 사이드바에 기상청 API 키 입력 (선택) 입력창이 나타납니다.

- 발급받은 본인의 기상청 API 키를 해당 입력창에 직접 입력하면 실시간 기상 관측 데이터를 즉시 호출하여 분석에 반영할 수 있습니다.

   
   
## 사용 라이브러리
- streamlit
- pandas
- requests
- matplotlib
- seaborn

## 앱 실행 화면
<img width="1881" height="925" alt="image" src="https://github.com/user-attachments/assets/cf0927e8-668c-4afd-9f74-93fe9e25d1ab" />
