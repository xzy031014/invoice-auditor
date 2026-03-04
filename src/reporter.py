"""
报告生成器 - 生成审核报告
"""
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import pandas as pd
import logging

from invoice_parser import InvoiceInfo, ReimbursementApplication
from validator import ValidationResult

logger = logging.getLogger(__name__)


class AuditReporter:
    """审核报告生成器"""

    def __init__(self, output_dir: str = "data/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_text_report(
        self,
        application: ReimbursementApplication,
        matched_invoices: List[InvoiceInfo],
        validation_result: ValidationResult
    ) -> str:
        """
        生成文本格式的审核报告

        Args:
            application: 报销申请单
            matched_invoices: 匹配的发票列表
            validation_result: 审核结果

        Returns:
            文本报告内容
        """
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("报销审核报告")
        report_lines.append("=" * 60)
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")

        # 申请单信息
        report_lines.append("【报销申请信息】")
        report_lines.append(f"申请人: {application.applicant}")
        report_lines.append(f"部门: {application.department}")
        report_lines.append(f"申请金额: ¥{application.amount or 0:.2f}")
        report_lines.append(f"申请日期: {application.apply_date or '未填写'}")
        report_lines.append(f"报销说明: {application.description or '无'}")
        report_lines.append("")

        # 发票信息
        report_lines.append("【发票明细】")
        total_amount = 0
        for i, invoice in enumerate(matched_invoices, 1):
            report_lines.append(f"{i}. {invoice.file_name}")
            report_lines.append(f"   发票号码: {invoice.invoice_number or '未识别'}")
            report_lines.append(f"   发票金额: ¥{invoice.amount or 0:.2f}")
            report_lines.append(f"   开票日期: {invoice.date or '未识别'}")
            report_lines.append(f"   销售方: {invoice.seller_name or '未识别'}")
            total_amount += invoice.amount or 0
            report_lines.append("")

        report_lines.append(f"发票总计: ¥{total_amount:.2f}")
        report_lines.append("")

        # 审核结果
        report_lines.append("【审核结果】")
        if validation_result.is_valid:
            report_lines.append("✓ 审核通过")
        else:
            report_lines.append("✗ 审核不通过")

        if validation_result.error_message:
            report_lines.append(f"错误: {validation_result.error_message}")

        if validation_result.warning_message:
            report_lines.append(f"警告: {validation_result.warning_message}")

        report_lines.append("")
        report_lines.append("=" * 60)

        return "\n".join(report_lines)

    def generate_excel_report(
        self,
        audit_results: List[Dict[str, Any]],
        filename: str = None
    ) -> str:
        """
        生成Excel格式的审核报告

        Args:
            audit_results: 审核结果列表
            filename: 输出文件名

        Returns:
            生成的文件路径
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"audit_report_{timestamp}.xlsx"

        output_path = self.output_dir / filename

        # 准备数据
        data = []
        for result in audit_results:
            row = {
                '申请人': result.get('applicant', ''),
                '部门': result.get('department', ''),
                '申请金额': result.get('application_amount', 0),
                '发票数量': result.get('invoice_count', 0),
                '发票总金额': result.get('total_invoice_amount', 0),
                '金额差异': result.get('amount_diff', 0),
                '审核状态': '通过' if result.get('is_valid') else '不通过',
                '错误信息': result.get('error_message', ''),
                '警告信息': result.get('warning_message', ''),
                '审核时间': result.get('audit_time', ''),
            }
            data.append(row)

        # 创建DataFrame
        df = pd.DataFrame(data)

        # 写入Excel
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # 汇总表
            df.to_excel(writer, sheet_name='审核汇总', index=False)

            # 统计表
            stats_data = {
                '统计项': ['总申请数', '审核通过', '审核不通过', '通过率'],
                '数值': [
                    len(data),
                    sum(1 for r in data if r['审核状态'] == '通过'),
                    sum(1 for r in data if r['审核状态'] == '不通过'),
                    f"{sum(1 for r in data if r['审核状态'] == '通过') / len(data) * 100:.1f}%"
                    if data else '0%'
                ]
            }
            stats_df = pd.DataFrame(stats_data)
            stats_df.to_excel(writer, sheet_name='统计', index=False)

        logger.info(f"Excel报告已生成: {output_path}")
        return str(output_path)

    def generate_invoice_detail_report(
        self,
        all_invoices: List[InvoiceInfo],
        filename: str = None
    ) -> str:
        """
        生成发票明细Excel报告

        Args:
            all_invoices: 所有发票列表
            filename: 输出文件名

        Returns:
            生成的文件路径
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"invoice_detail_{timestamp}.xlsx"

        output_path = self.output_dir / filename

        # 准备数据
        data = []
        for invoice in all_invoices:
            row = {
                '文件名': invoice.file_name,
                '发票号码': invoice.invoice_number or '',
                '发票金额': invoice.amount or 0,
                '开票日期': invoice.date or '',
                '销售方': invoice.seller_name or '',
                '购买方': invoice.buyer_name or '',
                '是否有效': '是' if invoice.is_valid() else '否',
            }
            data.append(row)

        # 创建DataFrame并导出
        df = pd.DataFrame(data)
        df.to_excel(output_path, index=False, engine='openpyxl')

        logger.info(f"发票明细报告已生成: {output_path}")
        return str(output_path)

    def save_text_report(
        self,
        content: str,
        filename: str = None
    ) -> str:
        """
        保存文本报告到文件

        Args:
            content: 报告内容
            filename: 文件名

        Returns:
            保存的文件路径
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"audit_report_{timestamp}.txt"

        output_path = self.output_dir / filename

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"文本报告已保存: {output_path}")
        return str(output_path)

    def generate_summary_report(
        self,
        audit_results: List[Dict[str, Any]]
    ) -> str:
        """
        生成汇总报告文本

        Args:
            audit_results: 审核结果列表

        Returns:
            汇总报告内容
        """
        lines = []
        lines.append("=" * 60)
        lines.append("报销审核汇总报告")
        lines.append("=" * 60)
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 统计
        total = len(audit_results)
        passed = sum(1 for r in audit_results if r.get('is_valid'))
        failed = total - passed

        lines.append("【总体统计】")
        lines.append(f"总申请数: {total}")
        lines.append(f"审核通过: {passed}")
        lines.append(f"审核不通过: {failed}")
        if total > 0:
            lines.append(f"通过率: {passed / total * 100:.1f}%")
        lines.append("")

        # 金额统计
        total_applied = sum(r.get('application_amount', 0) for r in audit_results)
        total_invoiced = sum(r.get('total_invoice_amount', 0) for r in audit_results)

        lines.append("【金额统计】")
        lines.append(f"申请总金额: ¥{total_applied:.2f}")
        lines.append(f"发票总金额: ¥{total_invoiced:.2f}")
        lines.append(f"金额差异: ¥{abs(total_applied - total_invoiced):.2f}")
        lines.append("")

        # 不通过的详情
        if failed > 0:
            lines.append("【不通过申请详情】")
            for result in audit_results:
                if not result.get('is_valid'):
                    lines.append(f"- {result.get('applicant', '未知')}: {result.get('error_message', '')}")
            lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)


# 测试代码
if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建报告生成器
    reporter = AuditReporter()

    # 测试汇总报告
    test_results = [
        {
            'applicant': '张三',
            'department': '技术部',
            'application_amount': 500.0,
            'invoice_count': 2,
            'total_invoice_amount': 500.0,
            'amount_diff': 0,
            'is_valid': True,
            'audit_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'applicant': '李四',
            'department': '市场部',
            'application_amount': 300.0,
            'invoice_count': 1,
            'total_invoice_amount': 250.0,
            'amount_diff': 50,
            'is_valid': False,
            'error_message': '发票金额与申请单不符',
            'audit_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    ]

    summary = reporter.generate_summary_report(test_results)
    print(summary)
