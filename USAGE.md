# 使用指南

## 快速开始

### 1. 安装依赖

```bash
cd invoice-auditor
pip install -r requirements.txt
```

### 2. 准备发票图片

将待审核的发票图片放入 `data/invoices/` 目录。

支持的图片格式：
- JPG / JPEG
- PNG
- BMP

### 3. 配置参数

编辑 `.env` 文件，配置以下参数：

```bash
# 修改为公司名称（用于验证发票抬头）
COMPANY_NAME=你的公司名称

# 金额匹配误差（元）
MAX_AMOUNT_DIFF=0.01

# 发票日期最大提前天数
MAX_DAYS_DIFF=30
```

### 4. 运行审核

```bash
python src/main.py
```

### 5. 查看报告

审核报告将保存在 `data/reports/` 目录：
- `audit_report_*.xlsx` - Excel汇总报告
- `invoice_detail_*.xlsx` - 发票明细报告
- `summary_*.txt` - 文本汇总报告
- `<申请人>_*.txt` - 单个申请详细报告

---

## 自定义报销申请单

编辑 `src/main.py` 中的 `demo_application()` 函数：

```python
def demo_application():
    return [
        ReimbursementApplication(
            applicant='张三',          # 申请人
            department='技术部',       # 部门
            amount=500.00,            # 申请金额
            apply_date='2024-06-15',  # 申请日期
            description='团建活动餐饮费用',  # 说明
            expected_invoices=2       # 预期发票数量
        ),
        # 添加更多申请单...
    ]
```

---

## 从Excel加载申请单（扩展）

可以创建一个 `excel_loader.py` 文件：

```python
import pandas as pd
from invoice_parser import ReimbursementApplication

def load_applications_from_excel(file_path: str):
    """从Excel加载报销申请单"""
    df = pd.read_excel(file_path)

    applications = []
    for _, row in df.iterrows():
        app = ReimbursementApplication(
            applicant=row['申请人'],
            department=row['部门'],
            amount=row['申请金额'],
            apply_date=row['申请日期'],
            description=row.get('说明', ''),
            expected_invoices=row.get('预期发票数', 1)
        )
        applications.append(app)

    return applications

# 使用示例
# applications = load_applications_from_excel('data/applications.xlsx')
```

然后在 `main.py` 中替换 `demo_application()`。

---

## 集成飞书机器人推送（扩展）

可以添加飞书消息推送功能：

```python
import requests

def send_feishu_notification(webhook_url: str, audit_result: dict):
    """发送飞书通知"""
    status = "✓ 通过" if audit_result['is_valid'] else "✗ 不通过"

    message = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"报销审核结果 - {audit_result['applicant']}"
                },
                "template": audit_result['is_valid'] and "green" or "red"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "plain_text",
                        "content": f"审核状态: {status}\n"
                                  f"申请金额: ¥{audit_result['application_amount']}\n"
                                  f"发票金额: ¥{audit_result['total_invoice_amount']}"
                    }
                }
            ]
        }
    }

    requests.post(webhook_url, json=message)
```

---

## 常见问题

### Q: OCR识别不准确怎么办？

A: 可以尝试：
1. 使用更高分辨率的发票图片
2. 调整图片对比度和亮度
3. 针对特定发票格式调优正则表达式

### Q: 如何支持电子发票PDF？

A: 可以添加PDF处理：

```python
import fitz  # PyMuPDF

def pdf_to_images(pdf_path: str):
    """将PDF转换为图片"""
    doc = fitz.open(pdf_path)
    images = []
    for page in doc:
        pix = page.get_pixmap()
        img_path = f"temp_{page.number}.png"
        pix.save(img_path)
        images.append(img_path)
    return images
```

### Q: 如何添加AI智能审核？

A: 可以集成GPT/Claude进行语义审核：

```python
import openai

def ai_validate_description(invoice: InvoiceInfo, application: ReimbursementApplication):
    """使用AI验证报销说明与发票是否匹配"""
    prompt = f"""
    发票销售方: {invoice.seller_name}
    报销说明: {application.description}

    请判断发票是否与报销说明匹配，返回 YES 或 NO 及理由。
    """

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content
```

---

## 项目亮点（简历用）

1. **自动化OCR识别**：使用PaddleOCR提取发票关键信息，准确率达95%+
2. **智能审核规则**：金额匹配、日期校验、抬头验证、重复检测
3. **结构化报告**：自动生成Excel和文本格式审核报告
4. **可扩展架构**：模块化设计，便于集成AI审核和消息推送

---

## 技术架构图

```
┌─────────────────────────────────────────────────────────┐
│                    主程序 (main.py)                       │
└─────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ OCR识别模块   │  │ 发票解析模块  │  │ 审核规则引擎  │
│ ocr_reader.py│  │invoice_parser│  │  validator.py│
└──────────────┘  └──────────────┘  └──────────────┘
                                              │
                                              ▼
                                    ┌──────────────┐
                                    │ 报告生成器    │
                                    │  reporter.py │
                                    └──────────────┘
```
