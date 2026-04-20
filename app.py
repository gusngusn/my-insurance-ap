import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import pdfplumber
from datetime import datetime

# --- 구글 시트 및 보안 설정 (기존과 동일) ---
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

st.set_page_config(page_title="현우 통합 관리 v5.9", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v5.9")

sheet = get_gsheet()

if sheet:
    all_values = sheet.get_all_values()
    db = pd.DataFrame(all_values[1:], columns=all_values[0]) if all_values else pd.DataFrame()
    
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 고객 조회 및 계약리스트", "✍️ AI 정보 등록", "🚘 자동차 증권", "📄 보장분석 PDF 스크랩"])

    # [TAB 4] 오직 '보유계약 현황' 페이지만 스크랩
    with tab4:
        st.subheader("📄 '보유계약 현황' 페이지 전용 스크랩")
        up_file = st.file_uploader("보장분석 PDF 업로드", type=['pdf'])
        target_u = st.selectbox("고객 선택", ["선택하세요"] + db['이름'].unique().tolist() if not db.empty else ["고객 없음"])
        
        if up_file and target_u != "선택하세요":
            if st.button("🚀 보유계약 현황 페이지 스캔"):
                try:
                    with pdfplumber.open(up_file) as pdf:
                        extracted_data = []
                        target_page_found = False
                        
                        for page in pdf.pages:
                            text = page.extract_text()
                            if not text: continue
                            
                            # '보유계약 현황' 제목이 있는 페이지인지 확인
                            if "보유계약 현황" in text or "보유계약현황" in text:
                                target_page_found = True
                                lines = text.split('\n')
                                
                                # 보험사 키워드
                                cos = ["삼성", "DB", "현대", "KB", "메리츠", "한화", "흥국", "교보", "라이나", "동양", "신한", "AIA", "롯데", "하나", "농협"]
                                
                                for line in lines:
                                    # 보험사 명칭이 포함된 라인만 필터링
                                    co = next((c for c in cos if c in line), "")
                                    if co:
                                        # 금액(원)과 날짜(20xx) 추출
                                        price = re.search(r'(\d{1,3}(?:,\d{3})*)\s*원', line)
                                        date = re.search(r'(20\d{2}[.\-/]\d{2}[.\-/]\d{2})', line)
                                        
                                        # 상품명: 보험사 이름 뒤부터 금액/날짜 전까지
                                        if price or date:
                                            s_idx = line.find(co) + len(co)
                                            e_idx = price.start() if price else (date.start() if date else len(line))
                                            nm = line[s_idx:e_idx].strip()
                                            
                                            # 불필요한 단어 제거 (정제)
                                            nm = re.sub(r'[^\w\s\(\)가-힣]', '', nm).replace("무배당", "").strip()
                                            
                                            if len(nm) >= 2:
                                                p_val = price.group(0) if price else "-"
                                                d_val = date.group(1) if date else "-"
                                                extracted_data.append(f"{co}/{nm}/{p_val}/{d_val}")
                                
                                # 핵심 페이지를 찾았으므로 더 이상의 페이지 탐색 중단 (별첨 페이지 방지)
                                if extracted_data: break 

                    if extracted_data:
                        # 시트 업데이트 로직
                        m_idx = db.index[db['이름'] == target_u].tolist()
                        r_num = m_idx[-1] + 2
                        cur_memo = db.iloc[m_idx[-1]]['병력(특이사항)'].split('[보장분석]')[0].strip()
                        new_memo = f"{cur_memo} | [보장분석] {' | '.join(list(set(extracted_data)))}"
                        
                        sheet.update_cell(r_num, 7, new_memo)
                        st.success(f"✅ {target_u}님 '보유계약 현황' 페이지에서 {len(set(extracted_data))}건을 정확히 스크랩했습니다!"); st.rerun()
                    else:
                        st.warning("'보유계약 현황' 페이지에서 계약 리스트를 찾지 못했습니다.")
                except Exception as e: st.error(f"오류: {e}")

    # [TAB 1] 조회 화면 - 저장된 데이터만 표로 출력
    with tab1:
        search_name = st.text_input("🔎 고객 성함 검색")
        if search_name and not db.empty:
            res = db[db['이름'].str.contains(search_name)]
            for idx, row in res.iterrows():
                with st.expander(f"👤 {row['이름']} 고객님 리스트"):
                    memo = row.get('병력(특이사항)', '')
                    if "[보장분석]" in memo:
                        items = [i.strip() for i in memo.split("[보장분석]")[-1].split('|') if i.strip()]
                        t_data = []
                        for it in items:
                            p = it.split('/')
                            if len(p) >= 2:
                                t_data.append({"보험사": p[0], "상품명": p[1], "보험료": p[2] if len(p)>2 else "-", "가입일": p[3] if len(p)>3 else "-"})
                        if t_data: st.table(pd.DataFrame(t_data).drop_duplicates())
