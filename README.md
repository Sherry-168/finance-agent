# 金融代理 (Finance Agent)

一个由人工智能驱动的个人理财助理。本仓库为 2026 GDUF AI Studio 二轮考核项目。

## 1. 项目说明 (Project Description)
*   **做了什么**：本项目实现了一个智能记账助手，用户可通过自然语言或上传账单截图，快速完成记账。
*   **面向场景**：解决传统手动记账繁琐、分类困难的问题。用户只需输入“打车25元”或上传一张淘宝/外卖截图，系统即可自动提取金额、类别并存入数据库，便于后续的消费统计与预算管理。

## 2. 技术栈与架构简述 (Brief description of technical line and architecture)
*   **前端**：Gradio（界面搭建、图表展示）
*   **后端**：FastAPI（接口开发）、SQLite（数据库存储）
*   **AI 核心**：Dify 工作流 (Workflow) + DeepSeek 多模态视觉大模型
*   **部署**：Docker

## 3. AI 核心模块说明 (Description of AI core module)

本项目核心 AI 驱动层采用 Dify 工作流搭建，接入 DeepSeek 多模态视觉大模型。

### 核心功能 (Core Functions0
*   **自然语言输入**：支持直接输入一句话（如“打车花了25块”），AI 自动提取结构化数据。
*   **多模态图片识别**：支持上传购物小票、外卖订单、淘宝账单截图，AI 直接读取图片内容。
*   **多笔账单拆分**：遇到包含多笔消费的长截图，AI 可精准拆分为 JSON 数组（Array）形式输出。
*   **结构化输出 (JSON)**：通过严格的 Prompt 约束，强制可视化大。
模型输出标准的 JSON 格式，方便后端直接解析入库。

### 数据输出*示例（多笔图片识别）
```json
[
{
"amount": 16.01,
"category": "购物",
"description": "meiji明治雪吻夹心巧克力29g*2盒",
"date": "11-10"
},
{
"amount": 159,
"category": "购物",
"description": "RK R75Pro客制化无线机械键盘",
"date": "11-10"
}
]
```
<img width="1179" height="1668" alt="c0e7f6b4fabecbb03a490e632c761b8c" src="https://github.com/user-attachments/assets/25fa4848-c4b3-4b04-b321-94ce56d8fcf7" />


