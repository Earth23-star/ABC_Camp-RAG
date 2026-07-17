"""YES24 IT 모바일 종합 베스트셀러 도서 목록을 수집하여 CSV 파일로 저장하는 스크래퍼 모듈.

이 모듈은 requests를 통해 브라우저 요청을 모방하여 데이터를 가져오고,
BeautifulSoup을 사용하여 HTML 구조에서 각 도서 정보를 파싱합니다.
상세 검색을 지원하기 위해 각 도서의 상세 소개(Description)도 병렬로 수집한 후 data/yes24_it_mobile_bestsellers.csv로 저장합니다.
"""

import os
import sys
import time
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
import pandas as pd
import re
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# Windows 콘솔 인코딩 대응
sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://www.yes24.com/'
}

def clean_number(text: Optional[str]) -> int:
    """문자열에서 숫자와 쉼표 등을 제외한 모든 문자를 제거하고 정수로 변환한다.

    Args:
        text: 숫자가 포함되었을 것으로 예상되는 원본 문자열.

    Returns:
        정수로 변환된 값. 입력값이 유효하지 않거나 숫자가 없으면 0을 반환한다.
    """
    if not text:
        return 0
    cleaned = re.sub(r'[^\d]', '', text)
    return int(cleaned) if cleaned else 0

def clean_author(auth_element: Optional[Tag]) -> str:
    """도서 정보 태그에서 저자 이름을 추출하여 쉼표로 연결된 문자열로 정제한다.

    Args:
        auth_element: 저자 정보를 포함하고 있는 BeautifulSoup Tag 객체.

    Returns:
        쉼표로 구분된 저자 목록 문자열. 저자 정보가 없는 경우 빈 문자열을 반환한다.
    """
    if not auth_element:
        return ""
    anchors = auth_element.find_all('a')
    if anchors:
        authors = [a.get_text(strip=True) for a in anchors]
        return ", ".join(authors)
    
    text = auth_element.get_text(strip=True)
    text = re.sub(r'\s*저\s*$', '', text)
    return text

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
        res.encoding = 'utf-8'
        if res.status_code != 200:
            return ""
            
        soup = BeautifulSoup(res.text, 'lxml')
        
        # 1. 상세 소개 영역 (#infoset_introduce) 추출
        intro_div = soup.select_one('#infoset_introduce .infoWrap_txt')
        if intro_div:
            text = intro_div.get_text(separator="\n", strip=True)
            if text:
                return text
                
        # 2. 폴백: 메타 태그의 description 추출
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content'].strip()
            
    except Exception:
        pass
        
    return ""

def scrape_yes24_bestsellers() -> None:
    """YES24 IT/모바일 종합 베스트셀러 도서 목록을 전체 페이지에 걸쳐 수집하고 CSV 파일로 저장한다.

    이 함수는 카테고리 베스트셀러 페이지를 순회하며 기본 정보를 수집한 후,
    멀티스레딩을 활용하여 각 도서의 상세 소개글(Description)을 병렬로 추가 수집합니다.
    수집 완료 후 'data/yes24_it_mobile_bestsellers.csv' 경로로 최종 저장됩니다.

    Raises:
        requests.exceptions.HTTPError: HTTP 요청 과정 중 에러가 발생하여 처리가 불가능한 경우.
    """
    base_url = "https://www.yes24.com/product/category/bestseller"
    category_number = "001001003"  # IT 모바일
    page_size = 24
    
    first_page_url = f"{base_url}?categoryNumber={category_number}&pageNumber=1&pageSize={page_size}"
    print(f"1페이지 요청 중: {first_page_url}")
    
    try:
        response = requests.get(first_page_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"1페이지를 불러오는 데 실패했습니다: {e}")
        sys.exit(1)
        
    soup = BeautifulSoup(response.text, 'lxml')
    
    # 맨끝 페이지 번호 추출
    end_page_elem = soup.find('a', class_=lambda c: c and 'end' in c)
    total_pages = 42  # 추출 실패 시 디폴트 값
    if end_page_elem and end_page_elem.get('title'):
        try:
            total_pages = int(end_page_elem.get('title'))
            print(f"동적으로 확인된 총 페이지 수: {total_pages}")
        except ValueError:
            pass
    else:
        page_links = soup.select('.yesUI_pagen a.num')
        if page_links:
            try:
                pages = [int(link.get_text(strip=True)) for link in page_links if link.get_text(strip=True).isdigit()]
                if pages:
                    total_pages = max(pages)
                    print(f"페이지 링크 분석을 통한 총 페이지 수: {total_pages}")
            except Exception:
                pass
                
    print(f"최종 {total_pages}페이지까지 기본 도서 데이터 수집을 시작합니다.")
    
    all_books: List[Dict[str, Any]] = []
    
    for page in range(1, total_pages + 1):
        target_url = f"{base_url}?categoryNumber={category_number}&pageNumber={page}&pageSize={page_size}"
        print(f"[{page}/{total_pages}] 페이지 기본 정보 수집 중...")
        
        try:
            if page > 1:
                response = requests.get(target_url, headers=HEADERS, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'lxml')
                
            book_items = soup.select('#yesBestList > li')
            if not book_items:
                print(f"{page}페이지에 도서 목록이 존재하지 않습니다. 수집을 조기 종료합니다.")
                break
                
            for item in book_items:
                # 1. 순위
                rank_elem = item.select_one('.ico.rank')
                rank = int(rank_elem.get_text(strip=True)) if rank_elem else None
                
                # 2. 도서명
                title_elem = item.select_one('.info_name .gd_name')
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                
                # 3. 상세페이지 링크
                href = title_elem.get('href', '')
                detail_link = f"https://www.yes24.com{href}" if href.startswith('/') else href
                
                # 4. 저자
                auth_elem = item.select_one('.info_auth')
                author = clean_author(auth_elem)
                
                # 5. 출판사
                pub_elem = item.select_one('.info_pub')
                publisher = pub_elem.get_text(strip=True) if pub_elem else ""
                
                # 6. 출판일
                date_elem = item.select_one('.info_date')
                publish_date = date_elem.get_text(strip=True) if date_elem else ""
                
                # 7. 할인율
                discount_elem = item.select_one('.info_price .txt_sale .num')
                discount_rate = discount_elem.get_text(strip=True) + "%" if discount_elem else "0%"
                
                # 8. 판매가
                sale_price_elem = item.select_one('.info_price strong.txt_num .yes_b')
                sale_price = clean_number(sale_price_elem.get_text(strip=True)) if sale_price_elem else 0
                
                # 9. 정가
                original_price_elem = item.select_one('.info_price span.txt_num.dash .yes_m')
                original_price = clean_number(original_price_elem.get_text(strip=True)) if original_price_elem else sale_price
                
                # 10. 판매지수
                sale_index_elem = item.select_one('.info_rating .saleNum')
                sale_index = clean_number(sale_index_elem.get_text(strip=True)) if sale_index_elem else 0
                
                # 11. 리뷰개수
                review_elem = item.select_one('.rating_rvCount a')
                review_count = clean_number(review_elem.get_text(strip=True)) if review_elem else 0
                
                # 12. 평점
                rating_elem = item.select_one('.rating_grade .yes_b')
                rating = float(rating_elem.get_text(strip=True)) if rating_elem else 0.0
                
                all_books.append({
                    'Rank': rank,
                    'Title': title,
                    'Author': author,
                    'Publisher': publisher,
                    'Publish Date': publish_date,
                    'Sale Price': sale_price,
                    'Original Price': original_price,
                    'Discount Rate': discount_rate,
                    'Sale Index': sale_index,
                    'Review Count': review_count,
                    'Rating': rating,
                    'Detail Link': detail_link,
                    'Description': ''  # 초기값 비워둠
                })
                
            time.sleep(0.5)
            
        except Exception as e:
            print(f"{page}페이지 수집 중 에러 발생: {e}")
            time.sleep(1.0)
            
    if not all_books:
        print("수집된 도서가 없습니다. 종료합니다.")
        return

    # 상세 정보(Description)를 멀티스레딩으로 수집
    total_books = len(all_books)
    print(f"\n기본 도서 정보 수집 완료. 총 {total_books}개 도서에 대한 상세 소개(Description) 병렬 수집을 시작합니다.")
    
    start_time = time.time()
    completed_count = 0
    max_workers = 30
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 각 도서 객체와 태스크를 매핑
        future_to_book = {
            executor.submit(fetch_description, book['Detail Link']): idx 
            for idx, book in enumerate(all_books)
        }
        
        for future in as_completed(future_to_book):
            idx = future_to_book[future]
            try:
                desc = future.result()
                all_books[idx]['Description'] = desc
            except Exception as e:
                print(f"[도서 {idx}] 상세 소개 수집 중 오류: {e}")
                
            completed_count += 1
            if completed_count % 100 == 0 or completed_count == total_books:
                print(f"상세 소개 수집 상황: {completed_count}/{total_books} 완료 ({completed_count/total_books*100:.1f}%) | 소요 시간: {time.time() - start_time:.1f}초")

    # CSV 파일로 저장
    df = pd.DataFrame(all_books)
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)
    csv_filename = os.path.join(data_dir, "yes24_it_mobile_bestsellers.csv")
    
    try:
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        print(f"\n성공! 총 {len(df)}개의 도서 데이터를 '{csv_filename}'에 성공적으로 저장했습니다.")
    except Exception as e:
        print(f"파일 저장 중 오류 발생: {e}")

if __name__ == '__main__':
    scrape_yes24_bestsellers()
