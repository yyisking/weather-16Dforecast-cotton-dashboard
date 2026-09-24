# 公开棉花看板 V0.7 展示合同

- 目标：公开展示 USDA FAS 2026 年 9 月六地供需快照（全球与中国、美国、巴西、印度、澳大利亚）、五个评分区（含澳大利亚东部棉区）和中亚十个定性天气观察 AOI。
- 输入：棉花供需决策简报 V0.2、五区 latest JSON/score daily、四区 frozen point/day 输入、澳洲七个 accepted ERA5 JSON（St George 为 gap）和 ERA5 seasonality V0.2 输入，以及中亚天气异常度 V0.2 sidecar。
- 范围：仅新建和发布本目录；不改旧 `cotton/dashboard/`、自动任务、其他作物或底层评分。
- 空值：显示“暂无可用值”或“当前阶段未纳入”，不得改写为 0。
- 解释：0—100 是当地、未校准的理论天气胁迫指数，不是减产率；五个评分区不得直接加总、排名或伪造全球天气分。中亚十个 AOI 的 `weather_anomaly_score` 是相对各自当地同期常态的偏离，不代表更不利、减产更多或可跨区排名；`weather_anomaly_score` 10/10 可用，但 `weather_stress_score`（棉花胁迫分）10/10 均保持 null，异常度不是胁迫分。
- 原始天气：五区均显示 `tmax_14d_mean`、`tmin_14d_mean`、`precip_14d_sum`、`sw_rad_14d_mean`，展示文案分别为 14日平均日最高温、14日平均日最低温、14日累计降水、14日平均日短波辐射，单位为 °C、°C、mm、MJ/m²/日；温度和辐射均为截至当日过去 14 个完整日值的算术平均，降水为过去 14 个完整日的累计。每个点先做完整 trailing-14 日窗口，再按冻结点位网络聚合。China 18 field points 等权（5 water points 排除）；Texas HP 64%/other 36%；Brazil MT 12 点等权；India 使用冻结州权重、州内点等权；Australia 7 点等权，St George 不补值。
- 原始天气若点级窗口缺一天则该点该变量为 null；payload 记录截止日实际有效点数和按冻结空间权重计算的 `current_spatial_coverage`；有效空间覆盖低于 60% 则区域为 null，不以 0 填充。当前图的截止日固定为 China/Texas/India 2026-09-13、Brazil 2026-09-16、Australia 2026-09-10；输入更晚日期不得绘图。
- 澳洲供需—天气连接：澳洲评分区详情从 brief V0.2 读取 USDA 产量和期末库存变化；显示千包（480 磅）口径与国内消费变化率缺口，不把天气指数换算为供给数量。
- 供需表固定六行；中亚 AOI 不进入供需表，仍为描述观察。其 `weather_anomaly_score` 10/10 可用；`weather_stress_score`（棉花胁迫分）10/10 保持 null，不得填成 0 或渲染为 0/100。
- 季节性页面轴只保留合同窗口：新疆 04—11 月、得州 02—11 月、巴西 MT 01—09 月、印度 06—12 月；澳洲为 2026/27 与 2025/26 的 09 月—次年 06 月跨年作季轴，5—6 月不补分；中亚 03—10 月仅为页面代理窗口，未核实当地作季。
- V0.5 季节图固定 cache key 为 `v=20260923-v05-raw-weather`。
- 原始天气与模型天气胁迫分必须分开展示。降水原值与过量降雨／收获期降雨模型分同时可见；新疆春季风害模型因子保留。原始天气不是生产影响、减产比例或单站实测。
- 太阳辐射模型状态必须保留：Brazil `included_in_model_contract`；Australia `included_and_active_in_current_stage`；China/India `observed_only_excluded_pending_dedup`；Texas `observed_only_excluded_local_direction_gap`。
- 五个评分区 seasonal payload 的分数 metric 必须声明 `scale_type=fixed_score_0_100`、`scale_min=0`、`scale_max=100` 和“0—100天气胁迫分；不是气象原值”；中亚气象原值 metric 保持 `scale_type=auto_unit`，按真实单位自动缩放。
- 每个评分 metric 的去年/今年数组必须有等长状态数组和 `active_periods`；状态只可为 `available`、`inactive_stage`、`future`、`source_gap`。历史带遇到 null 必须切断，不能跨缺口连接。
- 验收：公开页面中的供需值、评分区分数、澳洲官方供需变化、变量、日期、覆盖率、可信度、缺口和中亚季节序列必须逐源可追溯；中亚 `weather_anomaly_score` 应为 10/10 可用，`weather_stress_score`（棉花胁迫分）必须保留 null，不得渲染为 0/100。

## V0.7 产量加权展示合成与层级

- 新对象 `five_region_production_weighted_weather_stress_display` 只展示五个当地理论天气胁迫分的产量加权合成；权重读取当前 USDA 简报五区 `current_production_1000_480lb_bales`，合计 92,201 千包，禁止乘 R² 或旧全球权重。
- 固定五区权重：中国 33,500、美国 13,201、巴西 18,500、印度 24,000、澳大利亚 3,000；共同截止日为 2026-09-10，当前展示值为 34.203232814344204、覆盖率 1.0。对象必须标记 `display_only`、`not_calibrated`、`not_loss_percent`、`not_unified_model`；`global_numeric_weather_score` 仍为 null，`cross_region_weather_comparable` 仍为 false。
- 合成季节图固定 04-01—11-30，历史 2015—2024、去年 2025、今年 2026 至共同截止日；逐日按有效产量权重计算，覆盖低于 0.60 输出 null/status `coverage_below_gate`，不得补 0。逐日记录 coverage 与 `valid_region_ids`；历史带不补造澳洲历史分，且页面披露地区组合变化可能同时影响曲线。
- 产量加权展示标题和 payload `label` 固定为 `全球棉花五大种植区域天气胁迫总评分（产区产量加权）`，对象 ID 保持 `five_region_production_weighted_weather_stress_display`；总分使用独立 CSS class，桌面字号至少 56px，点击仍打开原季节图。
- 权重表置于默认关闭的原生 `<details>`，summary 精确为 `产量加权详情`；表格在展开后显示。
- V0.7 title、H1、dashboard_id 和 cache key 同步升级；cache key 固定为 `v=20260924-v07-display-hierarchy`。raw 降水与短波辐射 metric 标记 `nonnegative=true`，自动轴下界不得因 padding 为负；五区太阳辐射卡显示各区冻结中文模型状态。
