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

# 시스템 필수 헤더
EXPECTED_HEADERS = ["날짜", "이름", "주민번호", "연락처", "주소", "직업", "병력(특이사항)", "가족대표", "암", "뇌", "심", "수술", "차량번호", "보험사", "자동차만기일"]

st.set_page_config(page_title="현우 통합 관리 v4.4", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v4.4")

sheet = get_gsheet()

if sheet:
    # 데이터 로드
    all_values = sheet.get_all_values()
    if not all_values:
        sheet.insert_row(EXPECTED_HEADERS, 1)
        db = pd.DataFrame(columns=EXPECTED_HEADERS)
    else:
        db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])])
        db = db.fillna("")

    # --- 탭 구성 ---
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 고객 조회 및 계약리스트", "✍️ AI 정보 등록/업데이트", "🚘 자동차 증권 업데이트", "📄 보장분석 파일 업로드"])

    # [TAB 1] 고객 조회 (주민번호 노출 및 유지계약 리스트)
    with tab1:
        search_name = st.text_input("🔎 검색할 고객 성함")
        if search_name:
            search_results = db[db['이름'].astype(str).str.contains(search_name)]
            unique_results = search_results.drop_duplicates(subset=['이름', '연락처'], keep='last')
            if not unique_results.empty:
                for idx, row in unique_results.iterrows():
                    with st.expander(f"👤 {row['이름']} (주민번호: {row['주민번호']})", expanded=True):
                        st.markdown("### 📋 유지계약 리스트")
                        memo_raw = row.get('병력(특이사항)', '')
                        
                        if "[보장분석]" in memo_raw:
                            analysis_part = memo_raw.split("[보장분석]")[-1]
                            ins_items = [item.strip() for item in analysis_part.split('|') if item.strip()]
                            
                            table_data = []
                            for item in ins_items:
                                parts = item.split('/')
                                table_data.append({
                                    "보험회사": parts[0] if len(parts) > 0 else "확인불가",
                                    "상품명": parts[1] if len(parts) > 1 else "내용없음",
                                    "월 보험료": parts[2] if len(parts) > 2 else "-",
                                    "가입날짜": parts[3] if len(parts) > 3 else "-"
                                })
                            
                            if table_data:
                                st.table(pd.DataFrame(table_data))
                        else:
                            st.info("등록된 유지계약 데이터가 없습니다. 업로드 탭을 이용해 주세요.")
                        
                        st.markdown("---")
                        c1, c2 = st.columns(2)
                        with c1:
                            st.write(f"**연락처:** {row.get('연락처', '-')}")
                            st.write(f"**주소:** {row.get('주소', '-')}")
                            st.write(f"**직업:** {row.get('직업', '-')}")
                        with c2:
                            st.write(f"**차량:** {row.get('차량번호', '미등록')} / **보험사:** {row.get('보험사', '미등록')}")
                            st.write(f"**자동차만기:** {row.get('자동차만기일', '-')}")
                            st.info(f"**💡 기타특이사항:** {memo_raw.split('[보장분석]')[0].strip()}")
                            st.info("📄 보장분석 원본 파일은 구글 드라이브에서 고객명으로 검색하세요.")
            else: st.info("검색 결과가 없습니다.")

    # [TAB 2] AI 정보 등록 및 자동 병합
    with tab2:
        st.subheader("📝 텍스트로 정보 등록 및 자동 병합")
        raw_text = st.text_area("고객 정보를 자유롭게 입력하세요 (이름, 연락처, 주민번호, 주소 등)", height=200)
        if st.button("🚀 데이터 분석 및 시트 반영"):
            name, ssn, phone, addr, job, memo = "", "", "", "", "", ""
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
                    if not target_row['주소'] and addr: sheet.update_cell(row_num, 5, addr)
                    if memo:
                        new_memo = (target_row['병력(특이사항)'].split('[보장분석]')[0] + " " + memo).strip()
                        if "[보장분석]" in target_row['병력(특이사항)']:
                            new_memo += " | [보장분석]" + target_row['병력(특이사항)'].split('[보장분석]')[1]
                        sheet.update_cell(row_num, 7, new_memo)
                    st.success(f"✅ {name} 고객님 정보 업데이트 완료!")
                    st.rerun()
                else:
                    new_row = [datetime.now().strftime("%Y-%m-%d"), name, ssn, phone, addr, job, memo.strip(), name, 0, 0, 0, 0, "", "", ""]
                    sheet.append_row(new_row)
                    st.success(f"✅ {name} 고객님 신규 등록 완료!")
                    st.rerun()
            else: st.error("이름과 연락처는 필수 입력 사항입니다.")

    # [TAB 3] 자동차 증권 업데이트
    with tab3:
        st.subheader("🚘 자동차 보험 증권 업데이트")
        update_input = st.text_input("형식: 이름, 차량번호, 보험사, 만기일")
        if st.button("✅ 차량 정보 업데이트"):
            parts = [p.strip() for p in update_input.split(',')]
            if len(parts) >= 4:
                t_name, t_car, t_comp, t_exp = parts[0], parts[1], parts[2], parts[3]
                idx_list = db.index[db['이름'] == t_name].tolist()
                if idx_list:
                    row_num = idx_list[-1] + 2
                    sheet.update_cell(row_num, 13, t_car)
                    sheet.update_cell(row_num, 14, t_comp)
                    sheet.update_cell(row_num, 15, t_exp)
                    st.success(f"✅ {t_name}님 자동차 보험 정보가 반영되었습니다.")
                    st.rerun()
                else: st.error("해당 이름의 고객을 찾을 수 없습니다.")
            else: st.warning("형식을 맞춰주세요 (이름, 차량번호, 보험사, 만기일)")

    # [TAB 4] 보장분석 PDF 업로드 및 분석
    with tab4:
        st.subheader("📄 보장분석 PDF 데이터 정밀 추출")
        up_file = st.file_uploader("PDF 업로드", type=['pdf'])
        target_u = st.selectbox("고객 선택", ["선택하세요"] + db['이름'].unique().tolist())
        
        if up_file and target_u != "선택하세요":
            if st.button("🚀 PDF 분석 후 리스트업"):
                try:
                    with pdfplumber.open(up_file) as pdf:
                        text = "".join([page.extract_text() for page in pdf.pages])
                    
                    insurance_companies = ["삼성화재", "DB손해", "현대해상", "KB손해", "메리츠", "한화손해", "흥국화재", "신한라이프", "교보생명", "삼성생명", "라이나"]
                    extracted_list = []
                    
                    for line in text.split('\n'):
                        company = next((c for c in insurance_companies if c in line), "")
                        if company and ("보험" in line or "공제" in line):
                            price = re.search(r'\d{1,3}(?:,\d{3})*원', line)
                            date = re.search(r'\d{4}[.\-/]\d{2}[.\-/]\d{2}', line)
                            name = line.split(company)[-1].split('원')[0].strip()
                            
                            price_val = price.group() if price else "확인필요"
                            date_val = date.group() if date else "-"
                            extracted_list.append(f"{company}/{name}/{price_val}/{date_val}")
                    
                    unique_list = list(set(extracted_list))
                    
                    match_idx = db.index[db['이름'] == target_u].tolist()
                    if match_idx:
                        row_num = match_idx[-1] + 2
                        current_memo = db.iloc[match_idx[-1]]['병력(특이사항)'].split('[보장분석]')[0].strip()
                        final_memo = f"{current_memo} | [보장분석] {' | '.join(unique_list)}"
                        
                        sheet.update_cell(row_num, 7, final_memo)
                        st.success(f"✅ {target_u}님 유지계약 리스트 반영 완료!")
                        st.rerun()
                except Exception as e: st.error(f"분석 중 오류 발생: {e}")
