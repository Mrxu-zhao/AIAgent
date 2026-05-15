<template>
  <div class="${componentName}-container">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="!data?.length" class="empty">暂无数据</div>
    <div v-else class="content">
      <div
        v-for="item in data"
        :key="item.id"
        class="item"
        @click="handleSelect(item)"
      >
        {{ item.name }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  data?: any[]
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  data: () => [],
  loading: false
})

const emit = defineEmits<{
  (e: 'update', value: any): void
  (e: 'select', item: any): void
}>()

const handleSelect = (item: any) => {
  emit('select', item)
}
</script>

<style scoped lang="scss">
.${componentName}-container {
  padding: 16px;

  .loading {
    text-align: center;
    color: #999;
  }

  .empty {
    text-align: center;
    color: #999;
    padding: 32px;
  }

  .item {
    padding: 12px;
    border-bottom: 1px solid #eee;
    cursor: pointer;

    &:hover {
      background: #f5f5f5;
    }
  }
}
</style>
