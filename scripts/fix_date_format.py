#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复数据库中的日期格式
将所有RFC 2822格式转换为ISO 8601格式
"""
import sqlite3
from datetime import datetime, timezone

def normalize_date(date_str: str) -> str:
    """将各种日期格式统一转换为ISO格式（UTC时区）"""
    if not date_str:
        return datetime.now(timezone.utc).isoformat()
    
    date_str = date_str.strip()
    
    # 如果已经是ISO格式，直接返回
    if 'T' in date_str and ('+' in date_str or 'Z' in date_str):
        try:
            # 验证格式是否正确
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.isoformat()
        except:
            pass
    
    try:
        # 优先使用dateutil.parser
        try:
            from dateutil import parser as date_parser
            
            dt = date_parser.parse(date_str)
            
            # 如果没有时区信息，假设为UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            
            # 转换为UTC时区
            dt_utc = dt.astimezone(timezone.utc)
            
            return dt_utc.isoformat()
                
        except ImportError:
            print(f"  ⚠ dateutil未安装，尝试手动解析: {date_str}")
        except Exception as e:
            print(f"  ⚠ dateutil解析失败: {date_str} - {e}，尝试手动解析")
        
        # 如果dateutil失败，尝试手动解析
        formats = [
            '%a, %d %b %Y %H:%M:%S %z',  # Wed, 25 Mar 2026 14:24:11 +0000
            '%a, %d %b %Y %H:%M:%S %Z',  # Wed, 25 Mar 2026 14:24:11 GMT
            '%Y-%m-%dT%H:%M:%S%z',       # 2026-03-25T14:24:11+0000
            '%Y-%m-%dT%H:%M:%SZ',        # 2026-03-25T14:24:11Z
            '%Y-%m-%d %H:%M:%S',         # 2026-03-25 14:24:11
            '%a, %d %b %Y %H:%M:%S',     # Wed, 25 Mar 2026 14:24:11
            '%Y-%m-%dT%H:%M:%S.%f%z',    # 2026-03-25T14:24:11.000+0000
            '%Y-%m-%dT%H:%M:%S.%fZ',     # 2026-03-25T14:24:11.000Z
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                
                # 如果没有时区信息，假设为UTC
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                
                # 转换为UTC时区
                dt_utc = dt.astimezone(timezone.utc)
                
                return dt_utc.isoformat()
            except:
                continue
        
        # 所有格式都失败
        print(f"  ✗ 日期解析失败: '{date_str}'，使用当前时间")
        return datetime.now(timezone.utc).isoformat()
        
    except Exception as e:
        print(f"  ✗ 日期解析异常: {date_str} - {e}")
        return datetime.now(timezone.utc).isoformat()


def fix_date_formats():
    """修复数据库中的日期格式"""
    db_path = "data/rss_news.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 查询所有需要修复的记录（RFC 2822格式）
    cursor.execute('''
        SELECT id, published_at 
        FROM news 
        WHERE published_at LIKE '%Mon%' 
           OR published_at LIKE '%Tue%' 
           OR published_at LIKE '%Wed%' 
           OR published_at LIKE '%Thu%' 
           OR published_at LIKE '%Fri%' 
           OR published_at LIKE '%Sat%' 
           OR published_at LIKE '%Sun%'
    ''')
    
    rows = cursor.fetchall()
    
    print(f"找到 {len(rows)} 条需要修复的记录")
    
    if len(rows) > 0:
        print("前5条记录示例:")
        for i, (news_id, old_date) in enumerate(rows[:5]):
            print(f"  {i+1}. ID: {news_id}, 日期: {old_date}")
    
    fixed_count = 0
    failed_count = 0
    
    for news_id, old_date in rows:
        try:
            new_date = normalize_date(old_date)
            
            # 更新数据库
            cursor.execute('''
                UPDATE news 
                SET published_at = ? 
                WHERE id = ?
            ''', (new_date, news_id))
            
            fixed_count += 1
            
            if fixed_count % 50 == 0:
                print(f"  ✓ 已修复 {fixed_count} 条记录...")
                
        except Exception as e:
            print(f"  ✗ 修复失败 {news_id}: {e}")
            failed_count += 1
    
    # 提交事务
    conn.commit()
    print(f"\n事务已提交")
    
    print(f"\n修复完成:")
    print(f"  ✓ 成功: {fixed_count} 条")
    print(f"  ✗ 失败: {failed_count} 条")
    
    # 验证修复结果
    cursor.execute('''
        SELECT COUNT(*) 
        FROM news 
        WHERE published_at NOT LIKE '%T%'
    ''')
    remaining = cursor.fetchone()[0]
    print(f"  剩余未修复: {remaining} 条")
    
    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("修复数据库日期格式")
    print("=" * 60)
    fix_date_formats()