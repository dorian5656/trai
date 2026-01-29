#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 文件名：yibao_merge_fxcrm.py
# 作者：liuhd
# 日期：2026-01-28 10:00:00
# 描述：串联医保码抓取入库与推送CRM同步的一体化脚本（模块导入版）

"""
串联医保码抓取入库与推送CRM同步的一体化脚本

功能：
1. 从医保网站抓取医用耗材数据（包含分页处理）
2. 将抓取到的数据入库到本地数据库（PostgreSQL）
3. 从数据库读取数据，推送到纷享销客 CRM 系统

注意事项：
- 确保数据库连接配置正确
- 运行前请先备份数据库，以防数据丢失
- 建议在生产环境中使用前进行充分测试
"""
import sys
import os
import time
import platform
import subprocess
from pathlib import Path

from loguru import logger

# 尝试导入业务模块
try:
    import yibao_code
    from yibao_code import MedicalConsumableImporter
    import post_fxcrm
    from post_fxcrm import FxiaokeSyncer
except ImportError as e:
    logger.error(f"导入业务模块失败: {e}")
    sys.exit(1)


def kill_chrome_processes() -> None:
    """清理服务器上的谷歌浏览器进程 (chrome/chromium)."""
    logger.info("开始清理 Google Chrome 进程...")
    try:
        if platform.system() == "Windows":
            # Windows 系统使用 taskkill
            subprocess_args = {"check": False, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], **subprocess_args)
            subprocess.run(["taskkill", "/F", "/IM", "chromium.exe"], **subprocess_args)
            subprocess.run(["taskkill", "/F", "/IM", "chromedriver.exe"], **subprocess_args)
        elif platform.system() == "Linux":
            # Linux 系统使用 pkill
            subprocess_args = {"check": False, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
            # 使用 -f 匹配命令行参数，确保能杀掉相关进程
            subprocess.run(["pkill", "-9", "-f", "chrome"], **subprocess_args)
            subprocess.run(["pkill", "-9", "-f", "chromium"], **subprocess_args)
            subprocess.run(["pkill", "-9", "-f", "chromedriver"], **subprocess_args)
        
        logger.info("Google Chrome 进程清理完成.")
    except Exception as e:
        logger.error(f"清理 Chrome 进程时发生错误: {e}")


def find_latest_excel(search_dirs: list[Path]) -> Path | None:
    """在给定目录集合中查找最新的 Excel 文件（xls/xlsx）.
    
    参数:
        search_dirs (list[Path]): 需要搜索的目录列表.
    
    返回:
        Path | None: 最新修改的 Excel 文件路径, 如果未找到则返回 None.
    """
    candidates: list[Path] = []
    for d in search_dirs:
        try:
            candidates.extend(list(d.glob("*.xlsx")))
            candidates.extend(list(d.glob("*.xls")))
        except Exception:
            pass
    if not candidates:
        return None
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return latest


def get_excel_row_count(excel_path: Path) -> int:
    """读取 Excel 并返回数据行数（不含表头）.
    
    参数:
        excel_path (Path): Excel 文件的路径.
        
    返回:
        int: 数据行数, 如果读取失败返回 -1.
    """
    try:
        import pandas as pd
    except Exception as exc:
        logger.error(f"无法导入 pandas 库，读取行数失败: {exc}")
        return -1
    try:
        df = pd.read_excel(str(excel_path))
        return int(len(df))
    except Exception as exc:
        logger.error(f"读取 Excel 文件 {excel_path} 行数失败: {exc}")
        return -1


def cleanup_old_excels(target_dirs: list[Path]) -> None:
    """清理指定目录下的旧 Excel 文件 (.xls, .xlsx)."""
    logger.info("开始清理旧 Excel 文件...")
    count = 0
    for d in target_dirs:
        try:
            # 查找所有 Excel 文件
            files = list(d.glob("*.xlsx")) + list(d.glob("*.xls"))
            for f in files:
                try:
                    f.unlink()  # 删除文件
                    logger.debug(f"已删除旧文件: {f.name}")
                    count += 1
                except Exception as e:
                    logger.warning(f"无法删除文件 {f.name}: {e}")
        except Exception as e:
            logger.warning(f"扫描目录 {d} 失败: {e}")
    
    if count > 0:
        logger.info(f"旧 Excel 文件清理完成，共删除 {count} 个文件。")
    else:
        logger.info("未发现旧 Excel 文件，无需清理。")


def main() -> None:
    """主流程入口, 依次执行医保码抓取入库和推送至 CRM.
    
    流程:
    1. 清理可能残留的 Chrome 进程和旧 Excel 文件.
    2. 调用 yibao_code.MedicalConsumableImporter 进行医保数据抓取和入库.
    3. 检查并记录下载的 Excel 文件信息.
    4. 调用 post_fxcrm.FxiaokeSyncer 将医保数据推送到 CRM.
    5. 再次清理 Chrome 进程.
    """
    # 强制重置日志配置，确保只有控制台输出，防止之前的 Sink 残留
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")

    current_dir = Path(__file__).resolve().parent
    
    # 确保在脚本开始前清理残留进程和旧文件
    kill_chrome_processes()
    cleanup_old_excels([Path.cwd(), current_dir])
    
    start_time = time.time()

    # --- 阶段一：医保数据抓取与入库 ---
    logger.info(">>> 开始阶段一：医保数据抓取与入库")
    try:
        importer = MedicalConsumableImporter()
        importer.run()
        logger.info("阶段一完成：医保数据抓取与入库成功。")
    except Exception as e:
        logger.error(f"医保抓取入库执行失败: {e}")
        # 失败则终止后续任务
        kill_chrome_processes()
        sys.exit(1)
    finally:
        # 阶段一结束，清理医保抓取相关的日志 Sink
        # 这样可以防止阶段二的日志被写入阶段一的数据库或推送渠道
        try:
            import yibao_code
            yibao_code.teardown_logging()
            logger.info("阶段一日志 Sink 已清理")
        except Exception as e:
            logger.error(f"清理阶段一日志失败: {e}")

    # --- 中间统计：检查下载文件 ---
    # 下载完成后，读取最新 Excel 的数据行数并打印日志
    latest_excel = find_latest_excel([Path.cwd(), current_dir])
    if latest_excel is not None:
        row_count = get_excel_row_count(latest_excel)
        if row_count >= 0:
            logger.info(f"检测到最新下载的 Excel 文件: {latest_excel.name}，包含数据行数: {row_count}")
        else:
            logger.warning(f"无法获取 Excel 文件行数: {latest_excel}")
    else:
        logger.warning("未发现已下载的 Excel 文件，跳过行数统计。")

    # --- 阶段二：CRM 数据同步 ---
    logger.info(">>> 开始阶段二：医保数据推送至 CRM")
    try:
        syncer = FxiaokeSyncer()
        syncer.run()
        logger.info("阶段二完成：医保数据推送至 CRM 成功。")
    except Exception as e:
        logger.error(f"医保数据推送至 CRM 执行失败: {e}")
        kill_chrome_processes()
        sys.exit(1)
    finally:
        # 阶段二结束，清理 CRM 同步相关的日志 Sink
        try:
            import post_fxcrm
            post_fxcrm.teardown_logging()
            logger.info("阶段二日志 Sink 已清理")
        except Exception as e:
            logger.error(f"清理阶段二日志失败: {e}")

    elapsed_time = time.time() - start_time
    logger.info(f"医保数据抓取入库与推送至 CRM 全流程执行完毕. 总耗时: {elapsed_time:.2f}秒")
    
    # 所有任务执行完毕后，清理浏览器进程
    kill_chrome_processes()


if __name__ == "__main__":
    main()
