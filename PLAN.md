# Cardgen (ветка extgen) — только RouterAI

## Идея

Вся обработка изображений выполняется **удалённо** через агрегатор **[RouterAI](https://routerai.ru)** (OpenAI-совместимый API). Локально нет OpenCV, rembg, onnx и т.п.

Цепочка по умолчанию:

1. **Планировщик:** `openai/gpt-5.4` -- по фото товара формулирует краткую инструкцию на русском для редактирования (свет, фон, аккуратность краёв и т.д.).
2. **Изображение:** `google/gemini-2.5-flash-image` (Nano Banana) -- принимает исходное изображение + инструкцию, возвращает результат.

Модели можно переопределить переменными окружения `CARDGEN_CHAT_MODEL` и `CARDGEN_IMAGE_MODEL`.

## Требования

- Python ≥ 3.10  
- Ключ API RouterAI в переменной **`ROUTERAI_API_KEY`** (или `OPENAI_API_KEY`).  
- Опционально: **`ROUTERAI_BASE_URL`** (по умолчанию `https://routerai.ru/api/v1`).

## Установка

```powershell
cd d:\langs\python\cardgen
python -m venv .venv
.\.venv\Scripts\pip install -e .
```

## CLI

```bash
# Полная цепочка GPT → Nano Banana; результаты — PNG под теми же относительными путями
python -m cardgen process --in samples/in --out samples/out --brief "Белый фон, маркетплейс WB"

# Пропустить GPT: одна и та же инструкция для всех файлов
python -m cardgen process --in samples/in --out samples/out --instruction "Сделай нейтральный свет и белый фон #FFFFFF"
```

## Вход / выход

- **Вход:** JPG, PNG, WebP и др. (см. `cardgen/routerai.py`, `SUPPORTED_SUFFIXES`).
- **Выход:** всегда **PNG** (путь и имя совпадают с входом, расширение `.png`).

## Не входит в эту ветку

- Локальная цветокоррекция, rembg, скачивание превью с WB и любая офлайн-обработка пикселей.

Документы в `info/` остаются как справочные материалы по нише и маркетплейсу; технический пайплайн описан здесь.
