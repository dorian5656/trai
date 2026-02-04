<!--
文件名：frontend/src/components/business/LoginModal.vue
作者：zcl
日期：2026-02-04
描述：用户登录/注册模态框
-->

<script setup lang="ts">
import { reactive, ref, watch, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { ElMessage } from 'element-plus';
import { User, Lock, Message, Iphone, UserFilled } from '@element-plus/icons-vue';
import { useUserStore } from '@/stores/user';
import { useAppStore } from '@/stores/app';
import { register } from '@/api/auth';

const router = useRouter();
const route = useRoute();
const userStore = useUserStore();
const appStore = useAppStore();
const loading = ref(false);
const isRegister = ref(false); // 切换登录/注册模式

const loginForm = reactive({
  username: '',
  password: '',
});

const registerForm = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  full_name: '',
  email: '',
  phone: '',
});

// 监听模态框关闭，重置表单
watch(
  () => appStore.showLoginModal,
  (val) => {
    if (!val) {
      // 延迟重置，避免弹窗关闭动画时内容突然变空
      setTimeout(() => {
        isRegister.value = false;
        loginForm.username = '';
        loginForm.password = '';
        registerForm.username = '';
        registerForm.password = '';
        registerForm.confirmPassword = '';
        registerForm.full_name = '';
        registerForm.email = '';
        registerForm.phone = '';
      }, 300);
    }
  }
);

const handleLogin = async () => {
  if (!loginForm.username || !loginForm.password) {
    ElMessage.warning('请输入用户名和密码');
    return;
  }

  loading.value = true;
  try {
    await userStore.login({
      username: loginForm.username,
      password: loginForm.password,
    });
    
    ElMessage.success('登录成功');
    
    // 延迟刷新页面，确保 Token 写入和用户看到提示
    setTimeout(() => {
      window.location.reload();
    }, 500);
  } catch (error: any) {
    console.error(error);
    if (error.message && error.message.includes('Network Error')) {
      ElMessage.error('连接服务器失败，请检查网络或联系管理员');
    }
  } finally {
    loading.value = false;
  }
};

const handleRegister = async () => {
  // 简单校验
  if (!registerForm.username || !registerForm.password) {
    ElMessage.warning('请输入用户名和密码');
    return;
  }
  if (registerForm.password !== registerForm.confirmPassword) {
    ElMessage.warning('两次输入的密码不一致');
    return;
  }
  if (registerForm.password.length < 6) {
    ElMessage.warning('密码长度至少 6 位');
    return;
  }

  loading.value = true;
  try {
    await register({
      username: registerForm.username,
      password: registerForm.password,
      full_name: registerForm.full_name,
      email: registerForm.email,
      phone: registerForm.phone,
    });

    ElMessage.success('注册成功！请联系管理员审核激活账号。');
    isRegister.value = false; // 切换回登录页
  } catch (error: any) {
    console.error(error);
  } finally {
    loading.value = false;
  }
};

const toggleMode = () => {
  isRegister.value = !isRegister.value;
  // 清空表单
  loginForm.username = '';
  loginForm.password = '';
  registerForm.username = '';
  registerForm.password = '';
  registerForm.confirmPassword = '';
  registerForm.full_name = '';
  registerForm.email = '';
  registerForm.phone = '';
};

// 处理企业微信回调
onMounted(async () => {
  const code = route.query.code as string;
  // 只有当路由是 /login 或者带有 code 参数时才处理，避免在其他页面误触发
  if (code && !userStore.isLoggedIn) {
    loading.value = true;
    try {
      ElMessage.info('正在进行企业微信授权登录...');
      await userStore.loginByWecom(code);
      ElMessage.success('企业微信登录成功');
      // 直接跳转到首页并刷新，清除 URL 中的 code 参数
      window.location.href = '/';
    } catch (error) {
      console.error(error);
      ElMessage.error('企业微信登录失败，请重试或使用账号密码登录');
      router.replace(route.path); // 清除 query
      appStore.openLoginModal(); // 失败打开登录框
    } finally {
      loading.value = false;
    }
  }
});
</script>

<template>
  <el-dialog
    v-model="appStore.showLoginModal"
    :title="isRegister ? '用户注册' : 'TRAI 系统登录'"
    width="420px"
    center
    align-center
    append-to-body
    destroy-on-close
    class="login-dialog"
    modal-class="login-modal-overlay"
  >
    <div class="login-content">
      <div class="login-header">
        <p class="subtitle">{{ isRegister ? '提交信息后需等待管理员审核' : '欢迎回来，请登录您的账号' }}</p>
      </div>
      
      <!-- 登录表单 -->
      <el-form v-if="!isRegister" class="login-form" @keyup.enter="handleLogin">
        <el-form-item>
          <el-input
            v-model="loginForm.username"
            placeholder="用户名 (如 A0001)"
            :prefix-icon="User"
            size="large"
          />
        </el-form-item>
        
        <el-form-item>
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="密码"
            :prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>
        
        <el-button
          type="primary"
          class="submit-btn"
          size="large"
          :loading="loading"
          @click="handleLogin"
        >
          登录
        </el-button>
      </el-form>

      <!-- 注册表单 -->
      <el-form v-else class="register-form" @keyup.enter="handleRegister">
        <el-form-item>
          <el-input
            v-model="registerForm.username"
            placeholder="用户名 (必填, 如 A0001)"
            :prefix-icon="User"
          />
        </el-form-item>

        <el-form-item>
          <el-input
            v-model="registerForm.full_name"
            placeholder="真实姓名 (选填)"
            :prefix-icon="UserFilled"
          />
        </el-form-item>
        
        <el-form-item>
          <el-input
            v-model="registerForm.password"
            type="password"
            placeholder="密码 (至少6位)"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>

        <el-form-item>
          <el-input
            v-model="registerForm.confirmPassword"
            type="password"
            placeholder="确认密码"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>

        <el-form-item>
          <el-input
            v-model="registerForm.phone"
            placeholder="手机号 (选填)"
            :prefix-icon="Iphone"
          />
        </el-form-item>

        <el-form-item>
          <el-input
            v-model="registerForm.email"
            placeholder="邮箱 (选填)"
            :prefix-icon="Message"
          />
        </el-form-item>
        
        <el-button
          type="success"
          class="submit-btn"
          size="large"
          :loading="loading"
          @click="handleRegister"
        >
          注册账号
        </el-button>
      </el-form>

      <div class="form-footer">
        <el-link type="primary" @click="toggleMode">
          {{ isRegister ? '已有账号？去登录' : '没有账号？去注册' }}
        </el-link>
      </div>
    </div>
  </el-dialog>
</template>

<style>
.login-modal-overlay {
  backdrop-filter: blur(10px);
  background-color: rgba(0, 0, 0, 0.4) !important; /* 加深一点背景以便看清文字 */
}
</style>

<style scoped>
.login-content {
  padding: 0 10px;
}

.login-header {
  text-align: center;
  margin-bottom: 20px;
}

.subtitle {
  color: #909399;
  font-size: 14px;
  margin: 0;
}

.login-form, .register-form {
  margin-top: 10px;
}

.submit-btn {
  width: 100%;
  margin-top: 10px;
  font-size: 16px;
  padding: 12px 0;
}

.form-footer {
  margin-top: 20px;
  text-align: center;
}
</style>
