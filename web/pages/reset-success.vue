<template>
  <main class="done-page">
    <h1>Пароль обновлен</h1>
    <p>Пароль успешно изменен. Теперь вы можете войти в аккаунт.</p>
    <NuxtLink class="btn" to="/login">Перейти ко входу</NuxtLink>
  </main>
</template>

<style scoped>
.done-page {
  max-width: 420px;
  margin: 40px auto;
  padding: 0 16px;
}

.btn {
  display: inline-block;
  margin-top: 10px;
  background: #111827;
  color: #fff;
  text-decoration: none;
  border-radius: 8px;
  padding: 10px 12px;
}
</style>
