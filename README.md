# EMS – Energy Management System

## Лабораторна Робота №2: Аналіз даних та прогнозування енергоспоживання

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

### 3. Ініціалізувати БД та згенерувати дані (ЛР1)

```bash
# Ініціалізація (DDL + reference data + views + 8760h synthetic data)
python -m backend.scripts.init_db

# Або з reset (видалити та перестворити):
python -m backend.scripts.init_db --reset
```

### 4. Запустити аналітику (ЛР1)

```bash
python -m backend.scripts.run_analytics --year 2025
# Звіти збережено в reports/
```


### 5. Навчити моделі прогнозування (ЛР2)

```bash
python -m backend.scripts.train_models
```

### 6. Запустити Jupyter Notebook (ЛР2)

```bash
jupyter notebook notebooks/lab2_forecasting.ipynb
```

### 7. Відкрити pgAdmin

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
PZ-main/
├── docker-compose.yml # PostgreSQL 16 + pgAdmin
├── requirements.txt # Залежності ЛР1 + ЛР2
├── .env.example # Шаблон змінних середовища
│
├── reports/ # Генеровані звіти (CSV + PNG)
│   ├── 01_daily_consumption.csv
│   ├── 02_monthly_consumption.csv
│   ├── fig_01_daily.png # ЛР1 charts
│   ├── fig_lr2_01_yearly.png # ЛР2 EDA charts
│   └── ...
│
├── models_saved/ # Навчені ML-моделі (ЛР2)
│   ├── gradient_boosting.joblib
│   ├── random_forest.joblib
│   └── metadata.json
│
├── notebooks/
│   └── lab2_forecasting.ipynb # ЛР2: повний Data Science pipeline
│
└── backend/
    ├── config/
    │   ├── settings.yaml # ← ВСІ параметри системи
    │   └── config.py # Pydantic Settings loader
    │
    ├── app/
    │   ├── database.py # Engine, session_scope, get_db
    │   │
    │   ├── models/
    │   │   └── models.py # 9 ORM-моделей + enum-типи
    │   │
    │   ├── repositories/
    │   │   ├── base.py # Generic CRUD BaseRepository
    │   │   └── repositories.py # Domain repositories
    │   │
    │   ├── services/
    │   │   └── energy_service.py # EnergyService, TariffService
    │   │
    │   ├── analytics/
    │   │   ├── queries.py # SQL views DDL + AnalyticsQueries
    │   │   └── charts.py # Matplotlib chart generation
    │   │
    │   └── forecasting/ # ЛР2
    │       ├── __init__.py
    │       ├── feature_engineering.py  # Завантаження БД + 36 ознак
    │       ├── models.py # 6 ML-моделей + метрики
    │       ├── forecast_service.py # ForecastService (API для ЛР3/4)
    │       └── model_loader.py # joblib збереження/завантаження
    │
    └── scripts/
        ├── init_db.py # ЛР1: Ініціалізація БД
        ├── generate_data.py # ЛР1: Генератор 8760 годин
        ├── run_analytics.py # ЛР1: Аналітика → CSV + PNG
        └── train_models.py # ЛР2: Навчання ML-моделей
```

---

## ЛР1

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

### Тарифні зони

|  Зона |         Час (TIME)      |       Тариф      |
|-------|-------------------------|------------------|
| Денна | `07:00:00` – `23:00:00` | 6.90 грн/кВт·год |
| Нічна | `23:00:00` – `07:00:00` | 5.60 грн/кВт·год |

### Результати аналітики (2025 рік)

|     Показник      |                   Значення                   |
|-------------------|----------------------------------------------|
| Річне споживання  | 114 362 кВт·год                              |
| Питоме споживання | 134.5 кВт·год/м²                             |
| Річна вартість    | 764 711 грн                                  |
| Денна зона        | 95 601 кВт·год (83.6%) / 659 646 грн (86.3%) |
| Нічна зона        | 18 762 кВт·год (16.4%) / 105 065 грн (13.7%) |
| Аномальних годин  | 60 (0.69%)                                   |

### Генеровані звіти ЛР1

|             Файл           |    Тип     |                   Опис                     |
|----------------------------|------------|--------------------------------------------|
| `fig_01_daily.png`         | Лінійний   | Добове споживання + ковзне середнє 7 днів  |
| `fig_02_monthly.png`       | Стовпчаста | Місячне споживання день/ніч + вартість     |
| `fig_03_tariff.png`        | Кільцева   | Розподіл кВт·год і грн між зонами          |
| `fig_04_specific.png`      | Стовпчаста | кВт·год/м² з лініями нормативів            |
| `fig_05_hourly_profile.png`| Лінійний   | Добовий профіль будні vs вихідні           |
| `fig_06_load_factor.png`   | Лінійний   | Коефіцієнт навантаження та пік/середнє     |
| `fig_07_anomalies.png`     | Scatter    | Аномальні години (відхилення від baseline) |
| `fig_08_solar_balance.png` | Стовпчаста | Місячний баланс СЕС / BESS / мережа        |

## ЛР2

### Модулі

|           Файл           |                               Призначення                                |
|--------------------------|--------------------------------------------------------------------------|
| `feature_engineering.py` | Завантаження з БД + 36 ознак (часові, циклічні, погодні, лагові, ковзні) |
| `models.py`              | 6 ML-моделей, метрики R²/RMSE/MAE/MAPE                                   |
| `forecast_service.py`    | `ForecastService` — публічний API для ЛР3 і ЛР4                          |
| `model_loader.py`        | Збереження/завантаження через joblib                                     |

### Моделі прогнозування

|             Модель            |         Тип        |      Ознаки      |
|-------------------------------|--------------------|------------------|
| Baseline (Hourly Mean)        | Статистичний       | hour, is_weekend |
| Linear Regression             | Параметричний      | 13 базових       |
| Ridge Regression              | Параметричний + L2 | 13 базових       |
| Polynomial Regression (deg-2) | Нелінійний         | 8 ключових       |
| Random Forest                 | Ансамблевий        | всі 36           |
| Gradient Boosting             | Ансамблевий        | всі 36           |

### Ознаки (feature engineering)

```
Часові (7):    hour, day_of_week, day_of_month, month, quarter, week_of_year, day_of_year
Циклічні (8):  hour_sin/cos, month_sin/cos, dow_sin/cos, doy_sin/cos
Бінарні (5):   is_weekend, is_holiday, is_working_hour, is_working_time, season
Погодні (6):   temperature_c, hdd, cdd, temp_dev, solar_irradiance_wm2, humidity_pct
Тарифні (2):   is_day_tariff, tariff_price
Лагові (5):    lag_1, lag_2, lag_24, lag_48, lag_168
Ковзні (7):    rolling_mean/std_24/168, rolling_max/min_24, lag_168_delta
```

### Розбиття даних

|   Набір  |      Місяці      | Частка |
|----------|------------------|--------|
| Training | Січень–Жовтень   | 80%    |
| Testing  | Листопад–Грудень | 20%    |

### Графіки ЛР2 (Notebook)

| Рисунок |         Тип         |                      Опис                    |
|---------|---------------------|----------------------------------------------|
|  Рис.1  | Лінійний            | Погодинне споживання за рік + ковзне середнє |
|  Рис.2  | Area chart          | Типовий добовий профіль                      |
|  Рис.3  | Area chart          | Профіль будніх днів                          |
|  Рис.4  | Area chart          | Профіль вихідних днів                        |
|  Рис.5  | Стовпчаста          | Місячна динаміка із сезонним забарвленням    |
|  Рис.6  | Heatmap             | Година × день тижня                          |
|  Рис.7  | Декомпозиція        | Тренд + сезонність + залишки                 |
|  Рис.8  | Кореляційна матриця | Взаємозв'язки між ознаками                   |
|  Рис.9  | Scatter             | Споживання vs температура / HDD / CDD        |
|  Рис.10 | ACF/PACF            | Аналіз лагів (добова та тижнева циклічність) |
|    —    | Boxplots            | Розподіл по годині / дню / місяцю            |
|    —    | Порівняння моделей  | Bar chart R²/RMSE/MAE/MAPE                   |
|    —    | Фактичне vs прогноз | Часовий ряд + scatter                        |
|    —    | Залишки + Q-Q       | Residual plot + нормальний розподіл          |
|    —    | Feature importance  | Топ-20 ознак Gradient Boosting               |
|    —    | Прогноз місяця      | Погодинно + добово + економія СЕС            |

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
