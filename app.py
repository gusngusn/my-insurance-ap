import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 구글 시트 연결 설정 (현우님 시트 ID 적용 완료) ---
# 주소에서 핵심 ID인 '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'만 사용합니다.
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
SHEET_URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0'

st.set_page_config(page_title="현우 통합 보험 솔루션 v2.2", layout="wide")

# 데이터 불러오기 함수
def load_data():
    try:
        # 구글 시트를 CSV 형태로 읽어옵니다.
        df = pd.read_csv(SHEET_URL)
        return df.fillna("")
    except Exception as e:
        st.error(f"⚠️ 구글 시트 연결 실패: {e}")
        st.info("시트 오른쪽 상단 [공유] -> [링크가 있는 모든 사용자] -> [편집자]로 설정되어 있는지 확인해주세요.")
        return pd.DataFrame()

st.title("🛡️ 배현우 설계사 클라우드 영업 시스템 v2.2")

# --- 탭 구성 ---
tab_search, tab_manage = st.tabs(["🔍 고객 통합 검색", "⚙️ 시스템 관리"])

with tab_search:
    db = load_data()
    if not db.empty:
        search_name = st.text_input("🔎 검색할 고객 성함을 입력하세요", "")
        
        if search_name:
            # 이름으로 검색 (대소문자 구분 없이)
            user_data = db[db['이름'].astype(str).str.contains(search_name)]
            
            if not user_data.empty:
                for idx, row in user_data.iterrows():
                    with st.expander(f"👤 {row['이름']} 상세 정보 보기", expanded=True):
                        col1, col2 = st.columns([1, 1])
                        
                        with col1:
                            st.markdown("### 📋 인적 사항 및 메모")
                            st.write(f"**연락처:** {row['연락처']}")
                            st.write(f"**주민번호:** {row['주민번호']}")
                            st.write(f"**주소:** {row['주소']}")
                            st.write(f"**직업:** {row['직업']}")
                            st.info(f"**병력 및 특이사항:**\n\n{row['병력(특이사항)']}")
                            st.write(f"**가족 대표:** {row['가족대표']}")

                        with col2:
                            st.markdown("### 📊 보장 현황")
                            # 보장 데이터 (구글 시트 숫자를 기반으로 그래프 생성)
                            labels = ['암', '뇌', '심', '수술']
                            try:
                                # 시트의 데이터를 숫자로 변환
                                vals = [float(row['암']), float(row['뇌']), float(row['심']), float(row['수술'])]
                                targets = [5000, 2000, 2000, 100]
                                pcts = [(v/t)*100 for v, t in zip(vals, targets)]
                                
                                fig = go.Figure(go.Scatterpolar(r=pcts, theta=labels, fill='toself', line_color='#E91E63'))
                                fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), height=350)
                                st.plotly_chart(fig, use_container_width=True)
                                
                                st.write(f"✅ 현재 보장액: 암 {vals[0]}만 / 뇌 {vals[1]}만 / 심 {vals[2]}만 / 수술 {vals[3]}만")
                            except:
                                st.warning("보장 금액 데이터가 숫자가 아닙니다. 구글 시트를 확인해주세요.")
            else:
                st.warning(f"'{search_name}' 고객님을 찾을 수 없습니다.")
    else:
        st.info("구글 시트에 데이터를 입력하면 여기에 나타납니다.")

with tab_manage:
    st.subheader("🔗 데이터 동기화 안내")
    st.write("본 프로그램은 구글 시트와 실시간으로 연동됩니다.")
    st.markdown(f"[📂 내 구글 시트 바로가기 (클릭)](https://docs.google.com/spreadsheets/d/{SHEET_ID})")
    st.write("---")
    st.write("1. 구글 시트에 고객 정보를 입력하거나 수정하세요.")
    st.write("2. 프로그램에서 이름을 검색하면 수정된 내용이 즉시 반영됩니다.")