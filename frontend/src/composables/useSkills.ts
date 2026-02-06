// 文件名：frontend/src/composables/useSkills.ts
// 作者：zcl
// 日期：2026-01-28
// 描述：技能列表逻辑复用

import { ref } from 'vue';
import { ALL_SKILLS, MORE_SKILL_ITEM } from '@/constants/skills';

export interface Skill {
  icon: string;
  label: string;
  color?: string;
}

export function useSkills() {
  const activeSkill = ref<Skill | null>(null);

  const allSkills: Skill[] = ALL_SKILLS;

  const moreSkillItem = MORE_SKILL_ITEM;

  // 前5个展示，剩下的放入更多
  const visibleSkills = allSkills.slice(0, 5);
  const moreSkills = allSkills.slice(5);

  const handleSkillClick = (skill: Skill, onSpecialSkill?: (skill: Skill) => void) => {
    if (skill.label === '相似度识别') {
      if (onSpecialSkill) onSpecialSkill(skill);
    } else {
      activeSkill.value = skill;
    }
  };

  const removeSkill = () => {
    activeSkill.value = null;
  };

  return {
    allSkills,
    activeSkill,
    visibleSkills,
    moreSkills,
    moreSkillItem,
    handleSkillClick,
    removeSkill
  };
}
