import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re

# --- [1. 구글 시트 연결 설정] ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheets():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SHEET_ID)
        return spreadsheet.get_worksheet(0), spreadsheet.get_worksheet(1)
    except:
        return None, None

# --- [2. 데이터 로드 및 초기화] ---
st.set_page_config(page_title="배현우 FC 시스템 v49.0", layout="wide")
sheet1, sheet2 = get_gsheets()

h1 = ["등록일자", "이름", "주민번호", "연락처", "주소", "직업", "계좌번호", "차량번호", "자동차보험회사", "가입일자"]
h2 = ["계약자", "가입날짜", "보험회사", "상품명", "금액", "입력시간"]

if sheet1 and sheet2:
    data1 = sheet1.get_all_values()
    db_cust = pd.DataFrame(data1[1:], columns=h1[:len(data1[0])]) if len(data1) > 1 else pd.DataFrame(columns=h1)
    data2 = sheet2.get_all_values()
    db_contract = pd.DataFrame(data2[1:], columns=h2[:len(data2[0])]) if len(data2) > 1 else pd.DataFrame(columns=h2)
else:
    st.error("구글 시트 연결 실패"); st.stop()

if "menu" not in st.session_state:
    st.session_state.menu = "고객조회 및 수정"

# --- [3. 주민번호 마스킹 함수] ---
def mask_jumin(jumin):
    """화면 출력용으로만 주민번호 뒷자리를 마스킹합니다."""
    if not jumin or len(jumin) < 8:
        return jumin
    # 예: 830608-1673921 -> 830608-1******
    return jumin[:8] + "******"

# --- [4. 좌측 사이드바 메뉴] ---
with st.sidebar:
    st.header("📋 관리 메뉴")
    menu_options = ["고객조회 및 수정", "고객 신규등록", "보유계약 리스트 입력"]
    current_idx = menu_options.index(st.session_state.menu)
    st.session_state.menu = st.radio("메뉴 이동", menu_options, index=current_idx)

# --- [5. 메뉴별 기능 구현] ---

if st.session_state.menu == "고객조회 및 수정":
    st.title("🔍 고객 정보 및 보유계약 조회")
    search_name = st.text_input("조회할 고객명을 입력하세요")
    
    if search_name:
        target_res = db_cust[db_cust['이름'] == search_name]
        
        if not target_res.empty:
            cust = target_res.iloc[0]
            if f"edit_{search_name}" not in st.session_state: st.session_state[f"edit_{search_name}"] = False
            
            if not st.session_state[f"edit_{search_name}"]:
                st.subheader(f"👤 {search_name} 고객님 기본 정보")
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**이름:** {cust['이름']}")
                    # 화면 출력 시에만 마스킹 함수 적용
                    st.write(f"**주민번호:** {mask_jumin(cust.get('주민번호', '-'))}") 
                    st.write(f"**연락처:** {cust['연락처']}"); st.write(f"**주소:** {cust['주소']}"); st.write(f"**직업:** {cust['직업']}")
                with c2:
                    st.write(f"**계좌번호:** {cust.get('계좌번호', '-')}")
                    st.write(f"**차량번호:** {cust.get('차량번호', '-')}")
                    st.write(f"**보험회사:** {cust.get('자동차보험회사', '-')}")
                    st.write(f"**가입일자:** {cust.get('가입일자', '-')}")
                
                if st.button("📝 정보변경"): st.session_state[f"edit_{search_name}"] = True; st.rerun()

                st.markdown("---")
                st.subheader(f"📋 {search_name} 고객님 보유계약 현황")
                matched_contracts = db_contract[db_contract['계약자'] == search_name]
                if not matched_contracts.empty:
                    display_df = matched_contracts[["가입날짜", "보험회사", "상품명", "금액"]]
                    display_df.index = range(1, len(display_df) + 1)
                    st.table(display_df)
                else:
                    st.info("등록된 보유계약 내역이 없습니다.")
            else:
                with st.form("update_form"):
                    st.subheader(f"📝 {search_name} 정보 수정")
                    st.warning("⚠️ 개인정보 보호를 위해 수정 시 주민번호 전체를 다시 입력해 주세요.")
                    u1, u2 = st.columns(2)
                    with u1:
                        up_name = st.text_input("이름", value=cust['이름'])
                        # 수정 모드일 때는 기존 값이 빈칸으로 보이게 하여 전체 재입력 유도 (보안 강화를 위함)
                        up_jumin = st.text_input("주민번호 (전체 입력)", value="") 
                        up_phone = st.text_input("연락처", value=cust['연락처']); up_addr = st.text_input("주소", value=cust['주소']); up_job = st.text_input("직업", value=cust['직업'])
                    with u2:
                        up_acc = st.text_input("계좌번호", value=cust.get('계좌번호', ''))
                        up_car = st.text_input("차량번호", value=cust.get('차량번호', ''))
                        up_car_comp = st.text_input("자동차보험회사", value=cust.get('자동차보험회사', ''))
                        up_date = st.text_input("가입일자", value=cust.get('가입일자', ''))
                    
                    if st.form_submit_button("💾 변경 내용 저장"):
                        # 주민번호를 새로 입력하지 않았으면 기존 데이터(마스킹 안 된 원본) 유지
                        final_jumin = up_jumin if up_jumin.strip() else cust['주민번호']
                        updated_row = [datetime.now().strftime("%Y-%m-%d"), up_name, final_jumin, up_phone, up_addr, up_job, up_acc, up_car, up_car_comp, up_date]
                        for i, val in enumerate(updated_row): sheet1.update_cell(target_res.index[0] + 2, i + 1, val)
                        st.success("변경 완료"); st.session_state[f"edit_{search_name}"] = False; st.rerun()
                if st.button("취소"): st.session_state[f"edit_{search_name}"] = False; st.rerun()
        else:
            st.error(f"'{search_name}'님은 미등록 고객입니다.")
            if st.button("➕ 신규 등록하러 가기"): st.session_state.temp_name = search_name; st.session_state.menu = "고객 신규등록"; st.rerun()

elif st.session_state.menu == "고객 신규등록":
    st.title("➕ 신규 고객 등록")
    pre_name = st.session_state.get("temp_name", "")
    with st.form("reg_form"):
        r1, r2 = st.columns(2)
        with r1:
            r_name = st.text_input("이름", value=pre_name)
            r_jumin = st.text_input("주민번호 (- 포함)") 
            r_phone = st.text_input("연락처"); r_addr = st.text_input("주소"); r_job = st.text_input("직업")
        with r2:
            r_acc = st.text_input("계좌번호"); r_car = st.text_input("차량번호"); r_car_comp = st.text_input("자동차보험회사"); r_date = st.date_input("가입일자")
        if st.form_submit_button("✅ 고객 등록"):
            # 입력한 주민번호 원본이 시트에 그대로 전송됨
            sheet1.append_row([datetime.now().strftime("%Y-%m-%d"), r_name, r_jumin, r_phone, r_addr, r_job, r_acc, r_car, r_car_comp, r_date.strftime("%Y-%m-%d")])
            st.success("등록 완료!"); st.session_state.temp_name = ""; st.session_state.menu = "고객조회 및 수정"; st.rerun()

elif st.session_state.menu == "보유계약 리스트 입력":
    st.title("📄 보유계약 리스트 입력")
    selected_cust = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist() if not db_cust.empty else ["등록된 고객 없음"])
    if selected_cust != "선택" and selected_cust != "등록된 고객 없음":
        with st.form("contract_form"):
            st.subheader(f"📝 {selected_cust} 고객 계약 추가")
            c_name = st.text_input("계약자", value=selected_cust)
            c_date = st.text_input("가입날짜"); c_comp = st.text_input("보험회사"); c_prod = st.text_input("상품명"); c_price = st.text_input("금액")
            if st.form_submit_button("🚀 보장분석 시트로 전송"):
                new_contract = [c_name, c_date, c_comp, c_prod, c_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                sheet2.append_row(new_contract)
                st.success(f"✅ '보장분석시트'에 기록되었습니다!")
