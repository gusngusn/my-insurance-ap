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

st.set_page_config(page_title="현우 통합 관리 v6.1", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v6.1")

sheet = get_gsheet()

if sheet:
    all_values = sheet.get_all_values()
    db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])]) if all_values else pd.DataFrame(columns=EXPECTED_HEADERS)
    db = db.fillna("")

    tab1, tab2, tab3, tab4 = st.tabs(["🔍 고객 조회 및 계약리스트", "✍️ AI 정보 등록/업데이트", "🚘 자동차 증권 업데이트", "📄 보장분석 파일 업로드"])

    # [TAB 1] 고객 조회 - 정밀 리스트업
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

    # [TAB 4] 보장분석 PDF - 좌표 기반 정밀 스크랩
    with tab4:
        st.subheader("📄 '보유계약 현황' 데이터 정밀 스크랩")
        up_file = st.file_uploader("보장분석 PDF 업로드", type=['pdf'])
        target_u = st.selectbox("고객 선택", ["선택하세요"] + db['이름'].unique().tolist())
        
        if up_file and target_u != "선택하세요":
            if st.button("🚀 보유계약현황 완벽 추출"):
                try:
                    with pdfplumber.open(up_file) as pdf:
                        extracted_list = []
                        # 2페이지 근처에서 '보유계약 현황' 텍스트가 있는 곳을 탐색
                        for page in pdf.pages:
                            text = page.extract_text()
                            if text and "보유계약 현황" in text:
                                # 텍스트가 아닌 줄(Line) 단위로 읽어서 데이터 매칭
                                lines = text.split('\n')
                                for line in lines:
                                    # 보험사 키워드 (실제 PDF에 등장하는 키워드 중심)
                                    cos = ["삼성", "DB", "현대", "KB", "메리츠", "한화", "흥국", "교보", "라이나", "동양", "신한", "AIA", "롯데"]
                                    co = next((c for c in cos if c in line), "")
                                    
                                    if co and ("보험" in line or "공제" in line):
                                        # 미납/해지 제외
                                        if any(k in line for k in ["미납", "해지", "실효"]): continue
                                        
                                        # 보험료(원)와 가입일(20XX) 추출
                                        price = re.search(r'(\d{1,3}(?:,\d{3})*)\s*원', line)
                                        date = re.search(r'20\d{2}[.\-/]\d{2}[.\-/]\d{2}', line)
                                        
                                        # 상품명: 보험사 이후부터 보험료/날짜 이전까지
                                        start_idx = line.find(co) + len(co)
                                        end_idx = price.start() if price else (date.start() if date else len(line))
                                        raw_name = line[start_idx:end_idx].strip()
                                        
                                        # 불필요한 번호나 기호 제거
                                        clean_name = re.sub(r'^\d+\s*|[^\w\s가-힣]', '', raw_name).replace("무배당", "").strip()
                                        
                                        if len(clean_name) >= 2:
                                            extracted_list.append(f"{co}/{clean_name}/{price.group(0) if price else '-'}/{date.group(0) if date else '-'}")
                                if extracted_list: break

                    if extracted_list:
                        m_idx = db.index[db['이름'] == target_u].tolist()
                        r_num = m_idx[-1] + 2
                        cur_memo = db.iloc[m_idx[-1]]['병력(특이사항)'].split('[보장분석]')[0].strip()
                        new_memo = f"{cur_memo} | [보장분석] {' | '.join(list(set(extracted_list)))}"
                        sheet.update_cell(r_num, 7, new_memo)
                        st.success(f"✅ {target_u}님 보유계약 {len(set(extracted_list))}건 추출 완료!"); st.rerun()
                    else:
                        st.warning("데이터를 찾지 못했습니다. PDF 텍스트가 이미지 형태일 수 있습니다.")
                except Exception as e: st.error(f"오류: {e}")

    # [TAB 2, 3] 기존 로직 (생략 없이 전체 포함)
    with tab2:
        st.subheader("📝 고객 정보 등록")
        raw_text = st.text_area("텍스트 입력", height=150)
        if st.button("🚀 반영"):
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
