"""
审核规则引擎 - 验证发票和报销申请的合规性
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

from invoice_parser import InvoiceInfo, ReimbursementApplication

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """审核结果数据类"""
    is_valid: bool
    error_type: Optional[str] = None
    error_message: str = ""
    warning_message: str = ""
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class InvoiceValidator:
    """发票审核器 - 验证发票的合规性"""

    def __init__(
        self,
        company_name: str = None,
        company_tax_id: str = None,
        max_amount_diff: float = 0.01,
        max_days_diff: int = 30
    ):
        self.company_name = company_name
        self.company_tax_id = company_tax_id
        self.max_amount_diff = max_amount_diff
        self.max_days_diff = max_days_diff

    def validate_invoice(self, invoice: InvoiceInfo) -> ValidationResult:
        """
        验证单个发票的基本信息

        Args:
            invoice: 发票信息

        Returns:
            ValidationResult对象
        """
        errors = []
        warnings = []

        # 检查必填字段
        if not invoice.invoice_number:
            errors.append("缺少发票号码")
        if not invoice.amount or invoice.amount <= 0:
            errors.append("发票金额无效")
        if not invoice.date:
            errors.append("缺少开票日期")

        if errors:
            return ValidationResult(
                is_valid=False,
                error_type="MISSING_INFO",
                error_message="; ".join(errors)
            )

        # 验证日期合理性
        date_result = self._validate_invoice_date(invoice)
        if not date_result.is_valid:
            return date_result

        warnings.extend(date_result.warning_message.split("; "))

        # 验证购买方抬头
        if self.company_name and invoice.buyer_name:
            buyer_result = self._validate_buyer_name(invoice)
            if not buyer_result.is_valid:
                return buyer_result
            if buyer_result.warning_message:
                warnings.append(buyer_result.warning_message)

        return ValidationResult(
            is_valid=True,
            warning_message="; ".join(warnings) if warnings else ""
        )

    def _validate_invoice_date(self, invoice: InvoiceInfo) -> ValidationResult:
        """
        验证发票日期

        Args:
            invoice: 发票信息

        Returns:
            ValidationResult对象
        """
        try:
            invoice_date = datetime.strptime(invoice.date, "%Y-%m-%d")
        except ValueError:
            return ValidationResult(
                is_valid=False,
                error_type="INVALID_DATE",
                error_message=f"发票日期格式错误: {invoice.date}"
            )

        today = datetime.now()
        max_date = today + timedelta(days=7)  # 允许稍微超前
        min_date = today - timedelta(days=self.max_days_diff * 12)  # 最多一年前

        warnings = []

        if invoice_date > max_date:
            return ValidationResult(
                is_valid=False,
                error_type="FUTURE_DATE",
                error_message=f"发票日期不能晚于当前日期: {invoice.date}"
            )

        if invoice_date < min_date:
            warnings.append(f"发票日期较早: {invoice.date}，请确认是否合理")

        return ValidationResult(
            is_valid=True,
            warning_message="; ".join(warnings) if warnings else ""
        )

    def _validate_buyer_name(self, invoice: InvoiceInfo) -> ValidationResult:
        """
        验证购买方抬头

        Args:
            invoice: 发票信息

        Returns:
            ValidationResult对象
        """
        if not invoice.buyer_name:
            return ValidationResult(
                is_valid=False,
                error_type="MISSING_BUYER",
                error_message="发票缺少购买方信息"
            )

        # 简单的相似度检查
        if self.company_name and self.company_name not in invoice.buyer_name:
            return ValidationResult(
                is_valid=False,
                error_type="BUYER_MISMATCH",
                error_message=f"发票抬头与公司名称不符: 发票抬头为'{invoice.buyer_name}'"
            )

        return ValidationResult(is_valid=True)

    def validate_amount_match(
        self,
        invoice: InvoiceInfo,
        application: ReimbursementApplication
    ) -> ValidationResult:
        """
        验证发票金额与申请单是否匹配

        Args:
            invoice: 发票信息
            application: 报销申请单

        Returns:
            ValidationResult对象
        """
        if not invoice.amount or not application.amount:
            return ValidationResult(
                is_valid=False,
                error_type="MISSING_AMOUNT",
                error_message="发票或申请单缺少金额信息"
            )

        diff = abs(invoice.amount - application.amount)

        if diff > self.max_amount_diff:
            return ValidationResult(
                is_valid=False,
                error_type="AMOUNT_MISMATCH",
                error_message=(
                    f"发票金额与申请单不符: "
                    f"发票¥{invoice.amount:.2f} vs 申请¥{application.amount:.2f}, "
                    f"差异¥{diff:.2f}"
                ),
                details={
                    'invoice_amount': invoice.amount,
                    'application_amount': application.amount,
                    'difference': diff
                }
            )

        return ValidationResult(is_valid=True)


class ApplicationValidator:
    """报销申请审核器"""

    def __init__(self):
        self.processed_invoice_numbers = set()  # 用于检测重复发票

    def validate_application(
        self,
        application: ReimbursementApplication,
        matched_invoices: List[InvoiceInfo]
    ) -> ValidationResult:
        """
        验证报销申请单与匹配的发票

        Args:
            application: 报销申请单
            matched_invoices: 匹配的发票列表

        Returns:
            ValidationResult对象
        """
        warnings = []
        errors = []

        # 检查是否匹配到发票
        if not matched_invoices:
            return ValidationResult(
                is_valid=False,
                error_type="NO_MATCHED_INVOICE",
                error_message="未找到匹配的发票"
            )

        # 检查发票数量
        if (application.expected_invoices and
            len(matched_invoices) != application.expected_invoices):
            warnings.append(
                f"发票数量与预期不符: 实际{len(matched_invoices)}张 vs 预期{application.expected_invoices}张"
            )

        # 计算发票总金额
        total_invoice_amount = sum(inv.amount or 0 for inv in matched_invoices)

        # 金额对比
        if application.amount:
            amount_diff = abs(total_invoice_amount - application.amount)
            if amount_diff > 0.01:
                errors.append(
                    f"发票总金额与申请单不符: "
                    f"发票总计¥{total_invoice_amount:.2f} vs 申请¥{application.amount:.2f}"
                )

        # 检查日期逻辑
        if application.apply_date:
            try:
                apply_date = datetime.strptime(application.apply_date, "%Y-%m-%d")
                for invoice in matched_invoices:
                    if invoice.date:
                        invoice_date = datetime.strptime(invoice.date, "%Y-%m-%d")
                        if invoice_date > apply_date + timedelta(days=7):
                            warnings.append(
                                f"发票日期晚于申请日期: {invoice.file_name}"
                            )
            except ValueError:
                pass

        # 检查重复发票
        duplicate_result = self._check_duplicate_invoices(matched_invoices)
        if duplicate_result.error_message:
            errors.append(duplicate_result.error_message)

        if errors:
            return ValidationResult(
                is_valid=False,
                error_type="VALIDATION_FAILED",
                error_message="; ".join(errors)
            )

        return ValidationResult(
            is_valid=True,
            warning_message="; ".join(warnings) if warnings else "",
            details={
                'matched_invoice_count': len(matched_invoices),
                'total_amount': total_invoice_amount
            }
        )

    def _check_duplicate_invoices(
        self,
        invoices: List[InvoiceInfo]
    ) -> ValidationResult:
        """
        检查是否有重复发票

        Args:
            invoices: 发票列表

        Returns:
            ValidationResult对象
        """
        duplicates = []
        seen = {}

        for invoice in invoices:
            if invoice.invoice_number:
                if invoice.invoice_number in seen:
                    duplicates.append(
                        f"发票号 {invoice.invoice_number} 重复 "
                        f"({seen[invoice.invoice_number]} vs {invoice.file_name})"
                    )
                else:
                    seen[invoice.invoice_number] = invoice.file_name

        if duplicates:
            return ValidationResult(
                is_valid=False,
                error_type="DUPLICATE_INVOICE",
                error_message="; ".join(duplicates)
            )

        return ValidationResult(is_valid=True)

    def check_global_duplicates(self, all_invoices: List[InvoiceInfo]) -> List[str]:
        """
        检查全局重复发票（跨申请单）

        Args:
            all_invoices: 所有发票列表

        Returns:
            重复发票信息列表
        """
        invoice_map = {}
        duplicates = []

        for invoice in all_invoices:
            if invoice.invoice_number:
                if invoice.invoice_number in invoice_map:
                    duplicates.append(
                        f"发票号 {invoice.invoice_number} 在多个申请中出现"
                    )
                else:
                    invoice_map[invoice.invoice_number] = invoice.file_name

        return duplicates


# 测试代码
if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建审核器
    validator = InvoiceValidator(company_name="示例科技有限公司")

    # 测试发票
    test_invoice = InvoiceInfo(
        file_name="test.jpg",
        invoice_number="12345678",
        amount=100.50,
        date="2024-01-15",
        seller_name="XX公司",
        buyer_name="示例科技有限公司分公司"
    )

    result = validator.validate_invoice(test_invoice)
    print(f"\n=== 审核结果 ===")
    print(f"是否通过: {result.is_valid}")
    if result.error_message:
        print(f"错误: {result.error_message}")
    if result.warning_message:
        print(f"警告: {result.warning_message}")
