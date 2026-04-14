"""
64轮全面推演 — 卦象引擎出师表
四幕结构，每幕16轮，模拟完整人生弧线
"""
import sys
import io
import tempfile
import os
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))

from evolution.hexagram import HexagramEngine, HEXAGRAM_STRATEGIES, LINE_KEYWORDS

tmpdir = tempfile.mkdtemp(dir=os.environ.get('TEMP', '/tmp'))
eng = HexagramEngine(tmpdir)

# ═══════════════════════════════════════════════════════════════
# 64轮剧本：一个人的创业十年
# ═══════════════════════════════════════════════════════════════

SCRIPT = [
    # ━━ 第一幕：创业起步（R01-R16）━━
    # 从迷茫到找到方向，合伙人背叛、资金断裂、独自撑下来
    ("最近压力特别大，电商越来越难做了，流量太贵烧不起", 0.20),
    ("是啊不知道怎么办，每天焦虑到失眠", 0.18),
    ("有没有什么方向可以转型？我纠结了好久了", 0.22),
    ("短视频？感觉也卷，而且我没团队没资源没人脉", 0.20),
    ("合伙人上个月跑路了，欠我20万，现在就剩我一个人撑着", 0.12),
    ("想过放弃但又不甘心，这行我干了五年了", 0.25),
    ("昨天一个老客户主动找我说想聊聊合作", 0.35),
    ("谈了，他有个渠道缺供应商，但我现在没钱备货", 0.30),
    ("借了亲戚5万块先备了第一批货，心里没底", 0.28),
    ("第一批货发出去了，等反馈中，焦虑", 0.30),
    ("居然卖完了！虽然只赚了8000但证明方向对了", 0.55),
    ("又进了一批货，这次量大了一倍，有点慌", 0.45),
    ("第二批也卖得不错，开始有回头客了", 0.60),
    ("这个月终于回正了，虽然利润薄但活下来了", 0.65),
    ("决定了，就专注做家居供应链这条线", 0.70),
    ("拿到了第一个月度稳定订单，终于能喘口气了", 0.75),

    # ━━ 第二幕：扩张危机（R17-R32）━━
    # 团队扩大、融资、竞争加剧、核心员工被挖、供应链断裂
    ("准备招人了，一个运营一个客服", 0.70),
    ("融到了朋友投的50万天使轮，准备扩品类", 0.80),
    ("团队扩到8个人了，流水翻了三倍", 0.85),
    ("目标很清楚，三年做到家居类目前十", 0.85),
    ("竞争对手开始模仿我的选品策略了", 0.55),
    ("核心运营被对手挖走了，还带走了客户资源", 0.30),
    ("供应商突然涨价30%，利润直接腰斩", 0.25),
    ("这个月现金流告急，工资差点发不出来", 0.20),
    ("投资人开始催下一轮数据，但数据在下滑", 0.22),
    ("仓库被房东临时通知要收回，搬仓成本巨大", 0.18),
    ("两个老员工也提了离职，说看不到希望", 0.15),
    ("银行贷款到期，没钱还，逾期了", 0.12),
    ("供应链彻底断了，核心供应商跑去做我竞争对手了", 0.10),
    ("投资人说如果下个月数据不回来就撤资", 0.10),
    ("老婆说你要么关掉公司要么我们离婚", 0.08),
    ("扛不住了，决定裁员到3个人先活下来", 0.15),

    # ━━ 第三幕：重建与转型（R33-R48）━━
    # 废墟中重新开始、砍业务、换赛道、感情破裂、自我怀疑
    ("裁完员了，留下的三个人都是最能打的", 0.25),
    ("砍掉了所有亏损品类，只留两个最赚钱的", 0.30),
    ("前合伙人突然联系我说想回来，纠结要不要接受", 0.28),
    ("拒绝了他，不想重蹈覆辙，自己扛", 0.35),
    ("老婆真的提了离婚，签了协议", 0.10),
    ("离婚后一个人住，有时候半夜会怀疑自己到底在干嘛", 0.12),
    ("但白天上班还是打起精神，团队不能散", 0.25),
    ("试了一个新品类意外爆了，利润比之前高很多", 0.50),
    ("原来我之前方向就不对，一直在红海里卷", 0.45),
    ("开始研究高端定制家居，利润率完全不一样", 0.55),
    ("第一个高端客户成了，客单价是之前的十倍", 0.65),
    ("慢慢找到节奏了，虽然规模不大但利润稳了", 0.60),
    ("招了一个很靠谱的合伙人，互补型", 0.70),
    ("新合伙人带来了渠道资源，业务开始加速", 0.75),
    ("这个季度利润破纪录了，比扩张期还好", 0.80),
    ("重新租了大仓库，这次稳了再动", 0.78),

    # ━━ 第四幕：成熟与抉择（R49-R64）━━
    # 天花板、收购邀约、要不要上市、团队分裂、最终抉择
    ("年营收过了千万，但增速在放缓", 0.65),
    ("有个上市公司找我谈收购，开了个不错的价", 0.55),
    ("团队里有人想卖有人不想卖，开始分裂了", 0.40),
    ("合伙人觉得应该卖，我觉得还能再冲一冲", 0.38),
    ("收购方给了最后通牒，一周内决定", 0.35),
    ("跟合伙人吵了一架，差点闹翻", 0.25),
    ("冷静下来谈了一晚上，决定拒绝收购继续独立", 0.45),
    ("拒绝后团队士气反而起来了，说跟你干", 0.60),
    ("但得找到新的增长点，不能只靠现有品类", 0.50),
    ("开始做自有品牌，从渠道商转品牌商", 0.55),
    ("第一个自有品牌产品上线了，反馈褒贬不一", 0.45),
    ("调整了产品定位后第二版卖爆了", 0.70),
    ("拿到了A轮融资，估值过亿", 0.80),
    ("前妻打电话来恭喜，聊了很久", 0.50),
    ("团队50个人了，管理比做业务难多了", 0.45),
    ("三年过去了，终于做到了类目前十，当初的目标达成了", 0.85),
]

assert len(SCRIPT) == 64, f"Script has {len(SCRIPT)} rounds, expected 64"

# ═══════════════════════════════════════════════════════════════
# 执行推演
# ═══════════════════════════════════════════════════════════════

ACT_NAMES = {1: "创业起步", 2: "扩张危机", 3: "重建转型", 4: "成熟抉择"}
ACT_RANGES = {1: (1, 16), 2: (17, 32), 3: (33, 48), 4: (49, 64)}

all_msgs = []
records = []

print("═" * 85)
print("64轮全面推演 — 卦象引擎出师表")
print("═" * 85)

for i, (msg, rate) in enumerate(SCRIPT):
    r = i + 1
    act = 1 if r <= 16 else (2 if r <= 32 else (3 if r <= 48 else 4))
    all_msgs.append(msg)
    recent = all_msgs[-5:]

    old_hex = eng.current_hexagram
    old_lines = eng.current_lines.copy()
    result = eng.divine(recent, rate)

    lines = result["current"]["lines"]
    yin_count = sum(1 for l in lines if l == 0)
    lines_str = "".join("⚊" if l == 1 else "⚋" for l in lines)
    changing_dims = [eng.LINE_NAMES[c][1] for c in result["changing_lines"]]
    strat = result["current"]["strategy"]

    # 策略适配度评分: 累加制（基础3分，加减分后 clamp 到 1-5）
    _fit = 3.0

    # ── 扣分：状态与策略矛盾 ──
    # 低谷给进攻策略（严重错配）
    _attack_phrases = ["扩张", "大胆", "全面向好", "加速", "趁势", "好时机", "主动权", "万事俱备", "鼎盛"]
    if rate < 0.2 and any(p in strat for p in _attack_phrases):
        _fit -= 2.0
    elif rate < 0.3 and any(p in strat for p in _attack_phrases[:4]):
        _fit -= 1.0

    # 高峰给撤退策略（轻度错配）
    _retreat_phrases = ["撤退", "止损", "蛰伏", "放弃", "耗尽"]
    if rate > 0.7 and any(p in strat for p in _retreat_phrases):
        _fit -= 1.0

    # ── 加分：状态与策略匹配 ──
    # 犹豫期给了决断建议
    _hesitate_words = ["犹豫", "纠结", "要不要"]
    _decide_phrases = ["当断", "做决定", "别犹豫", "选一个"]
    if any(w in msg for w in _hesitate_words) and any(p in strat for p in _decide_phrases):
        _fit += 1.5

    # 低谷给了防守/稳定建议（完整短语防误匹配）
    _defend_phrases = ["守住", "稳住", "止损", "等待", "蓄力", "穿越", "直面",
                       "清醒", "一步步", "先理清", "先别", "调好", "别急", "不急",
                       "先活", "先确保", "韬光养晦"]
    if rate < 0.25 and any(p in strat for p in _defend_phrases):
        _fit += 1.5

    # 中间期给了过渡建议
    _transit_phrases = ["坚持", "一步步", "内在", "理清", "化解", "找到", "整顿"]
    if 0.25 <= rate <= 0.5 and any(p in strat for p in _transit_phrases):
        _fit += 1.0

    # 高峰期给了进攻建议
    _push_phrases = ["推进", "扩张", "加码", "全力", "趁势", "打出去", "壁垒", "变现"]
    if rate > 0.6 and any(p in strat for p in _push_phrases):
        _fit += 1.5

    # ── 动爻维度加分 ──
    # 如果动爻维度和策略主题一致，额外 +0.5
    _changing = result.get("changing_lines", [])
    if _changing:
        _dim_keywords = {
            0: ["情绪", "心态", "感觉"],   # 情绪基底
            1: ["行动", "做", "动", "执行"],  # 行动力
            2: ["认知", "想清楚", "看清"],   # 认知清晰度
            3: ["资源", "钱", "人"],         # 资源状态
            4: ["方向", "目标", "路"],       # 方向感
            5: ["满意", "值得", "意义"],     # 整体满意度
        }
        for c in _changing[:1]:  # 只看第一个动爻
            for kw in _dim_keywords.get(c, []):
                if kw in strat:
                    _fit += 0.5
                    break

    # clamp 到 1-5 整数
    fit_score = max(1, min(5, round(_fit)))

    rec = {
        "r": r, "act": act, "msg": msg, "rate": rate,
        "hex": result["current"]["hexagram"],
        "hex_name": result["current"]["name"],
        "future_hex": result["future"]["hexagram"],
        "future_name": result["future"]["name"],
        "lines": lines[:], "yin": yin_count,
        "changing": result["changing_lines"],
        "changing_dims": changing_dims,
        "strategy": strat,
        "style": HEXAGRAM_STRATEGIES.get(result["current"]["hexagram"], {}).get("style", ""),
        "display": result["display"],
        "fit": fit_score,
    }
    records.append(rec)

    # Print each round
    act_label = ACT_NAMES[act]
    if r in [1, 17, 33, 49]:
        print(f"\n{'━' * 85}")
        print(f"第{act}幕：{act_label}（R{ACT_RANGES[act][0]:02d}-R{ACT_RANGES[act][1]:02d}）")
        print(f"{'━' * 85}")

    fit_star = "★" * fit_score + "☆" * (5 - fit_score)
    print(f"\nR{r:02d} {lines_str} {rec['hex_name']:8s} 阴{yin_count} 率{rate:.0%} {fit_star}")
    print(f"   「{msg[:40]}{'…' if len(msg)>40 else ''}」")
    print(f"   → {result['display']}")

# ═══════════════════════════════════════════════════════════════
# 复 盘
# ═══════════════════════════════════════════════════════════════

print(f"\n\n{'═' * 85}")
print("复 盘")
print(f"{'═' * 85}")

# ── 1. 卦象覆盖率 ──
print(f"\n{'─' * 60}")
print("一、卦象覆盖率（目标≥40/64）")
print(f"{'─' * 60}")
main_hexagrams = set(r["hex"] for r in records)
future_hexagrams = set(r["future_hex"] for r in records)
all_hexagrams = main_hexagrams | future_hexagrams
print(f"主卦出现: {len(main_hexagrams)}/64")
print(f"变卦出现: {len(future_hexagrams)}/64")
print(f"合计覆盖: {len(all_hexagrams)}/64 ({'✓ 达标' if len(all_hexagrams)>=40 else '✗ 未达标'})")

# By act
for act in [1, 2, 3, 4]:
    act_hexes = set(r["hex"] for r in records if r["act"] == act)
    act_futures = set(r["future_hex"] for r in records if r["act"] == act)
    print(f"  第{act}幕: 主卦{len(act_hexes)}种 变卦{len(act_futures)}种 合计{len(act_hexes|act_futures)}种")

never_seen = set(HEXAGRAM_STRATEGIES.keys()) - all_hexagrams
if never_seen:
    print(f"从未触发({len(never_seen)}): {' '.join(sorted(never_seen)[:15])}{'…' if len(never_seen)>15 else ''}")

# ── 2. 卦象轨迹 ──
print(f"\n{'─' * 60}")
print("二、卦象轨迹（阴爻数=困难指数）")
print(f"{'─' * 60}")
for rec in records:
    bar = "■" * rec["yin"] + "□" * (6 - rec["yin"])
    act_mark = "│" if rec["r"] not in [1, 17, 33, 49] else "┃"
    print(f"R{rec['r']:02d} {bar} {rec['hex_name']:8s} →{rec['future_name']:8s} 率{rec['rate']:.0%}")

# ── 3. 相变点分析 ──
print(f"\n{'─' * 60}")
print("三、相变点（卦象质变时刻）")
print(f"{'─' * 60}")
phase_changes = []
prev_hex = None
for rec in records:
    if prev_hex and rec["hex"] != prev_hex:
        phase_changes.append(rec)
        dims = ",".join(rec["changing_dims"]) if rec["changing_dims"] else "无"
        print(f"R{rec['r']:02d} {prev_hex} → {rec['hex']}  动爻:{dims}  率{rec['rate']:.0%}")
    prev_hex = rec["hex"]
print(f"总相变: {len(phase_changes)}次 (64轮中{len(phase_changes)/64:.0%})")

# ── 4. 衰减周期统计 ──
print(f"\n{'─' * 60}")
print("四、衰减周期统计")
print(f"{'─' * 60}")
# How long does each hexagram persist?
streaks = []
current_streak_hex = records[0]["hex"]
current_streak_start = 1
for rec in records[1:]:
    if rec["hex"] != current_streak_hex:
        streaks.append((current_streak_hex, current_streak_start, rec["r"] - 1,
                        rec["r"] - current_streak_start))
        current_streak_hex = rec["hex"]
        current_streak_start = rec["r"]
streaks.append((current_streak_hex, current_streak_start, 64,
                64 - current_streak_start + 1))

long_streaks = [s for s in streaks if s[3] >= 3]
if long_streaks:
    print("持续≥3轮的卦象:")
    for hex_name, start, end, length in long_streaks:
        full_name = HEXAGRAM_STRATEGIES.get(hex_name, {}).get("name", hex_name)
        print(f"  {full_name:8s} R{start:02d}-R{end:02d} ({length}轮)")

avg_persist = sum(s[3] for s in streaks) / len(streaks)
print(f"平均持续: {avg_persist:.1f}轮/卦")
print(f"最长持续: {max(s[3] for s in streaks)}轮 ({[s for s in streaks if s[3]==max(ss[3] for ss in streaks)][0][0]})")

# ── 5. 策略适配度 ──
print(f"\n{'─' * 60}")
print("五、策略适配度")
print(f"{'─' * 60}")
fits = [r["fit"] for r in records]
avg_fit = sum(fits) / len(fits)
print(f"平均适配度: {avg_fit:.1f}/5")
for act in [1, 2, 3, 4]:
    act_fits = [r["fit"] for r in records if r["act"] == act]
    act_avg = sum(act_fits) / len(act_fits)
    low_fits = [r for r in records if r["act"] == act and r["fit"] <= 2]
    print(f"  第{act}幕({ACT_NAMES[act]}): {act_avg:.1f}/5  {'⚠ 错配'+str(len(low_fits))+'轮' if low_fits else '✓'}")
    for r in low_fits:
        print(f"    R{r['r']:02d} 率{r['rate']:.0%} {r['hex_name']} 「{r['strategy'][:25]}」")

# ── 6. 六爻维度热力图 ──
print(f"\n{'─' * 60}")
print("六、六爻维度热力图")
print(f"{'─' * 60}")
dim_names = ["情绪", "行动", "认知", "资源", "方向", "满意"]
# Header
print(f"     {''.join(f'{d:6s}' for d in dim_names)}")
for rec in records:
    vals = ""
    for l in rec["lines"]:
        vals += "  ██  " if l == 0 else "  ░░  "
    r = rec["r"]
    marker = " "
    if r in [1, 17, 33, 49]:
        marker = "▸"
    print(f"{marker}R{r:02d} {vals}")

# Dimension statistics
print(f"\n各维度阴爻占比:")
for dim_idx, dim_name in enumerate(dim_names):
    yin_count = sum(1 for r in records if r["lines"][dim_idx] == 0)
    pct = yin_count / 64
    bar = "█" * int(pct * 20) + "░" * (20 - int(pct * 20))
    print(f"  {dim_name} {bar} {pct:.0%} ({yin_count}/64轮为阴)")

# Dimension by act
print(f"\n各幕各维度阴爻率:")
print(f"      {''.join(f'{d:8s}' for d in dim_names)}")
for act in [1, 2, 3, 4]:
    act_recs = [r for r in records if r["act"] == act]
    vals = ""
    for dim_idx in range(6):
        yin_pct = sum(1 for r in act_recs if r["lines"][dim_idx] == 0) / len(act_recs)
        vals += f"  {yin_pct:5.0%} "
    print(f"  幕{act} {vals}")

# ── 7. 动爻频率 ──
print(f"\n{'─' * 60}")
print("七、动爻维度频率")
print(f"{'─' * 60}")
dim_change_counts = Counter()
for rec in records:
    for c in rec["changing"]:
        dim_change_counts[eng.LINE_NAMES[c][1]] += 1
for dim, cnt in dim_change_counts.most_common():
    pct = cnt / 64
    bar = "█" * int(pct * 20)
    print(f"  {dim:8s} {bar} {cnt}次 ({pct:.0%})")

# ── 8. 总评 ──
print(f"\n{'─' * 60}")
print("八、总评")
print(f"{'─' * 60}")

scores = {
    "卦象覆盖": (min(len(all_hexagrams) / 40, 1.0), f"{len(all_hexagrams)}/64"),
    "策略适配": (avg_fit / 5, f"{avg_fit:.1f}/5"),
    "相变敏感": (min(len(phase_changes) / 30, 1.0), f"{len(phase_changes)}次相变"),
    "衰减合理": (1.0 if 1.5 <= avg_persist <= 4.0 else 0.5, f"均{avg_persist:.1f}轮/卦"),
}

total = 0
for name, (score, detail) in scores.items():
    stars = "★" * int(score * 5) + "☆" * (5 - int(score * 5))
    print(f"  {name}: {stars} ({detail})")
    total += score

overall = total / len(scores)
print(f"\n  综合评分: {overall:.0%}")
if overall >= 0.8:
    print("  评语: 卦象引擎基本成熟，可以上线实战")
elif overall >= 0.6:
    print("  评语: 核心功能可用，部分场景需要优化")
else:
    print("  评语: 存在系统性问题，需要重大修改")
