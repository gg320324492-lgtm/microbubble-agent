"""内置公式库种子数据 — 微纳米气泡领域常见公式"""

# 分类定义 (parent_name → children)
CATEGORIES = [
    {"name": "bubble_dynamics", "display_name": "气泡动力学", "description": "微纳米气泡的生成、稳定、运动与粒径分析", "icon": "bubble_3", "parent": None, "sort": 1},
    {"name": "bubble_generation", "display_name": "气泡生成", "description": "气泡生成过程的力学与热力学计算", "icon": "bubble_3", "parent": "bubble_dynamics", "sort": 11},
    {"name": "bubble_stability", "display_name": "气泡稳定性", "description": "气泡溶解、稳定性与寿命计算", "icon": "bubble_3", "parent": "bubble_dynamics", "sort": 12},
    {"name": "bubble_size", "display_name": "粒径分析", "description": "气泡粒径分布与平均粒径计算", "icon": "bubble_3", "parent": "bubble_dynamics", "sort": 13},
    {"name": "bubble_rise", "display_name": "气泡上升速度", "description": "气泡在液体中的上升速度计算", "icon": "bubble_3", "parent": "bubble_dynamics", "sort": 14},

    {"name": "mass_transfer", "display_name": "传质过程", "description": "气体溶解、传质系数与曝气效率计算", "icon": "swap_vert", "parent": None, "sort": 2},
    {"name": "gas_dissolution", "display_name": "气体溶解", "description": "亨利定律与气体溶解平衡计算", "icon": "swap_vert", "parent": "mass_transfer", "sort": 21},
    {"name": "ozonation", "display_name": "臭氧化", "description": "臭氧传质与消毒计算", "icon": "swap_vert", "parent": "mass_transfer", "sort": 22},
    {"name": "oxygen_transfer", "display_name": "氧传质", "description": "氧传质系数与曝气效率计算", "icon": "swap_vert", "parent": "mass_transfer", "sort": 23},

    {"name": "water_quality", "display_name": "水质分析", "description": "常规水质指标计算与分析方法", "icon": "water_drop", "parent": None, "sort": 3},
    {"name": "cod", "display_name": "COD测定", "description": "化学需氧量(COD)测定计算", "icon": "water_drop", "parent": "water_quality", "sort": 31},
    {"name": "bod", "display_name": "生化需氧量", "description": "BOD5 与生化氧消耗计算", "icon": "water_drop", "parent": "water_quality", "sort": 32},
    {"name": "do", "display_name": "溶解氧", "description": "溶解氧饱和度与浓度计算", "icon": "water_drop", "parent": "water_quality", "sort": 33},
    {"name": "treatment", "display_name": "处理效率", "description": "污染物去除效率与吸附计算", "icon": "water_drop", "parent": "water_quality", "sort": 34},

    {"name": "chemical_kinetics", "display_name": "化学动力学", "description": "反应速率、消毒动力学与温度效应", "icon": "science", "parent": None, "sort": 4},
    {"name": "reaction_rate", "display_name": "反应速率", "description": "不同级数反应速率计算", "icon": "science", "parent": "chemical_kinetics", "sort": 41},
    {"name": "disinfection", "display_name": "消毒", "description": "消毒动力学与CT值计算", "icon": "science", "parent": "chemical_kinetics", "sort": 42},
    {"name": "temperature_effect", "display_name": "温度效应", "description": "温度对反应速率的影响 (Arrhenius)", "icon": "science", "parent": "chemical_kinetics", "sort": 43},

    {"name": "fluid_mechanics", "display_name": "流体力学", "description": "流态判断、压降计算与空化分析", "icon": "waves", "parent": None, "sort": 5},
    {"name": "flow_regime", "display_name": "流态判断", "description": "雷诺数、韦伯数等无量纲数计算", "icon": "waves", "parent": "fluid_mechanics", "sort": 51},
    {"name": "pressure_loss", "display_name": "压降计算", "description": "管道摩擦损失与空化数计算", "icon": "waves", "parent": "fluid_mechanics", "sort": 52},

    {"name": "statistical_analysis", "display_name": "统计分析", "description": "实验数据的统计处理与质量控制", "icon": "monitoring", "parent": None, "sort": 6},
    {"name": "descriptive_stats", "display_name": "描述统计", "description": "均值、标准差、RSD等基础统计", "icon": "monitoring", "parent": "statistical_analysis", "sort": 61},
    {"name": "calibration", "display_name": "标准曲线", "description": "线性回归与检出限计算", "icon": "monitoring", "parent": "statistical_analysis", "sort": 62},
]

# 公式库: 每个公式包含所有必填字段
FORMULA_LIBRARY = [
    # ── Bubble Dynamics: bubble_generation ──
    {
        "name": "Young-Laplace 压力",
        "formula_latex": "ΔP = 2γ / r",
        "formula_python": "2 * gamma / r",
        "variables": {
            "gamma": {"description": "表面张力", "unit": "N/m"},
            "r": {"description": "气泡半径", "unit": "m"},
        },
        "result_unit": "Pa",
        "conditions": "适用于球形气泡，忽略重力影响",
        "category_name": "bubble_generation",
    },
    {
        "name": "Laplace 压力 (双曲面)",
        "formula_latex": "ΔP = 2γ * (1/r₁ + 1/r₂)",
        "formula_python": "2 * gamma * (1/r1 + 1/r2)",
        "variables": {
            "gamma": {"description": "表面张力", "unit": "N/m"},
            "r1": {"description": "第一曲率半径", "unit": "m"},
            "r2": {"description": "第二曲率半径", "unit": "m"},
        },
        "result_unit": "Pa",
        "conditions": "适用于非球形气泡界面",
        "category_name": "bubble_generation",
    },
    # ── Bubble Dynamics: bubble_stability ──
    {
        "name": "Epstein-Plesset 溶解速率",
        "formula_latex": "dr/dt = -D·Cₛ·(1/r + 1/√(πDt)) / ρ",
        "formula_python": "-D * Cs * (1/r + 1/sqrt(pi * D * t)) / rho",
        "variables": {
            "D": {"description": "扩散系数", "unit": "m²/s"},
            "Cs": {"description": "饱和浓度", "unit": "kg/m³"},
            "rho": {"description": "气体密度", "unit": "kg/m³"},
            "r": {"description": "气泡半径", "unit": "m"},
            "t": {"description": "时间", "unit": "s"},
        },
        "result_unit": "m/s",
        "conditions": "适用于静止液体中单气泡溶解",
        "category_name": "bubble_stability",
    },
    {
        "name": "气泡寿命估算",
        "formula_latex": "t = ρ·r₀² / (2·D·Cₛ)",
        "formula_python": "rho * r0**2 / (2 * D * Cs)",
        "variables": {
            "rho": {"description": "气体密度", "unit": "kg/m³"},
            "r0": {"description": "初始半径", "unit": "m"},
            "D": {"description": "扩散系数", "unit": "m²/s"},
            "Cs": {"description": "饱和浓度", "unit": "kg/m³"},
        },
        "result_unit": "s",
        "conditions": "近似估算，忽略表面张力影响",
        "category_name": "bubble_stability",
    },
    # ── Bubble Dynamics: bubble_size ──
    {
        "name": "Sauter 平均直径",
        "formula_latex": "d₃₂ = Σ(nᵢ·dᵢ³) / Σ(nᵢ·dᵢ²)",
        "formula_python": "(n1*d1**3 + n2*d2**3 + n3*d3**3 + n4*d4**3 + n5*d5**3) / (n1*d1**2 + n2*d2**2 + n3*d3**2 + n4*d4**2 + n5*d5**2)",
        "variables": {
            "n1": {"description": "第1组气泡数量", "unit": ""},
            "d1": {"description": "第1组气泡直径", "unit": "m"},
            "n2": {"description": "第2组气泡数量", "unit": ""},
            "d2": {"description": "第2组气泡直径", "unit": "m"},
            "n3": {"description": "第3组气泡数量", "unit": ""},
            "d3": {"description": "第3组气泡直径", "unit": "m"},
            "n4": {"description": "第4组气泡数量", "unit": ""},
            "d4": {"description": "第4组气泡直径", "unit": "m"},
            "n5": {"description": "第5组气泡数量", "unit": ""},
            "d5": {"description": "第5组气泡直径", "unit": "m"},
        },
        "result_unit": "m",
        "conditions": "至少需要2组数据，建议使用5组以上",
        "category_name": "bubble_size",
    },
    # ── Bubble Dynamics: bubble_rise ──
    {
        "name": "Stokes 上升速度",
        "formula_latex": "v = 2g·r²·(ρₗ - ρ) / (9μ)",
        "formula_python": "2 * 9.81 * r**2 * (rho_l - rho_g) / (9 * mu)",
        "variables": {
            "r": {"description": "气泡半径", "unit": "m"},
            "rho_l": {"description": "液体密度", "unit": "kg/m³"},
            "rho_g": {"description": "气体密度", "unit": "kg/m³"},
            "mu": {"description": "液体动力黏度", "unit": "Pa·s"},
        },
        "result_unit": "m/s",
        "conditions": "Re < 1 时适用，微纳米气泡通常满足此条件",
        "category_name": "bubble_rise",
    },
    {
        "name": "Hadamard-Rybczynski 上升速度",
        "formula_latex": "v = 2g·r²·(ρₗ - ρ) / (3μ) · (μ + μₛ)/(2μ + 3μₛ)",
        "formula_python": "2 * 9.81 * r**2 * (rho_l - rho_g) / (3 * mu) * (mu + mu_g) / (2 * mu + 3 * mu_g)",
        "variables": {
            "r": {"description": "气泡半径", "unit": "m"},
            "rho_l": {"description": "液体密度", "unit": "kg/m³"},
            "rho_g": {"description": "气体密度", "unit": "kg/m³"},
            "mu": {"description": "液体动力黏度", "unit": "Pa·s"},
            "mu_g": {"description": "气体动力黏度", "unit": "Pa·s"},
        },
        "result_unit": "m/s",
        "conditions": "适用于界面可移动的气泡，比Stokes公式更准确",
        "category_name": "bubble_rise",
    },
    # ── Mass Transfer: gas_dissolution ──
    {
        "name": "亨利定律 (浓度)",
        "formula_latex": "C = k_H · P",
        "formula_python": "kH * P",
        "variables": {
            "kH": {"description": "亨利常数", "unit": "mol/(L·Pa)"},
            "P": {"description": "气体分压", "unit": "Pa"},
        },
        "result_unit": "mol/L",
        "conditions": "稀溶液、低压条件下适用",
        "category_name": "gas_dissolution",
    },
    {
        "name": "双膜传质速率",
        "formula_latex": "J = k_L·a · (Cₛ - C)",
        "formula_python": "kLa * (Cs - C)",
        "variables": {
            "kLa": {"description": "体积传质系数", "unit": "1/s"},
            "Cs": {"description": "饱和浓度", "unit": "mg/L"},
            "C": {"description": "实际浓度", "unit": "mg/L"},
        },
        "result_unit": "mg/(L·s)",
        "conditions": "双膜理论适用条件",
        "category_name": "gas_dissolution",
    },
    # ── Mass Transfer: ozonation ──
    {
        "name": "臭氧 CT 值",
        "formula_latex": "CT = C · t",
        "formula_python": "C * t",
        "variables": {
            "C": {"description": "臭氧浓度", "unit": "mg/L"},
            "t": {"description": "接触时间", "unit": "min"},
        },
        "result_unit": "mg·min/L",
        "conditions": "用于消毒效果评估",
        "category_name": "ozonation",
    },
    {
        "name": "臭氧利用率",
        "formula_latex": "η = (Cᵢ - Cₒ) / Cᵢ × 100",
        "formula_python": "(Ci - Co) / Ci * 100",
        "variables": {
            "Ci": {"description": "进口臭氧浓度", "unit": "mg/L"},
            "Co": {"description": "出口臭氧浓度", "unit": "mg/L"},
        },
        "result_unit": "%",
        "conditions": "连续流反应器",
        "category_name": "ozonation",
    },
    # ── Mass Transfer: oxygen_transfer ──
    {
        "name": "DO 浓度拟合 (KLa)",
        "formula_latex": "C = Cₛ - (Cₛ - C₀)·exp(-KLa·t)",
        "formula_python": "Cs - (Cs - C0) * exp(-KLa * t)",
        "variables": {
            "Cs": {"description": "饱和溶解氧浓度", "unit": "mg/L"},
            "C0": {"description": "初始溶解氧浓度", "unit": "mg/L"},
            "KLa": {"description": "体积传质系数", "unit": "1/min"},
            "t": {"description": "曝气时间", "unit": "min"},
        },
        "result_unit": "mg/L",
        "conditions": "适用于间歇式曝气实验数据拟合",
        "category_name": "oxygen_transfer",
    },
    {
        "name": "SOTR (标准氧传质速率)",
        "formula_latex": "SOTR = KLa · Cₛ · V / 1000",
        "formula_python": "KLa * Cs * V / 1000",
        "variables": {
            "KLa": {"description": "体积传质系数 (20°C)", "unit": "1/h"},
            "Cs": {"description": "饱和溶解氧浓度 (20°C)", "unit": "mg/L"},
            "V": {"description": "水体体积", "unit": "m³"},
        },
        "result_unit": "kg O₂/h",
        "conditions": "标准条件: 20°C, 1 atm, 清水",
        "category_name": "oxygen_transfer",
    },
    {
        "name": "SAE (标准曝气效率)",
        "formula_latex": "SAE = SOTR / P",
        "formula_python": "SOTR / P",
        "variables": {
            "SOTR": {"description": "标准氧传质速率", "unit": "kg O₂/h"},
            "P": {"description": "曝气功率", "unit": "kW"},
        },
        "result_unit": "kg O₂/(kWh)",
        "conditions": "标准条件: 20°C, 1 atm",
        "category_name": "oxygen_transfer",
    },
    # ── Water Quality: cod ──
    {
        "name": "COD 重铬酸法",
        "formula_latex": "COD = (V₀ - V₁) × C × 8000 / V",
        "formula_python": "(V0 - V1) * C * 8000 / V",
        "variables": {
            "V0": {"description": "空白消耗硫酸亚铁铵体积", "unit": "mL"},
            "V1": {"description": "样品消耗硫酸亚铁铵体积", "unit": "mL"},
            "C": {"description": "硫酸亚铁铵标准浓度", "unit": "mol/L"},
            "V": {"description": "水样体积", "unit": "mL"},
        },
        "result_unit": "mg/L",
        "conditions": "GB/T 11914-89 重铬酸盐法",
        "category_name": "cod",
    },
    # ── Water Quality: bod ──
    {
        "name": "BOD₅ 计算",
        "formula_latex": "BOD₅ = (DOᵢ - DO) / P",
        "formula_python": "(DO_i - DO_f) / P",
        "variables": {
            "DO_i": {"description": "培养前溶解氧", "unit": "mg/L"},
            "DO_f": {"description": "培养5天后溶解氧", "unit": "mg/L"},
            "P": {"description": "稀释比", "unit": ""},
        },
        "result_unit": "mg/L",
        "conditions": "HJ 505-2009 稀释接种法",
        "category_name": "bod",
    },
    # ── Water Quality: do ──
    {
        "name": "DO 饱和度 (淡水)",
        "formula_latex": "DOₛ = 14.652 - 0.41022T + 0.007991T² - 0.000077774T³",
        "formula_python": "14.652 - 0.41022 * T + 0.007991 * T**2 - 0.000077774 * T**3",
        "variables": {
            "T": {"description": "水温", "unit": "°C"},
        },
        "result_unit": "mg/L",
        "conditions": "1 atm 条件下淡水，温度范围 0~30°C",
        "category_name": "do",
    },
    # ── Water Quality: treatment ──
    {
        "name": "去除率",
        "formula_latex": "R = (C₀ - C) / C₀ × 100",
        "formula_python": "(C0 - Ct) / C0 * 100",
        "variables": {
            "C0": {"description": "初始浓度", "unit": "mg/L"},
            "Ct": {"description": "处理后浓度", "unit": "mg/L"},
        },
        "result_unit": "%",
        "conditions": "通用污染物去除效率计算",
        "category_name": "treatment",
    },
    {
        "name": "Langmuir 吸附等温式",
        "formula_latex": "qₑ = qₘₐₓ · K_L · Cₑ / (1 + K_L · Cₑ)",
        "formula_python": "qmax * KL * Ce / (1 + KL * Ce)",
        "variables": {
            "qmax": {"description": "最大吸附容量", "unit": "mg/g"},
            "KL": {"description": "Langmuir常数", "unit": "L/mg"},
            "Ce": {"description": "平衡浓度", "unit": "mg/L"},
        },
        "result_unit": "mg/g",
        "conditions": "适用于单分子层吸附",
        "category_name": "treatment",
    },
    # ── Chemical Kinetics: reaction_rate ──
    {
        "name": "一级反应动力学",
        "formula_latex": "C = C₀ · e^{-kt}",
        "formula_python": "C0 * exp(-k * t)",
        "variables": {
            "C0": {"description": "初始浓度", "unit": "mg/L"},
            "k": {"description": "一级速率常数", "unit": "1/min"},
            "t": {"description": "反应时间", "unit": "min"},
        },
        "result_unit": "mg/L",
        "conditions": "适用于浓度衰减符合一级反应的情况",
        "category_name": "reaction_rate",
    },
    {
        "name": "二级反应动力学",
        "formula_latex": "1/C = 1/C₀ + kt",
        "formula_python": "1 / (1/C0 + k * t)",
        "variables": {
            "C0": {"description": "初始浓度", "unit": "mg/L"},
            "k": {"description": "二级速率常数", "unit": "L/(mg·min)"},
            "t": {"description": "反应时间", "unit": "min"},
        },
        "result_unit": "mg/L",
        "conditions": "适用于二级反应",
        "category_name": "reaction_rate",
    },
    # ── Chemical Kinetics: disinfection ──
    {
        "name": "Chick-Watson 消毒模型",
        "formula_latex": "ln(N₀/N) = k · Cⁿ · t",
        "formula_python": "k * C**n * t",
        "variables": {
            "k": {"description": "灭活速率常数", "unit": "L/(mg·min)"},
            "C": {"description": "消毒剂浓度", "unit": "mg/L"},
            "n": {"description": "稀释系数", "unit": ""},
            "t": {"description": "接触时间", "unit": "min"},
        },
        "result_unit": "",
        "conditions": "N₀为初始微生物数，N为t时刻存活数",
        "category_name": "disinfection",
    },
    {
        "name": "CT 值 (消毒)",
        "formula_latex": "CT = C · t",
        "formula_python": "C * t",
        "variables": {
            "C": {"description": "消毒剂浓度", "unit": "mg/L"},
            "t": {"description": "接触时间", "unit": "min"},
        },
        "result_unit": "mg·min/L",
        "conditions": "饮用水消毒效果评价指标",
        "category_name": "disinfection",
    },
    # ── Chemical Kinetics: temperature_effect ──
    {
        "name": "Arrhenius 方程",
        "formula_latex": "k = A · e^{-Eₐ/(RT)}",
        "formula_python": "A * exp(-Ea / (R * T))",
        "variables": {
            "A": {"description": "指前因子", "unit": "1/s"},
            "Ea": {"description": "活化能", "unit": "J/mol"},
            "R": {"description": "气体常数 8.314", "unit": "J/(mol·K)", "default": 8.314},
            "T": {"description": "绝对温度", "unit": "K"},
        },
        "result_unit": "1/s",
        "conditions": "适用温度范围较宽时可用",
        "category_name": "temperature_effect",
    },
    # ── Fluid Mechanics: flow_regime ──
    {
        "name": "雷诺数",
        "formula_latex": "Re = ρvd / μ",
        "formula_python": "rho * v * d / mu",
        "variables": {
            "rho": {"description": "流体密度", "unit": "kg/m³"},
            "v": {"description": "流速", "unit": "m/s"},
            "d": {"description": "特征长度", "unit": "m"},
            "mu": {"description": "动力黏度", "unit": "Pa·s"},
        },
        "result_unit": "",
        "conditions": "Re < 2300 层流; 2300 < Re < 4000 过渡; Re > 4000 湍流",
        "category_name": "flow_regime",
    },
    {
        "name": "韦伯数",
        "formula_latex": "We = ρv²d / σ",
        "formula_python": "rho * v**2 * d / sigma_s",
        "variables": {
            "rho": {"description": "流体密度", "unit": "kg/m³"},
            "v": {"description": "流速", "unit": "m/s"},
            "d": {"description": "液滴/气泡直径", "unit": "m"},
            "sigma_s": {"description": "表面张力", "unit": "N/m"},
        },
        "result_unit": "",
        "conditions": "We > 12 时气泡易破碎",
        "category_name": "flow_regime",
    },
    # ── Fluid Mechanics: pressure_loss ──
    {
        "name": "Darcy-Weisbach 水头损失",
        "formula_latex": "hf = f · L · v² / (2g · D)",
        "formula_python": "f * L * v**2 / (2 * 9.81 * D)",
        "variables": {
            "f": {"description": "Darcy摩擦系数", "unit": ""},
            "L": {"description": "管长", "unit": "m"},
            "v": {"description": "流速", "unit": "m/s"},
            "D": {"description": "管径", "unit": "m"},
        },
        "result_unit": "m",
        "conditions": "适用于满管有压流",
        "category_name": "pressure_loss",
    },
    {
        "name": "空化数",
        "formula_latex": "σ = (P - Pᵥ) / (0.5ρv²)",
        "formula_python": "(P - Pv) / (0.5 * rho * v**2)",
        "variables": {
            "P": {"description": "参考压力", "unit": "Pa"},
            "Pv": {"description": "饱和蒸气压", "unit": "Pa"},
            "rho": {"description": "流体密度", "unit": "kg/m³"},
            "v": {"description": "特征流速", "unit": "m/s"},
        },
        "result_unit": "",
        "conditions": "σ < 1 时易发生空化",
        "category_name": "pressure_loss",
    },
    # ── Statistical Analysis: descriptive_stats ──
    {
        "name": "样本标准差",
        "formula_latex": "s = √(Σ(xᵢ - x̄)² / (n-1))",
        "formula_python": "sqrt((sum_sq) / (n - 1))",
        "variables": {
            "sum_sq": {"description": "各测量值与均值之差的平方和", "unit": ""},
            "n": {"description": "样本数量", "unit": ""},
        },
        "result_unit": "",
        "conditions": "n ≥ 2",
        "category_name": "descriptive_stats",
    },
    {
        "name": "相对标准偏差 (RSD)",
        "formula_latex": "RSD = s / x̄ × 100",
        "formula_python": "s / mean * 100",
        "variables": {
            "s": {"description": "标准差", "unit": ""},
            "mean": {"description": "均值", "unit": ""},
        },
        "result_unit": "%",
        "conditions": "通常 RSD < 5% 表示精密度良好",
        "category_name": "descriptive_stats",
    },
    # ── Statistical Analysis: calibration ──
    {
        "name": "检出限 LOD (3σ)",
        "formula_latex": "LOD = 3.3 · s_blank / slope",
        "formula_python": "3.3 * s_blank / slope",
        "variables": {
            "s_blank": {"description": "空白多次测量的标准差", "unit": ""},
            "slope": {"description": "标准曲线斜率", "unit": ""},
        },
        "result_unit": "",
        "conditions": "IUPAC 推荐方法",
        "category_name": "calibration",
    },
    {
        "name": "定量限 LOQ (10σ)",
        "formula_latex": "LOQ = 10 · s_blank / slope",
        "formula_python": "10 * s_blank / slope",
        "variables": {
            "s_blank": {"description": "空白多次测量的标准差", "unit": ""},
            "slope": {"description": "标准曲线斜率", "unit": ""},
        },
        "result_unit": "",
        "conditions": "IUPAC 推荐方法",
        "category_name": "calibration",
    },
]
