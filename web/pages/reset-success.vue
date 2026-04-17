<template>
  <main class="done-page">
    <h1>Password updated</h1>
    <p>Your password was successfully reset.</p>
    <NuxtLink class="btn" to="/login">Go to login</NuxtLink>
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
