<script setup lang="ts">
const { isAuthenticated, user } = useAuthSession();
</script>

<template>
  <main class="container">
    <!-- Authenticated state -->
    <template v-if="isAuthenticated">
      <section class="hero">
        <h1>Генерация инфографики для Ozon</h1>
        <p class="subtitle" v-if="user?.email">Привет, {{ user.email }}!</p>
        <p>Загрузите фото товара, выберите шаблон и получите готовую инфографику.</p>
        <NuxtLink to="/generate" class="cta-btn">Создать инфографику</NuxtLink>
      </section>
    </template>

    <!-- Not authenticated state -->
    <template v-else>
      <section class="hero">
        <h1>Cardgen — генератор инфографики для Ozon</h1>
        <p>Создавайте профессиональную инфографику для карточек товаров на Ozon с помощью ИИ.</p>
        <div class="cta-group">
          <NuxtLink to="/login" class="cta-btn">Войти</NuxtLink>
          <NuxtLink to="/register" class="cta-btn secondary">Регистрация</NuxtLink>
        </div>
      </section>
    </template>
  </main>
</template>

<style scoped>
.container {
  max-width: 760px;
  margin: 40px auto;
  padding: 0 16px;
}

.hero {
  text-align: center;
  padding: 60px 20px;
}

h1 {
  margin-bottom: 12px;
  font-size: 1.8rem;
}

.subtitle {
  color: #4b5563;
  margin-bottom: 8px;
}

.cta-group {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 24px;
}

.cta-btn {
  display: inline-block;
  background: #111827;
  color: #fff;
  padding: 12px 28px;
  border-radius: 10px;
  text-decoration: none;
  font-weight: 600;
  font-size: 1rem;
  transition: background 0.2s;
}

.cta-btn:hover {
  background: #374151;
}

.cta-btn.secondary {
  background: transparent;
  color: #111827;
  border: 2px solid #111827;
}

.cta-btn.secondary:hover {
  background: #f3f4f6;
}
</style>
