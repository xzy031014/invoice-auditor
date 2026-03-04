"""
OCR识别模块 - 使用PaddleOCR提取发票信息
"""
import os
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from paddleocr import PaddleOCR
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class OCRReader:
    """发票OCR识别器"""

    def __init__(self, use_gpu: bool = False, lang: str = 'ch'):
        """
        初始化OCR引擎

        Args:
            use_gpu: 是否使用GPU加速
            lang: 语言设置，'ch'为中文，'en'为英文
        """
        # 新版PaddleOCR 3.4+ 简化参数
        self.ocr = PaddleOCR(lang=lang, use_angle_cls=True)
        logger.info("OCR引擎初始化完成")

    def read_image(self, image_path: str) -> List[Dict]:
        """
        读取图片并返回OCR结果

        Args:
            image_path: 图片文件路径

        Returns:
            OCR识别结果列表，每个元素包含文本和坐标信息
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        try:
            result = self.ocr.ocr(image_path, cls=True)
            if result and result[0]:
                # 提取文本和位置信息
                ocr_data = []
                for line in result[0]:
                    box = line[0]  # 坐标
                    text_info = line[1]  # (文本, 置信度)
                    ocr_data.append({
                        'text': text_info[0],
                        'confidence': text_info[1],
                        'box': box
                    })
                logger.info(f"成功识别图片: {image_path}, 识别到 {len(ocr_data)} 个文本块")
                return ocr_data
            else:
                logger.warning(f"未能从图片中识别到文本: {image_path}")
                return []
        except Exception as e:
            logger.error(f"OCR识别出错: {image_path}, 错误: {str(e)}")
            return []

    def extract_invoice_number(self, ocr_data: List[Dict]) -> Optional[str]:
        """
        提取发票号码

        Args:
            ocr_data: OCR识别结果

        Returns:
            发票号码
        """
        # 发票号码通常是8位、10位或12位数字
        patterns = [
            r'发票号码[：:]\s*(\d{8,20})',
            r'No[.:]\s*(\d{8,20})',
            r'号码[：:]\s*(\d{8,20})',
        ]

        text = ' '.join([item['text'] for item in ocr_data])

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        # 尝试直接找8-20位数字（可能是发票号）
        numbers = re.findall(r'\b\d{8,20}\b', text)
        if numbers:
            return numbers[0]

        return None

    def extract_amount(self, ocr_data: List[Dict]) -> Optional[float]:
        """
        提取发票金额

        Args:
            ocr_data: OCR识别结果

        Returns:
            发票金额（元）
        """
        # 查找价税合计/金额相关关键词
        text = ' '.join([item['text'] for item in ocr_data])

        # 匹配 "价税合计 ¥123.45" 或 "合计 123.45元" 等格式
        patterns = [
            r'价税合计[￥¥$]?\s*([\d,]+\.?\d*)',
            r'合计[￥¥$]?\s*([\d,]+\.?\d*)',
            r'金额[￥¥$]?\s*([\d,]+\.?\d*)',
            r'总额[￥¥$]?\s*([\d,]+\.?\d*)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                # 取最大的金额作为发票金额
                amounts = [float(m.replace(',', '')) for m in matches]
                return max(amounts)

        # 备用方案：查找所有金额格式，取最大的
        all_amounts = re.findall(r'[￥¥$]?\s*([\d,]+\.\d{2})', text)
        if all_amounts:
            amounts = [float(a.replace(',', '')) for a in all_amounts]
            # 排除过小的金额（可能是单价）
            valid_amounts = [a for a in amounts if a > 1]
            if valid_amounts:
                return max(valid_amounts)

        return None

    def extract_date(self, ocr_data: List[Dict]) -> Optional[str]:
        """
        提取发票日期

        Args:
            ocr_data: OCR识别结果

        Returns:
            发票日期 (YYYY-MM-DD格式)
        """
        text = ' '.join([item['text'] for item in ocr_data])

        # 匹配多种日期格式
        patterns = [
            r'开票日期[：:]\s*(\d{4})[年\-/.](\d{1,2})[月\-/.](\d{1,2})',
            r'日期[：:]\s*(\d{4})[年\-/.](\d{1,2})[月\-/.](\d{1,2})',
            r'(\d{4})[年\-/.](\d{1,2})[月\-/.](\d{1,2})[日日]?',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                year = match.group(1)
                month = match.group(2).zfill(2)
                day = match.group(3).zfill(2)
                return f"{year}-{month}-{day}"

        return None

    def extract_seller_name(self, ocr_data: List[Dict]) -> Optional[str]:
        """
        提取销售方名称（开票方）

        Args:
            ocr_data: OCR识别结果

        Returns:
            销售方名称
        """
        text = ' '.join([item['text'] for item in ocr_data])

        # 查找销售方/开票方
        patterns = [
            r'销售方[名称名称]?[：:]\s*([^\s]{2,30}(?:公司|企业|集团|店|厂))',
            r'开票方[：:]\s*([^\s]{2,30}(?:公司|企业|集团|店|厂))',
            r'收款人[：:]\s*([^\s]{2,30}(?:公司|企业|集团))',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        # 如果找不到，尝试找包含"公司"的较长文本
        company_patterns = re.findall(r'([^。]{5,30}(?:公司|有限公司|股份公司))', text)
        if company_patterns:
            # 返回第一个匹配的公司名称
            return company_patterns[0].strip()

        return None

    def extract_buyer_name(self, ocr_data: List[Dict]) -> Optional[str]:
        """
        提取购买方名称（收票方）

        Args:
            ocr_data: OCR识别结果

        Returns:
            购买方名称
        """
        text = ' '.join([item['text'] for item in ocr_data])

        # 查找购买方
        patterns = [
            r'购买方[名称名称]?[：:]\s*([^\s]{2,30}(?:公司|企业|集团|店|厂))',
            r'收票方[：:]\s*([^\s]{2,30}(?:公司|企业|集团|店|厂))',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return None

    def parse_invoice(self, image_path: str) -> Dict:
        """
        解析发票图片，提取所有关键信息

        Args:
            image_path: 发票图片路径

        Returns:
            包含发票信息的字典
        """
        ocr_data = self.read_image(image_path)

        invoice_info = {
            'file_name': Path(image_path).name,
            'invoice_number': self.extract_invoice_number(ocr_data),
            'amount': self.extract_amount(ocr_data),
            'date': self.extract_date(ocr_data),
            'seller_name': self.extract_seller_name(ocr_data),
            'buyer_name': self.extract_buyer_name(ocr_data),
            'raw_text': ' '.join([item['text'] for item in ocr_data]),
        }

        logger.info(f"发票解析完成: {invoice_info['file_name']}")
        logger.debug(f"解析结果: {invoice_info}")

        return invoice_info


# 测试代码
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建OCR读取器
    reader = OCRReader()

    # 测试图片路径（需要替换为实际图片）
    test_image = "data/invoices/test_invoice.jpg"

    if os.path.exists(test_image):
        result = reader.parse_invoice(test_image)
        print("\n=== 发票信息 ===")
        for key, value in result.items():
            if key != 'raw_text':
                print(f"{key}: {value}")
    else:
        print(f"测试图片不存在: {test_image}")
        print("请将发票图片放在 data/invoices/ 目录下")
