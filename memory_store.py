#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rui AI 长期记忆模块
基于 SQLite + 全文检索，轻量级，无需额外依赖
中文优化：用 LIKE 模糊匹配 + 关键词提取，不依赖 FTS5 中文分词
"""
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta

DB_PATH = r"D:\llama\rui_state\memory.db"

# 确保目录存在
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_db()
    c = conn.cursor()

    # 记忆主表
    c.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            importance INTEGER DEFAULT 5,
            created_at REAL NOT NULL,
            last_accessed REAL,
            access_count INTEGER DEFAULT 0,
            source TEXT DEFAULT 'auto'
        )
    ''')

    conn.commit()
    conn.close()
    print("[记忆模块] 数据库初始化完成")


def extract_keywords(query):
    """
    从查询中提取关键词
    中文策略：提取2-4字的连续片段（滑动窗口），过滤停用词
    """
    # 先按空格、标点分割
    words = re.split(r'[\s,，。？！、;；:：]+', query)
    stopwords = {'的', '了', '吗', '呢', '啊', '呀', '哦', '我', '你', '他', '她', '它', '是', '在', '有', '和', '就', '都', '也', '很', '还', '要', '会', '能', '可以', '什么', '怎么', '为什么', '哪', '谁', '多少', '几', '用户', '请问', '告诉我', '一下'}

    keywords = []
    for word in words:
        word = word.strip()
        if not word:
            continue
        # 英文/数字词：直接保留
        if re.match(r'^[a-zA-Z0-9_]+$', word):
            if len(word) >= 2:
                keywords.append(word)
            continue
        # 中文：提取2字、3字、4字片段
        if len(word) >= 2:
            # 2字片段
            for i in range(len(word) - 1):
                seg = word[i:i+2]
                if seg not in stopwords and not re.match(r'^[a-zA-Z0-9]+$', seg):
                    keywords.append(seg)
            # 3字片段
            if len(word) >= 3:
                for i in range(len(word) - 2):
                    seg = word[i:i+3]
                    if seg not in stopwords:
                        keywords.append(seg)

    # 去重
    seen = set()
    unique = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            unique.append(k)

    return unique if unique else [query]


def add_memory(content, category="general", importance=5, source="auto"):
    """添加一条记忆"""
    conn = get_db()
    c = conn.cursor()
    now = time.time()

    # 检查是否已有相似记忆（简单判断：内容完全相同）
    c.execute("SELECT id, importance FROM memories WHERE content = ?", (content,))
    existing = c.fetchone()
    if existing:
        new_imp = min(10, existing["importance"] + 1)
        c.execute("UPDATE memories SET importance = ?, last_accessed = ? WHERE id = ?",
                  (new_imp, now, existing["id"]))
        conn.commit()
        conn.close()
        return existing["id"]

    c.execute('''
        INSERT INTO memories (content, category, importance, created_at, last_accessed, source)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (content, category, importance, now, now, source))

    mem_id = c.lastrowid
    conn.commit()
    conn.close()
    return mem_id


def search_memories(query, limit=5, min_importance=3):
    """
    搜索记忆（中文友好：直接用查询串做模糊匹配）
    """
    if not query or len(query.strip()) < 2:
        return []

    conn = get_db()
    c = conn.cursor()
    now = time.time()

    # 中文搜索策略：用查询串本身做 LIKE 匹配
    # 如果查询串是长句，也提取关键名词
    keywords = extract_keywords(query)

    # 构建 OR 条件：原始查询 + 提取的关键词
    all_terms = [query] + keywords
    # 去重
    seen = set()
    unique_terms = []
    for t in all_terms:
        if t and t not in seen and len(t) >= 2:
            seen.add(t)
            unique_terms.append(t)

    # 构建 LIKE 查询
    conditions = []
    params = []
    for term in unique_terms:
        conditions.append("content LIKE ?")
        params.append(f"%{term}%")

    where = " OR ".join(conditions)
    params.append(min_importance)

    c.execute(f'''
        SELECT id, content, category, importance, created_at, access_count
        FROM memories
        WHERE ({where}) AND importance >= ?
        ORDER BY importance DESC, created_at DESC
    ''', params)

    results = []
    for row in c.fetchall():
        content_lower = row["content"].lower()
        # 计算命中了多少个词
        hit_count = sum(1 for t in unique_terms if t.lower() in content_lower)

        age_days = (now - row["created_at"]) / 86400
        decay = 1.0 / (1.0 + age_days * 0.1)
        score = hit_count * row["importance"] * decay * (1 + row["access_count"] * 0.1)

        results.append({
            "id": row["id"],
            "content": row["content"],
            "category": row["category"],
            "importance": row["importance"],
            "age_days": round(age_days, 1),
            "score": round(score, 2),
            "hits": hit_count,
        })

        c.execute("UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                  (now, row["id"]))

    conn.commit()
    conn.close()

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


def list_memories(category=None, limit=50):
    """列出所有记忆"""
    conn = get_db()
    c = conn.cursor()

    if category:
        c.execute('''
            SELECT id, content, category, importance, created_at, access_count
            FROM memories WHERE category = ?
            ORDER BY importance DESC, created_at DESC LIMIT ?
        ''', (category, limit))
    else:
        c.execute('''
            SELECT id, content, category, importance, created_at, access_count
            FROM memories ORDER BY importance DESC, created_at DESC LIMIT ?
        ''', (limit,))

    results = []
    for row in c.fetchall():
        results.append({
            "id": row["id"],
            "content": row["content"],
            "category": row["category"],
            "importance": row["importance"],
            "created_at": datetime.fromtimestamp(row["created_at"]).strftime("%Y-%m-%d %H:%M"),
            "access_count": row["access_count"],
        })

    conn.close()
    return results


def delete_memory(mem_id):
    """删除一条记忆"""
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM memories WHERE id = ?", (mem_id,))
    conn.commit()
    count = c.rowcount
    conn.close()
    return count > 0


def prune_old_memories(max_age_days=90, min_importance=4):
    """清理过时的低重要性记忆"""
    conn = get_db()
    c = conn.cursor()
    cutoff = time.time() - max_age_days * 86400

    c.execute('''
        DELETE FROM memories
        WHERE created_at < ? AND importance < ?
    ''', (cutoff, min_importance))

    deleted = c.rowcount
    conn.commit()
    conn.close()
    return deleted


def get_memory_stats():
    """获取记忆统计"""
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) as total FROM memories")
    total = c.fetchone()["total"]

    c.execute("SELECT category, COUNT(*) as cnt FROM memories GROUP BY category")
    by_category = {row["category"]: row["cnt"] for row in c.fetchall()}

    c.execute("SELECT AVG(importance) as avg_imp FROM memories")
    avg_imp = c.fetchone()["avg_imp"] or 0

    conn.close()
    return {
        "total": total,
        "by_category": by_category,
        "avg_importance": round(avg_imp, 1),
    }


# 初始化
init_db()
