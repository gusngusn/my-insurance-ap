import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

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
st.set_page_config(page_title="배현우 FC 시스템 v50.0", layout="wide")
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

def mask_jumin(jumin):
    if not jumin or len(str(jumin)) < 8: return jumin
    return str(jumin)[:8] + "******"

# --- [3. 좌측 사이드바 메뉴] ---
with st.sidebar:
    st.header("📋 관리 메뉴")
    menu_options = ["고객조회 및 수정", "고객 신규등록", "보유계약 리스트 입력", "CSV DB 일괄 업로드"]
    current_idx = menu_options.index(st.session_state.menu)
    st.session_state.menu = st.radio("메뉴 이동", menu_options, index=current_idx)

# --- [4. 메뉴별 기능 구현] ---

# (1) 고객조회 및 수정
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
                    st.write(f"**이름:** {cust['이름']}"); st.write(f"**주민번호:** {mask_jumin(cust.get('주민번호', '-'))}")
                    st.write(f"**연락처:** {cust['연락처']}"); st.write(f"**주소:** {cust['주소']}"); st.write(f"**직업:** {cust['직업']}")
                with c2:
                    st.write(f"**계좌번호:** {cust.get('계좌번호', '-')}"); st.write(f"**차량번호:** {cust.get('차량번호', '-')}")
                    st.write(f"**보험회사:** {cust.get('자동차보험회사', '-')}"); st.write(f"**가입일자:** {cust.get('가입일자', '-')}")
                if st.button("📝 정보변경"): st.session_state[f"edit_{search_name}"] = True; st.rerun()

                st.markdown("---")
                st.subheader(f"📋 {search_name} 고객님 보유계약 현황")
                matched_contracts = db_contract[db_contract['계약자'] == search_name]
                if not matched_contracts.empty:
                    display_df = matched_contracts[["가입날짜", "보험회사", "상품명", "금액"]]
                    display_df.index = range(1, len(display_df) + 1)
                    st.table(display_df)
                else: st.info("등록된 보유계약 내역이 없습니다.")
            else:
                with st.form("update_form"):
                    st.subheader(f"📝 {search_name} 정보 수정")
                    st.warning("⚠️ 개인정보 보호를 위해 수정 시 주민번호 전체를 다시 입력해 주세요.")
                    u1, u2 = st.columns(2)
                    with u1:
                        up_name = st.text_input("이름", value=cust['이름']); up_jumin = st.text_input("주민번호 (전체 입력)", value="")
                        up_phone = st.text_input("연락처", value=cust['연락처']); up_addr = st.text_input("주소", value=cust['주소']); up_job = st.text_input("직업", value=cust['직업'])
                    with u2:
                        up_acc = st.text_input("계좌번호", value=cust.get('계좌번호', '')); up_car = st.text_input("차량번호", value=cust.get('차량번호', ''))
                        up_car_comp = st.text_input("자동차보험회사", value=cust.get('자동차보험회사', '')); up_date = st.text_input("가입일자", value=cust.get('가입일자', ''))
                    if st.form_submit_button("💾 변경 내용 저장"):
                        final_jumin = up_jumin if up_jumin.strip() else cust['주민번호']
                        updated_row = [datetime.now().strftime("%Y-%m-%d"), up_name, final_jumin, up_phone, up_addr, up_job, up_acc, up_car, up_car_comp, up_date]
                        for i, val in enumerate(updated_row): sheet1.update_cell(target_res.index[0] + 2, i + 1, val)
                        st.success("변경 완료"); st.session_state[f"edit_{search_name}"] = False; st.rerun()
                if st.button("취소"): st.session_state[f"edit_{search_name}"] = False; st.rerun()
        else:
            st.error(f"'{search_name}'님은 미등록 고객입니다.")
            if st.button("➕ 신규 등록하러 가기"): st.session_state.temp_name = search_name; st.session_state.menu = "고객 신규등록"; st.rerun()

# (2) 고객 신규등록
elif st.session_state.menu == "고객 신규등록":
    st.title("➕ 신규 고객 등록")
    pre_name = st.session_state.get("temp_name", "")
    with st.form("reg_form"):
        r1, r2 = st.columns(2)
        with r1:
            r_name = st.text_input("이름", value=pre_name); r_jumin = st.text_input("주민번호 (- 포함)")
            r_phone = st.text_input("연락처"); r_addr = st.text_input("주소"); r_job = st.text_input("직업")
        with r2:
            r_acc = st.text_input("계좌번호"); r_car = st.text_input("차량번호"); r_car_comp = st.text_input("자동차보험회사"); r_date = st.date_input("가입일자")
        if st.form_submit_button("✅ 고객 등록"):
            if r_name:
                sheet1.append_row([datetime.now().strftime("%Y-%m-%d"), r_name, r_jumin, r_phone, r_addr, r_job, r_acc, r_car, r_car_comp, r_date.strftime("%Y-%m-%d")])
                st.success("등록 완료!"); st.session_state.temp_name = ""; st.session_state.menu = "고객조회 및 수정"; st.rerun()
            else: st.warning("이름은 필수입니다.")

# (3) 보유계약 리스트 입력
elif st.session_state.menu == "보유계약 리스트 입력":
    st.title("📄 보유계약 리스트 입력")
    selected_cust = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist() if not db_cust.empty else ["등록된 고객 없음"])
    if selected_cust != "선택" and selected_cust != "등록된 고객 없음":
        with st.form("contract_form"):
            st.subheader(f"📝 {selected_cust} 고객 계약 추가")
            c_name = st.text_input("계약자", value=selected_cust)
            c_date = st.text_input("가입날짜"); c_comp = st.text_input("보험회사"); c_prod = st.text_input("상품명"); c_price = st.text_input("금액")
            if st.form_submit_button("🚀 보장분석 시트로 전송"):
                sheet2.append_row([c_name, c_date, c_comp, c_prod, c_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                st.success("✅ '보장분석시트'에 기록되었습니다!")

# (4) CSV DB 일괄 업로드 (신규 기능)
elif st.session_state.menu == "CSV DB 일괄 업로드":
    st.title("📂 기존 고객 DB 일괄 업로드 (CSV)")
    st.info("엑셀 파일을 'CSV(쉼표로 분리)' 형식으로 저장한 후 업로드해주세요.")
    
    upload_file = st.file_uploader("CSV 파일 선택", type=['csv'])
    
    if upload_file:
        try:
            # CSV 읽기 (빈칸은 처리)
            df = pd.read_csv(upload_file).fillna("")
            st.write("📊 업로드된 데이터 미리보기 (상위 5개)")
            st.dataframe(df.head())
            
            st.markdown("---")
            st.subheader("🔗 데이터 항목 매칭")
            st.write("구글 시트의 항목과 업로드한 CSV 파일의 제목을 알맞게 연결해 주세요. (해당 항목이 없으면 '선택 안 함' 유지)")
            
            # CSV 컬럼 옵션
            csv_cols = ["선택 안 함"] + list(df.columns)
            
            # 구글 시트 헤더 매칭 UI
            cols = st.columns(3)
            mapping = {}
            target_headers = ["이름", "주민번호", "연락처", "주소", "직업", "계좌번호", "차량번호", "자동차보험회사", "가입일자"]
            
            for i, header in enumerate(target_headers):
                with cols[i % 3]:
                    # CSV 파일에 구글 시트와 똑같은 이름이 있으면 자동 선택
                    default_idx = csv_cols.index(header) if header in csv_cols else 0
                    mapping[header] = st.selectbox(f"➡️ {header}", csv_cols, index=default_idx)
            
            if st.button("🚀 데이터 구글 시트로 일괄 전송"):
                with st.spinner("데이터를 전송하는 중입니다..."):
                    upload_data = []
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    
                    for _, row in df.iterrows():
                        # 이름이 없으면 스킵
                        name_val = row[mapping["이름"]] if mapping["이름"] != "선택 안 함" else ""
                        if not name_val: continue
                        
                        row_data = [
                            today_str,  # 등록일자 (자동)
                            name_val,
                            str(row[mapping["주민번호"]]) if mapping["주민번호"] != "선택 안 함" else "",
                            str(row[mapping["연락처"]]) if mapping["연락처"] != "선택 안 함" else "",
                            str(row[mapping["주소"]]) if mapping["주소"] != "선택 안 함" else "",
                            str(row[mapping["직업"]]) if mapping["직업"] != "선택 안 함" else "",
                            str(row[mapping["계좌번호"]]) if mapping["계좌번호"] != "선택 안 함" else "",
                            str(row[mapping["차량번호"]]) if mapping["차량번호"] != "선택 안 함" else "",
                            str(row[mapping["자동차보험회사"]]) if mapping["자동차보험회사"] != "선택 안 함" else "",
                            str(row[mapping["가입일자"]]) if mapping["가입일자"] != "선택 안 함" else ""
                        ]
                        upload_data.append(row_data)
                    
                    if upload_data:
                        # append_rows를 통해 API 호출 1번으로 대량 업로드 (속도 최적화)
                        sheet1.append_rows(upload_data)
                        st.success(f"✅ 총 {len(upload_data)}명의 고객 데이터가 성공적으로 일괄 등록되었습니다!")
                        st.balloons()
                    else:
                        st.error("업로드할 데이터가 없습니다. '이름' 항목 매칭을 확인해 주세요.")
        except Exception as e:
            st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")
