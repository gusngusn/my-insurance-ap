import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import pdfplumber
from datetime import datetime

# --- 1. 보안 및 구글 시트 설정 (생략 없음) ---
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

st.set_page_config(page_title="현우 통합 관리 v6.3", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v6.3")

sheet = get_gsheet()

if sheet:
    all_values = sheet.get_all_values()
    db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])]) if all_values else pd.DataFrame(columns=EXPECTED_HEADERS)
    db = db.fillna("")

    tab1, tab2, tab3, tab4 = st.tabs(["🔍 고객 조회 및 계약리스트", "✍️ AI 정보 등록/업데이트", "🚘 자동차 증권 업데이트", "📄 보장분석 파일 업로드"])

    # [TAB 1] 고객 조회 - 정밀 필터링 출력
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
                                # [강력 필터] 제목줄이나 무의미한 텍스트는 원천 차단
                                if any(k in item for k in ["No", "회사", "상품명", "계약일", "만기일", "보험서비스", "내용없음"]):
                                    continue
                                
                                parts = item.split('/')
                                if len(parts) >= 2:
                                    co, nm = parts[0].strip(), parts[1].strip()
                                    # 상품명이 너무 짧거나 숫자로만 된 경우 제외
                                    if len(nm) > 2 and not nm.isdigit():
                                        table_data.append({
                                            "보험회사": co,
                                            "상품명": nm,
                                            "월 보험료": parts[2].strip() if len(parts) > 2 else "-",
                                            "가입날짜": parts[3].strip() if len(parts) > 3 else "-"
                                        })
                            
                            if table_data:
                                st.table(pd.DataFrame(table_data).drop_duplicates(subset=['상품명']))
                            else: st.info("정상 유지 중인 계약 데이터가 없습니다.")
                        else: st.info("등록된 보장분석 데이터가 없습니다.")

    # [TAB 4] PDF 업로드 - 보유계약현황 정밀 스캔
    with tab4:
        st.subheader("📄 '보유계약 현황' 데이터 정밀 추출")
        up_file = st.file_uploader("PDF 업로드", type=['pdf'])
        target_u = st.selectbox("고객 선택", ["선택하세요"] + db['이름'].unique().tolist())
        
        if up_file and target_u != "선택하세요":
            if st.button("🚀 보유계약현황 완벽 추출"):
                try:
                    with pdfplumber.open(up_file) as pdf:
                        extracted = []
                        for page in pdf.pages:
                            text = page.extract_text()
                            if text and "보유계약 현황" in text:
                                lines = text.split('\n')
                                for line in lines:
                                    # 제목줄(No, 회사 등)이 포함된 줄은 무조건 패스
                                    if any(header in line for header in ["No", "회사", "상품명", "보험서비스"]):
                                        continue
                                        
                                    cos = ["삼성", "DB", "현대", "KB", "메리츠", "한화", "흥국", "교보", "라이나", "동양", "신한", "AIA"]
                                    co = next((c for c in cos if c in line), "")
                                    
                                    if co:
                                        price = re.search(r'(\d{1,3}(?:,\d{3})*)\s*원', line)
                                        date = re.search(r'20\d{2}[.\-/]\d{2}[.\-/]\d{2}', line)
                                        
                                        if price or date:
                                            # 상품명 정제 로직
                                            s_idx = line.find(co) + len(co)
                                            e_idx = price.start() if price else (date.start() if date else len(line))
                                            nm = line[s_idx:e_idx].strip()
                                            nm = re.sub(r'^\d+\s*|[^\w\s가-힣]', '', nm).replace("무배당", "").strip()
                                            
                                            if len(nm) >= 2:
                                                extracted.append(f"{co}/{nm}/{price.group(0) if price else '-'}/{date.group(0) if date else '-'}")
                                if extracted: break

                    if extracted:
                        m_idx = db.index[db['이름'] == target_u].tolist()
                        r_num = m_idx[-1] + 2
                        cur_memo = db.iloc[m_idx[-1]]['병력(특이사항)'].split('[보장분석]')[0].strip()
                        new_memo = f"{cur_memo} | [보장분석] {' | '.join(list(set(extracted)))}"
                        sheet.update_cell(r_num, 7, new_memo)
                        st.success(f"✅ {target_u}님 보유계약 {len(set(extracted))}건 반영 완료!"); st.rerun()
                except Exception as e: st.error(f"오류: {e}")
