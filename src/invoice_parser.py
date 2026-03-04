"""
发票解析模块 - 处理和结构化发票信息
"""
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import logging

from ocr_reader import OCRReader

logger = logging.getLogger(__name__)


class InvoiceInfo:
    """发票信息数据类"""

    def __init__(self, **kwargs):
        self.file_name = kwargs.get('file_name', '')
        self.invoice_number = kwargs.get('invoice_number')
        self.amount = kwargs.get('amount')
        self.date = kwargs.get('date')
        self.seller_name = kwargs.get('seller_name')
        self.buyer_name = kwargs.get('buyer_name')
        self.raw_text = kwargs.get('raw_text', '')

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'file_name': self.file_name,
            'invoice_number': self.invoice_number,
            'amount': self.amount,
            'date': self.date,
            'seller_name': self.seller_name,
            'buyer_name': self.buyer_name,
        }

    def is_valid(self) -> bool:
        """检查发票信息是否完整有效"""
        return all([
            self.invoice_number is not None,
            self.amount is not None and self.amount > 0,
            self.date is not None,
        ])


class ReimbursementApplication:
    """报销申请单数据类"""

    def __init__(self, **kwargs):
        self.applicant = kwargs.get('applicant', '')
        self.department = kwargs.get('department', '')
        self.amount = kwargs.get('amount')
        self.apply_date = kwargs.get('apply_date')
        self.description = kwargs.get('description', '')
        self.expected_invoices = kwargs.get('expected_invoices', 1)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'applicant': self.applicant,
            'department': self.department,
            'amount': self.amount,
            'apply_date': self.apply_date,
            'description': self.description,
            'expected_invoices': self.expected_invoices,
        }


class InvoiceParser:
    """发票解析器 - 处理批量发票和申请单"""

    def __init__(self, ocr_reader: OCRReader):
        self.ocr_reader = ocr_reader
        self.invoices: List[InvoiceInfo] = []
        self.applications: List[ReimbursementApplication] = []

    def parse_invoice_file(self, image_path: str) -> InvoiceInfo:
        """
        解析单个发票文件

        Args:
            image_path: 发票图片路径

        Returns:
            InvoiceInfo对象
        """
        logger.info(f"开始解析发票: {image_path}")
        result = self.ocr_reader.parse_invoice(image_path)
        return InvoiceInfo(**result)

    def parse_invoice_directory(self, directory: str) -> List[InvoiceInfo]:
        """
        解析目录下所有发票

        Args:
            directory: 发票图片目录

        Returns:
            发票信息列表
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            logger.error(f"发票目录不存在: {directory}")
            return []

        # 支持的图片格式
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.pdf'}

        invoice_files = [
            f for f in dir_path.iterdir()
            if f.is_file() and f.suffix.lower() in image_extensions
        ]

        logger.info(f"在目录 {directory} 中发现 {len(invoice_files)} 个发票文件")

        invoices = []
        for file_path in invoice_files:
            try:
                invoice = self.parse_invoice_file(str(file_path))
                if invoice.is_valid():
                    invoices.append(invoice)
                    logger.info(f"成功解析: {file_path.name}")
                else:
                    logger.warning(f"发票信息不完整，跳过: {file_path.name}")
            except Exception as e:
                logger.error(f"解析发票失败: {file_path.name}, 错误: {str(e)}")

        self.invoices = invoices
        return invoices

    def load_application_from_dict(self, app_data: Dict) -> ReimbursementApplication:
        """
        从字典加载报销申请单

        Args:
            app_data: 申请单数据字典

        Returns:
            ReimbursementApplication对象
        """
        return ReimbursementApplication(**app_data)

    def load_applications_from_list(self, app_list: List[Dict]) -> List[ReimbursementApplication]:
        """
        从字典列表加载多个报销申请单

        Args:
            app_list: 申请单数据列表

        Returns:
            ReimbursementApplication对象列表
        """
        applications = [self.load_application_from_dict(app) for app in app_list]
        self.applications = applications
        return applications

    def match_invoices_to_application(
        self,
        application: ReimbursementApplication
    ) -> List[InvoiceInfo]:
        """
        将发票匹配到报销申请单（简单的金额匹配逻辑）

        Args:
            application: 报销申请单

        Returns:
            匹配的发票列表
        """
        if application.amount is None:
            logger.warning("申请单未指定金额，无法匹配")
            return []

        matched_invoices = []
        total_matched = 0

        for invoice in self.invoices:
            if invoice.amount and (total_matched + invoice.amount) <= application.amount * 1.01:
                matched_invoices.append(invoice)
                total_matched += invoice.amount

        logger.info(
            f"申请单 {application.applicant} 金额 {application.amount} "
            f"匹配到 {len(matched_invoices)} 张发票，总计 {total_matched}"
        )

        return matched_invoices

    def get_invoice_summary(self) -> Dict[str, Any]:
        """
        获取发票汇总信息

        Returns:
            汇总信息字典
        """
        total_amount = sum(inv.amount or 0 for inv in self.invoices)
        valid_count = sum(1 for inv in self.invoices if inv.is_valid())

        return {
            'total_count': len(self.invoices),
            'valid_count': valid_count,
            'total_amount': total_amount,
            'sellers': list(set(inv.seller_name for inv in self.invoices if inv.seller_name)),
        }


# 测试代码
if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建解析器
    ocr_reader = OCRReader()
    parser = InvoiceParser(ocr_reader)

    # 测试：解析目录中的发票
    invoices = parser.parse_invoice_directory("data/invoices")

    print(f"\n=== 发票汇总 ===")
    summary = parser.get_invoice_summary()
    print(f"总数量: {summary['total_count']}")
    print(f"有效数量: {summary['valid_count']}")
    print(f"总金额: ¥{summary['total_amount']:.2f}")
