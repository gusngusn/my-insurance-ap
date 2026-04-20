import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 구글 시트 연동 설정 ---
# 현우님의 구글 시트 주소에서 복사한 ID를 아래에 넣으세요
SHEET_ID = '여기에_복사한_시트_ID를_넣으세요' 
SHEET_URL = f'https://docs.google.com/spreadsheets/d/{1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY/edit?gid=0#gid=0}/gviz/tq?tqx=out:csv'

st.set_page_config(page_title="현우 통합 보험 솔루션 v2.1 (Cloud)", layout="wide")

# 데이터 불러오기 함수
def load_data():
    try:
        # 구글 시트를 CSV 형태로 읽어옵니다.
        df = pd.read_csv(SHEET_URL).fillna("")
        return df
    except:
        st.error("구글 시트를 불러올 수 없습니다. ID와 공유 설정을 확인해주세요.")
        return pd.DataFrame()

# 데이터 저장 안내 (웹 버전은 시트로 직접 저장하는 추가 설정이 필요함)
# 우선은 시트 데이터를 기반으로 검색/조회하는 기능을 먼저 구현했습니다.

st.title("🛡️ 배현우 설계사 클라우드 영업 시스템 v2.1")

# --- 탭 구성 ---
tab_search, tab_reg = st.tabs(["🔍 고객 통합 검색", "📝 데이터 관리 안내"])

with tab_search:
    db = load_data()
    if not db.empty:
        search_name = st.text_input("🔎 검색할 고객 성함을 입력하세요")
        
        if search_name:
            user_data = db[db['이름'].str.contains(search_name)]
            if not user_data.empty:
                for idx, row in user_data.iterrows():
                    with st.expander(f"👤 {row['이름']} 상세 정보", expanded=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**연락처:** {row['연락처']}")
                            st.write(f"**주민번호:** {row['주민번호']}")
                            st.write(f"**주소:** {row['주소']}")
                            st.write(f"**특이사항:** {row['병력(특이사항)']}")
                        with col2:
                            # 보장 그래프 시각화
                            vals = [row['암'], row['뇌'], row['심'], row['수술']]
                            fig = go.Figure(go.Scatterpolar(r=vals, theta=['암', '뇌', '심', '수술'], fill='toself'))
                            st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("고객을 찾을 수 없습니다.")

with tab_reg:
    st.info("💡 클라우드 버전에서는 구글 시트에서 직접 데이터를 수정하면 프로그램에 즉시 반영됩니다.")
    st.markdown(f"[내 구글 시트 바로가기](https://docs.google.com/spreadsheets/d/{SHEET_ID})")