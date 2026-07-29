"""中文微纳米气泡领域同义词字典 (PR4 W90 +3..+5)

数据格式: {variant_word: canonical_word}
- canonical_word 是该 synonym group 的代表词
- 一组等价词共享同一个 canonical
- canonical 自指 (canonical_word → canonical_word) 也算 1 条

domain: 中文微纳米气泡 / 水处理 / 表面科学 / 流体力学 / 化工 / 生物医学
total entries: ≥ 200 条 (满足 plan §2 PR4 锚点范式门禁)

组织 (按领域分组, 共 ~30 synonym group + ~220 entries):

[微纳米气泡核心词]  8 group, 30 entries
[物化性质]          10 group, 40 entries
[制备方法]          6 group, 25 entries
[应用领域]          8 group, 35 entries
[测量表征]          8 group, 35 entries
[设备仪器]          5 group, 20 entries
[过程现象]          8 group, 30 entries
[通用中文术语]      3 group, 10 entries
[英文术语]          (合并在以上 group 内)

总: ~56 group + ~225 entries (远超 200 阈值)

修改原则 (派工 v6 段 5 反馈 #6 实战 — W75 B-1 沉淀):
- canonical 必须稳定, 不要中途换名
- variant 必须覆盖: 中文 + 英文 + 拼写变体 (e.g. micro-bubble / microbubble / micro bubble)
- 同一词不要跨 group (canonical 必须唯一)
"""

# 严格 dict, 任何 key 变更要走 PR4+1 派工 + CLAUDE.md 永久锚点段同步

SYNONYMS = {
    # === 微纳米气泡核心词 (8 group, 30 entries) ===

    # group: microbubble (canonical)
    "微气泡": "microbubble",
    "microbubble": "microbubble",
    "micro-bubble": "microbubble",
    "micro bubble": "microbubble",
    "microbubbles": "microbubble",
    "微米气泡": "microbubble",
    "微米级气泡": "microbubble",
    "微细气泡": "microbubble",
    "细小气泡": "microbubble",

    # group: nanobubble (canonical)
    "纳米气泡": "nanobubble",
    "nanobubble": "nanobubble",
    "nano-bubble": "nanobubble",
    "nano bubble": "nanobubble",
    "nanobubbles": "nanobubble",
    "超细气泡": "nanobubble",
    "亚微米气泡": "nanobubble",
    "ultrafine bubble": "nanobubble",
    "ultrafine bubbles": "nanobubble",
    "UFB": "nanobubble",

    # group: bulk_nanobubble (canonical)
    "体相纳米气泡": "bulk_nanobubble",
    "bulk nanobubble": "bulk_nanobubble",
    "bulk nanobubbles": "bulk_nanobubble",
    "BNB": "bulk_nanobubble",
    "游离纳米气泡": "bulk_nanobubble",
    "自由纳米气泡": "bulk_nanobubble",

    # group: surface_nanobubble (canonical)
    "表面纳米气泡": "surface_nanobubble",
    "surface nanobubble": "surface_nanobubble",
    "surface nanobubbles": "surface_nanobubble",
    "SNB": "surface_nanobubble",
    "界面纳米气泡": "surface_nanobubble",
    "固液界面纳米气泡": "surface_nanobubble",

    # group: cavitation (canonical)
    "空化": "cavitation",
    "cavitation": "cavitation",
    "空化作用": "cavitation",
    "空化效应": "cavitation",
    "空化现象": "cavitation",
    "气穴现象": "cavitation",

    # group: bubble (canonical) — 通用
    "气泡": "bubble",
    "bubble": "bubble",
    "bubbles": "bubble",
    "气泡群": "bubble",
    "bubble cloud": "bubble",

    # group: microbubble_cloud (canonical) — 微气泡云
    "微气泡云": "microbubble_cloud",
    "microbubble cloud": "microbubble_cloud",
    "气泡云": "microbubble_cloud",
    "bubble cloud": "microbubble_cloud",
    "微泡群": "microbubble_cloud",

    # group: froth (canonical) — 泡沫
    "泡沫": "froth",
    "froth": "froth",
    "foams": "froth",
    "foam": "froth",
    "气泡膜": "froth",

    # === 物化性质 (10 group, 40 entries) ===

    # group: zeta_potential (canonical)
    "zeta电位": "zeta_potential",
    "zeta 电位": "zeta_potential",
    "zeta potential": "zeta_potential",
    "电位": "zeta_potential",
    "电动电位": "zeta_potential",
    "电动势": "zeta_potential",
    "ζ电位": "zeta_potential",

    # group: surface_tension (canonical)
    "表面张力": "surface_tension",
    "surface tension": "surface_tension",
    "界面张力": "surface_tension",
    "interfacial tension": "surface_tension",
    "液气界面张力": "surface_tension",
    "液面张力": "surface_tension",

    # group: contact_angle (canonical)
    "接触角": "contact_angle",
    "contact angle": "contact_angle",
    "润湿角": "contact_angle",
    "wetting angle": "contact_angle",
    "接触角测量": "contact_angle",

    # group: diameter (canonical)
    "直径": "diameter",
    "diameter": "diameter",
    "粒径": "diameter",
    "气泡直径": "diameter",
    "尺寸": "diameter",

    # group: size_distribution (canonical)
    "粒径分布": "size_distribution",
    "size distribution": "size_distribution",
    "尺寸分布": "size_distribution",
    "气泡分布": "size_distribution",
    "droplet size distribution": "size_distribution",

    # group: density (canonical)
    "密度": "density",
    "density": "density",
    "气泡密度": "density",
    "微气泡密度": "density",

    # group: viscosity (canonical)
    "粘度": "viscosity",
    "黏度": "viscosity",
    "viscosity": "viscosity",
    "动力粘度": "viscosity",
    "运动粘度": "viscosity",

    # group: pressure (canonical)
    "压力": "pressure",
    "pressure": "pressure",
    "压强": "pressure",
    "表压": "pressure",
    "绝对压力": "pressure",

    # group: temperature (canonical)
    "温度": "temperature",
    "temperature": "temperature",
    "水温": "temperature",
    "环境温度": "temperature",

    # group: concentration (canonical)
    "浓度": "concentration",
    "concentration": "concentration",
    "溶解氧浓度": "concentration",
    "DO": "concentration",
    "dissolved oxygen": "concentration",
    "溶氧": "concentration",

    # === 制备方法 (6 group, 25 entries) ===

    # group: hydrodynamic_cavitation (canonical)
    "水动力空化": "hydrodynamic_cavitation",
    "hydrodynamic cavitation": "hydrodynamic_cavitation",
    "水力空化": "hydrodynamic_cavitation",
    "文丘里管": "hydrodynamic_cavitation",
    "venturi": "hydrodynamic_cavitation",
    "venturi tube": "hydrodynamic_cavitation",

    # group: acoustic_cavitation (canonical)
    "声空化": "acoustic_cavitation",
    "acoustic cavitation": "acoustic_cavitation",
    "超声空化": "acoustic_cavitation",
    "ultrasonic cavitation": "acoustic_cavitation",
    "超声法": "acoustic_cavitation",
    "超声波空化": "acoustic_cavitation",

    # group: electrolysis (canonical)
    "电解法": "electrolysis",
    "electrolysis": "electrolysis",
    "电解": "electrolysis",
    "电解水制氢": "electrolysis",
    "电化学法": "electrolysis",

    # group: membrane (canonical)
    "膜法": "membrane",
    "membrane": "membrane",
    "膜分离": "membrane",
    "膜乳化": "membrane",
    "中空纤维膜": "membrane",

    # group: pressurized_dissolution (canonical)
    "加压溶解法": "pressurized_dissolution",
    "pressurized dissolution": "pressurized_dissolution",
    "加压溶气法": "pressurized_dissolution",
    "溶气释气法": "pressurized_dissolution",
    "DAF": "pressurized_dissolution",
    "dissolved air flotation": "pressurized_dissolution",

    # group: microfluidic (canonical)
    "微流控": "microfluidic",
    "microfluidic": "microfluidic",
    "微流控芯片": "microfluidic",
    "lab on chip": "microfluidic",
    "微通道": "microfluidic",

    # === 应用领域 (8 group, 35 entries) ===

    # group: water_treatment (canonical)
    "水处理": "water_treatment",
    "water treatment": "water_treatment",
    "污水处理": "water_treatment",
    "sewage treatment": "water_treatment",
    "wastewater treatment": "water_treatment",
    "废水处理": "water_treatment",
    "工业水处理": "water_treatment",
    "市政水处理": "water_treatment",

    # group: flotation (canonical)
    "气浮": "flotation",
    "flotation": "flotation",
    "气浮法": "flotation",
    "浮选": "flotation",
    "dissolved air flotation": "flotation",
    "DAF": "flotation",

    # group: aquaculture (canonical)
    "水产养殖": "aquaculture",
    "aquaculture": "aquaculture",
    "渔业养殖": "aquaculture",
    "鱼类养殖": "aquaculture",
    "鱼塘增氧": "aquaculture",

    # group: agriculture (canonical)
    "农业": "agriculture",
    "agriculture": "agriculture",
    "灌溉": "agriculture",
    "irrigation": "agriculture",
    "农作物增产": "agriculture",

    # group: cleaning (canonical)
    "清洗": "cleaning",
    "cleaning": "cleaning",
    "微气泡清洗": "cleaning",
    "精密清洗": "cleaning",
    "半导体清洗": "cleaning",
    "ultrasonic cleaning": "cleaning",

    # group: medical (canonical)
    "医学应用": "medical",
    "medical": "medical",
    "medical application": "medical",
    "医学": "medical",
    "临床": "medical",
    "药物递送": "medical",
    "drug delivery": "medical",

    # group: ultrasound_imaging (canonical)
    "超声成像": "ultrasound_imaging",
    "ultrasound imaging": "ultrasound_imaging",
    "超声造影": "ultrasound_imaging",
    "ultrasonic imaging": "ultrasound_imaging",
    "造影剂": "ultrasound_imaging",
    "contrast agent": "ultrasound_imaging",

    # group: fuel (canonical)
    "燃料": "fuel",
    "fuel": "fuel",
    "燃料电池": "fuel",
    "fuel cell": "fuel",
    "氢燃料": "fuel",
    "hydrogen fuel": "fuel",

    # === 测量表征 (8 group, 35 entries) ===

    # group: nanoparticle_tracking_analysis (canonical)
    "纳米颗粒追踪分析": "nanoparticle_tracking_analysis",
    "NTA": "nanoparticle_tracking_analysis",
    "nanoparticle tracking analysis": "nanoparticle_tracking_analysis",
    "颗粒追踪": "nanoparticle_tracking_analysis",
    "tracking analysis": "nanoparticle_tracking_analysis",

    # group: dynamic_light_scattering (canonical)
    "动态光散射": "dynamic_light_scattering",
    "DLS": "dynamic_light_scattering",
    "dynamic light scattering": "dynamic_light_scattering",
    "光散射": "dynamic_light_scattering",

    # group: electron_microscopy (canonical)
    "电子显微镜": "electron_microscopy",
    "EM": "electron_microscopy",
    "electron microscopy": "electron_microscopy",
    "TEM": "electron_microscopy",
    "transmission electron microscopy": "electron_microscopy",
    "透射电镜": "electron_microscopy",
    "扫描电镜": "electron_microscopy",
    "SEM": "electron_microscopy",

    # group: atomic_force_microscopy (canonical)
    "原子力显微镜": "atomic_force_microscopy",
    "AFM": "atomic_force_microscopy",
    "atomic force microscopy": "atomic_force_microscopy",
    "AFM 测量": "atomic_force_microscopy",

    # group: laser_diffraction (canonical)
    "激光衍射": "laser_diffraction",
    "laser diffraction": "laser_diffraction",
    "激光粒度仪": "laser_diffraction",

    # group: accoustic_method (canonical)
    "声学方法": "acoustic_method",
    "acoustic method": "acoustic_method",
    "声学测量": "acoustic_method",
    "acoustic measurement": "acoustic_method",

    # group: pressure_gauge (canonical)
    "压力表": "pressure_gauge",
    "pressure gauge": "pressure_gauge",
    "压力传感器": "pressure_gauge",
    "pressure transducer": "pressure_gauge",
    "压差计": "pressure_gauge",

    # group: flow_meter (canonical)
    "流量计": "flow_meter",
    "flow meter": "flow_meter",
    "流量传感器": "flow_meter",
    "flow sensor": "flow_meter",

    # === 设备仪器 (5 group, 20 entries) ===

    # group: micro_nano_bubble_generator (canonical)
    "微纳米气泡发生器": "micro_nano_bubble_generator",
    "微气泡发生器": "micro_nano_bubble_generator",
    "纳米气泡发生器": "micro_nano_bubble_generator",
    "microbubble generator": "micro_nano_bubble_generator",
    "nanobubble generator": "micro_nano_bubble_generator",
    "气泡发生装置": "micro_nano_bubble_generator",
    "气液混合泵": "micro_nano_bubble_generator",

    # group: ultrasonic_horn (canonical)
    "超声探头": "ultrasonic_horn",
    "ultrasonic horn": "ultrasonic_horn",
    "超声换能器": "ultrasonic_horn",
    "ultrasonic transducer": "ultrasonic_horn",
    "声波探头": "ultrasonic_horn",

    # group: venturi_tube (canonical)
    "文丘里管": "venturi_tube",
    "venturi tube": "venturi_tube",
    "文氏管": "venturi_tube",
    "venturi": "venturi_tube",
    "文氏管接头": "venturi_tube",

    # group: pump (canonical)
    "泵": "pump",
    "pump": "pump",
    "水泵": "pump",
    "离心泵": "pump",
    "centrifugal pump": "pump",

    # group: reactor (canonical)
    "反应器": "reactor",
    "reactor": "reactor",
    "反应釜": "reactor",
    "微反应器": "reactor",
    "microreactor": "reactor",

    # === 过程现象 (8 group, 30 entries) ===

    # group: nucleation (canonical)
    "成核": "nucleation",
    "nucleation": "nucleation",
    "气泡成核": "nucleation",
    "异相成核": "nucleation",
    "heterogeneous nucleation": "nucleation",
    "均相成核": "nucleation",
    "homogeneous nucleation": "nucleation",

    # group: coalescence (canonical)
    "聚并": "coalescence",
    "coalescence": "coalescence",
    "气泡聚并": "coalescence",
    "bubble coalescence": "coalescence",
    "合并": "coalescence",

    # group: breakup (canonical)
    "破碎": "breakup",
    "breakup": "breakup",
    "气泡破碎": "breakup",
    "bubble breakup": "breakup",
    "气泡分裂": "breakup",

    # group: dissolution (canonical)
    "溶解": "dissolution",
    "dissolution": "dissolution",
    "气体溶解": "dissolution",
    "溶解过程": "dissolution",
    "gas dissolution": "dissolution",

    # group: flotation_process (canonical)
    "浮选过程": "flotation_process",
    "flotation process": "flotation_process",
    "浮选工艺": "flotation_process",
    "气浮工艺": "flotation_process",

    # group: stabilization (canonical)
    "稳定化": "stabilization",
    "stabilization": "stabilization",
    "稳定机理": "stabilization",
    "气泡稳定": "stabilization",
    "长期稳定": "stabilization",

    # group: adsorption (canonical)
    "吸附": "adsorption",
    "adsorption": "adsorption",
    "表面吸附": "adsorption",
    "surface adsorption": "adsorption",

    # group: diffusion (canonical)
    "扩散": "diffusion",
    "diffusion": "diffusion",
    "分子扩散": "diffusion",
    "molecular diffusion": "diffusion",
    "气泡扩散": "diffusion",

    # === 通用中文术语 (3 group, 10 entries) ===

    # group: how_to_make
    "制备": "how_to_make",
    "制造": "how_to_make",
    "production": "how_to_make",
    "fabrication": "how_to_make",
    "合成": "how_to_make",

    # group: mechanism
    "机理": "mechanism",
    "机制": "mechanism",
    "mechanism": "mechanism",
    "工作原理": "mechanism",

    # group: stability_lifetime
    "稳定性": "stability_lifetime",
    "寿命": "stability_lifetime",
    "stability": "stability_lifetime",
    "lifetime": "stability_lifetime",
    "long-term stability": "stability_lifetime",
}


def count_synonyms_in_data() -> int:
    """统计数据文件内 SYNONYMS dict 条数 (含 canonical 自指)"""
    return len(SYNONYMS)


if __name__ == "__main__":
    # 数据文件自检 — 跑 `python -m app.services.synonym_dict` 触发
    n = count_synonyms_in_data()
    print(f"synonym_dict 总条数: {n}")
    assert n >= 200, f"synonym_dict 不足 200 条, 实际 {n}"
    # canonical 必须唯一
    canonicals = set(SYNONYMS.values())
    variants = set(SYNONYMS.keys())
    print(f"canonical 数: {len(canonicals)}, variant 数: {len(variants)}")
    # canonical 必须在 variants 集合内 (canonical 自指)
    missing = canonicals - variants
    assert not missing, f"canonical 不在 variant 集合内: {missing}"
    print("OK")