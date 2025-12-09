from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date, datetime
from pydantic import BaseModel
from typing import List, Optional
import pytesseract
from PIL import Image
import io, os, re, cv2, numpy as np, traceback, logging

from database.database import get_db
from database import models

# ============================================================
# ⚙️ 로깅 설정
# ============================================================
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/receipts", tags=["receipts"])


# ============================================================
# 📘 1) 스키마 정의
# ============================================================
class ReceiptBase(BaseModel):
    store_name: str
    amount: int
    category: str
    receipt_date: date
    notes: Optional[str] = None


class ReceiptResponse(ReceiptBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# 🧩 2) 안전한 날짜 변환
# ============================================================
def to_date_safe(d):
    if isinstance(d, date):
        return d
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, str):
        s = d.strip()
        for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                continue
        m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", s)
        if m:
            y, mm, dd = map(int, m.groups())
            return date(y, mm, dd)
    return date.today()


# ============================================================
# 🧠 3) OCR 가게명 / 금액 추출
# ============================================================
KNOWN_BRANDS = {
    "폴드베이커리": ["폴드베이커리", "FOLD BAKERY", "FOLDBAKERY", "폴드", "FOLD"],
    "스타벅스": ["스타벅스", "STARBUCKS"],
    "이마트": ["이마트", "EMART", "E-MART"],
    "홈플러스": ["홈플러스", "HOMEPLUS"],
    "GS25": ["GS25", "GS편의점"],
    "CU": ["CU", "씨유"],
    "세븐일레븐": ["세븐일레븐", "7-ELEVEN"],
    "투썸플레이스": ["투썸", "TWOSOME", "투썸플레이스"],
    "이디야": ["이디야", "EDIYA"],
    "메가커피": ["메가커피", "MEGACOFFEE"],
    "컴포즈커피": ["컴포즈", "COMPOSE"],
    "파리바게뜨": ["파리바게뜨", "PARIS BAGUETTE"],
    "뚜레쥬르": ["뚜레쥬르", "TOUS LES JOURS"],
    "올리브영": ["올리브영", "OLIVE YOUNG", "OLIVEYOUNG", "O L I V E Y O U N G"],
    "다이소": ["다이소", "DAISO"],
    "롯데마트": ["롯데마트", "LOTTE MART"],
    "쿠팡": ["쿠팡", "COUPANG"],
    "SSG": ["SSG", "쓱"],
    "맥도날드": ["맥도날드", "MCDONALDS"],
    "버거킹": ["버거킹", "BURGER KING"],
    "KFC": ["KFC"],
    "서브웨이": ["서브웨이", "SUBWAY"],
}


def remove_spaces_from_text(t: str) -> str:
    t = re.sub(r"([가-힣])\s+([가-힣])", r"\1\2", t)
    t = re.sub(r"([A-Z])\s+([A-Z])", r"\1\2", t)
    return t


def extract_store_name(lines):
    if not lines:
        return "가게명 미확인"
    first = remove_spaces_from_text(lines[0])
    first = re.sub(r"\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2}.*$", "", first)
    first = re.sub(r"[^가-힣A-Za-z\s]", "", first).strip()
    if 2 <= len(first) <= 20:
        return first
    return "가게명 미확인"


def extract_store_name_with_brands(lines):
    if not lines:
        return "가게명 미확인"
    joined_text = " ".join(lines[:7])
    no_space = remove_spaces_from_text(joined_text).upper()
    no_special = re.sub(r"[^가-힣A-Z0-9]", "", joined_text).upper()
    candidate_texts = {no_space, no_special, joined_text.upper().replace(" ", "")}

    for brand, variations in KNOWN_BRANDS.items():
        for variation in variations:
            v_no_space = variation.replace(" ", "").upper()
            for text_variant in candidate_texts:
                if v_no_space in text_variant or text_variant.find(v_no_space) != -1:
                    logger.info(f"✅ 브랜드 발견: {brand} (매칭: {variation})")
                    return brand
    return extract_store_name(lines)


def clean_store_name(s):
    s = s.strip()
    s = re.sub(r"[『』「」『0Ｌㄴㅁ시]", "", s)
    s = re.sub(r"영수증.*$", "", s)
    s = re.sub(r"\d{4}.*$", "", s)
    s = " ".join(s.split())
    if len(s) > 25:
        s = s[:25]
    return s or "가게명 미확인"


def extract_total_amount(text):
    lines = text.split("\n")
    for line in lines:
        if re.search(r"(원|욘|웡|WON|USD|KRW|$)", line, re.IGNORECASE):
            m = re.search(r"(\d{1,3}(?:,\d{3})*)", line)
            if m:
                amt = int(m.group(1).replace(",", ""))
                if 100 <= amt <= 10000000:
                    return amt
    for line in lines:
        if any(k in line for k in ["합계", "총액", "결제금액", "금액", "TOTAL"]):
            m = re.search(r"(\d{1,3}(?:,\d{3})+)", line)
            if m:
                amt = int(m.group(1).replace(",", ""))
                if 100 <= amt <= 10000000:
                    return amt
    return 0


# ============================================================
# 🧾 4) OCR 파싱
# ============================================================
def parse_receipt_text(text: str):
    lines = text.split("\n")
    store_name = clean_store_name(extract_store_name_with_brands(lines))
    amount = extract_total_amount(text)

    receipt_date = None
    for p in [
        r"(\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})",
        r"(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)",
    ]:
        m = re.search(p, text)
        if m:
            s = (
                m.group(1)
                .replace("년", "-")
                .replace("월", "-")
                .replace("일", "")
                .replace(".", "-")
            )
            try:
                receipt_date = datetime.strptime(s, "%Y-%m-%d").date()
                break
            except:
                pass
    if not receipt_date:
        receipt_date = datetime.today().date()

    text_no_space = remove_spaces_from_text(text).upper()
    store_upper = remove_spaces_from_text(store_name).upper()
    category = "Others"
    category_keywords = {
        "Dining out": ["베이커리", "BAKERY", "카페", "커피", "COFFEE", "CAFE", "스타벅스",
                       "식당", "뷔페", "레스토랑", "맥도날드", "버거킹", "KFC", "피자", "치킨"],
        "Groceries": ["마트", "MART", "편의점", "홈플러스", "이마트", "EMART", "CU", "GS25",
                      "세븐일레븐", "쿠팡", "COUPANG", "SSG", "롯데마트", "COSTCO"],
        "Transportation": ["택시", "TAXI", "버스", "BUS", "지하철", "SUBWAY", "KTX", "주유소",
                           "PARKING", "고속도로", "코레일", "ASIANA", "대한항공"],
        "Entertainment": ["영화", "MOVIE", "CGV", "메가박스", "노래방", "KARAOKE", "게임",
                          "놀이공원", "콘서트", "뮤지컬", "박물관"],
        "Subscription": ["넷플릭스", "NETFLIX", "SPOTIFY", "유튜브", "배달의민족", "요기요", "왓챠",
                         "디즈니", "APPLE", "GOOGLE"],
        "Shopping": ["무신사", "UNIQLO", "ZARA", "NIKE", "백화점", "MALL", "아울렛",
                     "OUTLET", "의류", "가방", "올리브영", "OLIVEYOUNG"],
    }
    for cat, keys in category_keywords.items():
        if any(k.upper() in text_no_space for k in keys) or any(
            k.upper() in store_upper for k in keys
        ):
            category = cat
            break

    return {
        "store_name": store_name,
        "amount": amount,
        "receipt_date": receipt_date,
        "category": category,
    }


# ============================================================
# 📸 5) OCR + DB 저장 + 박스 이미지 생성
# ============================================================
@router.post("/upload_with_boxes")
async def upload_receipt_with_boxes(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        os.makedirs("uploads", exist_ok=True)
        image_path = f"uploads/{file.filename}"
        image.save(image_path)

        image_cv = np.array(image)
        data = pytesseract.image_to_data(image_cv, lang="kor+eng", output_type=pytesseract.Output.DICT)
        lines = {}

        # ✅ 박스 그리기 추가
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            if text and int(data["conf"][i]) > 0:
                (x, y, w, h) = (data["left"][i], data["top"][i], data["width"][i], data["height"][i])
                cv2.rectangle(image_cv, (x, y), (x + w, y + h), (0, 255, 0), 2)
                lines.setdefault(data["line_num"][i], []).append(text)

        # ✅ 결과 이미지 저장
        os.makedirs("static/results", exist_ok=True)
        boxed_path = f"static/results/boxed_{file.filename}"
        cv2.imwrite(boxed_path, image_cv)

        ocr_text = "\n".join([" ".join(lines[k]) for k in sorted(lines.keys())])
        parsed = parse_receipt_text(ocr_text)

        if parsed["amount"] <= 0:
            logger.warning("⚠️ 금액 인식 실패 → 기본값 1 적용")
            parsed["amount"] = 1

        new_receipt = models.Receipt(
            image_path=image_path,
            store_name=parsed["store_name"],
            amount=parsed["amount"],
            category=parsed["category"],
            receipt_date=to_date_safe(parsed["receipt_date"]),
            notes=f"OCR from {file.filename}",
        )
        db.add(new_receipt)
        db.commit()
        db.refresh(new_receipt)

        return JSONResponse(
            content={
                "message": "✅ OCR 인식 및 박스 이미지 생성 완료",
                "parsed_data": {**parsed, "receipt_date": str(parsed["receipt_date"])},
                "boxed_image": f"/static/results/boxed_{file.filename}",  # ✅ 추가됨
                "db_saved": {
                    "id": new_receipt.id,
                    "store_name": new_receipt.store_name,
                    "amount": new_receipt.amount,
                    "category": new_receipt.category,
                    "receipt_date": str(new_receipt.receipt_date),
                },
            }
        )

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 📂 6) CRUD
# ============================================================
@router.post("/", response_model=ReceiptResponse, status_code=status.HTTP_201_CREATED)
def create_receipt(receipt_data: ReceiptBase, db: Session = Depends(get_db)):
    new_r = models.Receipt(**receipt_data.model_dump())
    db.add(new_r)
    db.commit()
    db.refresh(new_r)
    return new_r

@router.get("", include_in_schema=False)
@router.get("/", response_model=List[ReceiptResponse])
def get_receipts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Receipt).offset(skip).limit(limit).all()


@router.get("/{rid}", response_model=ReceiptResponse)
def get_receipt(rid: int, db: Session = Depends(get_db)):
    r = db.query(models.Receipt).filter(models.Receipt.id == rid).first()
    if not r:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return r


@router.put("/{rid}", response_model=ReceiptResponse)
def update_receipt(rid: int, receipt_data: ReceiptBase, db: Session = Depends(get_db)):
    # 1) 기존 레코드 가져오기
    r = db.query(models.Receipt).filter(models.Receipt.id == rid).first()
    if not r:
        raise HTTPException(status_code=404, detail="Receipt not found")

    # 2) 필요한 필드만 안전하게 업데이트 (기존 image_path, created_at 등 유지됨)
    r.store_name = receipt_data.store_name
    r.amount = receipt_data.amount
    r.category = receipt_data.category
    r.receipt_date = to_date_safe(receipt_data.receipt_date)
    r.notes = receipt_data.notes

    # 3) 저장
    db.commit()
    db.refresh(r)

    return r

@router.delete("/{rid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_receipt(rid: int, db: Session = Depends(get_db)):
    r = db.query(models.Receipt).filter(models.Receipt.id == rid).first()
    if not r:
        raise HTTPException(status_code=404, detail="Receipt not found")
    db.delete(r)
    db.commit()
    return None


# ============================================================
# 📊 7) 월별 통계
# ============================================================
@router.get("/statistics/monthly")
def get_monthly_statistics(db: Session = Depends(get_db)):
    today = date.today()
    first_day = today.replace(day=1)
    next_month = (
        today.replace(year=today.year + 1, month=1, day=1)
        if today.month == 12
        else today.replace(month=today.month + 1, day=1)
    )
    q = f"""
        SELECT category AS name, SUM(amount) AS value
        FROM receipts
        WHERE receipt_date >= '{first_day.isoformat()}'
          AND receipt_date < '{next_month.isoformat()}'
        GROUP BY category
    """
    rows = db.execute(text(q)).fetchall()
    return JSONResponse(content=[{"name": r[0], "value": r[1]} for r in rows])

