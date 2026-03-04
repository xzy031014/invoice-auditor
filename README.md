# 企业报销单智能审核助手

一个基于OCR和AI的企业发票自动化审核工具，实现发票信息提取、智能匹配和异常检测。

## 功能特性

- **自动识别发票**：使用PaddleOCR提取发票金额、日期、抬头等关键信息
- **智能匹配**：将发票与报销申请单自动匹配，计算差异
- **异常检测**：自动发现金额不符、日期异常、抬头错误等问题
- **审核报告**：生成结构化审核报告，支持Excel导出

## 项目结构

```
invoice-auditor/
├── src/
│   ├── ocr_reader.py      # OCR识别模块
│   ├── invoice_parser.py   # 发票信息解析
│   ├── validator.py        # 审核规则引擎
│   ├── reporter.py         # 报告生成器
│   └── main.py            # 主程序入口
├── data/
│   ├── invoices/          # 发票图片目录
│   └── reports/           # 审核报告输出目录
├── logs/                  # 日志文件
├── requirements.txt       # 依赖包
├── .env.example          # 环境变量模板
└── README.md             # 项目说明
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境

```bash
cp .env.example .env
# 编辑 .env 文件，配置相关参数
```

### 3. 运行审核

```bash
python src/main.py
```

## 技术栈

- **OCR引擎**：PaddleOCR - 百度开源的OCR工具库
- **数据处理**：pandas, openpyxl
- **日期处理**：python-dateutil
- **日志**：logging

## 审核规则

1. **金额匹配**：发票金额与申请单金额误差不超过0.01元
2. **日期校验**：发票日期不能晚于当前日期，不能早于报销申请日期
3. **抬头校验**：发票抬头需与公司名称一致
4. **重复检测**：检测是否存在重复报销的发票

## 作者

开发于2024年，用于提升企业报销审核效率

## 许可证

MIT License
