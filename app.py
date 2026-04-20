import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import pdfplumber
from datetime import datetime

# --- 1. 보안 및 구글 시트 설정 ---
SHEET_ID = '1_MDfdDsYdOrmjU3ProttXS0qKsbbh5PXJ9tWFjA6zmY'
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_gsheet():
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).get_worksheet(0)
    except Exception as e:
        st.error(f"⚠️ 연결 실패: {e}")
        return None

EXPECTED_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]

st.set_page_config(page_title="현우 통합 관리 v4.7", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v4.7")

sheet = get_gsheet()

if sheet:
    all_values = sheet.get_all_values()
    db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])]) if all_values else pd.DataFrame(columns=EXPECTED_HEADERS)
    db = db.fillna("")

    tab1, tab2, tab3, tab4 = st.tabs(["🔍 고객 조회 및 계약리스트", "✍️ AI 정보 등록/업데이트", "🚘 자동차 증권 업데이트", "📄 보장분석 파일 업로드"])

    # [TAB 1] 고객 조회 (정제된 유지계약 리스트 출력)
    with tab1:
        search_name = st.text_input("🔎 검색할 고객 성함")
        if search_name:
            res = db[db['이름'].astype(str).str.contains(search_name)]
            res = res.drop_duplicates(subset=['이름', '연락처'], keep='last')
            if not res.empty:
                for idx, row in res.iterrows():
                    with st.expander(f"👤 {row['이름']} (주민번호: {row['주민번호']})", expanded=True):
                        st.markdown("### 📋 현재 유지계약 리스트")
                        memo_raw = row.get('병력(특이사항)', '')
                        
                        if "[보장분석]" in memo_raw:
                            analysis_part = memo_raw.split("[보장분석]")[-1]
                            ins_items = [item.strip() for item in analysis_part.split('|') if item.strip()]
                            
                            table_data = []
                            for item in ins_items:
                                # 미납, 해지, 실효 키워드가 있으면 리스트업에서 제외
                                if any(k in item for k in ["미납", "해지", "실효", "종료"]):
                                    continue
                                    
                                parts = item.split('/')
                                if len(parts) >= 2:
                                    # 상품명 정제 (빈 괄호 및 불필요한 꼬리표 제거)
                                    name = re.sub(r'\(.*?\)|\[.*?\]', '', parts[1]).strip()
                                    # 보험료 및 날짜 매칭
                                    price = parts[2].strip() if len(parts) > 2 else "-"
                                    date = parts[3].strip() if len(parts) > 3 else "-"
                                    
                                    if name and "내용없음" not in name:
                                        table_data.append({
                                            "보험회사": parts[0].strip(),
                                            "상품명": name,
                                            "월 보험료": price if "원" in price else "-",
                                            "가입날짜": date if len(date) > 5 else "-"
                                        })
                            
                            if table_data:
                                df_display = pd.DataFrame(table_data).drop_duplicates(subset=['상품명'], keep='first')
                                st.table(df_display)
                            else:
                                st.info("정상 유지 중인 계약 데이터가 없습니다.")
                        else:
                            st.info("등록된 보장분석 데이터가 없습니다.")

                        st.markdown("---")
                        c1, c2 = st.columns(2)
                        with c1:
                            st.write(f"**연락처:** {row.get('연락처', '-')}")
                            st.write(f"**주소:** {row.get('주소', '-')}")
                        with c2:
                            st.write(f"**차량:** {row.get('차량번호', '미등록')} / **만기일:** {row.get('자동차만기일', '-')}")
                            st.info(f"**💡 특이사항:** {memo_raw.split('[보장분석]')[0].strip()}")

    # [TAB 4] PDF 업로드 (추출 시 미납/해지 필터링 로직 포함)
    with tab4:
        st.subheader("📄 보장분석 PDF 데이터 정밀 추출")
        up_file = st.file_uploader("PDF 업로드", type=['pdf'])
        target_u = st.selectbox("고객 선택", ["선택하세요"] + db['이름'].unique().tolist())
        
        if up_file and target_u != "선택하세요":
            if st.button("🚀 유효 계약 정밀 분석"):
                try:
                    with pdfplumber.open(up_file) as pdf:
                        text = "".join([page.extract_text() for page in pdf.pages if page.extract_text()])
                    
                    insurance_companies = ["삼성화재", "DB손해", "현대해상", "KB손해", "메리츠", "한화손해", "흥국화재", "신한라이프", "교보생명", "삼성생명", "라이나", "동양생명", "AIA생명", "에이스손해"]
                    extracted_list = []
                    
                    for line in text.split('\n'):
                        # 1. 미납/해지/실효 라인은 수집 단계에서 차단
                        if any(k in line for k in ["미납", "해지", "실효"]):
                            continue
                            
                        company = next((c for c in insurance_companies if c in line), "")
                        if company and ("보험" in line or "공제" in line):
                            price = re.search(r'\d{1,3}(?:,\d{3})*원', line)
                            date = re.search(r'\d{4}[.\-/]\d{2}[.\-/]\d{2}', line)
                            name = line.split(company)[-1].split('원')[0].split('20')[0].strip()
                            
                            if len(name) > 2:
                                p_val = price.group() if price else "-"
                                d_val = date.group() if date else "-"
                                extracted_list.append(f"{company}/{name}/{p_val}/{d_val}")
                    
                    unique_list = list(set(extracted_list))
                    if unique_list:
                        match_idx = db.index[db['이름'] == target_u].tolist()
                        row_num = match_idx[-1] + 2
                        current_memo = db.iloc[match_idx[-1]]['병력(특이사항)'].split('[보장분석]')[0].strip()
                        final_memo = f"{current_memo} | [보장분석] {' | '.join(unique_list)}"
                        sheet.update_cell(row_num, 7, final_memo)
                        st.success(f"✅ {target_u}님 유효 계약 {len(unique_list)}건 반영 완료!")
                        st.rerun()
                except Exception as e: st.error(f"분석 오류: {e}")

    # [TAB 2, 3] 전체 로직 (생략 없이 통합)
    with tab2:
        st.subheader("📝 텍스트로 정보 등록/업데이트")
        raw_text = st.text_area("이름, 연락처 등을 입력하세요", height=150)
        if st.button("🚀 데이터 반영"):
            name, phone, ssn, addr, memo = "", "", "", "", ""
            lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
            for line in lines:
                if re.search(r'010[ \-]?\d{3,4}[ \-]?\d{4}', line): phone = line.replace(" ", "-")
                elif re.search(r'\d{6}[ \-]?\d{7}', line): ssn = line
                elif any(k in line for k in ["시", "구", "동", "길", "로"]): addr = line
                elif line == lines[0]: name = line
                else: memo += f"{line} "
            if name and phone:
                match_idx = db.index[(db['이름'] == name) & (db['연락처'] == phone)].tolist()
                if match_idx:
                    row_num = match_idx[-1] + 2
                    target_row = db.iloc[match_idx[-1]]
                    if not target_row['주민번호'] and ssn: sheet.update_cell(row_num, 3, ssn)
                    if memo:
                        base = target_row['병력(특이사항)'].split('[보장분석]')[0]
                        final = (base + " " + memo).strip()
                        if "[보장분석]" in target_row['병력(특이사항)']:
                            final += " | [보장분석]" + target_row['병력(특이사항)'].split('[보장분석]')[1]
                        sheet.update_cell(row_num, 7, final)
                    st.success("업데이트 완료!"); st.rerun()
                else:
                    sheet.append_row([datetime.now().strftime("%Y-%m-%d"), name, ssn, phone, addr, "", memo.strip(), name, 0,0,0,0,"","",""])
                    st.success("신규 등록 완료!"); st.rerun()

    with tab3:
        st.subheader("🚘 자동차 증권 업데이트")
        u_in = st.text_input("이름, 차량번호, 보험사, 만기일")
        if st.button("✅ 반영"):
            p = [i.strip() for i in u_in.split(',')]
            if len(p) >= 4:
                idx = db.index[db['이름'] == p[0]].tolist()
                if idx:
                    sheet.update_cell(idx[-1]+2, 13, p[1]); sheet.update_cell(idx[-1]+2, 14, p[2]); sheet.update_cell(idx[-1]+2, 15, p[3])
                    st.success("차량 정보 반영 완료!"); st.rerun()
