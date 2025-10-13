# 使用官方 Python 镜像作为基础
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码到工作目录
COPY . .

# 暴露 Streamlit 默认端口
EXPOSE 8501

# 设置容器启动时执行的命令
CMD ["streamlit", "run", "gui.py", "--server.address=0.0.0.0"]
