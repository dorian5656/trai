<!--
文件名：frontend/src/views/Login.vue
作者：zcl
日期：2026-01-27
描述：用户登录页面
-->

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { User, Lock, Message, Iphone, UserFilled } from '@element-plus/icons-vue';
import { useUserStore } from '@/stores/user';
import { register } from '@/api/auth';

const router = useRouter();
const userStore = useUserStore();
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
    
    // 跳转回首页
    router.push('/');
  } catch (error: any) {
    console.error(error);
    // 错误信息已在 request 拦截器中处理，但如果是 Network Error 可以在这里补充提示
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
    // 错误处理交由拦截器或显示默认
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
</script>

<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h2>{{ isRegister ? '用户注册' : 'TRAI 系统登录' }}</h2>
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
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #f0f2f5;
  background-image: url('https://gw.alipayobjects.com/zos/rmsportal/TVYTbAXWheQpRcWDaDMu.svg');
  background-repeat: no-repeat;
  background-position: center 110px;
  background-size: 100%;
}

.login-card {
  width: 100%;
  max-width: 420px;
  padding: 40px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  transition: all 0.3s;
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.login-header h2 {
  font-size: 24px;
  color: #303133;
  font-weight: 600;
  margin-bottom: 10px;
}

.subtitle {
  color: #909399;
  font-size: 14px;
  margin: 0;
}

.login-form, .register-form {
  margin-top: 20px;
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
