# TaijiOS 证据门操作系统 · 架构图

本目录是 TaijiOS 值班系统(evidence-gate operating loop)的交互式架构图与规格。

- `taiji-evidence-gate.html` —— 交互式成品(可直接浏览器打开;蓝图风格 + trace 动效)
- `taiji-evidence-gate.architecture.json` —— 规格(12 组件 / 11 连接 / 2 区域)
- 生成工具:[Archify](https://github.com/tt-a1i/archify)(MIT,agent 技能形态,2026-08-16 实测)

## 再生步骤

```bash
git clone --depth 1 https://github.com/tt-a1i/archify.git
node archify/archify/bin/archify.mjs render architecture \
  taiji-evidence-gate.architecture.json taiji-evidence-gate.html --quality standard
```

## 实测踩坑(2026-08-16,Archify v2.14 / node 24)

1. **组件必须手动 pos/size**:只给 id/type/label 时,带连接的渲染会在自动布局处产生 NaN 崩溃
2. **连接必须显式 fromSide/toSide**:否则报 clean-flow/endpoint-side-direction
3. **标签重叠**:横向相邻组件的间距要 ≥110px,或给连接加 labelDy=54
4. **showcase 品质 + security-group 边界会触发渲染器内部崩溃**:用 `standard` 品质交付

## 边界

本图是值班系统的架构自述,不是生产级服务的部署拓扑;所有组件与连接都有对应实据(仓库文件/launchd 任务/回执账本),但没有第三方审计。
