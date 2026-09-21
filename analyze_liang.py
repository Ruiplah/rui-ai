# -*- coding: utf-8 -*-
"""理想.xlsx 六项指令完整分析（修正版指令1：按用户聊天内容总结表达的意思）"""
import json, re
from collections import Counter, defaultdict
from datetime import datetime

rows = json.load(open(r"D:\llama\liangxiang_rows.json", encoding="utf-8"))
total = len(rows)
print("总消息数:", total)

# ---------- 工具函数 ----------
def split_kw(s):
    return [x.strip() for x in re.split(r"[、，,；;]", s) if x.strip()]

def hour_key(ts):
    try:
        return datetime.strptime(ts.strip(), "%Y-%m-%d %H:%M:%S").strftime("%H时")
    except Exception:
        return None

# ============================================================
# 指令1（修正版）：根据聊天内容总结每个用户表达的意思
# ============================================================
user_msgs = defaultdict(list)
for r in rows:
    user_msgs[r.get("群成员名称", "")].append(r)

print("\n" + "=" * 60)
print("【指令1】按用户总结所表达的意思")
user_summaries = []
for name, msgs in sorted(user_msgs.items(), key=lambda x: -len(x[1])):
    if not name:
        continue
    contents = [m.get("发言内容", "") for m in msgs if m.get("发言内容")]
    kws = [k for m in msgs for k in split_kw(m.get("关键词", ""))]
    negs = [k for m in msgs for k in split_kw(m.get("负向词", ""))]
    poss = [k for m in msgs for k in split_kw(m.get("正向词", ""))]
    labels = [m.get("舆情标签", "") for m in msgs]
    stance = "负面" if labels.count("负向") > labels.count("正向") and labels.count("负向") >= labels.count("中性") else ("正向" if labels.count("正向") > labels.count("负向") else "中性")
    kw_top = Counter(kws).most_common(3)
    sample = contents[0][:60] if contents else ""
    user_summaries.append((name, len(msgs), kw_top, negs[:2], poss[:2], stance, sample))
    print(f"- {name}（{len(msgs)}条，{stance}）关键词:{kw_top} 示例:{sample}")

# ============================================================
# 指令2：每小时群总会话数
# ============================================================
print("\n" + "=" * 60)
print("【指令2】每小时会话数")
hour_cnt = Counter()
hour_users = defaultdict(set)
for r in rows:
    h = hour_key(r.get("发言时间", ""))
    if h:
        hour_cnt[h] += 1
        hour_users[h].add(r.get("群成员名称", ""))
hour_items = sorted(hour_cnt.items())
total_hour = sum(hour_cnt.values())
print("时段分布:", hour_items, "| 总数:", total_hour)
peak_h = max(hour_cnt, key=hour_cnt.get)
print("最高峰:", peak_h, hour_cnt[peak_h], "条")

# ============================================================
# 指令3：热点话题深度分析（数量及对话占比）
# ============================================================
print("\n" + "=" * 60)
print("【指令3】热点话题")
topic_cnt = Counter()
for r in rows:
    for k in split_kw(r.get("关键词", "")):
        topic_cnt[k] += 1
    # 二级关注点也算话题维度
    for k in split_kw(r.get("二级关注点", "")):
        topic_cnt["[" + k + "]"] += 1
top_topics = topic_cnt.most_common(15)
print("话题TOP:", top_topics)

# ============================================================
# 指令4：热门产品点表格 + 用户态度
# ============================================================
print("\n" + "=" * 60)
print("【指令4】热门产品点 + 用户态度")
product_kws = ["L8", "L9", "MEGA", "音响", "屏幕", "移动屏", "版本", "尾款", "补贴", "床垫", "赠品", "降价", "价格", "提车", "交付", "保险", "配置"]
prod_stat = {}
for r in rows:
    content = (r.get("发言内容", "") or "") + (r.get("关键词", "") or "")
    senti = r.get("舆情标签", "") or "中性"
    for pk in product_kws:
        if pk.lower() in content.lower():
            s = prod_stat.setdefault(pk, Counter())
            s[senti] += 1
prod_items = sorted(prod_stat.items(), key=lambda x: -sum(x[1].values()))[:12]
for pk, s in prod_items:
    print(f"- {pk}: 正向{s['正向']} 中性{s['中性']} 负向{s['负向']} | 共{sum(s.values())}条")

# ============================================================
# 指令5：活跃用户TOP10 + 观点 + 用户类型
# ============================================================
print("\n" + "=" * 60)
print("【指令5】活跃用户TOP10")
user_cnt = Counter(r.get("群成员名称", "") for r in rows)
top10 = user_cnt.most_common(10)
print("TOP10:", top10)
# 重点用户观点（TOP3）抽样
for name, c in top10[:3]:
    msgs = user_msgs[name]
    contents = [m.get("发言内容", "") for m in msgs if m.get("发言内容")]
    kws = [k for m in msgs for k in split_kw(m.get("关键词", ""))]
    negs = [k for m in msgs for k in split_kw(m.get("负向词", ""))]
    poss = [k for m in msgs for k in split_kw(m.get("正向词", ""))]
    print(f"  重点用户 {name}: {c}条 关键词{Counter(kws).most_common(3)} 负向{Counter(negs).most_common(2)} 正向{Counter(poss).most_common(2)}")
    print(f"    代表发言: {contents[:3]}")

# ============================================================
# 指令6：车友会群讨论总结 + 负面观点TOP3
# ============================================================
print("\n" + "=" * 60)
print("【指令6】车友会群讨论 + 负面观点TOP3")
# 车友会群 = 群分组含'车主'/'车友会' 或 群名称含'车主'
club_rows = [r for r in rows if "车主" in (r.get("群名称", "") + r.get("群分组", ""))]
print("车友会群消息数:", len(club_rows), "/", total)
neg_rows = [r for r in club_rows if r.get("舆情标签") == "负向"]
print("负向消息数:", len(neg_rows))
neg_view = Counter()
for r in neg_rows:
    for k in split_kw(r.get("负向词", "")):
        neg_view[k] += 1
    # 无负向词但有内容时取关键词
    if not split_kw(r.get("负向词", "")):
        for k in split_kw(r.get("关键词", "")):
            neg_view["[" + k + "]"] += 1
print("负面观点TOP:", neg_view.most_common(12))

# 保存中间结果
out = {
    "total": total, "user_summaries": user_summaries, "hour_items": hour_items,
    "top_topics": top_topics, "prod_items": prod_items, "top10": top10,
    "neg_top": neg_view.most_common(10), "neg_count": len(neg_rows), "club_count": len(club_rows),
}
with open(r"D:\llama\analysis_result.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1, default=str)
print("\n分析完成 -> D:\\llama\\analysis_result.json")
