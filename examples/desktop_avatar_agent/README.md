# Desktop Avatar Agent Example

这个示例使用 `agentorch` 搭建一个本地桌面数字人智能体后端，面向三类能力：

- 实时对话承接
- Windows 桌面整理
- 编程与文件工作辅助

## 能力结构

- `agent_service.py`
  - 组装 `agentorch.create_agent(...)`
  - 注册内置工具包与桌面整理工具
- `desktop_tools.py`
  - 提供桌面扫描、整理预览、创建文件夹、移动文件等工具
- `server.py`
  - 提供本地 HTTP 接口给 Electron 或网页前端调用

## 接口

- `GET /health`
- `POST /chat`

请求示例：

```json
{
  "thread_id": "desktop-goblin-main",
  "message": "帮我看看桌面上哪些文件适合整理到 Documents 文件夹"
}
```

## 本地运行

推荐使用 Python 3.13 或更高版本：

```powershell
cd C:\Users\24260\Desktop\研究生生涯\智能体开发范式
py -3.13 -m pip install -e .
py -3.13 .\examples\desktop_avatar_agent\server.py
```

## 说明

- 默认桌面根目录是 `C:\Users\<用户名>\Desktop`
- 默认工作区根目录也指向桌面，所以智能体可以辅助处理桌面上的代码与文件
- 桌面整理工具默认不做删除，只做预览、建文件夹和移动
- 对于批量移动，系统提示词要求先预览并请求确认
