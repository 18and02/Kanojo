# P3 实施计划

P3 目标是在已经跑通的语音链路上接入形象层,顺序固定为:

1. P3.1 简单形象舞台与状态驱动;
2. P3.2 口型同步信号抽象;
3. P3.3 替换为 Live2D / 桌面女仆模型;
4. P3.4 口型、表情和动作的评测埋点。

## 里程碑

| 编号 | 交付 | 验收 |
| --- | --- | --- |
| P3.1 | 形象舞台 | 桌面端有可见形象;录音、生成、播放、打断会切换形象状态 |
| P3.2 | 口型同步 | TTS 播放期间有独立 mouth level 信号;停止或打断时立即归零 |
| P3.3 | Live2D 接入 | 复用 P3.1/P3.2 状态信号驱动真实模型 |
| P3.4 | 形象评测 | 记录语音首播、口型活动、打断到静音/闭嘴耗时 |

## 当前状态

- P3.1 已实现:
  - 桌面端新增 `avatar-stage`;
  - 形象状态由录音、转写、LLM 生成、TTS 合成/播放和打断状态驱动;
  - 播放状态分为 `idle / thinking / listening / speaking / interrupted`;
  - 当前先使用 CSS 形象,后续替换 Live2D 资产时不改变上游状态输入。
- P3.2 已实现:
  - TTS 实际出声时设置 `voiceActive`;
  - 独立 `lipSyncSource` 标记当前口型来源: `none / text / audio`;
  - 系统 `speechSynthesis` 使用文本节奏驱动 `avatarMouthLevel`;
  - 外部 TTS 音频使用 Web Audio `AnalyserNode` 采样音量,映射到 `avatarMouthLevel`;
  - 外部音频播放结束、系统语音结束、播放失败或打断时嘴型立即归零。
- P3.3 已实现:
  - 桌面端新增 `Live2DAvatar` 组件;
  - 默认使用 Live2D 官方 Haru Greeter 示例模型;
  - 模型资源和 Cubism Core 放在 renderer 静态目录,运行时不依赖远端 CDN;
  - `avatarMode` 驱动模型头部/身体姿态参数;
  - `lipSyncLive2DValue` 写入 `ParamMouthOpenY`;
  - Live2D 初始化失败时保留 CSS 形象 fallback。
- P3.4 已实现:
  - 桌面端在系统语音首播、外部 TTS 首播、口型同步结束和语音打断时写入 `avatar_*` 评测事件;
  - 后端新增通用 `POST /evaluation/events`,复用 SQLite `evaluation_events` 作为唯一真相源;
  - `/evaluation/summary` 增加 `avatar` 摘要,统计首播延迟、口型活跃时长/比例和打断闭嘴耗时;
  - 调试面板展示 P3.4 指标,最近事件列表会把 `avatar_voice_start / avatar_lip_sync / avatar_interrupt` 转成人类可读信息。

## P3.1 方案

P3.1 不直接引入真实 Live2D 资产。原因是当前项目需要先稳定“形象由管线驱动”的接口,再替换模型:

- 录音中:进入 listening;
- LLM / TTS 合成中:进入 thinking;
- TTS 实际播放中:进入 speaking,口型开合;
- 打断/停止:进入 interrupted,清空嘴型;
- 空闲:回到 idle。

## 后续接入点

真实 Live2D 接入时,优先把当前信号映射为模型参数:

```text
avatarMode        -> 表情 / 姿态
avatarMouthLevel  -> ParamMouthOpenY
voiceActive       -> 口型同步开关
lipSyncSource     -> 口型来源诊断
speechInterrupt   -> 立即停止动作和闭嘴
```

## P3.2 方案

P3.2 把“嘴型开合”从 `voiceActive` 随机动画拆成可复用信号:

- `avatarMouthLevel` 统一表示 0-3 四档开合;
- `lipSyncLive2DValue = avatarMouthLevel / 3`,可直接映射到 Live2D `ParamMouthOpenY`;
- 外部 TTS 播放真实音频时,用 Web Audio 分析 RMS 音量并实时换算开合档位;
- 浏览器系统语音拿不到音频流时,使用文本节奏作为 fallback;
- `interruptSpeech`、音频清理、播放结束、播放失败都会调用同一套停止逻辑,保证闭嘴和状态归零。

## P3.3 方案

P3.3 先不制作自定义桌面女仆资产,使用官方 Haru Greeter 示例模型完成真实 Live2D 渲染链路:

- PixiJS 负责 WebGL 画布;
- `pixi-live2d-display/cubism4` 负责加载 Cubism 3/4 `model3.json`;
- `live2dcubismcore.min.js` 在页面业务 bundle 前加载;
- 模型资源位于 `desktop/src/renderer/public/live2d/haru`;
- 口型参数每帧在 `beforeModelUpdate` 写入,避免被 idle motion 覆盖;
- `listening / thinking / speaking / interrupted` 映射为轻量头部与身体姿态,后续换自定义模型时继续复用同一信号。

## P3.4 方案

P3.4 把形象层从“能看见、能动”推进到“能评测”,先记录稳定的播放链路指标:

- `avatar_voice_start`:语音实际开始播放时写入,`latency_ms` 表示从当前语音片段开始合成/排队到首播的耗时;
- `avatar_lip_sync`:口型同步停止时写入,`payload.active_ms` 和 `payload.active_ratio` 表示嘴型非零样本的估算时长和比例;
- `avatar_interrupt`:打断逻辑完成后写入,`latency_ms` 表示打断入口到清理播放、闭嘴归零完成的耗时;
- 事件统一写入 `POST /evaluation/events`,方便后续导出实验数据,同时不把形象逻辑耦合进聊天和心跳接口;
- 调试面板只展示聚合指标和最近事件,不做自动评分,避免在样本量不足时给出误导性结论。

## 非目标

- P3.1/P3.2/P3.3/P3.4 不训练或绘制最终角色资产;
- P3.1/P3.2/P3.3/P3.4 不做桌面透明悬浮窗;
- P3.2 不做物理级音素口型,先完成可复用的播放状态和口型信号。
- P3.3 不定制最终人设动作库,只完成默认官方模型的真实接入。
- P3.4 不做主观自然度打分,只沉淀可复核的时序和活动指标。
