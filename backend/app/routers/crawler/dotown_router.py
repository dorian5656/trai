
import os
import subprocess
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from dotown_crawler.models import CrawlerTask, DotownImage
from sqlalchemy import func
from datetime import datetime
from typing import Optional, Dict, Any

router = APIRouter(
    prefix="/crawler/dotown",
    tags=["Dotown 爬虫管理"]
)

# 全局变量记录爬虫进程 (简单实现，生产环境建议使用 Celery/RQ)
CRAWLER_PROCESS: Optional[subprocess.Popen] = None

@router.post("/start", summary="启动爬虫任务")
async def start_crawler(
    target_count: int = Query(1000, description="目标抓取数量"),
    start_page: int = Query(1, description="起始页码"),
    max_page: int = Query(100, description="最大页码"),
    db: Session = Depends(get_db)
):
    global CRAWLER_PROCESS
    
    # 检查是否已有任务在运行
    if CRAWLER_PROCESS and CRAWLER_PROCESS.poll() is None:
        raise HTTPException(status_code=400, detail="爬虫任务正在运行中，请勿重复启动")
    
    # 创建任务记录
    task = CrawlerTask(
        task_name=f"Dotown-Task-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        spider_name="dotown",
        target_count=target_count,
        start_page=start_page,
        status="running",
        started_at=datetime.now()
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # 启动 Scrapy 进程
    # 注意：这里使用 subprocess 启动外部进程，确保不阻塞 FastAPI 主线程
    cmd = [
        "scrapy", "crawl", "dotown",
        "-a", f"target_count={target_count}",
        "-a", f"start_page={start_page}",
        "-a", f"max_page={max_page}",
        "-a", f"task_id={task.id}"  # 传递任务ID给爬虫
    ]
    
    cwd = "/home/code_dev/trai/backend/app/crawler/dotown_crawler"
    
    try:
        CRAWLER_PROCESS = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return {"message": "爬虫已启动", "task_id": task.id}
    except Exception as e:
        task.status = "failed"
        task.error_msg = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"启动失败: {e}")

@router.post("/stop", summary="停止爬虫任务")
async def stop_crawler(db: Session = Depends(get_db)):
    global CRAWLER_PROCESS
    
    if not CRAWLER_PROCESS or CRAWLER_PROCESS.poll() is not None:
        return {"message": "当前没有正在运行的爬虫任务"}
    
    try:
        CRAWLER_PROCESS.terminate()
        # 等待进程结束
        try:
            CRAWLER_PROCESS.wait(timeout=5)
        except subprocess.TimeoutExpired:
            CRAWLER_PROCESS.kill()
            
        CRAWLER_PROCESS = None
        
        # 更新最后运行的任务状态
        last_task = db.query(CrawlerTask).filter(CrawlerTask.status == "running").order_by(CrawlerTask.id.desc()).first()
        if last_task:
            last_task.status = "stopped"
            last_task.stopped_at = datetime.now()
            db.commit()
            
        return {"message": "爬虫任务已停止"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止失败: {e}")

@router.get("/status", summary="获取爬虫状态与统计")
async def get_crawler_status(db: Session = Depends(get_db)):
    global CRAWLER_PROCESS
    
    is_running = CRAWLER_PROCESS is not None and CRAWLER_PROCESS.poll() is None
    
    # 统计数据
    total_images = db.query(func.count(DotownImage.id)).scalar()
    today_images = db.query(func.count(DotownImage.id)).filter(
        func.date(DotownImage.crawled_at) == datetime.now().date()
    ).scalar()
    
    last_task = db.query(CrawlerTask).order_by(CrawlerTask.id.desc()).first()
    
    return {
        "is_running": is_running,
        "total_images": total_images,
        "today_new_images": today_images,
        "last_task": {
            "id": last_task.id if last_task else None,
            "status": last_task.status if last_task else None,
            "total_saved": last_task.total_saved if last_task else 0,
            "error_msg": last_task.error_msg if last_task else None
        }
    }
