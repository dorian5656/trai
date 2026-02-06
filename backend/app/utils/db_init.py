#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 文件名：backend/app/utils/db_init.py
# 作者：whf
# 日期：2026-01-26
# 描述：数据库初始化脚本，用于自动创建数据库和日志表

import asyncpg
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# 优先加载环境变量 (必须在导入 config 之前)
backend_dir = Path(__file__).resolve().parent.parent.parent
env_dev_path = backend_dir / ".env.dev"
env_path = backend_dir / ".env"
if env_dev_path.exists():
    load_dotenv(env_dev_path, override=True)
elif env_path.exists():
    load_dotenv(env_path)

from backend.app.utils.logger import logger
from backend.app.config import settings
from backend.app.utils.security import get_password_hash

class DBInitializer:
    """
    数据库初始化器
    
    职责:
    1. 检查并创建业务数据库 (itzx)
    2. 初始化核心表结构 (如 request_logs)
    """
    
    def __init__(self):
        self.sys_db = 'postgres'  # 系统管理库
        self.target_db = settings.POSTGRES_DB
        self.user = settings.POSTGRES_USER
        self.password = settings.POSTGRES_PASSWORD
        self.host = settings.POSTGRES_SERVER
        self.port = settings.POSTGRES_PORT

    async def check_and_create_db(self):
        """
        检查数据库是否存在。
        优先尝试直接连接目标数据库，成功则跳过创建。
        若连接失败（不存在），则尝试连接 postgres 库进行创建。
        """
        logger.info(f"⏳ [DB: {self.target_db}] 开始数据库存在性检查...")
        
        # 1. 尝试直接连接目标数据库
        try:
            conn = await asyncpg.connect(
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port,
                database=self.target_db
            )
            await conn.close()
            logger.success(f"✅ 数据库 '{self.target_db}' 已存在 (连接成功)，跳过创建")
            return True
        except Exception as e:
            # 如果是认证失败，那即使连接 postgres 也大概率失败，但还是按流程走一下
            logger.warning(f"⚠️ 无法直接连接数据库 '{self.target_db}' (可能不存在或认证失败): {e}")

        # 2. 尝试通过 postgres 库创建
        try:
            # 连接到默认 postgres 数据库进行管理操作
            sys_conn = await asyncpg.connect(
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port,
                database=self.sys_db
            )
            
            # 检查目标数据库是否存在
            exists = await sys_conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1",
                self.target_db
            )
            
            if not exists:
                logger.info(f"🆕 数据库 '{self.target_db}' 不存在，正在创建...")
                # create database 不能在事务块中运行
                await sys_conn.execute(f'CREATE DATABASE "{self.target_db}"')
                logger.success(f"✅ 数据库 '{self.target_db}' 创建成功")
            else:
                logger.success(f"✅ 数据库 '{self.target_db}' 已存在，跳过创建")
                
            await sys_conn.close()
            return True
            
        except Exception as e:
            logger.error(f"❌ 检查/创建数据库失败: {e}")
            if "does not exist" in str(e) or "Connection refused" in str(e):
                 logger.critical("无法连接到数据库服务器，请确保 PostgreSQL 已启动且配置正确。")
            return False

    async def _update_table_registry(self, conn, table_name, description):
        """
        更新 table_registry 总表信息
        """
        try:
            # 确保 table_registry 表存在
            create_registry_sql = """
            CREATE TABLE IF NOT EXISTS table_registry (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                table_name VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
                updated_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
            );
            COMMENT ON TABLE table_registry IS '数据库表注册中心，记录所有业务表信息';
            COMMENT ON COLUMN table_registry.id IS '主键ID';
            COMMENT ON COLUMN table_registry.table_name IS '表名';
            COMMENT ON COLUMN table_registry.description IS '表描述';
            COMMENT ON COLUMN table_registry.created_at IS '创建时间 (北京时间)';
            COMMENT ON COLUMN table_registry.updated_at IS '更新时间 (北京时间)';
            """
            await conn.execute(create_registry_sql)
            
            # 尝试修复旧表结构 (如果已存在 TIMESTAMPTZ)
            try:
                await conn.execute("ALTER TABLE table_registry ALTER COLUMN created_at TYPE TIMESTAMP(0) USING created_at::TIMESTAMP(0)")
                await conn.execute("ALTER TABLE table_registry ALTER COLUMN updated_at TYPE TIMESTAMP(0) USING updated_at::TIMESTAMP(0)")
                await conn.execute("ALTER TABLE table_registry ALTER COLUMN created_at SET DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')")
                await conn.execute("ALTER TABLE table_registry ALTER COLUMN updated_at SET DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')")
            except Exception as ex:
                pass # 忽略错误，假设可能是新表

            # 插入或更新表信息
            upsert_sql = """
            INSERT INTO table_registry (table_name, description, updated_at)
            VALUES ($1, $2, (NOW() AT TIME ZONE 'Asia/Shanghai'))
            ON CONFLICT (table_name) 
            DO UPDATE SET 
                description = EXCLUDED.description,
                updated_at = (NOW() AT TIME ZONE 'Asia/Shanghai');
            """
            await conn.execute(upsert_sql, table_name, description)
            logger.info(f"📝 [Registry] 已更新表 '{table_name}' 的元数据信息")
            
        except Exception as e:
            logger.error(f"❌ 更新表注册信息失败: {e}")

    async def init_ai_model_registry(self, conn):
        """
        初始化 AI 模型注册表 (ai_model_registry)
        """
        table_name = "ai_model_registry"
        
        # 1. 建表语句
        ddl = """
        CREATE TABLE IF NOT EXISTS ai_model_registry (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            filename VARCHAR(255) NOT NULL UNIQUE,
            type VARCHAR(50) NOT NULL,
            version VARCHAR(50),
            description TEXT,
            is_enabled BOOLEAN DEFAULT TRUE,
            use_gpu BOOLEAN DEFAULT TRUE,
            gpu_id INT DEFAULT 0,
            status VARCHAR(50) DEFAULT 'pending',
            error_msg TEXT,
            usage_scenario TEXT,
            created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
            updated_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
        );
        
        COMMENT ON TABLE ai_model_registry IS 'AI模型注册表，管理所有模型文件的状态与配置';
        COMMENT ON COLUMN ai_model_registry.id IS '主键ID';
        COMMENT ON COLUMN ai_model_registry.name IS '模型名称 (如 heart_like)';
        COMMENT ON COLUMN ai_model_registry.filename IS '模型文件名 (如 heart_like.pt)';
        COMMENT ON COLUMN ai_model_registry.type IS '模型类型 (yolo, ocr, llm)';
        COMMENT ON COLUMN ai_model_registry.version IS '模型版本号';
        COMMENT ON COLUMN ai_model_registry.description IS '模型描述';
        COMMENT ON COLUMN ai_model_registry.is_enabled IS '是否启用';
        COMMENT ON COLUMN ai_model_registry.use_gpu IS '是否使用GPU';
        COMMENT ON COLUMN ai_model_registry.gpu_id IS '指定GPU ID';
        COMMENT ON COLUMN ai_model_registry.status IS '状态 (pending, loaded, error, disabled)';
        COMMENT ON COLUMN ai_model_registry.error_msg IS '错误信息 (如有)';
        COMMENT ON COLUMN ai_model_registry.usage_scenario IS '使用场景描述';
        COMMENT ON COLUMN ai_model_registry.created_at IS '创建时间 (北京时间)';
        COMMENT ON COLUMN ai_model_registry.updated_at IS '更新时间 (北京时间)';
        """
        
        try:
            # 执行建表
            await conn.execute(ddl)
            
            # 尝试修复旧表结构
            try:
                await conn.execute("ALTER TABLE ai_model_registry ALTER COLUMN created_at TYPE TIMESTAMP(0) USING created_at::TIMESTAMP(0)")
                await conn.execute("ALTER TABLE ai_model_registry ALTER COLUMN updated_at TYPE TIMESTAMP(0) USING updated_at::TIMESTAMP(0)")
                await conn.execute("ALTER TABLE ai_model_registry ALTER COLUMN created_at SET DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')")
                await conn.execute("ALTER TABLE ai_model_registry ALTER COLUMN updated_at SET DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')")
            except:
                pass

            logger.success(f"表 {table_name} 初始化成功")
            
            # 注册到 table_registry
            await self._update_table_registry(conn, table_name, "AI模型注册表，管理所有模型文件的状态与配置")
            logger.success(f"📝 [Registry] 已更新表 '{table_name}' 的元数据信息")
            
        except Exception as e:
            logger.error(f"初始化 {table_name} 失败: {e}")
            raise e

    async def init_user_images_table(self, conn):
        """
        初始化用户图片表 (user_images)
        支持上传和 AI 生成的图片记录
        """
        table_name = "user_images"
        
        # [Update 2026-02-05] 增加 prompt, model, meta_data 字段支持文生图历史
        ddl = """
        CREATE TABLE IF NOT EXISTS user_images (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id VARCHAR(50) NOT NULL,
            filename VARCHAR(255) NOT NULL,
            s3_key VARCHAR(500),
            url TEXT NOT NULL,
            size BIGINT,
            mime_type VARCHAR(100),
            module VARCHAR(50) DEFAULT 'common',
            source VARCHAR(20) DEFAULT 'upload',
            prompt TEXT,
            meta_data JSONB,
            is_deleted BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
            updated_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
        );
        COMMENT ON TABLE user_images IS '用户图片表，存储上传和AI生成的图片记录';
        COMMENT ON COLUMN user_images.id IS '主键ID';
        COMMENT ON COLUMN user_images.user_id IS '用户ID (关联 sys_users.username)';
        COMMENT ON COLUMN user_images.filename IS '原始文件名';
        COMMENT ON COLUMN user_images.s3_key IS 'S3对象键 (用于删除)';
        COMMENT ON COLUMN user_images.url IS '访问URL';
        COMMENT ON COLUMN user_images.size IS '文件大小(字节)';
        COMMENT ON COLUMN user_images.mime_type IS '文件类型';
        COMMENT ON COLUMN user_images.module IS '所属模块 (upload/gen/ocr)';
        COMMENT ON COLUMN user_images.source IS '来源 (upload=上传, generated=AI生成)';
        COMMENT ON COLUMN user_images.prompt IS '生成提示词 (仅AI生成有效)';
        COMMENT ON COLUMN user_images.meta_data IS '元数据 (模型参数等)';
        COMMENT ON COLUMN user_images.is_deleted IS '是否已删除';
        COMMENT ON COLUMN user_images.created_at IS '创建时间';
        COMMENT ON COLUMN user_images.updated_at IS '更新时间';
        """
        
        try:
            await conn.execute(ddl)
            # 索引
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_images_user_id ON user_images(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_images_created_at ON user_images(created_at DESC)")
            
            # 尝试修复/升级旧表结构
            try:
                # 2026-02-05: 增加文生图相关字段
                await conn.execute("ALTER TABLE user_images ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'upload'")
                await conn.execute("ALTER TABLE user_images ADD COLUMN IF NOT EXISTS prompt TEXT")
                await conn.execute("ALTER TABLE user_images ADD COLUMN IF NOT EXISTS meta_data JSONB")
                
                await conn.execute("ALTER TABLE user_images ALTER COLUMN created_at TYPE TIMESTAMP(0) USING created_at::TIMESTAMP(0)")
                await conn.execute("ALTER TABLE user_images ALTER COLUMN updated_at TYPE TIMESTAMP(0) USING updated_at::TIMESTAMP(0)")
                await conn.execute("ALTER TABLE user_images ALTER COLUMN created_at SET DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')")
                await conn.execute("ALTER TABLE user_images ALTER COLUMN updated_at SET DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')")
            except Exception as e:
                logger.warning(f"尝试更新 user_images 表结构时出现非致命错误: {e}")
            
            logger.success(f"表 {table_name} 初始化成功")
            await self._update_table_registry(conn, table_name, "用户图片表，关联用户与S3存储，支持AI生成记录")
        except Exception as e:
            logger.error(f"初始化 {table_name} 失败: {e}")
            raise e

    async def init_speech_logs_table(self, conn):
        """
        初始化语音识别记录表 (speech_logs)
        """
        table_name = "speech_logs"
        ddl = """
        CREATE TABLE IF NOT EXISTS speech_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id VARCHAR(50) NOT NULL,
            audio_url TEXT NOT NULL,
            s3_key VARCHAR(500),
            recognition_text TEXT,
            duration FLOAT,
            model_version VARCHAR(50) DEFAULT 'funasr-paraformer',
            status VARCHAR(20) DEFAULT 'success',
            error_msg TEXT,
            created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
            updated_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
        );
        COMMENT ON TABLE speech_logs IS '语音识别历史记录表';
        COMMENT ON COLUMN speech_logs.id IS '主键ID';
        COMMENT ON COLUMN speech_logs.user_id IS '用户ID';
        COMMENT ON COLUMN speech_logs.audio_url IS '音频文件访问URL';
        COMMENT ON COLUMN speech_logs.s3_key IS 'S3对象键';
        COMMENT ON COLUMN speech_logs.recognition_text IS '识别结果文本';
        COMMENT ON COLUMN speech_logs.duration IS '音频时长(秒)';
        COMMENT ON COLUMN speech_logs.model_version IS '使用模型版本';
        COMMENT ON COLUMN speech_logs.status IS '状态 (success, failed)';
        COMMENT ON COLUMN speech_logs.error_msg IS '错误信息';
        COMMENT ON COLUMN speech_logs.created_at IS '创建时间';
        COMMENT ON COLUMN speech_logs.updated_at IS '更新时间';
        """
        
        try:
            await conn.execute(ddl)
            # 索引
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_speech_logs_user_id ON speech_logs(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_speech_logs_created_at ON speech_logs(created_at DESC)")
            
            logger.success(f"表 {table_name} 初始化成功")
            await self._update_table_registry(conn, table_name, "语音识别历史记录表")
        except Exception as e:
            logger.error(f"初始化 {table_name} 失败: {e}")
            raise e

    async def init_rbac_tables(self, conn):
        """
        初始化 RBAC 相关表结构 (用户/角色/权限/部门)
        """
        tables = [
            # 1. 部门表 (sys_departments)
            {
                "name": "sys_departments",
                "desc": "部门表，对应企业微信架构",
                "ddl": """
                CREATE TABLE IF NOT EXISTS sys_departments (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(100) NOT NULL,
                    parent_id UUID REFERENCES sys_departments(id) ON DELETE SET NULL,
                    leader VARCHAR(100),
                    wecom_id VARCHAR(50), -- 企业微信部门ID
                    order_num INT DEFAULT 0,
                    status INT DEFAULT 1, -- 1:启用, 0:停用
                    created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
                    updated_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
                );
                COMMENT ON TABLE sys_departments IS '系统部门表';
                COMMENT ON COLUMN sys_departments.id IS '部门ID';
                COMMENT ON COLUMN sys_departments.name IS '部门名称';
                COMMENT ON COLUMN sys_departments.parent_id IS '父部门ID';
                COMMENT ON COLUMN sys_departments.leader IS '负责人';
                COMMENT ON COLUMN sys_departments.wecom_id IS '企业微信部门ID';
                COMMENT ON COLUMN sys_departments.order_num IS '显示排序';
                COMMENT ON COLUMN sys_departments.status IS '部门状态 (1:启用, 0:停用)';
                COMMENT ON COLUMN sys_departments.created_at IS '创建时间';
                COMMENT ON COLUMN sys_departments.updated_at IS '更新时间';
                """
            },
            # 2. 用户表 (sys_users)
            {
                "name": "sys_users",
                "desc": "系统用户表",
                "ddl": """
                CREATE TABLE IF NOT EXISTS sys_users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    full_name VARCHAR(50),
                    email VARCHAR(100),
                    phone VARCHAR(20),
                    department_id UUID REFERENCES sys_departments(id) ON DELETE SET NULL,
                    wecom_userid VARCHAR(100), -- 企业微信UserID
                    avatar TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_superuser BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
                    updated_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
                );
                COMMENT ON TABLE sys_users IS '系统用户表';
                COMMENT ON COLUMN sys_users.id IS '用户ID';
                COMMENT ON COLUMN sys_users.username IS '用户名 (登录账号)';
                COMMENT ON COLUMN sys_users.password_hash IS '密码哈希值';
                COMMENT ON COLUMN sys_users.full_name IS '真实姓名';
                COMMENT ON COLUMN sys_users.email IS '电子邮箱';
                COMMENT ON COLUMN sys_users.phone IS '手机号码';
                COMMENT ON COLUMN sys_users.department_id IS '所属部门ID';
                COMMENT ON COLUMN sys_users.wecom_userid IS '企业微信UserID';
                COMMENT ON COLUMN sys_users.avatar IS '头像URL';
                COMMENT ON COLUMN sys_users.is_active IS '是否激活 (True:激活, False:禁用)';
                COMMENT ON COLUMN sys_users.is_superuser IS '是否超级管理员';
                COMMENT ON COLUMN sys_users.created_at IS '创建时间';
                COMMENT ON COLUMN sys_users.updated_at IS '更新时间';
                """
            },
            # 3. 角色表 (sys_roles)
            {
                "name": "sys_roles",
                "desc": "系统角色表",
                "ddl": """
                CREATE TABLE IF NOT EXISTS sys_roles (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(50) NOT NULL UNIQUE,
                    code VARCHAR(50) NOT NULL UNIQUE,
                    description TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
                    updated_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
                );
                COMMENT ON TABLE sys_roles IS '系统角色表';
                COMMENT ON COLUMN sys_roles.id IS '角色ID';
                COMMENT ON COLUMN sys_roles.name IS '角色名称 (如: 管理员)';
                COMMENT ON COLUMN sys_roles.code IS '角色编码 (如: admin)';
                COMMENT ON COLUMN sys_roles.description IS '角色描述';
                COMMENT ON COLUMN sys_roles.is_active IS '是否启用';
                COMMENT ON COLUMN sys_roles.created_at IS '创建时间';
                COMMENT ON COLUMN sys_roles.updated_at IS '更新时间';
                """
            },
            # 4. 权限表 (sys_permissions)
            {
                "name": "sys_permissions",
                "desc": "系统权限表",
                "ddl": """
                CREATE TABLE IF NOT EXISTS sys_permissions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(50) NOT NULL,
                    code VARCHAR(100) NOT NULL UNIQUE, -- 权限标识 (user:create)
                    type VARCHAR(20) NOT NULL, -- menu, button, api
                    parent_id UUID REFERENCES sys_permissions(id) ON DELETE SET NULL,
                    path VARCHAR(200), -- 路由路径或API路径
                    method VARCHAR(10), -- GET, POST (仅API类型有效)
                    icon VARCHAR(50),
                    order_num INT DEFAULT 0,
                    created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
                    updated_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
                );
                COMMENT ON TABLE sys_permissions IS '系统权限表';
                COMMENT ON COLUMN sys_permissions.id IS '权限ID';
                COMMENT ON COLUMN sys_permissions.name IS '权限名称';
                COMMENT ON COLUMN sys_permissions.code IS '权限标识 (如 user:add)';
                COMMENT ON COLUMN sys_permissions.type IS '类型 (menu:菜单, button:按钮, api:接口)';
                COMMENT ON COLUMN sys_permissions.parent_id IS '父级权限ID';
                COMMENT ON COLUMN sys_permissions.path IS '路由路径或API地址';
                COMMENT ON COLUMN sys_permissions.method IS 'HTTP方法 (仅API类型)';
                COMMENT ON COLUMN sys_permissions.icon IS '菜单图标';
                COMMENT ON COLUMN sys_permissions.order_num IS '显示排序';
                COMMENT ON COLUMN sys_permissions.created_at IS '创建时间';
                COMMENT ON COLUMN sys_permissions.updated_at IS '更新时间';
                """
            },
            # 5. 用户-角色关联表 (sys_user_roles)
            {
                "name": "sys_user_roles",
                "desc": "用户角色关联表",
                "ddl": """
                CREATE TABLE IF NOT EXISTS sys_user_roles (
                    user_id UUID REFERENCES sys_users(id) ON DELETE CASCADE,
                    role_id UUID REFERENCES sys_roles(id) ON DELETE CASCADE,
                    created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
                    updated_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
                    PRIMARY KEY (user_id, role_id)
                );
                COMMENT ON TABLE sys_user_roles IS '用户角色关联表';
                COMMENT ON COLUMN sys_user_roles.user_id IS '用户ID';
                COMMENT ON COLUMN sys_user_roles.role_id IS '角色ID';
                COMMENT ON COLUMN sys_user_roles.created_at IS '创建时间';
                COMMENT ON COLUMN sys_user_roles.updated_at IS '更新时间';
                """
            },
            # 6. 角色-权限关联表 (sys_role_permissions)
            {
                "name": "sys_role_permissions",
                "desc": "角色权限关联表",
                "ddl": """
                CREATE TABLE IF NOT EXISTS sys_role_permissions (
                    role_id UUID REFERENCES sys_roles(id) ON DELETE CASCADE,
                    permission_id UUID REFERENCES sys_permissions(id) ON DELETE CASCADE,
                    created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
                    updated_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
                    PRIMARY KEY (role_id, permission_id)
                );
                COMMENT ON TABLE sys_role_permissions IS '角色权限关联表';
                COMMENT ON COLUMN sys_role_permissions.role_id IS '角色ID';
                COMMENT ON COLUMN sys_role_permissions.permission_id IS '权限ID';
                COMMENT ON COLUMN sys_role_permissions.created_at IS '创建时间';
                COMMENT ON COLUMN sys_role_permissions.updated_at IS '更新时间';
                """
            }
        ]

        try:
            for table in tables:
                await conn.execute(table["ddl"])
                
                # 尝试修复旧表时间字段及添加新字段 (针对已存在的表)
                if "sys_" in table["name"]:
                    # 1. 确保时间字段存在
                    try:
                         await conn.execute(f"ALTER TABLE {table['name']} ADD COLUMN IF NOT EXISTS created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')")
                         await conn.execute(f"ALTER TABLE {table['name']} ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')")
                    except Exception as e:
                         logger.warning(f"表 {table['name']} 添加时间字段失败: {e}")

                    # 2. 修复时间字段类型
                    try:
                        await conn.execute(f"ALTER TABLE {table['name']} ALTER COLUMN created_at TYPE TIMESTAMP(0) USING created_at::TIMESTAMP(0)")
                        await conn.execute(f"ALTER TABLE {table['name']} ALTER COLUMN updated_at TYPE TIMESTAMP(0) USING updated_at::TIMESTAMP(0)")
                        await conn.execute(f"ALTER TABLE {table['name']} ALTER COLUMN created_at SET DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')")
                        await conn.execute(f"ALTER TABLE {table['name']} ALTER COLUMN updated_at SET DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')")
                    except Exception as e:
                        # 如果是字段不存在，尝试强制添加
                        if "does not exist" in str(e):
                            logger.warning(f"表 {table['name']} 修复时间字段失败(字段不存在)，尝试强制添加")
                            try:
                                await conn.execute(f"ALTER TABLE {table['name']} ADD COLUMN IF NOT EXISTS created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')")
                                await conn.execute(f"ALTER TABLE {table['name']} ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')")
                                logger.success(f"表 {table['name']} 强制添加时间字段成功")
                            except Exception as e2:
                                logger.error(f"表 {table['name']} 强制添加字段失败: {e2}")
                        else:
                            logger.warning(f"表 {table['name']} 修复时间字段失败: {e}")
                        
                    # 3. 自动迁移: sys_users 添加 source 字段
                    if table["name"] == "sys_users":
                        try:
                            await conn.execute("ALTER TABLE sys_users ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'local'")
                            await conn.execute("COMMENT ON COLUMN sys_users.source IS '用户来源 (local:本地注册, wecom:企业微信, feishu:飞书)'")
                        except Exception as e:
                            logger.warning(f"表 sys_users 添加 source 字段失败: {e}")
                
                logger.success(f"表 {table['name']} 初始化成功")
                await self._update_table_registry(conn, table["name"], table["desc"])
        except Exception as e:
            logger.error(f"初始化 RBAC 表失败: {e}")
            raise e

    async def init_env_log_table(self, conn):
        """
        初始化环境配置日志表 (sys_env_logs)
        """
        table_name = "sys_env_logs"
        ddl = """
        CREATE TABLE IF NOT EXISTS sys_env_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            env_hash VARCHAR(64) NOT NULL,
            env_content TEXT,
            machine_info VARCHAR(255),
            created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
            updated_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
        );
        COMMENT ON TABLE sys_env_logs IS '系统环境配置日志表，用于备份 .env 历史';
        COMMENT ON COLUMN sys_env_logs.id IS '主键ID';
        COMMENT ON COLUMN sys_env_logs.env_hash IS '环境配置哈希值 (MD5)';
        COMMENT ON COLUMN sys_env_logs.env_content IS '环境配置内容';
        COMMENT ON COLUMN sys_env_logs.machine_info IS '机器信息 (IP/Host)';
        COMMENT ON COLUMN sys_env_logs.created_at IS '创建时间';
        COMMENT ON COLUMN sys_env_logs.updated_at IS '更新时间';
        """
        try:
            await conn.execute(ddl)
            logger.success(f"表 {table_name} 初始化成功")
            await self._update_table_registry(conn, table_name, "系统环境配置日志表，用于备份 .env 历史")
        except Exception as e:
            logger.error(f"初始化 {table_name} 失败: {e}")
            raise e

    async def init_superuser(self, conn):
        """
        初始化超级管理员 (A6666)
        """
        try:
            # 检查是否已存在
            exists = await conn.fetchval("SELECT 1 FROM sys_users WHERE username = 'A6666'")
            if not exists:
                password_hash = get_password_hash("123456")
                await conn.execute("""
                    INSERT INTO sys_users (username, password_hash, full_name, is_superuser, is_active, source, created_at, updated_at)
                    VALUES ('A6666', $1, '超级管理员', TRUE, TRUE, 'local', NOW(), NOW())
                """, password_hash)
                logger.success("✅ 已创建默认超级管理员: A6666 / 123456")
            else:
                # 确保 A6666 是超级管理员且激活
                await conn.execute("""
                    UPDATE sys_users 
                    SET is_superuser = TRUE, is_active = TRUE, updated_at = NOW()
                    WHERE username = 'A6666'
                """)
                logger.info("✅ 超级管理员 A6666 已存在 (已确保权限正确)")
                
        except Exception as e:
            logger.error(f"❌ 初始化超级管理员失败: {e}")

    async def init_user_audios_table(self, conn):
        """
        初始化用户音频表 (user_audios)
        """
        table_name = "user_audios"
        ddl = """
        CREATE TABLE IF NOT EXISTS user_audios (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id VARCHAR(50) NOT NULL,
            filename VARCHAR(255) NOT NULL,
            s3_key VARCHAR(500) NOT NULL,
            url TEXT NOT NULL,
            size BIGINT,
            duration FLOAT,
            mime_type VARCHAR(100),
            module VARCHAR(50) DEFAULT 'common',
            source VARCHAR(20) DEFAULT 'upload', -- upload, generated
            prompt TEXT, -- TTS 文本
            text_content TEXT, -- ASR 识别结果 或 TTS 文本
            meta_data JSONB, -- 扩展信息
            is_deleted BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
            updated_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
        );
        COMMENT ON TABLE user_audios IS '用户音频表';
        COMMENT ON COLUMN user_audios.source IS '来源 (upload:上传, generated:生成)';
        COMMENT ON COLUMN user_audios.duration IS '时长(秒)';
        COMMENT ON COLUMN user_audios.text_content IS 'ASR识别结果或TTS文本';
        """
        try:
            await conn.execute(ddl)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_audios_user_id ON user_audios(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_audios_created_at ON user_audios(created_at DESC)")
            
            logger.success(f"表 {table_name} 初始化成功")
            await self._update_table_registry(conn, table_name, "用户音频表")
        except Exception as e:
            logger.error(f"初始化 {table_name} 失败: {e}")
            raise e

    async def init_chat_messages_table(self, conn):
        """
        初始化聊天消息表 (chat_messages)
        """
        table_name = "chat_messages"
        ddl_create = """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id VARCHAR(50), -- 会话ID (可选，用于分组)
            user_id VARCHAR(50) NOT NULL,
            role VARCHAR(20) NOT NULL, -- user, assistant, system
            content_type VARCHAR(20) DEFAULT 'text', -- text, image, audio, mixed
            content TEXT, -- 文本内容 (如果是 mixed，则是 JSON)
            model VARCHAR(50), -- 使用的模型名称
            media_urls JSONB, -- 关联的媒体文件 URLs (数组)
            meta_data JSONB, -- 扩展信息 (如 tokens, model_name)
            is_deleted BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
        );
        """
        
        ddl_comments = """
        COMMENT ON TABLE chat_messages IS '多模态对话历史表';
        COMMENT ON COLUMN chat_messages.role IS '角色 (user/assistant/system)';
        COMMENT ON COLUMN chat_messages.content_type IS '内容类型';
        COMMENT ON COLUMN chat_messages.model IS '模型名称';
        """
        
        try:
            # 1. 创建表 (如果不存在)
            await conn.execute(ddl_create)
            
            # 2. 补丁：确保 model 字段存在 (针对旧表)
            # 注意: 必须在添加注释之前执行
            await conn.execute("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS model VARCHAR(50)")
            
            # 3. 添加注释
            await conn.execute(ddl_comments)
            
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at DESC)")
            
            logger.success(f"表 {table_name} 初始化成功")
            await self._update_table_registry(conn, table_name, "多模态对话历史表")
        except Exception as e:
            logger.error(f"初始化 {table_name} 失败: {e}")
            raise e

    async def init_customer_leads_table(self, conn):
        """
        初始化客户留资线索表 (customer_leads)
        """
        table_name = "customer_leads"
        ddl = """
        CREATE TABLE IF NOT EXISTS customer_leads (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            phone VARCHAR(50) NOT NULL,
            product VARCHAR(255),
            region VARCHAR(255),
            client_ip VARCHAR(50),
            user_agent TEXT,
            submission_id VARCHAR(255) UNIQUE,
            submit_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            is_deleted BOOLEAN DEFAULT FALSE
        );
        COMMENT ON TABLE customer_leads IS '客户留资线索表';
        COMMENT ON COLUMN customer_leads.name IS '姓名';
        COMMENT ON COLUMN customer_leads.phone IS '电话';
        COMMENT ON COLUMN customer_leads.product IS '感兴趣产品';
        COMMENT ON COLUMN customer_leads.region IS '区域';
        COMMENT ON COLUMN customer_leads.client_ip IS '客户端IP';
        COMMENT ON COLUMN customer_leads.user_agent IS '浏览器UA';
        COMMENT ON COLUMN customer_leads.submission_id IS '提交ID (唯一)';
        COMMENT ON COLUMN customer_leads.status IS '处理状态 (pending/processed)';
        COMMENT ON COLUMN customer_leads.is_deleted IS '是否删除';
        COMMENT ON COLUMN customer_leads.created_at IS '创建时间';
        COMMENT ON COLUMN customer_leads.updated_at IS '更新时间';
        """
        
        try:
            await conn.execute(ddl)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_leads_phone ON customer_leads(phone)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_leads_submission_id ON customer_leads(submission_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_leads_created_at ON customer_leads(created_at DESC)")
            
            logger.success(f"表 {table_name} 初始化成功")
            await self._update_table_registry(conn, table_name, "客户留资线索表")
        except Exception as e:
            logger.error(f"初始化 {table_name} 失败: {e}")
            raise e

    async def init_dify_apps_table(self, conn):
        """
        初始化 Dify 应用表 (sys_dify_apps)
        """
        table_name = "sys_dify_apps"
        ddl = """
        CREATE TABLE IF NOT EXISTS sys_dify_apps (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            dify_app_id VARCHAR(100) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(255),
            api_key VARCHAR(255),
            mode VARCHAR(50) DEFAULT 'chat',
            icon VARCHAR(255),
            icon_background VARCHAR(20),
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            sync_source VARCHAR(20) DEFAULT 'api', -- api, manual, db_direct
            created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
            updated_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
        );
        COMMENT ON TABLE sys_dify_apps IS 'Dify应用配置表';
        COMMENT ON COLUMN sys_dify_apps.dify_app_id IS 'Dify平台AppID';
        COMMENT ON COLUMN sys_dify_apps.name IS '应用名称';
        COMMENT ON COLUMN sys_dify_apps.api_key IS 'API密钥';
        COMMENT ON COLUMN sys_dify_apps.mode IS '应用模式 (chat/workflow)';
        COMMENT ON COLUMN sys_dify_apps.sync_source IS '同步来源';
        """
        
        try:
            await conn.execute(ddl)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_sys_dify_apps_dify_app_id ON sys_dify_apps(dify_app_id)")
            
            logger.success(f"表 {table_name} 初始化成功")
            await self._update_table_registry(conn, table_name, "Dify应用配置表")
        except Exception as e:
            logger.error(f"初始化 {table_name} 失败: {e}")
            raise e

    async def sync_dify_apps(self):
        """
        从 Dify 数据库同步应用列表到本地 sys_dify_apps 表
        """
        logger.info("🚀 [Dify] 开始同步 Dify 应用到本地数据库...")
        
        # Dify DB Config (Use Settings)
        dify_db_config = {
            "host": settings.DIFY_PG_HOST,
            "port": settings.DIFY_PG_PORT,
            "user": settings.DIFY_PG_USER,
            "password": settings.DIFY_PG_PASSWORD,
            "database": settings.DIFY_PG_DB
        }
        
        dify_conn = None
        local_conn = None
        
        try:
            # 1. Connect to Dify DB
            try:
                dify_conn = await asyncpg.connect(**dify_db_config)
            except Exception as e:
                logger.warning(f"⚠️ [Dify] 无法连接 Dify 数据库 (跳过同步): {e}")
                return

            # 2. Connect to Local DB
            local_conn = await asyncpg.connect(
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port,
                database=self.target_db
            )

            # 3. Fetch Data
            # Get Apps
            apps = await dify_conn.fetch("""
                SELECT id, name, mode, icon, icon_background, description, created_at 
                FROM apps 
                ORDER BY created_at DESC
            """)
            
            # Get Tokens
            tokens = await dify_conn.fetch("SELECT app_id, token FROM api_tokens WHERE type='app'")
            token_map = {str(t['app_id']): t['token'] for t in tokens}
            
            logger.info(f"📊 [Dify] 发现 {len(apps)} 个应用, {len(tokens)} 个 API Key")

            # 4. Upsert
            count = 0
            for app in apps:
                app_id = str(app['id'])
                api_key = token_map.get(app_id)
                
                await local_conn.execute("""
                    INSERT INTO sys_dify_apps (
                        dify_app_id, name, api_key, mode, icon, icon_background, description, 
                        sync_source, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, 'db_direct', NOW()
                    )
                    ON CONFLICT (dify_app_id) 
                    DO UPDATE SET 
                        name = EXCLUDED.name,
                        api_key = COALESCE(EXCLUDED.api_key, sys_dify_apps.api_key),
                        mode = EXCLUDED.mode,
                        icon = EXCLUDED.icon,
                        icon_background = EXCLUDED.icon_background,
                        description = EXCLUDED.description,
                        sync_source = 'db_direct',
                        updated_at = NOW();
                """, 
                    app_id, app['name'], api_key, app['mode'], 
                    app['icon'], app['icon_background'], app['description']
                )
                count += 1
            
            logger.success(f"✅ [Dify] 同步完成! 已更新 {count} 个应用配置")
            
        except Exception as e:
            logger.error(f"❌ [Dify] 同步失败: {e}")
        finally:
            if dify_conn:
                await dify_conn.close()
            if local_conn:
                await local_conn.close()

    async def init_ai_video_tasks_table(self, conn):
        """
        初始化 AI 视频生成任务表 (ai_video_tasks)
        """
        table_name = "ai_video_tasks"
        ddl = """
        CREATE TABLE IF NOT EXISTS ai_video_tasks (
            id SERIAL PRIMARY KEY,
            task_id VARCHAR(64) NOT NULL UNIQUE,
            user_id VARCHAR(64),
            prompt TEXT NOT NULL,
            model VARCHAR(64) DEFAULT 'Wan2.1-T2V-1.3B',
            status VARCHAR(32) DEFAULT 'pending',
            video_url VARCHAR(512),
            cover_url VARCHAR(512),
            width INTEGER,
            height INTEGER,
            duration FLOAT,
            cost_time FLOAT,
            error_msg TEXT,
            created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai'),
            updated_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
        );
        COMMENT ON TABLE ai_video_tasks IS 'AI视频生成任务表';
        COMMENT ON COLUMN ai_video_tasks.id IS '主键ID';
        COMMENT ON COLUMN ai_video_tasks.task_id IS '任务ID (UUID)';
        COMMENT ON COLUMN ai_video_tasks.user_id IS '用户ID';
        COMMENT ON COLUMN ai_video_tasks.prompt IS '提示词';
        COMMENT ON COLUMN ai_video_tasks.model IS '模型名称';
        COMMENT ON COLUMN ai_video_tasks.status IS '状态: pending/processing/success/failed';
        COMMENT ON COLUMN ai_video_tasks.video_url IS '视频地址 (S3/Local)';
        COMMENT ON COLUMN ai_video_tasks.cover_url IS '封面图地址';
        COMMENT ON COLUMN ai_video_tasks.width IS '宽度';
        COMMENT ON COLUMN ai_video_tasks.height IS '高度';
        COMMENT ON COLUMN ai_video_tasks.duration IS '视频时长(秒)';
        COMMENT ON COLUMN ai_video_tasks.cost_time IS '生成耗时(秒)';
        COMMENT ON COLUMN ai_video_tasks.error_msg IS '错误信息';
        COMMENT ON COLUMN ai_video_tasks.created_at IS '创建时间';
        COMMENT ON COLUMN ai_video_tasks.updated_at IS '更新时间';
        """
        
        try:
            await conn.execute(ddl)
            # 索引
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_video_tasks_task_id ON ai_video_tasks(task_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_video_tasks_user_id ON ai_video_tasks(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_video_tasks_status ON ai_video_tasks(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_video_tasks_created_at ON ai_video_tasks(created_at DESC)")
            
            logger.success(f"表 {table_name} 初始化成功")
            await self._update_table_registry(conn, table_name, "AI视频生成任务表")
        except Exception as e:
            logger.error(f"初始化 {table_name} 失败: {e}")
            raise e

    async def init_tables(self):
        """
        连接目标数据库，创建表结构。
        """
        logger.info(f"🔌 [DB: {self.target_db}] 正在连接以初始化表结构...")
        try:
            conn = await asyncpg.connect(
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port,
                database=self.target_db
            )
            
            # 1. 定义核心表 (request_logs)
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS request_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                request_id VARCHAR(50) NOT NULL,
                method VARCHAR(10) NOT NULL,
                path TEXT NOT NULL,
                status_code INTEGER,
                client_ip VARCHAR(50),
                user_id VARCHAR(50),
                request_body TEXT,
                response_body TEXT,
                error_detail TEXT,
                duration_ms DOUBLE PRECISION,
                is_success BOOLEAN DEFAULT FALSE,
                user_agent TEXT,
                device VARCHAR(100),
                created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
            );
            
            -- 确保 device 字段存在 (针对旧表)
            ALTER TABLE request_logs ADD COLUMN IF NOT EXISTS device VARCHAR(100);
            
            -- 尝试修复时间字段
            try:
                 ALTER TABLE request_logs ALTER COLUMN created_at TYPE TIMESTAMP(0) USING created_at::TIMESTAMP(0);
                 ALTER TABLE request_logs ALTER COLUMN created_at SET DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai');
            except:
                 pass;
            
            -- 添加中文注释
            COMMENT ON TABLE request_logs IS 'API请求日志表';
            COMMENT ON COLUMN request_logs.id IS '唯一主键';
            COMMENT ON COLUMN request_logs.request_id IS '请求追踪ID (X-Request-ID)';
            COMMENT ON COLUMN request_logs.method IS 'HTTP请求方法';
            COMMENT ON COLUMN request_logs.path IS '请求路径';
            COMMENT ON COLUMN request_logs.status_code IS 'HTTP状态码';
            COMMENT ON COLUMN request_logs.client_ip IS '客户端IP地址';
            COMMENT ON COLUMN request_logs.user_id IS '用户ID (若已认证)';
            COMMENT ON COLUMN request_logs.request_body IS '请求体内容 (原始内容)';
            COMMENT ON COLUMN request_logs.response_body IS '响应体内容 (可选)';
            COMMENT ON COLUMN request_logs.error_detail IS '错误堆栈或详情';
            COMMENT ON COLUMN request_logs.duration_ms IS '请求耗时(毫秒)';
            COMMENT ON COLUMN request_logs.is_success IS '请求是否成功 (code<400)';
            COMMENT ON COLUMN request_logs.user_agent IS 'User-Agent';
            COMMENT ON COLUMN request_logs.device IS '客户端设备信息 (PC/Mobile/Tablet)';
            COMMENT ON COLUMN request_logs.created_at IS '请求创建时间 (北京时间)';
            """
            
            # 由于 asyncpg 不能执行多条 SQL (除非用 execute 且不带参数，或者用脚本模式)，这里还是得拆分
            # 但是 asyncpg 的 execute 其实支持简单的多条语句。
            # 为了稳妥，我们手动拆分关键部分，或者简单执行。
            # 注意: 上面的 SQL 字符串中包含 try-except 伪代码，这在 SQL 中是不合法的。我需要修正它。
            
            # 修正后的逻辑：
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS request_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                request_id VARCHAR(50) NOT NULL,
                method VARCHAR(10) NOT NULL,
                path TEXT NOT NULL,
                status_code INTEGER,
                client_ip VARCHAR(50),
                user_id VARCHAR(50),
                request_body TEXT,
                response_body TEXT,
                error_detail TEXT,
                duration_ms DOUBLE PRECISION,
                is_success BOOLEAN DEFAULT FALSE,
                user_agent TEXT,
                device VARCHAR(100),
                created_at TIMESTAMP(0) NOT NULL DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')
            );
            """)
            
            # 补丁和注释
            patch_sql = """
            ALTER TABLE request_logs ADD COLUMN IF NOT EXISTS device VARCHAR(100);
            
            COMMENT ON TABLE request_logs IS 'API请求日志表';
            COMMENT ON COLUMN request_logs.id IS '唯一主键';
            COMMENT ON COLUMN request_logs.request_id IS '请求追踪ID (X-Request-ID)';
            COMMENT ON COLUMN request_logs.method IS 'HTTP请求方法';
            COMMENT ON COLUMN request_logs.path IS '请求路径';
            COMMENT ON COLUMN request_logs.status_code IS 'HTTP状态码';
            COMMENT ON COLUMN request_logs.client_ip IS '客户端IP地址';
            COMMENT ON COLUMN request_logs.user_id IS '用户ID (若已认证)';
            COMMENT ON COLUMN request_logs.request_body IS '请求体内容 (原始内容)';
            COMMENT ON COLUMN request_logs.response_body IS '响应体内容 (可选)';
            COMMENT ON COLUMN request_logs.error_detail IS '错误堆栈或详情';
            COMMENT ON COLUMN request_logs.duration_ms IS '请求耗时(毫秒)';
            COMMENT ON COLUMN request_logs.is_success IS '请求是否成功 (code<400)';
            COMMENT ON COLUMN request_logs.user_agent IS 'User-Agent';
            COMMENT ON COLUMN request_logs.device IS '客户端设备信息 (PC/Mobile/Tablet)';
            COMMENT ON COLUMN request_logs.created_at IS '请求创建时间 (北京时间)';
            """
            await conn.execute(patch_sql)
            
            # 自动迁移: 修改时间字段精度
            try:
                await conn.execute("ALTER TABLE request_logs ALTER COLUMN created_at TYPE TIMESTAMP(0) USING created_at::TIMESTAMP(0)")
                await conn.execute("ALTER TABLE request_logs ALTER COLUMN created_at SET DEFAULT (NOW() AT TIME ZONE 'Asia/Shanghai')")
            except:
                pass

            # 更新注册表
            await self._update_table_registry(conn, "request_logs", "API请求日志表，记录所有请求、响应及设备信息")
            logger.success(f"📝 [Registry] 已更新表 'request_logs' 的元数据信息")
            
            # 2. 初始化 AI 模型注册表
            await self.init_ai_model_registry(conn)

            # 3. 初始化用户图片表
            await self.init_user_images_table(conn)

            # 4. 初始化 RBAC 相关表
            await self.init_rbac_tables(conn)

            # 5. 初始化 Env Log 表
            await self.init_env_log_table(conn)
            
            # 6. 初始化语音识别记录表
            await self.init_speech_logs_table(conn)
            
            # 6.1 初始化用户音频表
            await self.init_user_audios_table(conn)

            # 6.2 初始化聊天消息表
            await self.init_chat_messages_table(conn)
            
            # 6.3 初始化客户留资表
            await self.init_customer_leads_table(conn)

            # 6.4 初始化 AI 视频任务表
            await self.init_ai_video_tasks_table(conn)

            # 6.5 初始化 Dify 应用表
            await self.init_dify_apps_table(conn)
            
            # 7. 初始化超级管理员
            await self.init_superuser(conn)

            logger.success("✅ 所有表结构初始化完成")
            await conn.close()
            return True
            
        except Exception as e:
            logger.error(f"❌ 初始化表结构失败: {e}")
            return False

    async def run(self):
        """
        执行完整的初始化流程
        """
        success = await self.check_and_create_db()
        if success:
            await self.init_tables()
            # 自动同步 Dify 应用
            await self.sync_dify_apps()

if __name__ == "__main__":
    import sys
    from pathlib import Path
    # 添加项目根目录到 sys.path 以便导入 config
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))
    
    initializer = DBInitializer()
    asyncio.run(initializer.run())