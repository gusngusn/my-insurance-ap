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

st.set_page_config(page_title="현우 통합 관리 v5.6", layout="wide")
st.title("🛡️ 배현우 설계사 통합 관리 시스템 v5.6")

sheet = get_gsheet()

if sheet:
    all_values = sheet.get_all_values()
    if not all_values:
        sheet.insert_row(EXPECTED_HEADERS, 1)
        db = pd.DataFrame(columns=EXPECTED_HEADERS)
    else:
        db = pd.DataFrame(all_values[1:], columns=EXPECTED_HEADERS[:len(all_values[0])])
        db = db.fillna("")

    tab1, tab2, tab3, tab4 = st.tabs(["🔍 고객 조회 및 계약리스트", "✍️ AI 정보 등록/업데이트", "🚘 자동차 증권 업데이트", "📄 보장분석 파일 업로드"])

    # [TAB 1] 고객 조회 및 보유계약 리스트 출력
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
                                # 상담에 불필요한 키워드 필터링
                                if any(k in item for k in ["미납", "해지", "실효", "종료", "보험회사", "상품명"]): continue
                                
                                parts = item.split('/')
                                if len(parts) >= 2:
                                    # 상품명 정제
                                    name = parts[1].strip()
                                    name = re.sub(r'^\d+\s*', '', name) # 앞 숫자 제거
                                    
                                    price = parts[2].strip() if len(parts) > 2 else "-"
                                    date = parts[3].strip() if len(parts) > 3 else "-"
                                    
                                    if len(name) >= 2:
                                        table_data.append({
                                            "보험회사": parts[0].strip(),
                                            "상품명": name,
                                            "월 보험료": price,
                                            "가입날짜": date
                                        })
                            
                            if table_data:
                                # 중복 제거 후 깔끔하게 출력
                                final_df = pd.DataFrame(table_data).drop_duplicates()
                                st.table(final_df)
                            else: st.info("정상 유지 중인 계약 데이터가 없습니다.")
                        else: st.info("등록된 보장분석 데이터가 없습니다.")
                        
                        st.markdown("---")
                        # (나머지 연락처/주소 등 정보 표시 동일)
                        st.write(f"**연락처:** {row.get('연락처', '-')} | **주소:** {row.get('주소', '-')}")

    # [TAB 4] 보장분석 PDF 정밀 분석 (보유계약 리스트 타겟팅)
    with tab4:
        st.subheader("📄 보장분석 PDF '보유계약현황' 추출")
        up_file = st.file_uploader("보장분석 PDF 업로드", type=['pdf'])
        target_u = st.selectbox("업데이트할 고객", ["선택하세요"] + db['이름'].unique().tolist())
        
        if up_file and target_u != "선택하세요":
            if st.button("🚀 보유계약 리스트 정밀 분석"):
                try:
                    with pdfplumber.open(up_file) as pdf:
                        all_text = ""
                        for page in pdf.pages:
                            text = page.extract_text()
                            if text: all_text += text + "\n"
                    
                    # 1. 보험사 키워드 (누락 방지를 위해 확장)
                    cos = ["삼성", "DB", "현대", "KB", "메리츠", "한화", "흥국", "교보", "라이나", "동양", "에이스", "AIA", "신한", "푸르덴셜", "하나", "농협", "우체국"]
                    extracted = []
                    
                    # 2. '보유계약현황' 페이지 내의 리스트 패턴 분석
                    for line in all_text.split('\n'):
                        # 미납/해지 데이터는 제외
                        if any(k in line for k in ["미납", "해지", "실효", "소멸"]): continue
                        
                        # 보험사 이름이 포함된 라인 찾기
                        co = next((c for c in cos if c in line), "")
                        if co:
                            # 보험료(원)와 날짜(20XX) 패턴 찾기
                            pr = re.search(r'\d{1,3}(?:,\d{3})*원', line)
                            dt = re.search(r'20\d{2}[.\-/]\d{2}[.\-/]\d{2}', line)
                            
                            # 상품명 추출 로직 강화: 보험사 이후부터 보험료/날짜 이전까지를 상품명으로 인식
                            temp_name = line.split(co)[-1]
                            if pr: temp_name = temp_name.split(pr.group())[0]
                            elif dt: temp_name = temp_name.split(dt.group())[0]
                            
                            clean_name = temp_name.strip()
                            if len(clean_name) >= 2:
                                info = f"{co}/{clean_name}/{pr.group() if pr else '-'}/{dt.group() if dt else '-'}"
                                extracted.append(info)
                    
                    if extracted:
                        m_idx = db.index[db['이름'] == target_u].tolist()
                        r_num = m_idx[-1] + 2
                        # 기존 보장분석 데이터만 삭제하고 교체
                        cur_memo = db.iloc[m_idx[-1]]['병력(특이사항)'].split('[보장분석]')[0].strip()
                        new_memo = f"{cur_memo} | [보장분석] {' | '.join(list(set(extracted)))}"
                        sheet.update_cell(r_num, 7, new_memo)
                        st.success(f"✅ {target_u}님의 보유계약 {len(set(extracted))}건을 성공적으로 업데이트했습니다!"); st.rerun()
                    else:
                        st.warning("유효한 보유계약 리스트를 찾지 못했습니다. 파일 내용을 확인해주세요.")
                except Exception as e: st.error(f"오류: {e}")
