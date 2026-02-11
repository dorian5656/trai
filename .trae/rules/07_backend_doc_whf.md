# TRAI 文档更新规范
> **后端规则**: 适用于所有后端开发人员.

## 1. 更新流程
- **模块优先**: 先更 `backend/README.md`, `frontend/README.md` 或 `backend/pyqt_app/README.md`.
- **聚合同步**: 再将日志同步至根目录 `README.md`, 并采用 `Emoji 模块_时间戳` 格式.
  - 后端: `🛠️ 后端_YYYY_MM_DD_HHMM`
  - 前端: `🎨 前端_YYYY_MM_DD_HHMM`
  - 客户端: `💻 客户端_YYYY_MM_DD_HHMM`

## 2. 格式规范
- **位置**: 必须插入到文档末尾的 `## 📝 更新日志 (Changelog)` 章节下，禁止破坏文档顶部标题结构。
- **时间戳**: 三级标题 `### Emoji 模块_YYYY_MM_DD_HHMM` (倒序排列，最新的在最上面).
- **严禁预估**: 必须使用命令获取系统精准时间.
- **分类**: `后端-内容`, `前端-内容`, `数据库-内容`.
- **命令**: `python -c "import datetime; print(datetime.datetime.now().strftime('%Y_%m_%d_%H%M'))"`
