"""
企业报销单智能审核助手 - 演示版本
不需要安装任何依赖，可以直接运行查看效果
"""
import json
import os
from pathlib import Path
from datetime import datetime


# ==================== 数据类 ====================

class InvoiceInfo:
    """发票信息"""
    def __init__(self, file_name, invoice_number, amount, date, seller_name, buyer_name):
        self.file_name = file_name
        self.invoice_number = invoice_number
        self.amount = amount
        self.date = date
        self.seller_name = seller_name
        self.buyer_name = buyer_name

    def is_valid(self):
        return all([
            self.invoice_number,
            self.amount and self.amount > 0,
            self.date
        ])

    def to_dict(self):
        return {
            'file_name': self.file_name,
            'invoice_number': self.invoice_number,
            'amount': self.amount,
            'date': self.date,
            'seller_name': self.seller_name,
            'buyer_name': self.buyer_name,
        }


class ReimbursementApplication:
    """报销申请单"""
    def __init__(self, applicant, department, amount, apply_date, description, expected_invoices=1):
        self.applicant = applicant
        self.department = department
        self.amount = amount
        self.apply_date = apply_date
        self.description = description
        self.expected_invoices = expected_invoices

    def to_dict(self):
        return {
            'applicant': self.applicant,
            'department': self.department,
            'amount': self.amount,
            'apply_date': self.apply_date,
            'description': self.description,
            'expected_invoices': self.expected_invoices,
        }


# ==================== 模拟OCR识别 ====================

def simulate_ocr_recognition(image_files):
    """
    模拟OCR识别发票
    实际项目中会使用 PaddleOCR 进行真实识别
    """
    print("\n" + "="*50)
    print("📷 OCR识别中...")
    print("="*50)

    # 模拟识别结果
    mock_results = {
        'invoice001.jpg': InvoiceInfo(
            file_name='invoice001.jpg',
            invoice_number='12345678',
            amount=268.50,
            date='2024-06-15',
            seller_name='海底捞火锅店',
            buyer_name='示例科技有限公司'
        ),
        'invoice002.jpg': InvoiceInfo(
            file_name='invoice002.jpg',
            invoice_number='87654321',
            amount=231.50,
            date='2024-06-14',
            seller_name='滴滴出行科技有限公司',
            buyer_name='示例科技有限公司'
        ),
        'invoice003.jpg': InvoiceInfo(
            file_name='invoice003.jpg',
            invoice_number='11112222',
            amount=1200.00,
            date='2024-06-10',
            seller_name='如家酒店集团',
            buyer_name='示例科技有限公司分公司'  # 抬头略有不同
        ),
    }

    invoices = []
    for filename in image_files:
        if filename in mock_results:
            invoice = mock_results[filename]
            invoices.append(invoice)
            print(f"✓ {filename}: ¥{invoice.amount} - {invoice.seller_name}")
        else:
            print(f"✗ {filename}: 识别失败（演示数据中不存在）")

    return invoices


# ==================== 审核规则引擎 ====================

class InvoiceValidator:
    """发票审核器"""

    def __init__(self, company_name="示例科技有限公司"):
        self.company_name = company_name
        self.processed_invoice_numbers = set()

    def validate_invoice(self, invoice):
        """验证单个发票"""
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
            return {'valid': False, 'errors': errors, 'warnings': warnings}

        # 检查重复发票
        if invoice.invoice_number in self.processed_invoice_numbers:
            errors.append(f"发票号重复: {invoice.invoice_number}")
        else:
            self.processed_invoice_numbers.add(invoice.invoice_number)

        # 检查购买方抬头
        if invoice.buyer_name and self.company_name not in invoice.buyer_name:
            warnings.append(f"发票抬头可能不匹配: '{invoice.buyer_name}'")

        # 检查日期
        try:
            invoice_date = datetime.strptime(invoice.date, "%Y-%m-%d")
            today = datetime.now()
            if invoice_date > today:
                errors.append(f"发票日期不能晚于今天: {invoice.date}")
        except ValueError:
            errors.append(f"发票日期格式错误: {invoice.date}")

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }


class ApplicationValidator:
    """报销申请审核器"""

    def validate_application(self, application, matched_invoices):
        """验证报销申请与发票的匹配"""
        errors = []
        warnings = []

        if not matched_invoices:
            errors.append("未找到匹配的发票")
            return {'valid': False, 'errors': errors, 'warnings': warnings}

        # 检查发票数量
        if application.expected_invoices and len(matched_invoices) != application.expected_invoices:
            warnings.append(
                f"发票数量与预期不符: 实际{len(matched_invoices)}张 vs 预期{application.expected_invoices}张"
            )

        # 计算发票总金额
        total_invoice_amount = sum(inv.amount for inv in matched_invoices)

        # 金额对比
        if application.amount:
            amount_diff = abs(total_invoice_amount - application.amount)
            if amount_diff > 0.01:
                errors.append(
                    f"发票总金额与申请单不符: "
                    f"发票总计¥{total_invoice_amount:.2f} vs 申请¥{application.amount:.2f}"
                )

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'total_invoice_amount': total_invoice_amount
        }


# ==================== 报告生成器 ====================

class AuditReporter:
    """审核报告生成器"""

    def __init__(self, output_dir="data/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(self, application, matched_invoices, validation_result):
        """生成文本报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("报销审核报告")
        lines.append("=" * 60)
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 申请单信息
        lines.append("【报销申请信息】")
        lines.append(f"申请人: {application.applicant}")
        lines.append(f"部门: {application.department}")
        lines.append(f"申请金额: ¥{application.amount:.2f}")
        lines.append(f"报销说明: {application.description}")
        lines.append("")

        # 发票信息
        lines.append("【发票明细】")
        for i, invoice in enumerate(matched_invoices, 1):
            lines.append(f"{i}. {invoice.file_name}")
            lines.append(f"   发票号: {invoice.invoice_number}")
            lines.append(f"   金额: ¥{invoice.amount:.2f}")
            lines.append(f"   日期: {invoice.date}")
            lines.append(f"   销售方: {invoice.seller_name}")

        total_amount = sum(inv.amount for inv in matched_invoices)
        lines.append(f"\n发票总计: ¥{total_amount:.2f}")
        lines.append("")

        # 审核结果
        lines.append("【审核结果】")
        if validation_result['valid']:
            lines.append("✓ 审核通过")
        else:
            lines.append("✗ 审核不通过")

        if validation_result['errors']:
            lines.append(f"错误: {'; '.join(validation_result['errors'])}")

        if validation_result['warnings']:
            lines.append(f"警告: {'; '.join(validation_result['warnings'])}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def save_report(self, content, filename):
        """保存报告到文件"""
        output_path = self.output_dir / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"📄 报告已保存: {output_path}")
        return str(output_path)

    def print_summary(self, results):
        """打印汇总信息"""
        print("\n" + "=" * 60)
        print("📊 审核汇总")
        print("=" * 60)

        total = len(results)
        passed = sum(1 for r in results if r['valid'])

        print(f"总申请数: {total}")
        print(f"审核通过: {passed}")
        print(f"审核不通过: {total - passed}")
        if total > 0:
            print(f"通过率: {passed / total * 100:.1f}%")
        print("")


# ==================== 主程序 ====================

def main():
    """主程序"""
    import sys
    import io

    # 设置UTF-8编码输出
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("\n" + "="*60)
    print("企业报销单智能审核助手 - 演示版")
    print("="*60)
    print("注意：这是演示版本，使用模拟数据")
    print("     实际使用需要安装 Python 和 PaddleOCR")
    print("="*60)

    # 创建审核器
    invoice_validator = InvoiceValidator(company_name="示例科技有限公司")
    application_validator = ApplicationValidator()
    reporter = AuditReporter()

    # 模拟发票图片文件
    invoice_files = ['invoice001.jpg', 'invoice002.jpg', 'invoice003.jpg']

    # 步骤1: OCR识别
    print("\n[OCR识别] 开始识别发票...")
    invoices = simulate_ocr_recognition(invoice_files)

    # 报销申请单
    applications = [
        ReimbursementApplication(
            applicant='张三',
            department='技术部',
            amount=500.00,
            apply_date='2024-06-15',
            description='团队建设餐饮费用',
            expected_invoices=2
        ),
        ReimbursementApplication(
            applicant='李四',
            department='市场部',
            amount=1200.00,
            apply_date='2024-06-10',
            description='客户拜访住宿费用',
            expected_invoices=1
        ),
        ReimbursementApplication(
            applicant='王五',
            department='销售部',
            amount=800.00,
            apply_date='2024-06-12',
            description='差旅交通费用',
            expected_invoices=1
        ),
    ]

    # 步骤2: 逐一审核
    print("\n" + "="*60)
    print("🔍 开始审核报销申请...")
    print("="*60)

    all_results = []

    for app in applications:
        print(f"\n--- 审核: {app.applicant} ({app.department}) ---")

        # 简单匹配：按金额匹配发票
        matched_invoices = []
        remaining_amount = app.amount or 0

        for inv in invoices:
            if inv.amount and inv.amount <= remaining_amount * 1.1:
                matched_invoices.append(inv)
                remaining_amount -= inv.amount

        # 验证发票
        invoice_valid = True
        for inv in matched_invoices:
            result = invoice_validator.validate_invoice(inv)
            if not result['valid']:
                invoice_valid = False
                print(f"  ✗ 发票验证失败: {', '.join(result['errors'])}")
            if result['warnings']:
                print(f"  ⚠ 发票警告: {', '.join(result['warnings'])}")

        # 验证申请单
        app_result = application_validator.validate_application(app, matched_invoices)

        # 综合结果
        is_valid = invoice_valid and app_result['valid']

        print(f"\n  状态: {'[通过] 审核通过' if is_valid else '[失败] 审核不通过'}")
        if app_result['errors']:
            print(f"  错误: {', '.join(app_result['errors'])}")
        if app_result['warnings']:
            print(f"  警告: {', '.join(app_result['warnings'])}")

        # 生成报告
        report_content = reporter.generate_report(
            app,
            matched_invoices,
            {'valid': is_valid, 'errors': app_result['errors'], 'warnings': app_result['warnings']}
        )

        filename = f"{app.applicant}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        reporter.save_report(report_content, filename)

        all_results.append({
            'applicant': app.applicant,
            'valid': is_valid,
            'errors': app_result['errors'],
            'warnings': app_result['warnings']
        })

        # 从总池中移除已使用的发票
        for inv in matched_invoices:
            if inv in invoices:
                invoices.remove(inv)

    # 步骤3: 输出汇总
    reporter.print_summary(all_results)

    # 步骤4: 检查未匹配的发票
    if invoices:
        print("\n[警告] 以下发票未被匹配到任何申请:")
        for inv in invoices:
            print(f"  - {inv.file_name}: ¥{inv.amount} ({inv.invoice_number})")

    print("\n" + "="*60)
    print("[完成] 审核完成！")
    print(f"[报告] 报告保存在: {reporter.output_dir}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
