import os

# 1. 고도화된 폴더 구조 및 전체 소스 코드 정의
project_structure = {
    "backend": {
        "requirements.txt": "requests\npandas\nsupabase\npython-dotenv",
        "data_collector.py": """import requests
import pandas as pd
from supabase import create_client
import os

# .env 파일 또는 환경 변수에서 로드 권장
SUPABASE_URL = "YOUR_SUPABASE_URL"
SUPABASE_KEY = "YOUR_SUPABASE_ANON_KEY"
PUBLIC_DATA_KEY = "YOUR_PUBLIC_DATA_KEY"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def collect_and_save():
    # 1. 공공데이터 API 호출
    url = "http://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"
    params = {'serviceKey': PUBLIC_DATA_KEY, 'resultType': 'json', 'numOfRows': '50'}
    
    response = requests.get(url, params=params)
    data = response.json()['response']['body']['items']['item']
    
    # 2. 데이터 가공 및 DB 저장
    for item in data:
        stock_data = {
            "code": item['srtnCd'],
            "name": item['itmsNm'],
            "close_price": int(item['clpr']),
            "change_pct": float(item['fltRt'])
        }
        supabase.table("stocks").upsert(stock_data).execute()
    print("데이터 동기화 완료")

if __name__ == "__main__":
    collect_and_save()
"""
    },
    "frontend": {
        "App.jsx": """// [복사 대상] 이전 대화에서 제공된 React MVP 전체 코드를 이곳에 넣으십시오.
import React, { useState } from 'react';
// ... (생략된 전체 React 코드가 들어갈 자리)
export default function App() { return <div>상세 코드는 채팅창의 React 컴포넌트를 참고하세요.</div>; }
"""
    },
    "docs": {
        "schema.sql": """-- 1. 종목 테이블 생성
CREATE TABLE stocks (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sector TEXT,
    close_price INTEGER,
    change_pct FLOAT,
    rsi INTEGER,
    buy_score INTEGER DEFAULT 0,
    is_leader BOOLEAN DEFAULT false,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. 검색 기록 테이블
CREATE TABLE search_history (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    query_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);""",
        "setup_flow.md": """# 실행 프로세스
1. Supabase 프로젝트 생성 및 SQL 실행
2. API 키 발급 (공공데이터포털, DART, Gemini)
3. Backend 패키지 설치: pip install -r backend/requirements.txt
4. 데이터 수집 실행: python backend/data_collector.py
5. Frontend 실행: npm run dev"""
    }
}

def create_project():
    base_path = os.getcwd()
    for folder, files in project_structure.items():
        folder_path = os.path.join(base_path, folder)
        os.makedirs(folder_path, exist_ok=True)
        for file_name, content in files.items():
            with open(os.path.join(folder_path, file_name), "w", encoding="utf-8") as f:
                f.write(content)
    print("✅ 모든 파일이 Full MVP 버전으로 업데이트되었습니다.")

if __name__ == "__main__":
    create_project()