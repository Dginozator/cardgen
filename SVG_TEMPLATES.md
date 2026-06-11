# SVG-шаблоны Cardgen

## Обзор

Шаблоны — это обычные SVG-файлы, в которых специальными `id` атрибутами размечены **зоны** для автоматической подстановки данных (изображение товара, заголовок, буллеты).

Вся визуальная компоновка (фон, шрифты, цвета, размеры, расположение) задаётся прямо в SVG — дизайнером, в Figma → Export SVG или любом SVG-редакторе (Inkscape, Boxy SVG, etc).

---

## Зоны (конвенция `id`)

| `id` элемента       | Назначение                          | Тип элемента       |
|----------------------|-------------------------------------|--------------------|
| `zone_product_image` | Область для фото товара            | `<rect>` или `<g>` |
| `zone_text_{field}`  | Текстовое поле                      | `<text>`           |
| `zone_bullets_{field}` | Контейнер для буллетов           | `<g>`              |
| `bg` или `bg_ai`     | Фон (градиент / AI-генерация)      | `<rect>`           |

### Примеры зон

```xml
<!-- Фото товара -->
<rect id="zone_product_image" x="100" y="50" width="700" height="600" fill="transparent"/>

<!-- Заголовок ({{title}} будет заменён на реальный текст) -->
<text id="zone_text_title" x="450" y="730" font-size="44" font-weight="bold" fill="#FFFFFF" text-anchor="middle">
  {{title}}
</text>

<!-- Буллеты -->
<g id="zone_bullets_features" x="80" y="840"
   font-family="Arial, sans-serif" font-size="30" fill="#E0E0E0"
   data-bullet-color="#4FC3F7" data-line-spacing="16">
</g>

<!-- Статический фоновый градиент -->
<rect id="bg" fill="url(#bg_gradient)" width="900" height="1200"/>

<!-- AI-генерируемый фон (будет заменён на сгенерированное изображение) -->
<rect id="bg_ai" fill="#1a1a2e" width="900" height="1200"/>
```

---

## Атрибуты буллетов (data-*)

Буллет-контейнер `<g>` поддерживает кастомные `data-*` атрибуты:

| Атрибут               | По умолчанию | Описание                            |
|-----------------------|--------------|--------------------------------------|
| `data-bullet-color`   | `#4FC3F7`    | Цвет символа-маркера (✓)            |
| `data-bullet-font-size` | = font-size | Размер маркера                      |
| `data-line-spacing`   | `0`          | Доп. отступ между строками (px)     |

---

## Минимальный шаблон

```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg width="900" height="1200" viewBox="0 0 900 1200" xmlns="http://www.w3.org/2000/svg">
  <!-- Фон -->
  <rect id="bg" fill="#1a1a2e" width="900" height="1200"/>

  <!-- Фото товара -->
  <rect id="zone_product_image" x="100" y="50" width="700" height="600" fill="transparent"/>

  <!-- Заголовок -->
  <text id="zone_text_title" x="450" y="730" font-size="44" font-weight="bold" fill="#FFF" text-anchor="middle">
    {{title}}
  </text>

  <!-- Буллеты -->
  <g id="zone_bullets_features" x="80" y="840" font-size="28" fill="#E0E0E0"
     data-bullet-color="#4FC3F7" data-line-spacing="12">
  </g>
</svg>
```

---

## Workflow: создание нового шаблона

### 1. Дизайн в Figma / Inkscape

Создайте макет инфографики (900×1200 для 3:4, 900×900 для 1:1). Расположите элементы как вам нужно.

### 2. Экспорт SVG

Экспортируйте в SVG. Откройте файл и добавьте `id` атрибуты к ключевым элементам:
- Прямоугольник под фото товара → `id="zone_product_image"`
- Текст заголовка → `id="zone_text_title"` (вместо текста можно оставить `{{title}}`)
- Область для буллетов → `<g id="zone_bullets_features" ...>`

### 3. Загрузка через API

```bash
curl -X POST http://localhost:8000/templates/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "name=Мой шаблон" \
  -F "slug=my-template-3x4" \
  -F "svg_file=@template.svg" \
  -F "style_hints=modern tech style, blue tones" \
  -F "output_format=PNG"
```

### 4. Или через Directus UI

1. Откройте Directus → Files → Upload SVG
2. Скопируйте `id` загруженного файла
3. Откройте Templates → Create item
4. Заполните name, slug, width, height
5. В поле `svg_file` выберите загруженный файл
6. Превью сгенерируется автоматически

---

## Примеры шаблонов

В `worker/templates/` лежат примеры:

| Файл                  | Размер  | Описание                              |
|-----------------------|---------|----------------------------------------|
| `infographic-3x4.svg` | 900×1200| Полная инфографика с градиентным фоном |
| `infographic-1x1.svg` | 900×900 | Квадратная карточка                   |
| `product-slide-3x4.svg` | 900×1200| AI-фон + только фото товара          |

---

## Валидация шаблона

При загрузке API автоматически проверяет:
- Наличие `zone_product_image`
- Наличие хотя бы одной текстовой или буллет-зоны
- Корректность SVG-разметки
- Извлекает width/height из `<svg>` элемента

Предупреждения возвращаются в ответе `warnings`, но загрузка не блокируется.

---

## Структура данных шаблона в Directus

```
templates:
  id            UUID       (PK, авто)
  name          string     "Ozon Infographic 3:4"
  slug          string     "ozon-infographic-3x4"
  svg_file      file       → directus_files (SVG файл шаблона)
  preview_image file       → directus_files (авто-превью PNG)
  width         integer    900
  height        integer    1200
  output_format string     "PNG" | "JPEG" | "WEBP"
  style_hints   text       "modern, blue tones, tech"
  is_active     boolean    true
  sort          integer    0