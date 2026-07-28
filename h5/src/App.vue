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
        <span class="icon">🔥</span>
        <span class="label">机会</span>
      </router-link>
      <router-link to="/status" class="tab" active-class="active">
        <span class="icon">📊</span>
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
  padding-bottom: 60px;
}

.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header h1 {
  font-size: 18px;
  font-weight: 600;
}

.badge {
  background: rgba(255,255,255,0.2);
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
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
  background: white;
  border-top: 1px solid #e8e8e8;
  display: flex;
  justify-content: space-around;
  padding: 6px 0;
  z-index: 100;
}

.tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-decoration: none;
  color: #999;
  font-size: 12px;
  padding: 4px 24px;
}

.tab .icon {
  font-size: 20px;
  margin-bottom: 2px;
}

.tab.active {
  color: #667eea;
}
</style>
