"""기존 YES24 베스트셀러 데이터에 상세 도서 소개(Description) 필드를 보완하여 새로운 경로로 마이그레이션하는 스크립트.

이 스크립트는 기존 수집된 CSV 파일을 읽어 각 도서의 상세 링크로부터 도서 소개 글을 병렬로 수집한 후,
data/yes24_it_mobile_bestsellers.csv 파일로 새롭게 저장합니다.
"""

import os
import sys
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# 콘솔 출력 인코딩 우회 (Windows 환경)
sys.stdout.reconfigure(encoding='utf-8')

# 크롤링 설정
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}
MAX_WORKERS = 30  # 병렬 처리 스레드 개수

def fetch_description(detail_url: str) -> str:
    """도서 상세 페이지에서 책 소개 글을 가져온다.

    상세 페이지의 '#infoset_introduce .infoWrap_txt' 영역을 우선 파싱하며,
    해당 영역이 없을 경우 메타 태그의 description 값을 폴백으로 사용한다.

    Args:
        detail_url: 도서 상세 페이지 URL.

    Returns:
        수집된 책 소개 문자열. 수집 실패 시 빈 문자열을 반환한다.
    """
    if not detail_url or not isinstance(detail_url, str) or not detail_url.startswith('http'):
        return ""
        
    try:
        res = requests.get(detail_url, headers=HEADERS, timeout=8)
        res.encoding = 'utf-8'  # 상세페이지 인코딩 적용
        if res.status_code != 200:
            return ""
            
        soup = BeautifulSoup(res.text, 'lxml')
        
        # 1. 상세 소개 영역 (#infoset_introduce) 추출
        intro_div = soup.select_one('#infoset_introduce .infoWrap_txt')
        if intro_div:
            # 텍스트를 깨끗하게 정제
            text = intro_div.get_text(separator="\n", strip=True)
            if text:
                return text
                
        # 2. 폴백: 메타 태그의 description 추출
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content'].strip()
            
    except Exception:
        # 조용히 빈 문자열 리턴하여 안정성 유지
        pass
        
    return ""

def main():
    """기존 CSV 데이터를 읽어 상세 소개 컬럼을 채우고 새 디렉터리로 저장한다."""
    src_file = "yes24_it_mobile_bestsellers.csv"
    dest_file = os.path.join("data", "yes24_it_mobile_bestsellers.csv")
    
    if not os.path.exists(src_file):
        print(f"오류: 원본 파일 '{src_file}'이 존재하지 않습니다.")
        sys.exit(1)
        
    print(f"기존 데이터 로드 중: {src_file}")
    df = pd.DataFrame()
    try:
        df = pd.read_csv(src_file)
    except Exception as e:
        print(f"CSV 파일을 읽는 중 오류 발생: {e}")
        sys.exit(1)
        
    total_books = len(df)
    print(f"총 {total_books}개의 도서 데이터에 대해 상세 소개(Description) 크롤링을 시작합니다.")
    print(f"스레드 풀 크기: {MAX_WORKERS}")
    
    descriptions = [""] * total_books
    start_time = time.time()
    
    # Detail Link와 순번 매핑하여 병렬 처리
    url_to_index = {row['Detail Link']: idx for idx, row in df.iterrows()}
    urls = list(url_to_index.keys())
    
    completed_count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 각 URL에 대해 크롤링 태스크 할당
        future_to_url = {executor.submit(fetch_description, url): url for url in urls}
        
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            idx = url_to_index[url]
            try:
                desc = future.result()
                descriptions[idx] = desc
            except Exception as e:
                print(f"\n[Index {idx}] 크롤링 중 오류 발생: {e}")
                
            completed_count += 1
            if completed_count % 100 == 0 or completed_count == total_books:
                elapsed = time.time() - start_time
                print(f"진행 상황: {completed_count}/{total_books} 완료 ({completed_count/total_books*100:.1f}%) | 소요 시간: {elapsed:.1f}초")
                
    # 데이터프레임에 새 컬럼 추가
    df['Description'] = descriptions
    
    # 새로운 경로에 CSV 저장
    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
    df.to_csv(dest_file, index=False, encoding='utf-8-sig')
    
    total_elapsed = time.time() - start_time
    print(f"\n완료! 마이그레이션이 성공적으로 처리되었습니다.")
    print(f"새 저장소: {dest_file}")
    print(f"총 소요 시간: {total_elapsed:.1f}초")

if __name__ == '__main__':
    main()
