# EMS – Energy Management System

## Лабораторна Робота №1: Проектування системи збереження та збору даних

**Об'єкт:** Поліклініка, Київ | **Площа:** 850 м² | **Режим:** 8:00–20:00

---

## Зміст

1. [Структура бази даних](#база-даних)
2. [Швидкий старт](#швидкий-старт)
3. [Структура проєкту](#структура-проєкту)
4. [Генерація даних](#генерація-даних)
5. [Аналітика та запити](#аналітика)

## База даних

### Таблиці

| Таблиця                     | Рядків | Призначення                 |
| --------------------------- | ------ | --------------------------- |
| `objects`                   | 1      | Медичний центр              |
| `meters`                    | 6      | Лічильники рівнів 1–3       |
| `measurements`              | 52 560 | Погодинні покази (6 × 8760) |
| `weather_data`              | 8 760  | Метеодані Київ 2025         |
| `tariff_zones`              | 2      | День 6.9 грн, Ніч 5.6 грн   |
| `baseline_consumption`      | ~576   | Очікуване споживання        |
| `energy_efficiency_metrics` | 365    | Денні KPI                   |
| `solar_generation`          | 8 760  | Генерація СЕС 51.7 кВт      |
| `battery_state`             | 8 760  | Стан BESS 40.96 кВт·год     |

### Views

| View                  | Опис                                                                 |
| --------------------- | -------------------------------------------------------------------- |
| `level_1_consumption` | Загальне споживання (головний лічильник) + тарифна зона + вартість   |
| `level_2_consumption` | Зональне споживання (ОВАС, освітлення, медобладнання, ІТ) + частка % |
| `level_3_consumption` | Обладнаннєвий рівень (СЕС, BESS, аварійне)                           |
| `daily_meter_summary` | Добові агрегати per meter                                            |
| `monthly_energy_cost` | Щомісячна енергія + вартість                                         |

---

## Швидкий старт

### Передумови

- Python 3.11+
- Docker & Docker Compose
- Git

### 1. Клонувати та встановити залежності

```bash
git clone <repo-url>
cd

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Запустити PostgreSQL

```bash
docker-compose up -d

# Перевірити стан:
docker-compose ps
# Очікуємо: ems_postgres  healthy
```

### 3. Ініціалізувати БД та згенерувати дані

```bash
# Ініціалізація (DDL + reference data + views + 8760h synthetic data)
python -m backend.scripts.init_db

# Або з reset (видалити та перестворити):
python -m backend.scripts.init_db --reset
```

### 4. Запустити аналітику

```bash
python -m backend.scripts.run_analytics --year 2025
# Звіти збережено в reports/
```

### 5. Відкрити pgAdmin

Перейти на: http://localhost:5050  
Логін: `admin@example.com` | Пароль: `admin`

Додати сервер:

- Host: `postgres`
- Port: `5432`
- Database: `ems_db`
- Username: `ems_user`
- Password: `ems_password`

---

## Структура проекту

```
ems-lab1/
├── docker-compose.yml              # PostgreSQL + pgAdmin
├── requirements.txt
├── .env.example
├── reports/                        # Генеровані CSV-звіти (gitignore)
├── backend/
│   ├── config/
│   │   ├── settings.yaml           # ← ВСІ параметри системи
│   │   └── config.py               # Pydantic Settings loader
│   ├── app/
│   │   ├── database.py             # Engine, SessionLocal, session_scope
│   │   ├── models/
│   │   │   └── models.py           # 9 ORM моделей + enum-типи
│   │   ├── repositories/
│   │   │   ├── base.py             # Generic CRUD BaseRepository
│   │   │   └── repositories.py     # Domain repositories
│   │   ├── services/
│   │   │   └── energy_service.py   # EnergyService, TariffService
│   │   └── analytics/
│   │       └── queries.py          # Views DDL + AnalyticsQueries
│   └── scripts/
│       ├── init_db.py              # Ініціалізація БД
│       ├── generate_data.py        # Генератор даних
│       └── run_analytics.py        # Виконати всі запити → CSV
```

---

## Генерація даних

### Параметри об'єкта

| Параметр                 | Значення    |
| ------------------------ | ----------- |
| Тип                      | Поліклініка |
| Площа                    | 850 м²      |
| Потужність               | 95 кВт      |
| Режим роботи             | 8:00–20:00  |
| Середнє навантаження     | 22 кВт      |
| Мінімальне навантаження  | 5 кВт       |
| Максимальне навантаження | 38 кВт      |
| СЕС                      | 35 кВт      |
| BESS                     | 25 кВт·год  |

### Алгоритм

```
Для кожної години в 2025 році (8760 годин):
    1. Температура = base_monthly + diurnal_cycle(hour) + noise
    2. Інсоляція = peak_monthly × cos(hour-14) × (1 - 0.75×cloud)
    3. Навантаження = avg_kw × profile[hour] × day_factor × season × temp_adj ± noise
    4. Сонячна ген. = irradiance/1000 × capacity × temp_coeff × inv_eff
    5. BESS dispatch:
         Ніч + низький SOC  → зарядка від мережі
         Надлишок СЕС → зарядка від СЕС
         Піковий день + SOC > 20% → розрядка
    6. Розподіл по 6 лічильниках
```

### Погодинний профіль навантаження (8:00–20:00)

Ключова особливість — різкий контраст між нічним та денним часом:

| Час         | Коеф.     | Опис                                     |
| ----------- | --------- | ---------------------------------------- |
| 00:00–07:00 | 0.08–0.12 | Нічний режим: чергові системи (~5–7 кВт) |
| 07:00       | 0.20      | Підготовка до відкриття                  |
| 08:00       | 0.60      | Відкриття, початок прийому               |
| 10:00–11:00 | 1.00      | Денний пік                               |
| 18:00–20:00 | 0.65→0.15 | Завершення прийому                       |
| 20:00–23:00 | 0.10–0.15 | Закриття                                 |

### Сезонні коефіцієнти

| Сезон | Коеф. | Причина       |
| ----- | ----- | ------------- |
| Зима  | 1.18  | Опалення      |
| Весна | 0.95  | Помірне       |
| Літо  | 1.08  | Кондиціювання |
| Осінь | 0.92  | Мінімальне    |

### Рівні обліку

```
Рівень 1 (Лічильник 1 — ГРЩ-1):
  Загальне споживання будівлі

Рівень 2 (Лічильники 2–4):
  ЩО-2 ОВАС 30%
  ЩО-3 Освітлення 18%
  ЩО-4 Медичне обл. 32%
  (решта 20% = незафіксовані загальні витрати)

Рівень 3 (Лічильники 5–6):
  ЩО-5 СЕС → solar_generation.power_kw
  ЩО-6 BESS → battery_state.power_kw
```

---

## Аналітика

### Приклади SQL-запитів

**1. Добове споживання:**

```sql
SELECT day, SUM(energy_kwh) AS total_kwh, SUM(cost_uah) AS cost_uah, day_type
FROM level_1_consumption
WHERE day BETWEEN '2025-07-01' AND '2025-07-07'
GROUP BY day, day_type
ORDER BY day;
```

**2. Місячне споживання:**

```sql
SELECT * FROM monthly_energy_cost WHERE year = 2025;
```

**3. Аномалії (>20% відхилення від baseline):**

```sql
SELECT bc.day, bc.hour, bc.actual_kwh, bc.baseline_kwh,
       ROUND(bc.deviation_pct, 1) AS deviation_pct
FROM (
    SELECT l1.day, l1.hour, l1.day_type,
           SUM(l1.energy_kwh) AS actual_kwh,
           AVG(bc.expected_kwh) AS baseline_kwh,
           (SUM(l1.energy_kwh) - AVG(bc.expected_kwh))
               / NULLIF(AVG(bc.expected_kwh), 0) * 100 AS deviation_pct
    FROM level_1_consumption l1
    LEFT JOIN baseline_consumption bc
           ON bc.object_id = 1
          AND bc.month = EXTRACT(MONTH FROM l1.day)::INT
          AND bc.hour_of_day = l1.hour
          AND bc.day_type = l1.day_type
    GROUP BY l1.day, l1.hour, l1.day_type
) bc
WHERE ABS(bc.deviation_pct) > 20
ORDER BY ABS(bc.deviation_pct) DESC
LIMIT 20;
```

**4. Питоме споживання кВт·год/м²:**

```sql
SELECT month, year,
       ROUND(SUM(energy_kwh) / 850.0, 2) AS kwh_per_m2
FROM level_1_consumption
GROUP BY year, month
ORDER BY year, month;
```

**5. Тарифні зони (день/ніч):**

```sql
SELECT tariff_zone,
       ROUND(SUM(energy_kwh)::numeric, 0) AS total_kwh,
       ROUND(SUM(cost_uah)::numeric, 0) AS total_uah
FROM level_1_consumption
GROUP BY tariff_zone;
```
---
