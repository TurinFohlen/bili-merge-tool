#!/usr/bin/env python3
"""命令行界面（主入口）"""
import os, sys, time, atexit
from registry import registry
import error_log

@registry.register("ui.cli", "ui", "main() -> int")
class CliMain:
    def __init__(self):
        self.rish_exec = None
        self.scanner = None
        self.video_processor = None
        self.progress_mgr = None
        self.exporter = None
        
        self.output_dir = "/storage/emulated/0/Download/B站视频"
    
    def setup_dependencies(self):
        """从注册中心获取所有依赖组件实例"""
        # 获取服务实例
        rish_executor = registry.get_service("rish.executor")
        file_operator = registry.get_service("file.operator")
        self.scanner = registry.get_service("bili.scanner")
        entry_reader = registry.get_service("bili.entry_reader")
        format_detector = registry.get_service("bili.format_detector")
        extractor_dash = registry.get_service("extractor.dash")
        extractor_blv = registry.get_service("extractor.blv")
        merger = registry.get_service("merger.ffmpeg")
        self.progress_mgr = registry.get_service("progress.manager")
        self.video_processor = registry.get_service("video.processor")
        self.exporter = registry.get_service("exporter.local")
        
        # 注入 rish_exec 到各个需要它的组件
        self.rish_exec = rish_executor.exec_with_retry
        file_operator.set_rish_executor(self.rish_exec)
        self.scanner.set_rish_executor(self.rish_exec)
        entry_reader.set_rish_executor(self.rish_exec)
        format_detector.set_rish_executor(self.rish_exec)
        extractor_dash.set_dependencies(file_operator, self.rish_exec)
        extractor_blv.set_dependencies(file_operator, self.rish_exec)
        
        # 注入 video_processor 的依赖
        self.video_processor.set_dependencies(
            scanner=self.scanner,
            entry_reader=entry_reader,
            format_detector=format_detector,
            extractor_dash=extractor_dash,
            extractor_blv=extractor_blv,
            merger=merger,
            progress_mgr=self.progress_mgr
        )
        
        # 设置进度文件路径
        self.progress_mgr.set_progress_file(f"{self.output_dir}/.bili_progress.json")
    
    def print_banner(self):
        print("=" * 60)
        print("      B站缓存视频合并工具 v3.0（组件化）")
        print("=" * 60)
        print()
    
    def check_environment(self) -> bool:
        """环境检查（rish + ffmpeg）"""
        print("ℹ️  检查环境...")
        
        # 检查 rish（通过调用测试命令）
        try:
            rc, out, err = self.rish_exec("echo __bili_test__", check=False, timeout=30)
            if rc == 0 and "__bili_test__" in out:
                print("✅ rish: 可用")
            else:
                print(f"❌ rish 响应异常: rc={rc}")
                return False
        except Exception as e:
            print(f"❌ rish 不可用: {e}")
            return False
        
        # 检查 ffmpeg
        ffmpeg_path = "/data/data/com.termux/files/usr/bin/ffmpeg"
        if not os.path.exists(ffmpeg_path):
            print(f"❌ ffmpeg 未安装: {ffmpeg_path}")
            print("ℹ️  运行: pkg install ffmpeg")
            return False
        print("✅ ffmpeg: 已安装")
        
        return True
    
    def ensure_output_dir(self):
        """确保输出目录存在"""
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            print(f"✅ 输出目录: {self.output_dir}")
        except Exception as e:
            print(f"❌ 无法创建输出目录: {e}")
            raise
    
    def main(self) -> int:
        """主流程"""
        self.print_banner()
        
        # 1. 设置依赖
        self.setup_dependencies()
        
        # 2. 环境检查
        if not self.check_environment():
            return 1
        print()
        
        # 3. 确保输出目录
        try:
            self.ensure_output_dir()
        except Exception:
            return 1
        print()
        
        # 4. 加载进度
        progress = self.progress_mgr.load()
        print(f"ℹ️  已完成 {len(progress)} 个视频")
        print()
        
        # 5. 扫描 UID
        try:
            print("ℹ️  扫描 B站缓存...")
            uids = self.scanner.list_uids()
            if not uids:
                print("⚠️  未发现 UID 文件夹")
                return 1
            print(f"✅ 发现 {len(uids)} 个 UID 文件夹")
        except Exception as e:
            print(f"❌ 扫描失败: {e}")
            return 1
        print()
        
        # 6. 统计
        stats = {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0}
        
        # 7. 遍历所有 UID
        for i, uid in enumerate(uids, 1):
            print(f"ℹ️  处理 UID [{i}/{len(uids)}]: {uid}")
            
            # 获取 c_* 列表（带重试）
            try:
                c_folders = self.scanner.list_c_folders(uid)
            except Exception as e:
                print(f"  ❌ 获取缓存列表失败: {e}")
                continue
            
            if not c_folders:
                print(f"  ⚠️  未找到缓存文件夹")
                continue
            
            # 统计待处理数
            pending = [c for c in c_folders if not progress.get(c)]
            done = len(c_folders) - len(pending)
            print(f"  ℹ️  {len(c_folders)} 个缓存：{done} 已完成，{len(pending)} 待处理")
            
            if done:
                stats['skipped'] += done
            
            if not pending:
                continue
            
            # 处理每个视频
            for c_folder in pending:
                stats['total'] += 1
                success = self.video_processor.process(uid, c_folder, progress)
                if success:
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
                print()
        
        # 8. 最终统计
        print("\n" + "=" * 60)
        print("✅ 全部完成!")
        print("=" * 60)
        print(f"  总计: {stats['total']}")
        print(f"  ✅ 成功: {stats['success']}")
        print(f"  ❌ 失败: {stats['failed']}")
        print(f"  ⏭️  跳过: {stats['skipped']}")
        print("=" * 60)
        print()
        
        # 9. 询问是否导出
        if stats['success'] > 0 or stats['skipped'] > 0:
            choice = input("是否导出已合并的视频? (y/n): ").strip().lower()
            if choice == 'y':
                target = input("请输入导出目标路径: ").strip()
                if target:
                    success_count, fail_count = self.exporter.export(self.output_dir, target)
                    print(f"\n✅ 导出完成: 成功 {success_count}，失败 {fail_count}")
        
        return 0
