import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import re
import requests
import xml.etree.ElementTree as ET

# --- [1. 구글 시트 연결 설정] ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def get_gsheets():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SHEET_ID)
        
        ws = spreadsheet.worksheets()
        # 시트가 3개 미만이면 자동으로 생성 (1:고객DB, 2:보장분석, 3:실적시트)
        while len(ws) < 3:
            spreadsheet.add_worksheet(title=f"시트{len(ws)+1}", rows="100", cols="20")
            ws = spreadsheet.worksheets()
            
        return ws[0], ws[1], ws[2]
    except Exception as e:
        st.error(f"구글 시트 연결 오류: {e}")
        return None, None, None

# --- [2. 실시간 보험 뉴스 스크래핑 함수] ---
@st.cache_data(ttl=3600) # 1시간마다 갱신
def get_insurance_news():
    url = "https://news.google.com/rss/search?q=%EB%B3%B4%ED%97%98&hl=ko&gl=KR&ceid=KR:ko"
    try:
        resp = requests.get(url, timeout=5)
        root = ET.fromstring(resp.content)
        items = []
        for item in root.findall('.//item')[:5]:
            title = item.find('title').text
            link = item.find('link').text
            items.append({"제목": title, "링크": link})
        return items
    except:
        return []

# --- [3. 메인 설정 및 데이터 로드] ---
st.set_page_config(page_title="배현우 FC 성과관리 시스템", layout="wide")
sheet1, sheet2, sheet3 = get_gsheets()

h1 = ["등록일자", "이름", "주민번호", "연락처", "주소", "직업", "계좌번호", "차량번호", "자동차보험회사", "가입일자"]
h2 = ["계약자", "가입날짜", "보험회사", "상품명", "금액", "입력시간"]
h3 = ["계약자", "가입날짜", "보험회사", "상품명", "금액", "입력시간"]

if sheet1 and sheet2 and sheet3:
    # 데이터 로드
    data1 = sheet1.get_all_values()
    db_cust = pd.DataFrame(data1[1:], columns=h1[:len(data1[0])]) if len(data1) > 1 else pd.DataFrame(columns=h1)
    
    data2 = sheet2.get_all_values()
    db_contract = pd.DataFrame(data2[1:], columns=h2[:len(data2[0])]) if len(data2) > 1 else pd.DataFrame(columns=h2)
    
    data3 = sheet3.get_all_values()
    db_perf = pd.DataFrame(data3[1:], columns=h3[:len(data3[0])]) if len(data3) > 1 else pd.DataFrame(columns=h3)
    
    # 실적 분석을 위한 데이터 전처리 (금액 숫자화 및 날짜 포맷팅)
    if not db_perf.empty:
        db_perf['금액_숫자'] = db_perf['금액'].replace('[^0-9]', '', regex=True).apply(lambda x: int(x) if x else 0)
        db_perf['가입날짜_dt'] = pd.to_datetime(db_perf['가입날짜'].str.replace('.', '-'), errors='coerce')
    else:
        db_perf['금액_숫자'] = 0
        db_perf['가입날짜_dt'] = pd.NaT
else:
    st.error("구글 시트를 불러오지 못했습니다. 권한 설정을 확인해주세요."); st.stop()

# --- [4. 메뉴 세션 및 좌측 사이드바] ---
if "menu" not in st.session_state:
    st.session_state.menu = "📊 메인 대시보드"

with st.sidebar:
    st.header("📋 관리 메뉴")
    menu_options = [
        "📊 메인 대시보드", 
        "🔍 고객 조회 및 수정", 
        "➕ 고객 신규등록", 
        "📄 보유계약 입력", 
        "💰 실적 입력 및 분석", 
        "📂 CSV DB 일괄 업로드"
    ]
    current_idx = menu_options.index(st.session_state.menu) if st.session_state.menu in menu_options else 0
    st.session_state.menu = st.radio("메뉴 이동", menu_options, index=current_idx)

today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

# --- [5. 메뉴별 기능 상세 구현] ---

# (1) 메인 대시보드
if st.session_state.menu == "📊 메인 대시보드":
    st.title("🚀 배현우 FC 성과 대시보드")
    
    # 월간 실적 계산
    if not db_perf.empty:
        this_month_df = db_perf[db_perf['가입날짜_dt'].dt.month == today.month]
        m_count = len(this_month_df)
        m_total = this_month_df['금액_숫자'].sum()
    else:
        m_count = 0
        m_total = 0

    # 상단 요약 지표 (월간 실적 건수 및 금액)
    c1, c2, c3 = st.columns(3)
    c1.metric(f"🎯 {today.month}월 실적 건수", f"{m_count} 건")
    c2.metric(f"💰 {today.month}월 실적 합계", f"{m_total:,} 원")
    c3.metric("👥 총 누적 관리 고객", f"{len(db_cust)} 명")

    st.markdown("---")
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("🎂 한 달 내 생일 도래 고객")
        upcoming_bdays = []
        for _, row in db_cust.iterrows():
            jumin = str(row.get('주민번호', '')).strip()
            if len(jumin) >= 6 and jumin[:6].isdigit():
                mmdd = jumin[2:6]
                try:
                    bday_this_year = datetime(today.year, int(mmdd[:2]), int(mmdd[2:]))
                    if bday_this_year < today:
                        bday_this_year = datetime(today.year + 1, int(mmdd[:2]), int(mmdd[2:]))
                    days_left = (bday_this_year - today).days
                    if 0 <= days_left <= 30:
                        upcoming_bdays.append({"고객명": row['이름'], "생일": f"{mmdd[:2]}월 {mmdd[2:]}일", "D-Day": f"D-{days_left}"})
                except: pass
        if upcoming_bdays:
            bday_df = pd.DataFrame(upcoming_bdays).sort_values(by="D-Day")
            st.dataframe(bday_df, use_container_width=True, hide_index=True)
        else:
            st.info("한 달 내 생일인 고객이 없습니다.")

        st.markdown("<br>", unsafe_allow_html=True)
            
        st.subheader("🚗 자동차보험 만기 도래 (D-45)")
        upcoming_auto = []
        for _, row in db_cust.iterrows():
            car_date_str = str(row.get('가입일자', '')).strip().replace('.', '-').replace('/', '-')
            car_comp = str(row.get('자동차보험회사', '')).strip()
            if car_date_str and car_comp and car_comp != '-':
                try:
                    m = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', car_date_str)
                    if m:
                        y, m_val, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                        exp_date = datetime(y + 1, m_val, d)
                        days_left = (exp_date - today).days
                        if 0 <= days_left <= 45:
                            upcoming_auto.append({"고객명": row['이름'], "만기일": exp_date.strftime("%Y-%m-%d"), "보험사": car_comp, "D-Day": f"D-{days_left}"})
                except: pass
        if upcoming_auto:
            auto_df = pd.DataFrame(upcoming_auto).sort_values(by="D-Day")
            st.dataframe(auto_df, use_container_width=True, hide_index=True)
        else:
            st.info("가까운 시일 내 만기되는 자동차보험이 없습니다.")
            
    with col_right:
        st.subheader("📰 오늘의 실시간 보험 뉴스")
        news_items = get_insurance_news()
        if news_items:
            for news in news_items:
                st.markdown(f"- [{news['제목']}]({news['링크']})")
        else:
            st.write("뉴스를 불러올 수 없습니다.")

# (2) 고객 조회 및 수정
elif st.session_state.menu == "🔍 고객 조회 및 수정":
    st.title("🔍 고객 정보 및 보유계약 조회")
    search_name = st.text_input("조회할 고객명을 입력하세요")
    
    if search_name:
        target_res = db_cust[db_cust['이름'] == search_name]
        
        if not target_res.empty:
            cust = target_res.iloc[0]
            if f"edit_{search_name}" not in st.session_state: 
                st.session_state[f"edit_{search_name}"] = False
            
            if not st.session_state[f"edit_{search_name}"]:
                st.subheader(f"👤 {search_name} 고객님 기본 정보")
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**이름:** {cust['이름']}")
                    # 현우님 요청: 주민번호 생략(마스킹) 없이 전체 표시
                    st.write(f"**주민번호:** {cust.get('주민번호', '-')}") 
                    st.write(f"**연락처:** {cust['연락처']}")
                    st.write(f"**주소:** {cust['주소']}")
                    st.write(f"**직업:** {cust['직업']}")
                with c2:
                    st.write(f"**계좌번호:** {cust.get('계좌번호', '-')}")
                    st.write(f"**차량번호:** {cust.get('차량번호', '-')}")
                    st.write(f"**보험회사:** {cust.get('자동차보험회사', '-')}")
                    st.write(f"**가입일자:** {cust.get('가입일자', '-')}")
                
                if st.button("📝 정보변경"): 
                    st.session_state[f"edit_{search_name}"] = True
                    st.rerun()

                st.markdown("---")
                st.subheader(f"📋 {search_name} 고객님 보유계약 현황 (보장분석시트)")
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
                    u1, u2 = st.columns(2)
                    with u1:
                        up_name = st.text_input("이름", value=cust['이름'])
                        up_jumin = st.text_input("주민번호", value=cust['주민번호'])
                        up_phone = st.text_input("연락처", value=cust['연락처'])
                        up_addr = st.text_input("주소", value=cust['주소'])
                        up_job = st.text_input("직업", value=cust['직업'])
                    with u2:
                        up_acc = st.text_input("계좌번호", value=cust.get('계좌번호', ''))
                        up_car = st.text_input("차량번호", value=cust.get('차량번호', ''))
                        up_car_comp = st.text_input("자동차보험회사", value=cust.get('자동차보험회사', ''))
                        up_date = st.text_input("가입일자", value=cust.get('가입일자', ''))
                    
                    if st.form_submit_button("💾 변경 내용 저장"):
                        updated_row = [datetime.now().strftime("%Y-%m-%d"), up_name, up_jumin, up_phone, up_addr, up_job, up_acc, up_car, up_car_comp, up_date]
                        for i, val in enumerate(updated_row): 
                            sheet1.update_cell(target_res.index[0] + 2, i + 1, val)
                        st.success("정보가 변경되었습니다.")
                        st.session_state[f"edit_{search_name}"] = False
                        st.rerun()
                if st.button("취소"): 
                    st.session_state[f"edit_{search_name}"] = False
                    st.rerun()
        else:
            st.error(f"'{search_name}'님은 미등록 고객입니다.")
            if st.button("➕ 신규 등록하러 가기"): 
                st.session_state.temp_name = search_name
                st.session_state.menu = "➕ 고객 신규등록"
                st.rerun()

# (3) 고객 신규등록
elif st.session_state.menu == "➕ 고객 신규등록":
    st.title("➕ 신규 고객 등록")
    pre_name = st.session_state.get("temp_name", "")
    with st.form("reg_form"):
        r1, r2 = st.columns(2)
        with r1:
            r_name = st.text_input("이름", value=pre_name)
            r_jumin = st.text_input("주민번호 (- 포함)") 
            r_phone = st.text_input("연락처")
            r_addr = st.text_input("주소")
            r_job = st.text_input("직업")
        with r2:
            r_acc = st.text_input("계좌번호")
            r_car = st.text_input("차량번호")
            r_car_comp = st.text_input("자동차보험회사")
            r_date = st.date_input("가입일자")
            
        if st.form_submit_button("✅ 고객 등록"):
            if r_name:
                sheet1.append_row([datetime.now().strftime("%Y-%m-%d"), r_name, r_jumin, r_phone, r_addr, r_job, r_acc, r_car, r_car_comp, r_date.strftime("%Y-%m-%d")])
                st.success("신규 고객 등록 완료!")
                st.session_state.temp_name = ""
                st.session_state.menu = "🔍 고객 조회 및 수정"
                st.rerun()
            else:
                st.warning("이름은 필수 입력 항목입니다.")

# (4) 보유계약 입력 (보장분석시트 연동)
elif st.session_state.menu == "📄 보유계약 입력":
    st.title("📄 보유계약 리스트 수동 입력")
    st.info("고객의 기존 보유계약을 보장분석 시트에 등록합니다.")
    
    selected_cust = st.selectbox("고객 선택", ["선택"] + db_cust['이름'].unique().tolist() if not db_cust.empty else ["등록된 고객 없음"])
    
    if selected_cust != "선택" and selected_cust != "등록된 고객 없음":
        with st.form("contract_form"):
            c_name = st.text_input("계약자", value=selected_cust)
            c_date = st.text_input("가입날짜 (예: 2026.01.10)")
            c_comp = st.text_input("보험회사")
            c_prod = st.text_input("상품명")
            c_price = st.text_input("금액 (월 보험료)")
            
            if st.form_submit_button("🚀 보장분석 시트로 전송"):
                if c_name and c_date and c_comp:
                    new_contract = [c_name, c_date, c_comp, c_prod, c_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                    sheet2.append_row(new_contract)
                    st.success(f"✅ {c_name}님의 계약이 보장분석시트에 기록되었습니다!")
                else:
                    st.warning("계약자, 가입날짜, 보험회사는 필수입니다.")

# (5) 실적 입력 및 분석 (실적시트 연동)
elif st.session_state.menu == "💰 실적 입력 및 분석":
    st.title("💰 실적 관리 및 분석")
    
    tab_input, tab_analysis = st.tabs(["✍️ 신규 실적 입력", "📈 기간별 성과 분석"])
    
    with tab_input:
        st.subheader("새로운 체결 실적을 등록하세요.")
        with st.form("perf_form"):
            p_name = st.selectbox("계약자 선택", db_cust['이름'].unique().tolist() if not db_cust.empty else ["고객없음"])
            p_date = st.date_input("가입날짜(체결일)", today)
            p_comp = st.text_input("보험회사")
            p_prod = st.text_input("상품명")
            p_price = st.text_input("금액 (숫자만 기입. 예: 150000)")
            
            if st.form_submit_button("🚀 실적 등록하기"):
                if p_name != "고객없음" and p_price:
                    sheet3.append_row([p_name, p_date.strftime("%Y.%m.%d"), p_comp, p_prod, p_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                    st.success("실적이 성공적으로 등록되었습니다. 메인 대시보드에 반영됩니다!")
                    st.rerun()
                else:
                    st.warning("금액을 반드시 입력해 주세요.")

    with tab_analysis:
        st.subheader("기간별 실적 현황 조회")
        period = st.radio("조회 기간 선택", ["주간 실적", "월간 실적", "연간 실적"], horizontal=True)
        
        if not db_perf.empty:
            if period == "주간 실적":
                start_of_week = today - timedelta(days=today.weekday())
                filtered_df = db_perf[db_perf['가입날짜_dt'] >= start_of_week]
            elif period == "월간 실적":
                filtered_df = db_perf[db_perf['가입날짜_dt'].dt.month == today.month]
            else:
                filtered_df = db_perf[db_perf['가입날짜_dt'].dt.year == today.year]
                
            total_sum = filtered_df['금액_숫자'].sum()
            count = len(filtered_df)
            
            st.markdown(f"### **총 {count}건 / 누적 실적: {total_sum:,} 원**")
            
            if not filtered_df.empty:
                display_cols = ["계약자", "가입날짜", "보험회사", "상품명", "금액"]
                st.dataframe(filtered_df[display_cols].reset_index(drop=True), use_container_width=True)
            else:
                st.info(f"해당 기간({period})의 실적 데이터가 없습니다.")
        else:
            st.info("아직 등록된 실적 데이터가 없습니다.")

# (6) CSV DB 일괄 업로드
elif st.session_state.menu == "📂 CSV DB 일괄 업로드":
    st.title("📂 기존 고객 DB 스마트 병합 (CSV)")
    st.info("중복 고객은 자동으로 제외되며, 기존 정보 중 비어있는 칸만 새로운 데이터로 채워집니다.")
    
    upload_file = st.file_uploader("CSV 파일 선택", type=['csv'])
    
    if upload_file:
        try:
            df = pd.read_csv(upload_file).fillna("")
            st.write("📊 업로드된 데이터 미리보기 (상위 5개)")
            st.dataframe(df.head())
            
            st.markdown("---")
            st.subheader("🔗 데이터 항목 매칭")
            csv_cols = ["선택 안 함"] + list(df.columns)
            
            cols = st.columns(3)
            mapping = {}
            target_headers = ["이름", "주민번호", "연락처", "주소", "직업", "계좌번호", "차량번호", "자동차보험회사", "가입일자"]
            
            for i, header in enumerate(target_headers):
                with cols[i % 3]:
                    default_idx = 0
                    if header in csv_cols:
                        default_idx = csv_cols.index(header)
                    elif header == "연락처":
                        for syn in ["전화번호", "핸드폰", "휴대폰", "연락처"]:
                            if syn in csv_cols:
                                default_idx = csv_cols.index(syn)
                                break
                    elif header == "주소":
                        if "집주소" in csv_cols: 
                            default_idx = csv_cols.index("집주소")
                    
                    mapping[header] = st.selectbox(f"➡️ {header}", csv_cols, index=default_idx)
            
            if st.button("🚀 데이터 스마트 병합 전송"):
                with st.spinner("중복 확인 및 데이터를 병합하는 중입니다..."):
                    new_upload_data = []
                    update_count = 0
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    
                    for _, row in df.iterrows():
                        name_val = str(row[mapping["이름"]]).strip() if mapping["이름"] != "선택 안 함" else ""
                        if not name_val: continue
                        
                        in_data = {
                            "주민번호": str(row[mapping["주민번호"]]).strip() if mapping["주민번호"] != "선택 안 함" else "",
                            "연락처": str(row[mapping["연락처"]]).strip() if mapping["연락처"] != "선택 안 함" else "",
                            "주소": str(row[mapping["주소"]]).strip() if mapping["주소"] != "선택 안 함" else "",
                            "직업": str(row[mapping["직업"]]).strip() if mapping["직업"] != "선택 안 함" else "",
                            "계좌번호": str(row[mapping["계좌번호"]]).strip() if mapping["계좌번호"] != "선택 안 함" else "",
                            "차량번호": str(row[mapping["차량번호"]]).strip() if mapping["차량번호"] != "선택 안 함" else "",
                            "자동차보험회사": str(row[mapping["자동차보험회사"]]).strip() if mapping["자동차보험회사"] != "선택 안 함" else "",
                            "가입일자": str(row[mapping["가입일자"]]).strip() if mapping["가입일자"] != "선택 안 함" else ""
                        }
                        
                        existing = db_cust[db_cust['이름'] == name_val]
                        
                        if not existing.empty:
                            idx = existing.index[0]
                            sheet_row_idx = idx + 2
                            existing_data = existing.iloc[0]
                            
                            col_index_map = {
                                "주민번호": 3, "연락처": 4, "주소": 5, "직업": 6, 
                                "계좌번호": 7, "차량번호": 8, "자동차보험회사": 9, "가입일자": 10
                            }
                            
                            updates_made = False
                            for key, col_num in col_index_map.items():
                                curr_val = str(existing_data.get(key, "")).strip()
                                new_val = in_data[key]
                                
                                if curr_val in ["", "-", "None", "nan"] and new_val:
                                    sheet1.update_cell(sheet_row_idx, col_num, new_val)
                                    updates_made = True
                                    
                            if updates_made:
                                update_count += 1
                        else:
                            new_upload_data.append([
                                today_str, 
                                name_val, 
                                in_data["주민번호"], 
                                in_data["연락처"], 
                                in_data["주소"], 
                                in_data["직업"], 
                                in_data["계좌번호"], 
                                in_data["차량번호"], 
                                in_data["자동차보험회사"], 
                                in_data["가입일자"]
                            ])
                    
                    if new_upload_data:
                        sheet1.append_rows(new_upload_data)
                        
                    st.success(f"📊 작업 내역: 신규 고객 {len(new_upload_data)}명 등록, 기존 고객 {update_count}명 정보 보완.")
                    st.balloons()
        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")
