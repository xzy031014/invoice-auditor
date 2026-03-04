"""
企业报销单智能审核助手 - 主程序
"""
import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

# 添加当前目录到路径，确保可以导入其他模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_reader import OCRReader
from invoice_parser import InvoiceParser, ReimbursementApplication
from validator import InvoiceValidator, ApplicationValidator
from reporter import AuditReporter


# 配置日志
def setup_logging(log_level: str = "INFO", log_file: str = None):
    """配置日志系统"""
    level = getattr(logging, log_level.upper(), logging.INFO)

    handlers = [logging.StreamHandler()]

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


class InvoiceAuditSystem:
    """发票审核系统主类"""

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化审核系统

        Args:
            config: 配置字典，包含系统参数
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 初始化各个模块
        self.ocr_reader = OCRReader(
            use_gpu=self.config.get('use_gpu', False)
        )
        self.parser = InvoiceParser(self.ocr_reader)
        self.invoice_validator = InvoiceValidator(
            company_name=self.config.get('company_name'),
            company_tax_id=self.config.get('company_tax_id'),
            max_amount_diff=self.config.get('max_amount_diff', 0.01),
            max_days_diff=self.config.get('max_days_diff', 30)
        )
        self.application_validator = ApplicationValidator()
        self.reporter = AuditReporter(
            output_dir=self.config.get('report_dir', 'data/reports')
        )

        self.all_invoices: List = []
        self.audit_results: List[Dict] = []

    def load_invoices(self, invoice_dir: str) -> int:
        """
        加载并解析发票

        Args:
            invoice_dir: 发票图片目录

        Returns:
            成功解析的发票数量
        """
        self.logger.info(f"开始加载发票: {invoice_dir}")
        invoices = self.parser.parse_invoice_directory(invoice_dir)
        self.all_invoices = invoices
        self.logger.info(f"成功加载 {len(invoices)} 张发票")
        return len(invoices)

    def audit_application(
        self,
        application: ReimbursementApplication,
        matched_invoices: List = None
    ) -> Dict[str, Any]:
        """
        审核单个报销申请

        Args:
            application: 报销申请单
            matched_invoices: 预先匹配的发票列表（可选）

        Returns:
            审核结果字典
        """
        self.logger.info(f"开始审核申请: {application.applicant}")

        # 如果没有预先匹配发票，则自动匹配
        if matched_invoices is None:
            matched_invoices = self.parser.match_invoices_to_application(application)

        # 验证每张发票
        invoice_validation_results = []
        for invoice in matched_invoices:
            result = self.invoice_validator.validate_invoice(invoice)
            invoice_validation_results.append(result)

            # 如果发票验证失败，直接返回失败结果
            if not result.is_valid:
                return {
                    'applicant': application.applicant,
                    'department': application.department,
                    'application_amount': application.amount,
                    'invoice_count': len(matched_invoices),
                    'total_invoice_amount': sum(inv.amount or 0 for inv in matched_invoices),
                    'amount_diff': 0,
                    'is_valid': False,
                    'error_message': f"发票验证失败: {result.error_message}",
                    'warning_message': '',
                    'audit_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'matched_invoices': matched_invoices,
                }

        # 验证申请单与发票的匹配
        app_result = self.application_validator.validate_application(
            application, matched_invoices
        )

        # 计算金额差异
        total_invoice_amount = sum(inv.amount or 0 for inv in matched_invoices)
        amount_diff = abs(total_invoice_amount - (application.amount or 0))

        # 组合警告信息
        warning_messages = []
        if app_result.warning_message:
            warning_messages.append(app_result.warning_message)
        for inv_result in invoice_validation_results:
            if inv_result.warning_message:
                warning_messages.append(inv_result.warning_message)

        result = {
            'applicant': application.applicant,
            'department': application.department,
            'application_amount': application.amount,
            'invoice_count': len(matched_invoices),
            'total_invoice_amount': total_invoice_amount,
            'amount_diff': amount_diff,
            'is_valid': app_result.is_valid,
            'error_message': app_result.error_message or '',
            'warning_message': '; '.join(warning_messages),
            'audit_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'matched_invoices': matched_invoices,
        }

        self.audit_results.append(result)
        return result

    def audit_batch_applications(
        self,
        applications: List[ReimbursementApplication]
    ) -> List[Dict]:
        """
        批量审核报销申请

        Args:
            applications: 报销申请单列表

        Returns:
            审核结果列表
        """
        self.logger.info(f"开始批量审核 {len(applications)} 个申请")

        results = []
        for app in applications:
            result = self.audit_application(app)
            results.append(result)

            # 生成并保存单个申请的报告
            if result['matched_invoices']:
                report_content = self.reporter.generate_text_report(
                    app,
                    result['matched_invoices'],
                    ValidationResult(
                        is_valid=result['is_valid'],
                        error_message=result['error_message'],
                        warning_message=result['warning_message']
                    )
                )
                report_file = f"{app.applicant}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                self.reporter.save_text_report(report_content, report_file)

        # 检查全局重复发票
        duplicates = self.application_validator.check_global_duplicates(self.all_invoices)
        if duplicates:
            self.logger.warning(f"发现全局重复发票: {'; '.join(duplicates)}")

        return results

    def generate_final_reports(self) -> Dict[str, str]:
        """
        生成最终审核报告

        Returns:
            各类报告的文件路径
        """
        self.logger.info("开始生成最终报告")

        report_paths = {}

        # 生成Excel汇总报告
        if self.audit_results:
            excel_path = self.reporter.generate_excel_report(self.audit_results)
            report_paths['excel'] = excel_path

        # 生成发票明细报告
        if self.all_invoices:
            invoice_detail_path = self.reporter.generate_invoice_detail_report(self.all_invoices)
            report_paths['invoice_detail'] = invoice_detail_path

        # 生成文本汇总报告
        if self.audit_results:
            summary = self.reporter.generate_summary_report(self.audit_results)
            summary_path = self.reporter.save_text_report(
                summary,
                f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            report_paths['summary'] = summary_path

        self.logger.info(f"报告生成完成: {report_paths}")
        return report_paths


def load_config_from_env() -> Dict[str, Any]:
    """从环境变量加载配置"""
    load_dotenv()

    config = {
        'company_name': os.getenv('COMPANY_NAME', ''),
        'company_tax_id': os.getenv('COMPANY_TAX_ID', ''),
        'invoice_dir': os.getenv('INVOICE_DIR', 'data/invoices'),
        'report_dir': os.getenv('REPORT_DIR', 'data/reports'),
        'max_amount_diff': float(os.getenv('MAX_AMOUNT_DIFF', '0.01')),
        'max_days_diff': int(os.getenv('MAX_DAYS_DIFF', '30')),
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'log_file': os.getenv('LOG_FILE', 'logs/audit.log'),
        'use_gpu': os.getenv('USE_GPU', 'false').lower() == 'true',
    }

    return config


def demo_application():
    """创建演示用的报销申请单"""
    return [
        ReimbursementApplication(
            applicant='张三',
            department='技术部',
            amount=500.00,
            apply_date='2024-06-15',
            description='团建活动餐饮费用',
            expected_invoices=2
        ),
        ReimbursementApplication(
            applicant='李四',
            department='市场部',
            amount=1200.00,
            apply_date='2024-06-10',
            description='客户招待费用',
            expected_invoices=1
        ),
    ]


def main():
    """主函数"""
    # 加载配置
    config = load_config_from_env()

    # 设置日志
    setup_logging(config['log_level'], config['log_file'])

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("企业报销单智能审核助手")
    logger.info("=" * 60)

    # 创建审核系统
    system = InvoiceAuditSystem(config)

    # 加载发票
    invoice_count = system.load_invoices(config['invoice_dir'])

    if invoice_count == 0:
        logger.warning(f"发票目录为空或没有有效发票: {config['invoice_dir']}")
        logger.info("请在发票目录中放入发票图片，然后重新运行")
        return

    # 加载报销申请单（这里使用演示数据）
    # 实际使用时可以从Excel/数据库/文件中加载
    applications = demo_application()
    logger.info(f"加载了 {len(applications)} 个报销申请单")

    # 批量审核
    results = system.audit_batch_applications(applications)

    # 输出审核结果摘要
    print("\n" + "=" * 60)
    print("【审核结果摘要】")
    print("=" * 60)
    for result in results:
        status = "✓ 通过" if result['is_valid'] else "✗ 不通过"
        print(f"{result['applicant']} ({result['department']}): {status}")
        if not result['is_valid']:
            print(f"  原因: {result['error_message']}")
        if result['warning_message']:
            print(f"  警告: {result['warning_message']}")

    # 生成报告
    report_paths = system.generate_final_reports()

    print("\n" + "=" * 60)
    print("【报告已生成】")
    print("=" * 60)
    for report_type, path in report_paths.items():
        print(f"{report_type}: {path}")

    logger.info("审核完成")


if __name__ == "__main__":
    main()
