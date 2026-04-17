<template>
  <div class="app-shell">
    <header class="top-nav">
      <NuxtLink to="/">Cardgen Auth SPA</NuxtLink>
      <nav>
        <NuxtLink to="/register">Register</NuxtLink>
        <NuxtLink to="/login">Login</NuxtLink>
        <NuxtLink to="/forgot-password">Forgot Password</NuxtLink>
      </nav>
    </header>
    <NuxtPage />
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  font-family: Inter, Arial, sans-serif;
  color: #111827;
}

.top-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid #e5e7eb;
}

.top-nav nav {
  display: flex;
  gap: 14px;
}

a {
  color: #111827;
  text-decoration: none;
}

a.router-link-active {
  font-weight: 700;
}
</style>
