"""
Flask Web 应用 - 企业报销单智能审核助手
"""
import os
import sys
import tempfile
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file

sys.path.insert(0, 'src')
from ocr_reader import OCRReader
from invoice_parser import ReimbursementApplication

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# 初始化OCR
ocr_reader = OCRReader()

# 数据存储
invoices = []
applications = []


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/invoices', methods=['GET'])
def get_invoices():
    return jsonify(invoices)


@app.route('/api/upload', methods=['POST'])
def upload_invoice():
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
            tmp_path = tmp.name
            file.save(tmp_path)
            result = ocr_reader.parse_invoice(tmp_path)
            result['id'] = len(invoices) + 1
            result['upload_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            result['original_filename'] = file.filename
            invoices.append(result)
            return jsonify({'success': True, 'invoice': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/submit', methods=['POST'])
def submit_application():
    data = request.json

    try:
        app = ReimbursementApplication(
            applicant=data.get('applicant', ''),
            department=data.get('department', ''),
            amount=float(data.get('amount', 0)),
            apply_date=data.get('date', datetime.now().strftime('%Y-%m-%d')),
            description=data.get('description', ''),
            expected_invoices=0
        )

        # 关联所有发票
        app.selected_invoices = invoices.copy()

        # 计算审核
        total = sum(inv.get('amount', 0) for inv in invoices)
        app.audit_result = {
            'total_invoice': total,
            'diff': abs(total - app.amount),
            'passed': abs(total - app.amount) < 0.01
        }

        app.id = len(applications) + 1
        applications.append(app)

        return jsonify({'success': True, 'result': {
            'id': app.id,
            'applicant': app.applicant,
            'amount': app.amount,
            'total_invoice': total,
            'diff': app.audit_result['diff'],
            'passed': app.audit_result['passed']
        }})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/clear', methods=['POST'])
def clear_data():
    global invoices, applications
    invoices = []
    applications = []
    return jsonify({'success': True})


if __name__ == '__main__':
    print("=" * 50)
    print("企业报销单智能审核助手")
    print("=" * 50)
    print("访问地址: http://localhost:5000")
    print("=" * 50)
    app.run(debug=False, host='127.0.0.1', port=5000)
