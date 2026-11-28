# 语音识别准确率报告

- 生成时间：2026-11-27 20:22:35
- 识别引擎：cloud（6 条）（调用方式：API http://127.0.0.1:8000/api/v1）
- 识别模型：`qwen3.8-omni-flash`（协议 `omni`；全模态模型如 qwen3.8-omni-flash 通过文字指令要求阿拉伯数字金额）
- manifest：`D:\桌面\finance-agent\data\asr_samples\manifest.csv`
- 明细 CSV：`D:\桌面\finance-agent\data\asr_samples\benchmark_results.csv`
- 样本数：6，整体字符准确率 **100.0%**

## 按麦克风/设备

| 分组 | 样本数 | 字符准确率 | 平均 CER | 完全匹配率 | 调用失败 |
|---|---:|---:|---:|---:|---:|
| laptop_mic | 6 | 100.0% | 0.000 | 100.0% | 0 |

## 按设备 × 噪声条件

| 分组 | 样本数 | 字符准确率 | 平均 CER | 完全匹配率 | 调用失败 |
|---|---:|---:|---:|---:|---:|
| laptop_mic / fan | 3 | 100.0% | 0.000 | 100.0% | 0 |
| laptop_mic / quiet | 3 | 100.0% | 0.000 | 100.0% | 0 |

## 失败样本

- 无

## 口径与限制

- 字符准确率 = `1 - CER`，CER 为归一化后字符级编辑距离 / 参考文本字数；
  标点与空白不计入，全半角数字统一。它比「整句对不对」更能反映优惠券数字听错这类局部错误。
- `device` 列来自 manifest，脚本不能自动识别真实麦克风型号；请用实际录音设备名称填写。
- `low_gain` / `office_noise` / `cafe_noise` / `fan_hum` 是对同一段干净录音的**仿真**处理，
  不是真实环境录音；正式答辩结论请以 `noise=real_recording` 的真实录音行为准。
- `engine` 为 `mock` 的数字只验证评测链路，不代表真实 ASR 能力。
