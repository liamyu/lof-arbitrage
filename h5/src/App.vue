<template>
  <div class="app">
    <header class="header">
      <h1>LOF 套利监测</h1>
      <span class="badge">H5</span>
    </header>

    <main class="main">
      <router-view />
    </main>

    <nav class="tabbar">
      <router-link to="/opportunities" class="tab" active-class="active">
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M3 17l6-6 4 4 8-8"/>
          <path d="M17 7h6v6"/>
        </svg>
        <span class="label">机会</span>
      </router-link>
      <router-link to="/status" class="tab" active-class="active">
        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M6 20V10"/>
          <path d="M12 20V4"/>
          <path d="M18 20v-6"/>
        </svg>
        <span class="label">状态</span>
      </router-link>
    </nav>
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  padding-bottom: 64px;
  background: var(--surface-muted);
}

.header {
  background: var(--surface);
  color: var(--foreground);
  padding: 14px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 100;
  border-bottom: 1px solid var(--border);
}

.header h1 {
  font-size: 17px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
}

.badge {
  background: var(--surface-muted);
  color: var(--text-muted);
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid var(--border);
}

.main {
  flex: 1;
  padding: 12px;
}

.tabbar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--surface);
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: space-around;
  padding: 6px 0 calc(6px + env(safe-area-inset-bottom));
  z-index: 100;
}

.tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-decoration: none;
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 500;
  padding: 6px 28px;
  border-radius: var(--radius);
  transition: color 0.16s ease, background-color 0.16s ease;
}

.tab .icon {
  width: 22px;
  height: 22px;
  margin-bottom: 3px;
}

.tab.active {
  color: var(--primary);
  background: var(--surface-muted);
}

@media (min-width: 768px) {
  .app {
    max-width: 480px;
    margin: 0 auto;
    border-left: 1px solid var(--border);
    border-right: 1px solid var(--border);
  }
}
</style>
