# 数据可视化设计规范

## 一、图表选择指南

### 图表分类
```
对比类：柱状图、条形图、雷达图
趋势类：折线图、面积图
占比类：饼图、环形图、南丁格尔图
分布类：散点图、直方图
流程类：漏斗图、桑基图
关系类：关系图、力导向图
```

### 选择原则
| 数据维度 | 推荐图表 |
|----------|----------|
| 单一变量对比 | 柱状图/条形图 |
| 多维度对比 | 雷达图 |
| 时间趋势变化 | 折线图 |
| 占比构成 | 饼图/环形图 |
| 排名TOP N | 条形图 |
| 转化漏斗 | 漏斗图 |
| 地理分布 | 地图 |

### 常见场景选择
```
用户增长 → 折线图（面积）
收入构成 → 饼图
区域销售排名 → 条形图
转化漏斗 → 漏斗图
用户画像 → 雷达图
```

## 二、色彩规范

### 主色调
| 用途 | 色值 | 说明 |
|------|------|------|
| 主色 | #409EFF | 核心数据 |
| 成功 | #67C23A | 正向指标 |
| 警告 | #E6A23C | 中性指标 |
| 危险 | #F56C6C | 负向指标 |
| 信息 | #909399 | 辅助信息 |

### 扩展色板
```
#5470C6  #91CC75  #FAC858  #EE6666  #73C0DE  #3BA272  #FC8452  #9A60B4
```
适用于多系列数据，最多 8 个色系

### 图表配色原则
1. 同一图表内颜色不超过 7 种
2. 相邻色系使用对比明显的颜色
3. 背景色使用浅色系
4. 深色背景使用浅色数据

## 三、图表设计规范

### 柱状图/条形图
```javascript
// Element Plus ECharts 配置
{
  xAxis: {
    type: 'category',
    data: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    axisLabel: { color: '#606266' }
  },
  yAxis: {
    type: 'value',
    axisLabel: { color: '#606266' }
  },
  series: [{
    type: 'bar',
    data: [120, 200, 150, 80, 70, 110, 130],
    itemStyle: { color: '#409EFF' }
  }]
}
```

规范：
- 柱子宽度：20px
- 柱子间距：8px
- 数值标签显示在柱子上方
- 超过 5 个建议用条形图

### 折线图
```javascript
{
  xAxis: { type: 'category', data: ['1月', '2月', '3月', '4月'] },
  yAxis: { type: 'value' },
  series: [{
    type: 'line',
    data: [320, 332, 401, 434],
    smooth: true,  // 平滑曲线
    areaStyle: {}  // 面积图
  }]
}
```

规范：
- 折线宽度：2px
- 数据点大小：4px
- 面积图透明度：0.3
- 显示数值标签（数据点少时）
- 启用数据缩放（数据点多时）

### 饼图
```javascript
{
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],  // 环形图
    data: [
      { value: 1048, name: '搜索引擎' },
      { value: 735, name: '直接访问' },
      { value: 580, name: '邮件营销' }
    ],
    label: {
      formatter: '{b}: {d}%'
    }
  }]
}
```

规范：
- 标签显示在右侧或下方
- 显示百分比
- 超过 5 项时显示前 4 项 + 其他
- 扇形角度最小 5°

### 仪表盘
```javascript
{
  series: [{
    type: 'gauge',
    startAngle: 180,
    endAngle: 0,
    min: 0,
    max: 100,
    splitNumber: 5,
    axisLine: {
      lineStyle: {
        width: 20,
        color: [
          [0.3, '#67C23A'],
          [0.7, '#E6A23C'],
          [1, '#F56C6C']
        ]
      }
    },
    pointer: { length: '60%' },
    detail: { formatter: '{value}%' }
  }]
}
```

## 四、仪表盘布局规范

### 标准布局
```
┌────────────────────────────────────────────────┐
│ 总览标题                      [时间范围 ▼]     │
├────────────────────────────────────────────────┤
│ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│ │ 关键指标1 │ │ 关键指标2 │ │ 关键指标3 │       │
│ │   10,234  │ │   ¥50,000 │ │    85.2%  │       │
│ │  ↑12.5%  │ │  ↑8.3%   │ │  ↓2.1%   │       │
│ └──────────┘ └──────────┘ └──────────┘       │
├──────────────────────────┬─────────────────────┤
│       趋势图             │      占比图         │
│     （占2/3宽度）       │    （占1/3宽度）    │
├──────────────────────────┴─────────────────────┤
│              数据表格/排行榜                     │
└────────────────────────────────────────────────┘
```

### 尺寸规范
| 元素 | 规范 |
|------|------|
| 指标卡片 | 高度 100px，宽度自适应 |
| 图表 | 高度 300-400px |
| 表格 | 高度自适应 |

## 五、交互规范

### 通用交互
- Hover 显示 Tooltip
- 点击图例切换显示/隐藏
- 支持缩放和拖拽
- 支持导出图片

### Tooltip 规范
```
格式：指标名称：数值（单位）
多系列时分组显示
支持自定义格式化
```

### 图例规范
```
位置：图表下方或右侧
样式：水平或垂直排列
交互：点击可切换系列
```

## 六、常用组件库

### Vue 3 + ECharts
```javascript
// 安装
npm install echarts vue-echarts

// 使用
<template>
  <v-chart :option="option" autoresize />
</template>
```

### 推荐配置
```javascript
// 全局主题色配置
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, LineChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'

echarts.use([CanvasRenderer, PieChart, LineChart, BarChart, TitleComponent, TooltipComponent, LegendComponent])
```

## 七、性能优化

1. **数据采样**：数据量超过 1000 点时采样
2. **懒加载**：不在视口内不渲染
3. **按需引入**：只引入需要的图表类型
4. **关闭动画**：大数据量时关闭动画
5. **SSR 注意**：客户端渲染图表
