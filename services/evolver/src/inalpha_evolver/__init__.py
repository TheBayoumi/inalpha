"""Inalpha 策略演化引擎。

E1 范围：单代闭环 —— LLM 变异种子策略 → 三道沙盒 → 回测评估 → 落演化候选表。
E2 先扩展 best-parent 多代选择 + early stopping；MAP-Elites / Island Model 后置。
"""

__version__ = "0.1.0"
