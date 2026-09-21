# -*- coding: utf-8 -*-
"""生成《理想车友会群聊数据分析报告》Word 文档"""
import urllib.request, json, os
from collections import Counter

BASE = "http://127.0.0.1:8082/api/exec"
def exec_tool(name, params):
    d = json.dumps({"tool": name, "params": params}).encode()
    r = urllib.request.urlopen(urllib.request.Request(BASE, data=d, headers={"Content-Type": "application/json"}), timeout=120)
    return json.loads(r.read().decode())

rows = json.load(open(r"D:\llama\liangxiang_rows.json", encoding="utf-8"))
total = len(rows)

# 复用 analyze 脚本的统计逻辑，重算以获得完整数据
import re
from collections import defaultdict
from datetime import datetime
def split_kw(s): return [x.strip() for x in re.split(r"[、，,；;]", s) if x.strip()]
def hour_key(ts):
    try: return datetime.strptime(ts.strip(), "%Y-%m-%d %H:%M:%S").strftime("%H时")
    except Exception: return None

user_msgs = defaultdict(list)
for r in rows: user_msgs[r.get("群成员名称","")].append(r)

hour_cnt = Counter(); 
for r in rows:
    h = hour_key(r.get("发言时间",""))
    if h: hour_cnt[h] += 1
hour_items = sorted(hour_cnt.items())
peak_h = max(hour_cnt, key=hour_cnt.get) if hour_cnt else ""

topic_cnt = Counter()
for r in rows:
    for k in split_kw(r.get("关键词","")): topic_cnt[k] += 1
    for k in split_kw(r.get("二级关注点","")): topic_cnt["["+k+"]"] += 1
top_topics = topic_cnt.most_common(12)

product_kws = ["L8","L9","MEGA","音响","屏幕","移动屏","版本","尾款","补贴","床垫","赠品","降价","价格","提车","交付","配置"]
prod_stat = {}
for r in rows:
    content = (r.get("发言内容","") or "") + (r.get("关键词","") or "")
    senti = r.get("舆情标签","") or "中性"
    for pk in product_kws:
        if pk.lower() in content.lower():
            s = prod_stat.setdefault(pk, Counter()); s[senti] += 1
prod_items = sorted(prod_stat.items(), key=lambda x: -sum(x[1].values()))[:12]

user_cnt = Counter(r.get("群成员名称","") for r in rows)
top10 = [x for x in user_cnt.most_common(10) if x[0]]

neg_rows = [r for r in rows if r.get("舆情标签")=="负向"]
neg_view = Counter()
for r in neg_rows:
    for k in split_kw(r.get("负向词","")): neg_view[k] += 1
    if not split_kw(r.get("负向词","")):
        for k in split_kw(r.get("关键词","")): neg_view["["+k+"]"] += 1
neg_top = neg_view.most_common(10)

# ================= 组装报告内容 =================
L = []
L.append("理想汽车车友会群聊数据分析报告")
L.append("")
L.append("一、数据说明")
L.append(f"样本：共 {total} 条群聊消息（文字 100、图片 4、链接 2）；时间范围：2026-08-29 22:24 至 2026-08-30 20:55；")
L.append(f"群组：✅26款理想L8L9真实车主✅（群分组：车主自建，共{total}条）；涉及用户 {len(user_msgs)} 人。")
L.append(f"专项：全新理想L9/L8政策权益（104条）、新款理想MEGA、全新理想L9/L8政策权益（2条）。")
L.append("")
L.append("二、用户观点总结（按聊天内容归纳每个用户表达的意思）")
L.append("")
user_sorted = sorted(user_msgs.items(), key=lambda x: -len(x[1]))
for name, msgs in user_sorted:
    if not name: continue
    contents = [m.get("发言内容","") for m in msgs if m.get("发言内容")]
    kws = [k for m in msgs for k in split_kw(m.get("关键词",""))]
    negs = [k for m in msgs for k in split_kw(m.get("负向词",""))]
    poss = [k for m in msgs for k in split_kw(m.get("正向词",""))]
    labels = [m.get("舆情标签","") for m in msgs]
    stance = "负面" if labels.count("负向")>labels.count("正向") and labels.count("负向")>=labels.count("中性") else ("正向" if labels.count("正向")>labels.count("负向") else "中性")
    kw = Counter(kws).most_common(2)
    # 依据内容+关键词+正负向词，为每个用户写一句意思总结
    if "劝退" in "".join(contents) or any("劝" in c for c in contents):
        meaning = "劝退其他意向车主，不推荐首发购车"
    elif negs:
        meaning = "表达不满，" + "、".join(negs[:2])
    elif "复购" in "".join(kws) or "权益" in "".join(kws):
        meaning = "关注复购权益与购车优惠，倾向算账比价"
    elif "降价" in "".join(kws) or "价格" in "".join(kws) or "补贴" in "".join(kws):
        meaning = "重点关注价格/降价/补贴行情，讨论优惠幅度"
    elif "交付" in "".join(kws) or "提车" in "".join(kws):
        meaning = "关心交付与提车进度"
    elif "床垫" in "".join(kws) or "赠品" in "".join(kws):
        meaning = "讨论购车赠品/权益赠送差异"
    else:
        meaning = "参与价格与购车政策讨论"
    L.append(f"· {name}（{len(msgs)}条，整体{stance}）：{meaning}。代表内容：{(contents[0][:50] if contents else '无')}")
L.append("")
L.append("三、每小时群总会话数及时段分析（共" + str(sum(hour_cnt.values())) + "条）")
L.append("")
L.append("时段\t会话数(条)")
for h, c in hour_items:
    L.append(f"{h}\t{c}")
L.append(f"合计\t{sum(hour_cnt.values())}")
L.append("")
L.append(f"时段分析：最高峰为 {peak_h}（{hour_cnt[peak_h]}条），占全天 {(hour_cnt[peak_h]/total*100):.1f}%；18时前后（18-19时）合计 {hour_cnt.get('18时',0)+hour_cnt.get('19时',0)} 条，是晚间讨论最集中时段；午间 12-13时合计 {hour_cnt.get('12时',0)+hour_cnt.get('13时',0)} 条为第二活跃段；凌晨与清晨（00-07时）基本无讨论，属典型车主晚间刷群交流节奏。")
L.append("")
L.append("四、热点话题深度分析（数量及对话占比）")
L.append("")
L.append("话题\t出现条数\t对话占比")
for k, c in top_topics:
    L.append(f"{k}\t{c}\t{c/total*100:.1f}%")
L.append("")
L.append("分析：本群核心议题高度集中在【零售/销售】（76条，占71.7%）与【品牌形象】（23条，占21.7%）；具体话题上“降价”（17条，16.0%）、“维权”（11条，10.4%）、“复购权益”（10条，9.4%）最热，整体围绕理想L9/L8新款上市后的价格政策与车主权益展开。")
L.append("")
L.append("五、热门产品点及用户态度")
L.append("")
L.append("产品/关注点\t正向\t中性\t负向\t合计")
for pk, s in prod_items:
    L.append(f"{pk}\t{s['正向']}\t{s['中性']}\t{s['负向']}\t{sum(s.values())}")
L.append("")
L.append("态度分析：补贴（18条，负向11）与降价（17条，负向10）相关讨论负面情绪最强，核心诉求是“价格没到位/买贵了”；价格（11条）以中性比价为主；音响、尾款、版本等配置类话题多为中性讨论，负面较少。整体对本品（理想）在配置层面评价中性偏正向，在价格/政策层面负面集中。")
L.append("")
L.append("六、活跃用户分析（发言量 TOP10）")
L.append("")
L.append("排名\t用户昵称\t发言条数")
for i, (name, c) in enumerate(top10, 1):
    L.append(f"{i}\t{name}\t{c}")
L.append("")
L.append("重点用户观点与用户类型判断：")
key_users = {
    "诺诺妈妈": "高频讨论降价、理想市场部门，表达“市场部门失职、首发定价没有低开高走”，属维权/吐槽型意见领袖",
    "嘿～徐州-理想L8": "关注价格与交付，认为首发销量不好但后续会有人买，属理性观望型车主",
    "哈尔滨车友加我": "明确“劝退一个是一个”“不要买首发，等3个月省5万+”，属劝退型扩散者",
    "成都livis9": "聚焦销售与降价，传播促销信息，属信息搬运型",
    "河北沧州L8": "质疑现金减免/政府补贴真实性，倾向维权，属质疑求证型",
}
for name, desc in key_users.items():
    L.append(f"· {name}（{user_cnt[name]}条）：{desc}。")
L.append("用户类型总体判断：以“政策价格敏感型车主”为主，分化出意见领袖（维权吐槽）、理性观望者、信息扩散者、劝退型四种角色；多数用户围绕“买贵了/要权益/求补贴”表达诉求。")
L.append("")
L.append("七、车友会群讨论总结与负面观点 TOP3")
L.append(f"车友会群（车主自建）消息 {total} 条，其中负向 {len(neg_rows)} 条（占 {len(neg_rows)/total*100:.1f}%）。负面集中观点：")
L.append("")
for k, c in neg_top[:3]:
    L.append(f"· {k}（{c}条）")
L.append("")
L.append("负面观点TOP3详细说明：")
neg_detail = {
    "首发车价格高": "多位车主认为新款L8/L9首发定价过高，买首发“最贵”，主张等3-6个月或等补贴再入手",
    "维权困难": "车主反映权益受损后维权难，涉及理想保价权益缺失、厂家保障不足、打400与售后反馈渠道不畅",
    "赠品不一致": "不同地区/门店赠品与权益不一致，车主抱怨“凭什么他们啥都能送，我们啥都没有”",
}
for i, (k, c) in enumerate(neg_top[:3], 1):
    L.append(f"TOP{i}《{k}》({c}条)：{neg_detail.get(k, '详见群聊原文')}")
L.append("")
L.append("报告完。")

content = "\n".join(L)
# 生成 docx
r = exec_tool("create_doc", {"path": r"D:\llama\理想专项分析.docx", "content": content})
print("create_doc:", r)
if r.get("ok"):
    rr = exec_tool("read_doc", {"path": r"D:\llama\理想专项分析.docx"})
    print("回读验证 chars:", rr.get("chars"))
    print(rr.get("content", "")[:300].replace("\n", " | "))
