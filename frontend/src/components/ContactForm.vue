<!--
文件名：frontend/src/components/ContactForm.vue
作者：zcl
日期：2026-01-28
描述：客户留资表单组件
-->
<template>
  <div class="contact-form-overlay" v-if="formState.show" @click="handleClose">
    <div class="contact-form-container" @click.stop>
      <div class="form-header">
        <h3>填写联系方式</h3>
        <span class="close-btn" @click="handleClose">&times;</span>
      </div>
      
      <div class="form-body" v-if="!formState.submitResult.showResult">
        <p class="form-desc">请留下您的联系方式，我们将安排专人为您服务</p>
        
        <div class="form-group">
          <label>姓名 <span class="required">*</span></label>
          <input 
            type="text" 
            v-model="formState.contact.name" 
            placeholder="请输入您的姓名"
            :class="{ 'error': formState.errors.name }"
            @input="formState.errors.name = ''"
          />
          <span class="error-msg" v-if="formState.errors.name">{{ formState.errors.name }}</span>
        </div>
        
        <div class="form-group">
          <label>手机号码 <span class="required">*</span></label>
          <input 
            type="text" 
            v-model="formState.contact.phone" 
            placeholder="请输入手机号码"
            :class="{ 'error': formState.errors.phone }"
            @input="formState.errors.phone = ''"
            maxlength="11"
          />
          <span class="error-msg" v-if="formState.errors.phone">{{ formState.errors.phone }}</span>
        </div>
        
        <div class="form-group">
          <label>感兴趣的产品 <span class="required">*</span></label>
          <input 
            type="text" 
            v-model="formState.contact.product" 
            placeholder="例如：静脉留置针"
            :class="{ 'error': formState.errors.product }"
            @input="formState.errors.product = ''"
          />
          <span class="error-msg" v-if="formState.errors.product">{{ formState.errors.product }}</span>
        </div>
        
        <div class="form-group">
          <label>所在区域 <span class="required">*</span></label>
          <input 
            type="text" 
            v-model="formState.contact.zona" 
            placeholder="例如：河南省长垣市"
            :class="{ 'error': formState.errors.zona }"
            @input="formState.errors.zona = ''"
          />
          <span class="error-msg" v-if="formState.errors.zona">{{ formState.errors.zona }}</span>
        </div>
        
        <div class="form-actions">
          <button 
            class="submit-btn" 
            :disabled="formState.isSubmitting"
            @click="submitContactForm"
          >
            {{ formState.isSubmitting ? '提交中...' : '立即提交' }}
          </button>
        </div>
      </div>
      
      <div class="result-body" v-else>
        <div class="success-icon" v-if="formState.submitResult.success">✓</div>
        <div class="error-icon" v-else>!</div>
        <h3>{{ formState.submitResult.success ? '提交成功' : '提交失败' }}</h3>
        <p>{{ formState.submitResult.message }}</p>
        <button class="close-result-btn" @click="handleClose">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, onMounted } from 'vue';
import { submitCustomerInfo, type CustomerData } from '@/api/customer';

const emit = defineEmits(['close', 'submit']);

const formState = reactive({
  show: true,
  isSubmitting: false,
  contact: {
    name: '',
    phone: '',
    product: '',
    zona: ''
  } as CustomerData,
  errors: {
    name: '',
    phone: '',
    product: '',
    zona: ''
  },
  submitResult: {
    success: false,
    message: '',
    showResult: false
  }
});

const handleClose = () => {
  emit('close');
};

const validateForm = () => {
  let isValid = true;

  // Name validation
  const name = formState.contact.name.trim();
  if (!name) {
    formState.errors.name = '请填写您的姓名';
    isValid = false;
  } else if (!/^[\u4e00-\u9fa5a-zA-Z\s]{2,20}$/.test(name)) {
    formState.errors.name = '姓名请输入2-20个中英文字符';
    isValid = false;
  } else {
    formState.errors.name = '';
  }

  // Phone validation
  const phone = formState.contact.phone.trim();
  if (!phone) {
    formState.errors.phone = '请填写您的联系电话';
    isValid = false;
  } else if (!/^1[3-9]\d{9}$/.test(phone)) {
    formState.errors.phone = '请填写正确的11位手机号码';
    isValid = false;
  } else {
    formState.errors.phone = '';
  }

  // Product validation
  const product = formState.contact.product.trim();
  if (!product) {
    formState.errors.product = '请填写您感兴趣的产品';
    isValid = false;
  } else {
    formState.errors.product = '';
  }

  // Zona validation
  const zona = formState.contact.zona.trim();
  if (!zona) {
    formState.errors.zona = '请填写您所在的区域';
    isValid = false;
  } else {
    formState.errors.zona = '';
  }

  return isValid;
};

const submitContactForm = async () => {
  if (formState.isSubmitting) return;
  
  if (validateForm()) {
    formState.isSubmitting = true;
    formState.submitResult.showResult = false;
    
    try {
      const result = await submitCustomerInfo(formState.contact);
      
      formState.submitResult = {
        success: result.success,
        message: result.message,
        showResult: true
      };
      
      if (result.success) {
        setTimeout(() => {
          emit('submit', formState.contact);
          // handleClose(); // Let user close it or close automatically
        }, 1500);
      }
      
    } catch (error: any) {
      formState.submitResult = {
        success: false,
        message: error.message || '网络异常，请重试',
        showResult: true
      };
    } finally {
      formState.isSubmitting = false;
    }
  }
};
</script>

<style scoped>
.contact-form-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}

.contact-form-container {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 400px;
  padding: 20px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  border-bottom: 1px solid #eee;
  padding-bottom: 10px;
}

.form-header h3 {
  margin: 0;
  font-size: 18px;
  color: #333;
}

.close-btn {
  font-size: 24px;
  cursor: pointer;
  color: #999;
  line-height: 1;
}

.form-desc {
  font-size: 14px;
  color: #666;
  margin-bottom: 20px;
}

.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  font-size: 14px;
  color: #333;
  margin-bottom: 6px;
}

.required {
  color: red;
}

.form-group input {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.3s;
  box-sizing: border-box;
}

.form-group input:focus {
  border-color: #2473ba;
}

.form-group input.error {
  border-color: #ff4d4f;
}

.error-msg {
  font-size: 12px;
  color: #ff4d4f;
  margin-top: 4px;
  display: block;
}

.form-actions {
  margin-top: 25px;
}

.submit-btn {
  width: 100%;
  background: #2473ba;
  color: white;
  border: none;
  padding: 12px;
  border-radius: 6px;
  font-size: 16px;
  cursor: pointer;
  transition: background 0.3s;
}

.submit-btn:disabled {
  background: #8cc0ea;
  cursor: not-allowed;
}

.result-body {
  text-align: center;
  padding: 20px 0;
}

.success-icon {
  width: 60px;
  height: 60px;
  background: #52c41a;
  color: white;
  border-radius: 50%;
  font-size: 36px;
  line-height: 60px;
  margin: 0 auto 15px;
}

.error-icon {
  width: 60px;
  height: 60px;
  background: #ff4d4f;
  color: white;
  border-radius: 50%;
  font-size: 36px;
  line-height: 60px;
  margin: 0 auto 15px;
}

.close-result-btn {
  margin-top: 20px;
  padding: 8px 24px;
  border: 1px solid #ddd;
  background: white;
  border-radius: 4px;
  cursor: pointer;
}
</style>
