"""
HyperBrowser 安装配置
"""

from setuptools import setup, find_packages

setup(
    name="hyperbrowser",
    version="2.0.0",
    description="高效反检测浏览器自动化框架，面向 AI Agent",
    author="HyperBrowser Team",
    packages=find_packages(),
    install_requires=[
        "patchright>=1.0.0",
        "playwright>=1.40.0",
        "openai>=1.0.0",
        "pydantic>=2.0.0",
        "mcp>=1.0.0,<2.0.0",
    ],
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
