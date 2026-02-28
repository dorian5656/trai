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
            v-model="formState.contact.region" 
            placeholder="例如：河南省长垣市"
            :class="{ 'error': formState.errors.region }"
            @input="formState.errors.region = ''"
          />
          <span class="error-msg" v-if="formState.errors.region">{{ formState.errors.region }}</span>
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
import { submitContactLead } from '@/api/contact';

const emit = defineEmits(['close', 'submit']);

const formState = reactive({
  show: true,
  isSubmitting: false,
  contact: {
    name: '',
    phone: '',
    product: '',
    region: ''
  },
  errors: {
    name: '',
    phone: '',
    product: '',
    region: ''
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
  const region = formState.contact.region.trim();
  if (!region) {
    formState.errors.region = '请填写您所在的区域';
    isValid = false;
  } else {
    formState.errors.region = '';
  }

  return isValid;
};

const submitContactForm = async () => {
  if (formState.isSubmitting) return;
  
  if (validateForm()) {
    formState.isSubmitting = true;
    formState.submitResult.showResult = false;
    
    try {
      const result = await submitContactLead(formState.contact);
      
      if (result.code === 200) {
        formState.submitResult = {
          success: true,
          message: result.msg,
          showResult: true
        };
      } else {
        formState.submitResult = {
          success: false,
          message: result.msg,
          showResult: true
        };
      }
      
      if (result.code === 200) {
        setTimeout(() => {
          emit('submit', formState.contact);
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
  border-radius: 0.75rem;
  width: 90%;
  max-width: 25rem;
  padding: 1.25rem;
  box-shadow: 0 0.25rem 1.25rem rgba(0, 0, 0, 0.15);
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from { transform: translateY(1.25rem); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.9375rem;
  border-bottom: 1px solid #eee;
  padding-bottom: 0.625rem;
}

.form-header h3 {
  margin: 0;
  font-size: 1.125rem;
  color: #333;
}

.close-btn {
  font-size: 1.5rem;
  cursor: pointer;
  color: #999;
  line-height: 1;
}

.form-desc {
  font-size: 0.875rem;
  color: #666;
  margin-bottom: 1.25rem;
}

.form-group {
  margin-bottom: 0.9375rem;
}

.form-group label {
  display: block;
  font-size: 0.875rem;
  color: #333;
  margin-bottom: 0.375rem;
}

.required {
  color: red;
}

.form-group input {
  width: 100%;
  padding: 0.625rem;
  border: 1px solid #ddd;
  border-radius: 0.375rem;
  font-size: 0.875rem;
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
  font-size: 0.75rem;
  color: #ff4d4f;
  margin-top: 0.25rem;
  display: block;
}

.form-actions {
  margin-top: 1.5625rem;
}

.submit-btn {
  width: 100%;
  background: #2473ba;
  color: white;
  border: none;
  padding: 0.75rem;
  border-radius: 0.375rem;
  font-size: 1rem;
  cursor: pointer;
  transition: background 0.3s;
}

.submit-btn:disabled {
  background: #8cc0ea;
  cursor: not-allowed;
}

.result-body {
  text-align: center;
  padding: 1.25rem 0;
}

.success-icon {
  width: 3.75rem;
  height: 3.75rem;
  background: #52c41a;
  color: white;
  border-radius: 50%;
  font-size: 2.25rem;
  line-height: 3.75rem;
  margin: 0 auto 0.9375rem;
}

.error-icon {
  width: 3.75rem;
  height: 3.75rem;
  background: #ff4d4f;
  color: white;
  border-radius: 50%;
  font-size: 2.25rem;
  line-height: 3.75rem;
  margin: 0 auto 0.9375rem;
}

.close-result-btn {
  margin-top: 1.25rem;
  padding: 0.5rem 1.5rem;
  border: 1px solid #ddd;
  background: white;
  border-radius: 0.25rem;
  cursor: pointer;
}
</style>
