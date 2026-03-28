#!/usr/bin/env python3
"""
HTML页面滚动录制工具 (超高规格版)
支持多比例（抖音9:16、微信6:7、横屏16:9）、平滑滚动、超清录制
使用Playwright内置录制（最高质量）
"""

import argparse
import time
import os
import sys
import shutil
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright
import signal
# 比例配置（支持2K分辨率）
RATIO_CONFIG = {
    "9:16": {"width": 1440, "height": 2560, "name": "抖音竖屏2K"},
    "6:7":  {"width": 1440, "height": 1680, "name": "微信竖屏2K"},
    "16:9": {"width": 2560, "height": 1440, "name": "横屏2K"}
}

# 滚动速度配置 (像素/秒)
SPEED_CONFIG = {
    "slow": 80,
    "medium": 150,
    "fast": 250
}


def get_page_height(page):
    """获取页面总高度"""
    return page.evaluate("document.body.scrollHeight")


def smooth_scroll_js():
    """返回平滑滚动的JavaScript代码"""
    return """
    // 平滑滚动函数
    window.__scrollPaused = false;
    window.__scrollSpeed = 150; // 默认速度
    window.__scrollComplete = false;
    
    function smoothScroll(speed) {
        if (window.__scrollPaused) {
            requestAnimationFrame(() => smoothScroll(speed));
            return;
        }
        
        const currentScroll = window.scrollY;
        const maxScroll = document.body.scrollHeight - window.innerHeight;
        
        if (currentScroll < maxScroll - 1) {  // 留1px容差
            // 计算这一帧应该滚动的距离
            const scrollStep = speed / 60; // 假设60fps
            
            // 添加微小的随机变化，模拟人类滚动
            const variation = 0.85 + Math.random() * 0.3; // 0.85-1.15倍
            
            window.scrollBy(0, scrollStep * variation);
            requestAnimationFrame(() => smoothScroll(speed));
        } else {
            window.__scrollComplete = true;
        }
    }
    
    // 暂停滚动
    window.pauseScroll = function() {
        window.__scrollPaused = true;
    };
    
    // 恢复滚动
    window.resumeScroll = function() {
        window.__scrollPaused = false;
    };
    
    // 设置滚动速度
    window.setScrollSpeed = function(speed) {
        window.__scrollSpeed = speed;
    };
    """


def record_scroll(html_path, output_path, duration=60, speed: str | int = "slow", 
                  ratio="9:16", fps=30, start_pause=2, end_pause=3, auto_duration=False):
    """
    执行滚动录制（超清版）
    使用Playwright内置录制（最高质量）
    """
    
    # 获取配置
    config = RATIO_CONFIG.get(ratio, RATIO_CONFIG["16:9"])
    width = config["width"]
    height = config["height"]
    
    # 解析速度
    if isinstance(speed, str):
        scroll_speed = SPEED_CONFIG.get(speed, SPEED_CONFIG["slow"])
    else:
        scroll_speed = speed
    
    print(f"\n{'='*60}")
    print(f"📹 HTML页面滚动录制工具 (超清版)")
    print(f"{'='*60}")
    print(f"📄 源文件: {html_path}")
    print(f"💾 输出路径: {output_path}")
    print(f"📐 比例: {ratio} ({config['name']})")
    print(f"📐 分辨率: {width}x{height}")
    print(f"⏱️  录制时长: {duration}秒")
    print(f"🚀 滚动速度: {scroll_speed} px/s")
    print(f"🎞️  帧率: {fps}fps")
    print(f"{'='*60}\n")
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    
    # 转换HTML路径为绝对路径
    html_abs_path = os.path.abspath(html_path)
    file_url = f"file:///{html_abs_path.replace(os.sep, '/')}"
    
    with sync_playwright() as p:
        # 启动浏览器（非headless模式，显示实际窗口）
        print("🌐 启动浏览器（显示实际窗口）...")
        browser = p.chromium.launch(
            headless=False,  # 显示实际浏览器窗口
            args=[
                f"--window-size={width},{height}",
                "--window-position=0,0",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows"
            ]
        )
        
        # 创建上下文，启用视频录制
        context = browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=1,  # 2K分辨率，不需要额外缩放
            record_video_dir="temp_videos",
            record_video_size={"width": width, "height": height}
        )
        page = context.new_page()
        
        # 等待浏览器窗口完全显示
        print("⏳ 等待浏览器窗口显示...")
        time.sleep(5)  # 增加等待时间
        
        # 确保浏览器窗口在前台
        page.bring_to_front()
        time.sleep(1)
        
        # 加载页面
        print(f"📄 加载页面: {file_url}")
        page.goto(file_url, wait_until="networkidle")
        time.sleep(2)
        
        # 获取页面信息
        page_height = get_page_height(page)
        print(f"📏 页面高度: {page_height}px")
        
        # 计算预计滚动时间
        scroll_time = (page_height - height) / scroll_speed
        
        # 自动计算录制时长
        if auto_duration:
            duration = scroll_time + start_pause + end_pause + 3  # 额外3秒缓冲
            print(f"⏱️  自动计算录制时长: {duration:.1f}秒 (滚动: {scroll_time:.1f}秒)")
        else:
            print(f"⏱️  预计滚动时间: {scroll_time:.1f}秒")
        
        # 注入滚动脚本
        page.evaluate(smooth_scroll_js())
        
        print("🎬 开始Playwright视频录制...")
        
        try:
            # 开始前停留
            if start_pause > 0:
                print(f"\n⏸️  开始前停留 {start_pause} 秒...")
                time.sleep(start_pause)
            
            # 开始滚动
            print(f"\n🚀 开始滚动录制...")
            page.evaluate(f"smoothScroll({scroll_speed})")
            
            # 监控滚动进度
            elapsed = 0
            check_interval = 0.5
            last_scroll_pos = 0
            stuck_count = 0
            
            while elapsed < duration:
                time.sleep(check_interval)
                elapsed += check_interval
                
                current_pos = page.evaluate("window.scrollY")
                max_scroll = page.evaluate("document.body.scrollHeight - window.innerHeight")
                scroll_complete = page.evaluate("window.__scrollComplete")
                
                progress = (current_pos / max_scroll * 100) if max_scroll > 0 else 100
                print(f"\r📊 进度: {progress:.1f}% | 已录制: {elapsed:.1f}秒 | 位置: {current_pos:.0f}/{max_scroll:.0f}px", end="")
                
                if scroll_complete:
                    print(f"\n✅ 页面滚动完成，继续录制剩余时间...")
                
                if abs(current_pos - last_scroll_pos) < 1:
                    stuck_count += 1
                    if stuck_count > 10:
                        print("\n⚠️  检测到滚动停止")
                        break
                else:
                    stuck_count = 0
                last_scroll_pos = current_pos
            
            # 结束后停留
            if end_pause > 0:
                print(f"\n\n⏸️  结束后停留 {end_pause} 秒...")
                time.sleep(end_pause)
            
            print("\n✅ 录制完成！")
            
        except KeyboardInterrupt:
            print("\n\n⚠️  用户中断录制")
        finally:
            # 关闭上下文（自动保存视频）
            print("💾 保存视频...")
            context.close()
            browser.close()
        
        # 查找并移动生成的视频文件
        temp_videos = list(Path("temp_videos").glob("*.webm"))
        if temp_videos:
            temp_video = temp_videos[0]
            
            # 转换为MP4格式
            if output_path.endswith('.mp4'):
                print("🔄 转换为MP4格式...")
                
                # 使用FFmpeg转换（如果可用）
                try:
                    convert_cmd = [
                        "ffmpeg", "-y",
                        "-i", str(temp_video),
                        "-c:v", "libx264",
                        "-preset", "slow",
                        "-crf", "18",  # 高质量
                        "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart",
                        "-r", "30",  # 强制设置帧率为30fps
                        output_path
                    ]
                    subprocess.run(convert_cmd, capture_output=True)
                    os.remove(temp_video)
                    print("✓ 转换完成（帧率已调整为30fps）")
                except:
                    # 如果FFmpeg不可用，直接移动文件
                    shutil.move(str(temp_video), output_path)
                    print("✓ 保存完成")
            else:
                shutil.move(str(temp_video), output_path)
            
            # 清理临时目录
            try:
                os.rmdir("temp_videos")
            except:
                pass
        
        # 检查输出文件
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            
            # 获取视频时长
            try:
                duration_actual = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", output_path],
                    capture_output=True, text=True
                ).stdout.strip()
            except:
                duration_actual = "未知"
            
            print(f"\n{'='*60}")
            print(f"✅ 录制成功！")
            print(f"📁 文件: {output_path}")
            print(f"📊 大小: {file_size:.2f} MB")
            print(f"⏱️  时长: {duration_actual}秒")
            print(f"{'='*60}\n")
        else:
            print(f"\n❌ 录制失败，文件未生成: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="HTML页面滚动录制工具 (超高规格版)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 抖音竖屏录制（默认，2K分辨率）
  python scroll_recorder.py report.html
  
  # 横屏录制（2K分辨率）
  python scroll_recorder.py report.html --ratio 16:9
  
  # 微信竖屏录制，时长90秒
  python scroll_recorder.py report.html --ratio 6:7 --duration 90
  
  # 横屏录制，60fps，慢速滚动
  python scroll_recorder.py report.html --ratio 16:9 --fps 60 --speed slow
  
  # 自定义滚动速度（每秒100像素）
  python scroll_recorder.py report.html --speed 100
  
  # 自动计算时长，确保滚动到底部
  python scroll_recorder.py report.html --auto
        """
    )
    
    parser.add_argument("html_file", help="HTML文件路径")
    parser.add_argument("--output", "-o", help="输出文件路径（默认自动生成）")
    parser.add_argument("--duration", "-d", type=int, default=60, 
                        help="录制时长，单位秒（默认60）")
    parser.add_argument("--speed", "-s", default="medium",
                        help="滚动速度: slow/medium/fast 或数字（像素/秒，默认medium）")
    parser.add_argument("--ratio", "-r", default="9:16", choices=["9:16", "6:7", "16:9"],
                        help="视频比例（默认9:16）")
    parser.add_argument("--fps", "-f", type=int, default=30, choices=[24, 30, 60],
                        help="视频帧率（默认30）")
    parser.add_argument("--start-pause", type=int, default=2,
                        help="开始前停留秒数（默认2）")
    parser.add_argument("--end-pause", type=int, default=3,
                        help="结束后停留秒数（默认3）")
    parser.add_argument("--auto", action="store_true",
                        help="自动计算录制时长，确保滚动到底部")
    
    args = parser.parse_args()
    
    # 检查HTML文件是否存在
    if not os.path.exists(args.html_file):
        print(f"❌ 错误: HTML文件不存在: {args.html_file}")
        sys.exit(1)
    
    # 解析速度参数
    speed = args.speed
    if speed not in SPEED_CONFIG:
        try:
            speed = int(speed)
        except ValueError:
            print(f"⚠️  无效的速度参数: {speed}，使用默认值 medium")
            speed = "medium"
    
    # 生成输出文件名
    if args.output:
        output_path = args.output
    else:
        html_name = Path(args.html_file).stem
        ratio_suffix = args.ratio.replace(":", "x")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"videos/{html_name}_{ratio_suffix}_{timestamp}.mp4"
    
    # 执行录制
    record_scroll(
        html_path=args.html_file,
        output_path=output_path,
        duration=args.duration,
        speed=speed,
        ratio=args.ratio,
        fps=args.fps,
        start_pause=args.start_pause,
        end_pause=args.end_pause,
        auto_duration=args.auto
    )


if __name__ == "__main__":
    main()