"""Small built-in Chinese name -> canonical SMILES dictionary.

Curated, offline-only entries. Values must be valid SMILES;
``tests/test_naming.py`` parses every entry to keep this table honest. A
larger vocabulary can later ship as an opt-in data extra; the core package
stays tiny and dependency-free.
"""

from __future__ import annotations

ZH_NAMES: dict[str, str] = {
    # Blind-test molecules (§11)
    "苯甲酸": "OC(=O)c1ccccc1",
    "咖啡因": "Cn1cnc2c1c(=O)n(C)c(=O)n2C",
    "布洛芬": "CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O",
    "阿司匹林": "CC(=O)Oc1ccccc1C(=O)O",
    "乙酰水杨酸": "CC(=O)Oc1ccccc1C(=O)O",
    "香兰素": "COc1cc(C=O)ccc1O",
    "香草醛": "COc1cc(C=O)ccc1O",
    "芳樟醇": "CC(C)=CCCC(C)(O)C=C",
    "β-大马酮": "CC(=O)/C=C/C1=C(C)CCCC1(C)C",
    "胆固醇": "CC(C)CCC[C@@H](C)[C@H]1CC[C@@H]2[C@@]1(C)CC[C@H]1[C@H]2CC=C2C[C@@H](O)CC[C@]12C",
    "胆甾醇": "CC(C)CCC[C@@H](C)[C@H]1CC[C@@H]2[C@@]1(C)CC[C@H]1[C@H]2CC=C2C[C@@H](O)CC[C@]12C",
    "青霉素G": "CC1(C)S[C@@H]2[C@H](NC(=O)Cc3ccccc3)C(=O)N2[C@H]1C(=O)O",
    "苄青霉素": "CC1(C)S[C@@H]2[C@H](NC(=O)Cc3ccccc3)C(=O)N2[C@H]1C(=O)O",
    "18-冠-6": "C1COCCOCCOCCOCCOCCO1",
    "18-冠醚-6": "C1COCCOCCOCCOCCOCCO1",
    "卟啉": "c1cc2cc3ccc(cc4ccc(cc5ccc(cc1n2)[nH]5)n4)[nH]3",
    "硫酸根离子": "[O-]S(=O)(=O)[O-]",
    "甜菜碱": "C[N+](C)(C)CC([O-])=O",
    "二茂铁": "[cH-]1cccc1.[cH-]1cccc1.[Fe+2]",
    "葡萄糖": "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",
    "三苯基膦": "c1ccc(cc1)P(c1ccccc1)c1ccccc1",
    "三硝基甲苯": "Cc1c(cc(cc1[N+](=O)[O-])[N+](=O)[O-])[N+](=O)[O-]",
    "TNT": "Cc1c(cc(cc1[N+](=O)[O-])[N+](=O)[O-])[N+](=O)[O-]",
    "紫杉醇": (
        "CC1=C2[C@@]([C@]([C@H]([C@@H]3[C@]4([C@H](OC4)C[C@@H]([C@]3(C(=O)[C@@H]2OC(=O)C)C)O)"
        "OC(=O)C)OC(=O)c2ccccc2)(C[C@@H]1OC(=O)[C@H](O)[C@@H](NC(=O)c1ccccc1)c1ccccc1)O)(C)C"
    ),
    "环丙沙星": "OC(=O)c1cn(C2CC2)c2cc(N3CCNCC3)c(F)cc2c1=O",
    "偶氮苯": "c1ccc(cc1)/N=N/c1ccccc1",
    # Common solvents and reagents
    "水": "O",
    "甲烷": "C",
    "甲醇": "CO",
    "乙醇": "CCO",
    "乙腈": "CC#N",
    "丙酮": "CC(C)=O",
    "乙酸乙酯": "CCOC(C)=O",
    "四氢呋喃": "C1CCOC1",
    "二氯甲烷": "ClCCl",
    "氯仿": "ClC(Cl)Cl",
    "三氯甲烷": "ClC(Cl)Cl",
    "二甲亚砜": "CS(C)=O",
    "DMSO": "CS(C)=O",
    "N,N-二甲基甲酰胺": "CN(C)C=O",
    "DMF": "CN(C)C=O",
    "苯": "c1ccccc1",
    "甲苯": "Cc1ccccc1",
    "苯酚": "Oc1ccccc1",
    "乙酸": "CC(=O)O",
    "甲酸": "C(=O)O",
    "甲醛": "C=O",
    "乙醛": "CC=O",
    "草酸": "OC(=O)C(=O)O",
    "柠檬酸": "OC(=O)CC(O)(CC(=O)O)C(=O)O",
    "尿素": "NC(N)=O",
    "甘油": "OCC(O)CO",
    "丙三醇": "OCC(O)CO",
    "乙二醇": "OCCO",
    "过氧化氢": "OO",
    "双氧水": "OO",
    "二氧化碳": "O=C=O",
    "一氧化碳": "[C-]#[O+]",
    "氨": "N",
    "氯化钠": "[Na+].[Cl-]",
    "氢氧化钠": "[Na+].[OH-]",
    "硫酸": "OS(=O)(=O)O",
    "硝酸": "O[N+](=O)[O-]",
    "盐酸": "[Cl-]",
    # Common drugs
    "对乙酰氨基酚": "CC(=O)Nc1ccc(O)cc1",
    "扑热息痛": "CC(=O)Nc1ccc(O)cc1",
    "二甲双胍": "CN(C)C(=N)N=C(N)N",
}
