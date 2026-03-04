# Python 安装指南

## 方式一：从官网安装（推荐）

1. 访问 Python 官网：https://www.python.org/downloads/

2. 下载 Python 3.10 或 3.11 版本（Windows installer）

3. 安装时**务必勾选**：
   - ✅ Add Python to PATH（非常重要！）

4. 安装完成后，重启命令行窗口

5. 验证安装：
   ```bash
   python --version
   pip --version
   ```

---

## 方式二：使用 Windows Store

1. 打开 Microsoft Store
2. 搜索 "Python 3.11" 或 "Python 3.10"
3. 点击安装

---

## 安装完Python后，继续安装项目依赖

```bash
cd C:\Users\x'z'y\invoice-auditor
pip install -r requirements.txt
```

如果下载慢，可以使用国内镜像：
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```
