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

st.set_page_config(page_title="현우 통합 관리 v6.0", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v6.0")

sheet = get_gsheet()

if sheet:
    all_values = sheet.get_all_values()
    db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])]) if all_values else pd.DataFrame(columns=EXPECTED_HEADERS)
    db = db.fillna("")

    tab1, tab2, tab3, tab4 = st.tabs(["🔍 고객 조회 및 계약리스트", "✍️ AI 정보 등록/업데이트", "🚘 자동차 증권 업데이트", "📄 보장분석 파일 업로드"])

    # [TAB 1] 고객 조회 - 정제된 리스트 출력
    with tab1:
        search_name = st.text_input("🔎 검색할 고객 성함")
        if search_name:
            res = db[db['이름'].astype(str).str.contains(search_name)]
            res = res.drop_duplicates(subset=['이름', '연락처'], keep='last')
            if not res.empty:
                for idx, row in res.iterrows():
                    with st.expander(f"👤 {row['이름']} (주민번호: {row['주민번호']})", expanded=True):
                        st.markdown("### 📋 보유계약현황 리스트")
                        memo_raw = row.get('병력(특이사항)', '')
                        if "[보장분석]" in memo_raw:
                            analysis_part = memo_raw.split("[보장분석]")[-1]
                            ins_items = [item.strip() for item in analysis_part.split('|') if item.strip()]
                            table_data = []
                            for item in ins_items:
                                parts = item.split('/')
                                if len(parts) >= 2:
                                    table_data.append({
                                        "보험회사": parts[0].strip(),
                                        "상품명": parts[1].strip(),
                                        "월 보험료": parts[2].strip() if len(parts) > 2 else "-",
                                        "가입날짜": parts[3].strip() if len(parts) > 3 else "-"
                                    })
                            if table_data:
                                st.table(pd.DataFrame(table_data).drop_duplicates(subset=['상품명']))
                        else: st.info("등록된 보장분석 데이터가 없습니다.")
                        st.markdown("---")
                        st.write(f"**연락처:** {row.get('연락처', '-')} | **주소:** {row.get('주소', '-')}")

    # [TAB 4] 보장분석 PDF - '표 추출' 로직으로 전면 교체
    with tab4:
        st.subheader("📄 '보유계약 현황' 표(Table) 정밀 스크랩")
        up_file = st.file_uploader("보장분석 PDF 업로드", type=['pdf'])
        target_u = st.selectbox("고객 선택", ["선택하세요"] + db['이름'].unique().tolist())
        
        if up_file and target_u != "선택하세요":
            if st.button("🚀 보유계약 표 데이터 정밀 추출"):
                try:
                    with pdfplumber.open(up_file) as pdf:
                        extracted_list = []
                        # 보통 2페이지에 보유계약 현황 표가 있음
                        for page in pdf.pages:
                            # 페이지 텍스트 확인 (보유계약 현황 섹션인지 체크)
                            page_text = page.extract_text()
                            if page_text and ("보유계약 현황" in page_text or "보유계약현황" in page_text):
                                # [핵심] 텍스트가 아닌 '표(Table)' 구조로 추출
                                tables = page.extract_tables()
                                for table in tables:
                                    for row_data in table:
                                        # 유효한 행인지 확인 (보험사 이름이나 숫자가 들어있는지)
                                        row_str = " ".join([str(cell) for cell in row_data if cell])
                                        if any(co in row_str for co in ["삼성", "DB", "현대", "KB", "메리츠", "한화", "흥국", "교보", "라이나", "동양", "신한", "AIA"]):
                                            # 행 데이터 정제
                                            clean_row = [str(cell).replace('\n', ' ').strip() for cell in row_data if cell]
                                            # 데이터가 3칸 이상일 때만 (보험사/상품명/보험료 등)
                                            if len(clean_row) >= 3:
                                                co = next((c for c in ["삼성화재", "삼성생명", "DB손해", "현대해상", "KB손해", "메리츠", "한화손해", "흥국화재", "신한라이프", "교보생명", "라이나", "동양생명", "AIA"] if c in row_str), clean_row[0])
                                                nm = clean_row[1] if len(clean_row) > 1 else "-"
                                                pr = next((item for item in clean_row if "원" in item), "-")
                                                dt = next((item for item in clean_row if re.search(r'\d{4}', item)), "-")
                                                extracted_list.append(f"{co}/{nm}/{pr}/{dt}")
                                if extracted_list: break # 페이지를 찾았으면 중단

                    if extracted_list:
                        m_idx = db.index[db['이름'] == target_u].tolist()
                        r_num = m_idx[-1] + 2
                        cur_memo = db.iloc[m_idx[-1]]['병력(특이사항)'].split('[보장분석]')[0].strip()
                        new_memo = f"{cur_memo} | [보장분석] {' | '.join(list(set(extracted_list)))}"
                        sheet.update_cell(r_num, 7, new_memo)
                        st.success(f"✅ {target_u}님 보유계약 {len(set(extracted_list))}건 추출 완료!"); st.rerun()
                    else:
                        st.warning("표 데이터를 찾지 못했습니다. 리포트의 표 형식이 표준과 다를 수 있습니다.")
                except Exception as e: st.error(f"오류: {e}")

    # [TAB 2, 3] 기존 로직 전체 포함 (생략 없음)
    with tab2:
        st.subheader("📝 고객 정보 등록")
        raw_text = st.text_area("텍스트 입력", height=150)
        if st.button("🚀 반영"):
            # (기존 등록 로직 전체)
            name, phone, ssn, addr, memo = "", "", "", "", ""
            lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
            for line in lines:
                if re.search(r'010[ \-]?\d{3,4}[ \-]?\d{4}', line): phone = line.replace(" ", "-")
                elif re.search(r'\d{6}[ \-]?\d{7}', line): ssn = line
                elif any(k in line for k in ["시", "구", "동", "길", "로"]): addr = line
                elif line == lines[0]: name = line
                else: memo += f"{line} "
            if name and phone:
                m_idx = db.index[(db['이름'] == name) & (db['연락처'] == phone)].tolist()
                if m_idx:
                    r_num = m_idx[-1] + 2
                    sheet.update_cell(r_num, 3, ssn)
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
                    st.success("반영 완료!"); st.rerun()
