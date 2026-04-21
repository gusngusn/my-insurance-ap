import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- [1. 구글 시트 연결 설정] ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).sheet1
    except:
        return None

# --- [2. 초기 세팅] ---
st.set_page_config(page_title="고객 관리 시스템", layout="wide")
sheet = get_gsheet()

if sheet:
    raw_data = sheet.get_all_values()
    if len(raw_data) > 0:
        headers = raw_data[0]
        db_cust = pd.DataFrame(raw_data[1:], columns=headers)
    else:
        db_cust = pd.DataFrame(columns=["이름", "주민번호", "연락처", "주소", "직업"])
else:
    st.error("시트에 연결할 수 없습니다.")
    st.stop()

# --- [3. 좌측 사이드바 버튼] ---
with st.sidebar:
    st.header("메뉴")
    if st.button("👥 고객정보 관리", use_container_width=True):
        st.session_state.menu = "customer_info"

# --- [4. 메인 화면 로직] ---
if "menu" in st.session_state and st.session_state.menu == "customer_info":
    st.title("👤 고객정보 조회 및 등록")
    
    # 1) 고객 조회
    search_name = st.text_input("조회할 고객 이름을 입력하세요")
    
    if search_name:
        # 검색 결과 확인
        result = db_cust[db_cust['이름'] == search_name]
        
        if not result.empty:
            st.subheader(f"✅ '{search_name}' 고객 정보")
            st.table(result)
        else:
            st.warning(f"'{search_name}' 이름으로 등록된 고객이 없습니다.")
            
            # 2) 신규 등록 버튼 및 입력란
            st.markdown("---")
            st.subheader("🆕 신규 고객 등록")
            with st.form("new_customer_form"):
                new_name = st.text_input("이름", value=search_name)
                new_jumin = st.text_input("주민번호")
                new_phone = st.text_input("연락처")
                new_addr = st.text_input("주소")
                new_job = st.text_input("직업")
                
                if st.form_submit_button("등록하기"):
                    if new_name and new_jumin:
                        # 시트에 데이터 추가
                        sheet.append_row([new_name, new_jumin, new_phone, new_addr, new_job])
                        st.success(f"{new_name} 고객님이 성공적으로 등록되었습니다.")
                        st.rerun()
                    else:
                        st.error("이름과 주민번호는 필수 입력 항목입니다.")
else:
    st.title("메뉴를 선택해 주세요.")
    st.write("좌측의 [고객정보 관리] 버튼을 누르면 조회가 시작됩니다.")
