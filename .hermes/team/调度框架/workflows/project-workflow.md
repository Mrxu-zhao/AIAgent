# 项目工作流定义

## 快速导航

> 详细流程规范请查看 [团队流程规范.md](../../../../团队流程规范.md)

| 阶段 | 负责人 | 详细说明 |
|------|--------|----------|
| 需求分析 | 吴雪梅 | 团队流程规范 - 需求分析阶段 |
| UCD设计 | 吴俊杰 | 团队流程规范 - UCD设计阶段 |
| 架构设计 | 张欣怡 | 团队流程规范 - 架构设计阶段 |
| 数据库设计 | 周嘉诚 | 团队流程规范 - 数据库设计阶段 |
| 前端开发 | 李思雨、周晓明、林雅婷 | 团队流程规范 - 前端开发阶段 |
| 后端开发 | 陈启明、王浩然、赵文杰 | 团队流程规范 - 后端开发阶段 |
| 功能测试 | 郑晓彤 | 团队流程规范 - 功能测试阶段 |
| 性能测试 | 孙美玲 | 团队流程规范 - 性能测试阶段 |
| 部署上线 | 黄志远 | 团队流程规范 - 部署阶段 |

## 并行调度示例

```bash
# 需求 + UCD + 架构 并行
./team-dispatch.sh requirements-analyst "分析xxx需求"
./team-dispatch.sh ucd "设计xxx原型"
./team-dispatch.sh architect "设计xxx架构"

# 前端 + 后端 并行
./team-dispatch.sh frontend-1 "开发xxx页面"
./team-dispatch.sh backend-1 "开发xxx接口"

# 功能 + 性能测试 并行
./team-dispatch.sh qa-functional "测试xxx功能"
./team-dispatch.sh qa-performance "性能测试xxx"
```

---

*负责人: 秦燕 | 版本: v2.0 | 创建: 2026-04-30*
