# ============================================================
# 🧠 OCR 비교 과제 (손글씨 버전)
# 엔진: Tesseract / OCR.Space / PyMuPDF
# 개선: 대비 강화, threshold 최적화, deskew 제거, PSM 조정
# ============================================================

import cv2
import numpy as np
import requests
import json
import fitz
from PIL import Image, ImageEnhance
import pytesseract
import io
import Levenshtein
import matplotlib.pyplot as plt
import os

# ============================================================
# 0️⃣ 경로 설정
# ============================================================
base_dir = "/home/ubuntu/flask_app/1103/1103_assignment"
image_path = os.path.join(base_dir, "data/handwriting.jpeg")
pdf_path = os.path.join(base_dir, "data/handwriting.pdf")
truth_path = os.path.join(base_dir, "data/original.txt")   # 원문 텍스트 따로 저장된 파일
temp_dir = os.path.join(base_dir, "temp")
result_dir = os.path.join(base_dir, "results")
os.makedirs(temp_dir, exist_ok=True)
os.makedirs(result_dir, exist_ok=True)

# ============================================================
# 1️⃣ 이미지 불러오기
# ============================================================
img = cv2.imread(image_path)
if img is None:
    print("❌ 이미지를 찾을 수 없습니다:", image_path)
    exit()

# ============================================================
# 2️⃣ 전처리 (이미지 품질 향상)
# ============================================================

# (1) Grayscale
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# (2) 대비 강화 (명암 3배)
pil_img = Image.fromarray(gray)
enhancer = ImageEnhance.Contrast(pil_img)
contrast_img = enhancer.enhance(3.0)
contrast_np = np.array(contrast_img)
cv2.imwrite(os.path.join(temp_dir, "contrast_boost.jpg"), contrast_np)

# (3) 약한 대비 버전 (OCR.Space용)
enhancer_light = ImageEnhance.Contrast(pil_img)
light_contrast_img = enhancer_light.enhance(1.5)
light_np = np.array(light_contrast_img)
cv2.imwrite(os.path.join(temp_dir, "light_contrast.jpg"), light_np)

# (4) Binarization (Threshold = 160)
_, im_bw = cv2.threshold(contrast_np, 160, 255, cv2.THRESH_BINARY)
cv2.imwrite(os.path.join(temp_dir, "bw_image.jpg"), im_bw)

# (5) Noise Removal
def noise_removal(image):
    kernel = np.ones((1, 1), np.uint8)
    image = cv2.dilate(image, kernel, iterations=1)
    image = cv2.erode(image, kernel, iterations=1)
    image = cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel)
    image = cv2.medianBlur(image, 3)
    return image

no_noise = noise_removal(im_bw)
cv2.imwrite(os.path.join(temp_dir, "no_noise.jpg"), no_noise)

# 🔥 최종 전처리 이미지 선택
final_image_tesseract = os.path.join(temp_dir, "contrast_boost.jpg")
final_image_ocrspace = os.path.join(temp_dir, "light_contrast.jpg")

# ============================================================
# 3️⃣ OCR 함수 정의
# ============================================================

def ocr_tesseract(image_path):
    """Tesseract OCR (kor+eng 혼합 지원, psm 6 모드)"""
    img = Image.open(image_path)
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(img, lang='kor+eng', config=custom_config)
    return text.strip()


def ocr_space_api(image_path, api_key='K84806241488957', language='kor'):
    """OCR.Space API (영문/한글 혼합 이미지용)"""
    url_api = "https://api.ocr.space/parse/image"

    img = Image.open(image_path)
    if img.width > 1000:
        ratio = 1000 / img.width
        new_size = (1000, int(img.height * ratio))
        img = img.resize(new_size)
        image_path = os.path.join(temp_dir, "resized.jpg")
        img.save(image_path)

    with open(image_path, 'rb') as f:
        try:
            response = requests.post(
                url_api,
                files={"filename": f},
                data={"apikey": api_key, "language": language},
                timeout=120
            )
            result = response.json()

             # ✅ 디버깅용 출력 추가
            print("🔍 [OCR.Space Debug Info]")
            print("OCRExitCode:", result.get("OCRExitCode"))
            print("ErrorMessage:", result.get("ErrorMessage"))
            print("IsErroredOnProcessing:", result.get("IsErroredOnProcessing"))

        except requests.exceptions.ReadTimeout:
            print("⏱️ OCR.Space 응답 시간 초과 (Timeout)")
            return ""

    parsed = result.get("ParsedResults")
    text_detected = parsed[0].get("ParsedText", "") if parsed else ""
    return text_detected.strip()


def ocr_pymupdf(pdf_path):
    """PyMuPDF OCR (PDF 텍스트 및 이미지 포함)"""
    doc = fitz.open(pdf_path)
    full_text = ""
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        full_text += page.get_text()
        for img_info in page.get_images():
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            img_bytes = base_image["image"]
            img_pil = Image.open(io.BytesIO(img_bytes))
            img_text = pytesseract.image_to_string(img_pil, lang='kor+eng')
            full_text += "\n[이미지 OCR 결과]\n" + img_text + "\n"
    return full_text.strip()


def calculate_accuracy(original_text, ocr_text):
    """Levenshtein 거리 기반 인식률 계산"""
    distance = Levenshtein.distance(original_text, ocr_text)
    max_len = max(len(original_text), len(ocr_text))
    return round((1 - distance / max_len) * 100, 2) if max_len > 0 else 0

# ============================================================
# 4️⃣ 메인 실행
# ============================================================
if __name__ == "__main__":
    with open(truth_path, "r", encoding="utf-8") as f:
        original_text = f.read().strip()

    print("📘 [원본 텍스트 불러오기 완료]")
    print(original_text)
    print("=" * 70)

    print("1️⃣ Tesseract OCR 실행 중...")
    tesseract_text = ocr_tesseract(final_image_tesseract)

    print("2️⃣ OCR.Space API 실행 중...")
    ocrspace_text = ocr_space_api(final_image_ocrspace)

    print("3️⃣ PyMuPDF OCR 실행 중...")
    pymupdf_text = ocr_pymupdf(pdf_path)

    print("\n📊 인식률 계산 중...\n")
    tesseract_acc = calculate_accuracy(original_text, tesseract_text)
    ocrspace_acc = calculate_accuracy(original_text, ocrspace_text)
    pymupdf_acc = calculate_accuracy(original_text, pymupdf_text)

    print("✅ 인식률 결과:")
    print(f"Tesseract  : {tesseract_acc:.2f}%")
    print(f"OCR.Space  : {ocrspace_acc:.2f}%")
    print(f"PyMuPDF    : {pymupdf_acc:.2f}%")

    # ============================================================
    # 5️⃣ 시각화 및 결과 저장
    # ============================================================
    engines = ['Tesseract', 'OCR.Space', 'PyMuPDF']
    accuracies = [tesseract_acc, ocrspace_acc, pymupdf_acc]
    plt.figure(figsize=(6, 4))
    bars = plt.bar(engines, accuracies, color=['#E0E0E0', '#B0B0B0', '#707070'])
    plt.title("OCR Engine Accuracy Comparison (Handwriting)", fontsize=14)
    plt.xlabel("OCR Engine", fontsize=12)
    plt.ylabel("Accuracy (%)", fontsize=12)
    plt.ylim(0, 110)
    for bar, acc in zip(bars, accuracies):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height()-10,
                 f"{acc:.1f}%", ha='center', va='bottom', fontsize=10, color='white')
    graph_path = os.path.join(result_dir, "ocr_accuracy_handwriting.png")
    plt.tight_layout()
    plt.savefig(graph_path)

    result_txt = os.path.join(result_dir, "ocr_results_handwriting.txt")
    with open(result_txt, "w", encoding="utf-8") as f:
        f.write("📘 OCR 비교 결과 (Handwriting)\n\n")
        f.write(f"[원본 텍스트]\n{original_text}\n\n")
        f.write("[Tesseract 결과]\n" + tesseract_text + "\n\n")
        f.write("[OCR.Space 결과]\n" + ocrspace_text + "\n\n")
        f.write("[PyMuPDF 결과]\n" + pymupdf_text + "\n\n")
        f.write("📊 인식률 비교\n")
        f.write(f"Tesseract : {tesseract_acc:.2f}%\n")
        f.write(f"OCR.Space : {ocrspace_acc:.2f}%\n")
        f.write(f"PyMuPDF   : {pymupdf_acc:.2f}%\n")

    print(f"\n✅ 결과 저장 완료: {result_txt}")
    print(f"📊 그래프 저장 완료: {graph_path}")
