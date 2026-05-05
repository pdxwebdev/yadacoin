<template>
  <div class="agent-nav">
    <div class="nav-label">Agents</div>
    <button
      v-for="agent in agents"
      :key="agent.id"
      class="nav-item"
      :class="{ active: modelValue === agent.id }"
      :title="agent.description"
      @click="$emit('update:modelValue', agent.id)"
    >
      <span class="icon">{{ agent.icon }}</span>
      <span class="label-text">{{ agent.label }}</span>
    </button>
  </div>
</template>

<script setup>
defineProps({ agents: Array, modelValue: String });
defineEmits(["update:modelValue"]);
</script>

<style scoped>
.agent-nav {
  display: flex;
  flex-direction: column;
  padding: 12px 0 8px;
}
.nav-label {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
  padding: 0 14px 8px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 14px;
  background: none;
  border: none;
  border-left: 2px solid transparent;
  color: var(--subtext);
  cursor: pointer;
  text-align: left;
  font-size: 0.86rem;
  font-family: inherit;
  transition:
    background 0.12s,
    color 0.12s,
    border-color 0.12s;
  width: 100%;
}
.nav-item:hover {
  background: rgba(124, 58, 237, 0.08);
  color: var(--text);
}
.nav-item.active {
  border-left-color: var(--accent);
  background: rgba(124, 58, 237, 0.12);
  color: var(--accent2);
}
.icon {
  font-size: 1.1rem;
  flex-shrink: 0;
}
.label-text {
  font-weight: 500;
}
</style>
