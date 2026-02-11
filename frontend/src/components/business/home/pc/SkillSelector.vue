<!--
文件名：frontend/src/components/business/home/SkillSelector.vue
作者：zcl
日期：2026-01-28
描述：技能选择组件
-->
<script setup lang="ts">
import { ElPopover } from 'element-plus';
import type { Skill } from '@/composables/useSkills';

defineProps<{
  visibleSkills: Skill[];
  moreSkills: Skill[];
  moreSkillItem: Skill;
}>();

const emit = defineEmits<{
  (e: 'select', skill: Skill): void;
}>();
</script>

<template>
  <div class="skills-grid">
    <button 
      v-for="skill in visibleSkills" 
      :key="skill.label" 
      class="skill-chip"
      @click="emit('select', skill)"
      :style="{ '--skill-color': skill.color || '#4e5969' } as any"
    >
      <span class="skill-icon" v-html="skill.icon"></span>
      <span class="skill-label">{{ skill.label }}</span>
    </button>
    
    <!-- 更多按钮 -->
    <el-popover
      placement="top-start"
      :width="200"
      trigger="hover"
      popper-class="more-skills-popover"
    >
      <template #reference>
        <button 
          class="skill-chip"
          :style="{ '--skill-color': moreSkillItem.color } as any"
        >
          <span class="skill-icon" v-html="moreSkillItem.icon"></span>
          <span class="skill-label">{{ moreSkillItem.label }}</span>
        </button>
      </template>
      <div class="more-skills-list">
        <div 
          v-for="skill in moreSkills" 
          :key="skill.label" 
          class="more-skill-item"
          @click="emit('select', skill)"
        >
          <span class="skill-icon" v-html="skill.icon" :style="{ color: skill.color }"></span>
          <span class="skill-label">{{ skill.label }}</span>
        </div>
      </div>
    </el-popover>
  </div>
</template>

<style scoped lang="scss">
.skills-grid {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.75rem;
  margin-top: 1.25rem;

  .skill-chip {
    display: flex;
    align-items: center;
    background: #f7f8fa;
    border: 1px solid #e5e6eb;
    padding: 0.5rem 1rem;
    border-radius: 1.25rem;
    cursor: pointer;
    transition: all 0.2s;
    
    &:hover {
      background: white;
      border-color: var(--skill-color, #165dff);
      box-shadow: 0 0.125rem 0.5rem rgba(0,0,0,0.05);
    }

    .skill-icon { 
      margin-right: 0.375rem; 
      color: var(--skill-color, #4e5969);
      display: flex;
      align-items: center;
    }
    .skill-label { font-size: 0.875rem; color: #4e5969; }
  }
}
</style>

<style lang="scss">
.more-skills-popover {
  padding: 0.5rem !important;
  border-radius: 0.75rem !important;
  background: #fff !important;
  border: 1px solid #e5e6eb !important;
  box-shadow: 0 0.25rem 0.75rem rgba(0, 0, 0, 0.15) !important;
  
  .more-skills-list {
    display: flex;
    flex-direction: column;
    
    .more-skill-item {
      display: flex;
      align-items: center;
      padding: 0.625rem;
      cursor: pointer;
      border-radius: 0.5rem;
      transition: background-color 0.2s;
      
      &:hover {
        background-color: #f2f3f5;
      }
      
      .skill-icon {
        margin-right: 0.625rem;
        display: flex;
        align-items: center;
        width: 1rem;
        height: 1rem;
      }
      
      .skill-label {
        font-size: 0.875rem;
        color: #4e5969;
      }
    }
  }
}
</style>
