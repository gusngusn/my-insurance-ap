import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

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

# --- [2. 데이터 로드 및 초기화] ---
st.set_page_config(page_title="배현우 FC 고객관리 v44.0", layout="wide")
sheet = get_gsheet()

# 시트 헤더 순서 고정
headers = ["등록일자", "이름", "주민번호", "연락처", "주소", "직업", "계좌번호", "자동차보험", "자동차보험회사", "가입일자"]

if sheet:
    raw_data = sheet.get_all_values()
    if len(raw_data) > 0:
        db_cust = pd.DataFrame(raw_data[1:], columns=headers[:len(raw_data[0])])
    else:
        db_cust = pd.DataFrame(columns=headers)
else:
    st.error("구글 시트 연결 실패"); st.stop()

# --- [3. 좌측 사이드바 메뉴] ---
with st.sidebar:
    st.header("📋 관리 메뉴")
    # 메뉴 선택
    menu = st.radio("메뉴 이동", ["고객조회 및 수정", "고객 신규등록"])

# --- [4. 메뉴별 기능 구현] ---

# (1) 고객조회 및 수정
if menu == "고객조회 및 수정":
    st.title("🔍 고객 정보 상세 조회")
    search_name = st.text_input("조회할 고객명을 입력하세요")

    if search_name:
        target_res = db_cust[db_cust['이름'] == search_name]

        if not target_res.empty:
            cust = target_res.iloc[0]
            row_idx = target_res.index[0] + 2 # 시트 행 번호
            
            # 정보변경 모드 세션 관리
            if f"edit_{search_name}" not in st.session_state:
                st.session_state[f"edit_{search_name}"] = False

            if not st.session_state[f"edit_{search_name}"]:
                # --- 조회 화면 ---
                st.subheader(f"👤 {search_name} 고객님 정보")
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**이름:** {cust['이름']}")
                    st.write(f"**주민번호:** {cust['주민번호']}")
                    st.write(f"**연락처:** {cust['연락처']}")
                    st.write(f"**주소:** {cust['주소']}")
                    st.write(f"**직업:** {cust['직업']}")
                with c2:
                    st.write(f"**계좌번호:** {cust.get('계좌번호', '-')}")
                    st.write(f"**자동차보험:** {cust.get('자동차보험', '-')}")
                    st.write(f"**보험회사:** {cust.get('자동차보험회사', '-')}")
                    st.write(f"**가입일자:** {cust.get('가입일자', '-')}")
                
                if st.button("📝 정보변경"):
                    st.session_state[f"edit_{search_name}"] = True
                    st.rerun()
            else:
                # --- 수정 화면 (정보변경 버튼 클릭 시) ---
                st.subheader(f"📝 {search_name} 고객 정보 수정")
                with st.form("update_form"):
                    u1, u2 = st.columns(2)
                    with u1:
                        up_name = st.text_input("이름", value=cust['이름'])
                        up_jumin = st.text_input("주민번호", value=cust['주민번호'])
                        up_phone = st.text_input("연락처", value=cust['연락처'])
                        up_addr = st.text_input("주소", value=cust['주소'])
                        up_job = st.text_input("직업", value=cust['직업'])
                    with u2:
                        up_acc = st.text_input("계좌번호", value=cust.get('계좌번호', ''))
                        up_car = st.text_input("자동차보험", value=cust.get('자동차보험', ''))
                        up_car_comp = st.text_input("자동차보험회사", value=cust.get('자동차보험회사', ''))
                        up_date = st.text_input("가입일자", value=cust.get('가입일자', ''))
                    
                    if st.form_submit_button("💾 변경 내용 저장"):
                        updated_row = [datetime.now().strftime("%Y-%m-%d"), up_name, up_jumin, up_phone, up_addr, up_job, up_acc, up_car, up_car_comp, up_date]
                        for i, val in enumerate(updated_row):
                            sheet.update_cell(row_idx, i + 1, val)
                        st.success("정보가 변경되었습니다."); st.session_state[f"edit_{search_name}"] = False; st.rerun()
                
                if st.button("취소"):
                    st.session_state[f"edit_{search_name}"] = False; st.rerun()
        else:
            # 등록되지 않은 고객일 경우
            st.error(f"'{search_name}' 고객님은 등록되지 않은 이름입니다.")
            if st.button(f"➕ {search_name} 신규 등록하러 가기"):
                st.session_state.temp_name = search_name
                # 메뉴 세션 상태를 변경하여 신규등록 화면으로 유도
                st.info("신규등록 메뉴를 클릭하여 등록을 진행해주세요.")

# (2) 고객 신규등록
if menu == "고객 신규등록":
    st.title("➕ 신규 고객 등록")
    # 조회에서 넘어온 이름이 있다면 자동 입력
    pre_name = st.session_state.get("temp_name", "")
    
    with st.form("reg_form"):
        st.write("항목별로 정보를 입력하세요.")
        r1, r2 = st.columns(2)
        with r1:
            r_name = st.text_input("이름", value=pre_name)
            r_jumin = st.text_input("주민번호")
            r_phone = st.text_input("연락처")
            r_addr = st.text_input("주소")
            r_job = st.text_input("직업")
        with r2:
            r_acc = st.text_input("계좌번호")
            r_car = st.text_input("자동차보험(상품명)")
            r_car_comp = st.text_input("자동차보험회사")
            r_date = st.date_input("가입일자")
            
        if st.form_submit_button("✅ 신규 고객 등록"):
            if r_name and r_jumin:
                new_row = [datetime.now().strftime("%Y-%m-%d"), r_name, r_jumin, r_phone, r_addr, r_job, r_acc, r_car, r_car_comp, r_date.strftime("%Y-%m-%d")]
                sheet.append_row(new_row)
                st.success(f"{r_name} 고객님 등록 완료!")
                if "temp_name" in st.session_state: del st.session_state.temp_name
            else:
                st.warning("이름과 주민번호는 필수입니다.")
