#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名: backend/app/routers/wecom/wecom_func.py
# 作者: whf
# 日期: 2026-01-27
# 描述: 企业微信业务逻辑

from backend.app.utils.wecom_utils import wecom_app
from backend.app.utils.logger import logger
from backend.app.utils.pg_utils import PGUtils
from fastapi import HTTPException
from sqlalchemy import text
import uuid

class WeComService:
    @staticmethod
    async def get_user_info(user_id: str):
        try:
            return wecom_app.get_user_info(user_id)
        except Exception as e:
            logger.error(f"查询企业微信用户失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def get_departments(department_id: int = None):
        try:
            return wecom_app.get_department_list(department_id)
        except Exception as e:
            logger.error(f"查询企业微信部门失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def sync_data():
        """
        同步企业微信部门和用户数据到本地数据库
        """
        try:
            logger.info("开始同步企业微信数据...")
            
            # 1. 获取所有部门
            dept_resp = wecom_app.get_department_list()
            depts = dept_resp.get('department', [])
            logger.info(f"获取到 {len(depts)} 个部门")
            
            # 2. 识别根部门 (复用 test 脚本中的逻辑)
            all_ids = set(d['id'] for d in depts)
            roots = []
            for d in depts:
                pid = d['parentid']
                if pid == 0:
                    roots.append(d)
                elif pid not in all_ids:
                    roots.append(d)
            
            # 去重
            unique_roots = {d['id']: d for d in roots}.values()
            logger.info(f"识别到 {len(unique_roots)} 个根部门: {[d['name'] for d in unique_roots]}")
            
            all_users = []
            seen_userids = set()
            
            for root in unique_roots:
                try:
                    user_resp = wecom_app.get_department_users(root['id'], fetch_child=1, simple=False)
                    u_list = user_resp.get('userlist', [])
                    for u in u_list:
                         if u['userid'] not in seen_userids:
                             all_users.append(u)
                             seen_userids.add(u['userid'])
                except Exception as ex:
                    logger.error(f"获取部门 {root['name']} (ID: {root['id']}) 成员失败: {ex}")
            
            users = all_users
            logger.info(f"获取到 {len(users)} 个用户 (去重后)")
            
            # 3. 入库操作 (使用事务)
            engine = PGUtils.get_engine()
            async with engine.begin() as conn:
                # --- 同步部门 ---
                # 先清空旧数据? 或者 upsert? 
                # 为了保持关系，建议 upsert。这里简化处理，先清理全部再插入(慎用)，或者 insert on conflict update
                # 考虑到外键约束，先同步部门，再同步用户
                
                # 建立 wecom_id -> uuid 映射，用于处理 parent_id
                dept_map = {} # int(wecom_id) -> uuid
                
                # 预先生成或查询 UUID
                # 先查询已存在的部门，建立映射
                existing_depts = await conn.execute(text("SELECT id, wecom_id FROM sys_departments WHERE wecom_id IS NOT NULL"))
                for row in existing_depts:
                    try:
                        # 确保 key 为 int 类型
                        dept_map[int(row.wecom_id)] = row.id
                    except ValueError:
                        logger.warning(f"发现非数字的 wecom_id: {row.wecom_id}, 跳过映射")
                
                # 插入/更新部门
                # 注意：部门有层级依赖，需按层级顺序插入，或者先插入所有再更新 parent_id
                # 策略：先插入所有部门 (parent_id 暂空)，然后再更新 parent_id
                
                for dept in depts:
                    d_id = int(dept['id']) # 确保为 int
                    d_name = dept['name']
                    d_parent = dept['parentid'] # int
                    d_order = dept['order']
                    
                    if d_id in dept_map:
                        # 更新
                        await conn.execute(
                            text("""
                                UPDATE sys_departments 
                                SET name = :name, order_num = :order_num, updated_at = NOW()
                                WHERE id = :id
                            """),
                            {"name": d_name, "order_num": d_order, "id": dept_map[d_id]}
                        )
                    else:
                        # 插入
                        new_uuid = uuid.uuid4()
                        await conn.execute(
                            text("""
                                INSERT INTO sys_departments (id, name, wecom_id, order_num, status, created_at, updated_at)
                                VALUES (:id, :name, :wecom_id, :order_num, 1, NOW(), NOW())
                            """),
                            {"id": new_uuid, "name": d_name, "wecom_id": str(d_id), "order_num": d_order}
                        )
                        dept_map[d_id] = new_uuid
                
                # 更新部门父子关系
                for dept in depts:
                    d_id = int(dept['id'])
                    d_parent = int(dept['parentid'])
                    if d_parent in dept_map and d_id in dept_map:
                        await conn.execute(
                            text("UPDATE sys_departments SET parent_id = :parent_id WHERE id = :id"),
                            {"parent_id": dept_map[d_parent], "id": dept_map[d_id]}
                        )

                logger.info(f"部门数据同步完成，当前映射大小: {len(dept_map)}")

                # --- 同步用户 ---
                # 记录本次同步到的所有 UserID，用于判断离职
                synced_userids = set()
                
                # Debug: 打印前5个用户的部门信息以供调试
                debug_count = 0

                for u in users:
                    # 字段映射
                    userid = u['userid']
                    name = u['name']
                    synced_userids.add(userid)
                    
                    mobile = u.get('mobile', '')
                    email = u.get('email', '')
                    avatar = u.get('avatar', '')
                    # 部门 (取第一个)
                    dept_list = u.get('department', [])
                    main_dept_id = None
                    
                    if dept_list:
                        # 确保 w_dept_id 转为 int 进行查找
                        try:
                            w_dept_id = int(dept_list[0])
                            if w_dept_id in dept_map:
                                main_dept_id = dept_map[w_dept_id]
                            else:
                                if debug_count < 5:
                                    logger.warning(f"用户 {name} ({userid}) 所属部门ID {w_dept_id} 未在 dept_map 中找到")
                                    debug_count += 1
                        except ValueError:
                            logger.warning(f"用户 {name} ({userid}) 部门ID格式错误: {dept_list[0]}")
                    else:
                        if debug_count < 5:
                            logger.warning(f"用户 {name} ({userid}) 没有部门信息")
                            debug_count += 1
                    
                    # 检查用户是否存在 (通过 wecom_userid 或 username?)
                    # 假设 username = userid (企业微信UserID通常唯一)
                    # 或者如果 username 已存在但 wecom_userid 空，则关联
                    
                    # 策略：以 wecom_userid 为准进行 upsert
                    # 如果不存在，则创建新用户，默认密码可能需要设置一个随机的或者特定规则
                    # 注意：sys_users.username 是唯一键。
                    
                    # 检查是否存在
                    existing_user = await conn.execute(
                        text("SELECT id FROM sys_users WHERE wecom_userid = :uid OR username = :uid"),
                        {"uid": userid}
                    )
                    user_row = existing_user.first()
                    
                    if user_row:
                        # 更新
                        await conn.execute(
                            text("""
                                UPDATE sys_users 
                                SET full_name = :name, phone = :phone, email = :email, 
                                    avatar = :avatar, department_id = :dept_id, 
                                    wecom_userid = :wecom_userid, is_active = TRUE, updated_at = NOW()
                                WHERE id = :id
                            """),
                            {
                                "name": name, "phone": mobile, "email": email, 
                                "avatar": avatar, "dept_id": main_dept_id,
                                "wecom_userid": userid, "id": user_row.id
                            }
                        )
                    else:
                        # 插入
                        # 默认密码 hash (假设默认密码 123456)
                        # 这里直接存个占位符，因为企业微信登录通常走 OAuth，不走密码
                        # 但为了满足非空约束
                        default_pwd_hash = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWrn3ILAWO.opgn7jo7q.0s/0C6X.G" # 123456
                        
                        await conn.execute(
                            text("""
                                INSERT INTO sys_users (
                                    username, password_hash, full_name, phone, email, 
                                    avatar, department_id, wecom_userid, source, is_active, 
                                    created_at, updated_at
                                ) VALUES (
                                    :username, :pwd, :name, :phone, :email,
                                    :avatar, :dept_id, :wecom_userid, 'wecom', TRUE,
                                    NOW(), NOW()
                                )
                            """),
                            {
                                "username": userid, "pwd": default_pwd_hash, "name": name,
                                "phone": mobile, "email": email, "avatar": avatar,
                                "dept_id": main_dept_id, "wecom_userid": userid
                            }
                        )
                
                # --- 处理离职人员 ---
                # 逻辑：找出所有 source='wecom' 且 is_active=True 且不在 synced_userids 中的用户
                # 将其标记为 is_active=False
                if synced_userids:
                    # 获取所有当前活跃的企业微信用户
                    all_wecom_users_result = await conn.execute(
                        text("SELECT id, wecom_userid, username FROM sys_users WHERE source = 'wecom' AND is_active = TRUE")
                    )
                    
                    disabled_count = 0
                    for u_row in all_wecom_users_result:
                        uid = u_row.wecom_userid or u_row.username # 优先用 wecom_userid
                        if uid not in synced_userids:
                            # 标记为离职
                            await conn.execute(
                                text("UPDATE sys_users SET is_active = FALSE, updated_at = NOW() WHERE id = :id"),
                                {"id": u_row.id}
                            )
                            disabled_count += 1
                            logger.info(f"用户 {u_row.username} (ID: {u_row.id}) 已不在企业微信列表中，标记为离职/禁用")
                    
                    if disabled_count > 0:
                        logger.info(f"已处理 {disabled_count} 名离职人员")

                logger.info("用户数据同步完成")
                
            return {"msg": "同步成功", "dept_count": len(depts), "user_count": len(users)}
            
        except Exception as e:
            logger.error(f"同步企业微信数据失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))

wecom_service = WeComService()
