#!/usr/bin/env python3
"""
命令行界面 v3.2.0 - 支持本地缓存模式

新特性：
  - 统一打包分片传输
  - 本地缓存复用
  - 彻底摆脱 rish 不稳定问题
"""
import os
import sys
from registry import registry

@registry.register("ui.cli.v2", "ui", "main() -> int")
class CliMainV2:
    def __init__(self):
        self.rish_exec = None
        self.scanner = None
        self.pack_transfer = None
        self.local_finder = None
        self.video_processor_local = None
        self.progress_mgr = None
        self.exporter = None
        
        self.output_dir = "/storage/emulated/0/Download/B站视频"
        self.local_cache_dir = "/storage/emulated/0/Download/bili_local_cache"
    
    def setup_dependencies(self):
        """从注册中心获取所有依赖组件实例"""
        # 基础服务
        rish_executor = registry.get_service("rish.executor")
        self.rish_exec = rish_executor.exec_with_retry
        
        self.scanner = registry.get_service("bili.scanner")
        self.scanner.set_rish_executor(self.rish_exec)
        
        # 新组件：打包传输
        self.pack_transfer = registry.get_service("pack.transfer")
        self.pack_transfer.set_rish_executor(self.rish_exec)
        self.pack_transfer.set_local_cache(self.local_cache_dir)
        
        # 新组件：本地文件查找
        self.local_finder = registry.get_service("local.file_finder")
        
        # 合并器
        merger = registry.get_service("merger.ffmpeg")
        
        # 进度管理
        self.progress_mgr = registry.get_service("progress.manager")
        self.progress_mgr.set_progress_file(f"{self.output_dir}/.bili_progress.json")
        
        # 新处理器：本地缓存模式
        self.video_processor_local = registry.get_service("video.processor.local")
        self.video_processor_local.set_dependencies(
            pack_transfer=self.pack_transfer,
            local_finder=self.local_finder,
            merger=merger,
            progress_mgr=self.progress_mgr
        )
        
        # 导出器
        self.exporter = registry.get_service("exporter.local")
    
    def print_banner(self):
        print("=" * 60)
        print("   B站缓存视频合并工具 v3.2.0（本地缓存模式）")
        print("=" * 60)
        print()
        print("🎯 新特性：")
        print("  · 统一打包分片传输")
        print("  · 本地缓存复用（断点续传）")
        print("  · 彻底摆脱 rish 不稳定问题")
        print("=" * 60)
        print()
    
    def check_environment(self) -> bool:
        """环境检查（rish + ffmpeg + 本地缓存目录）"""
        print("ℹ️  检查环境...")
        
        # 检查 rish（仅用于数据传输）
        try:
            rc, out, err = self.rish_exec("echo __bili_test__", check=False, timeout=30)
            if rc == 0 and "__bili_test__" in out:
                print("✅ rish: 可用（用于数据传输）")
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
        
        # 创建本地缓存目录
        try:
            os.makedirs(self.local_cache_dir, exist_ok=True)
            print(f"✅ 本地缓存目录: {self.local_cache_dir}")
        except Exception as e:
            print(f"❌ 无法创建缓存目录: {e}")
            return False
        
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
        """主流程（本地缓存模式）"""
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
            
            # 获取 c_* 列表
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
            
            # 处理每个视频（使用本地缓存模式）
            for c_folder in pending:
                stats['total'] += 1
                success = self.video_processor_local.process(uid, c_folder, progress)
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
