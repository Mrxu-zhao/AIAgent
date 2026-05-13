# Agents 团队成员

## 目录结构
每个 Agent 包含：
- `SOUL.md` - Agent 灵魂定义
- `config.yaml` - 配置文件
- `knowledge/` - 领域知识库

## 角色知识标准入口
每个角色的 `knowledge/` 目录建议优先从以下入口读取：
- `README.md` - 知识索引与历史专题文件清单
- `overview.md` - 角色边界与输入输出
- `playbooks/` - 高频任务打法与排障手册
- `patterns/` - 推荐模式与反模式
- `checklists/` - 设计与交付检查项
- `pitfalls/` - 常见错误
- `templates/` - 标准输出模板
- `examples/` - 优秀示例方向

## 成员列表

| Agent | 角色 | 知识库 |
|-------|------|--------|
| architect | 系统架构师 | 架构模式、微服务、华为云 |
| backend-dev | 后端开发 | SpringBoot、MySQL、Redis、API设计 |
| dba | 数据库设计师 | MySQL优化、分库分表、索引 |
| devops | 运维工程师 | Docker、K8s、监控、日志 |
| frontend-dev | 前端开发 | Vue、React、交互设计 |
| qa-functional | 功能测试 | 测试用例、API测试、缺陷分析 |
| qa-performance | 性能测试 | JMeter、JVM调优、性能分析 |
| requirements-analyst | 需求分析师 | 需求分析、领域知识、模板 |
| ucd | UI/UX设计师 | 交互设计、B端规范、组件库 |

## 使用建议
- 团队公共背景优先看 `.hermes/team/knowledge/`
- 同角色共享知识优先看 `.hermes/agents/<role>/knowledge/`
- 团队实例个体差异优先看 `.hermes/team/agents/<agent>/knowledge/`
