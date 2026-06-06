# EMS – Energy Management System

## Лабораторна Робота №4: Веб-інтерфейс для моніторингу та управління

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
jupyter notebook notebooks/lab2_forecasting.ipynb     # ЛР2
jupyter notebook notebooks/lab3_ems_simulation.ipynb  # ЛР3
```

### 7. Ініціалізувати таблиці симуляції (ЛР3)

```bash
python -m backend.scripts.init_simulation_db
```

### 8. Запустити EMS симуляцію (ЛР3)

```bash
python -m backend.scripts.run_simulation --start 2025-07-01 --days 7
```

### 9. Відкрити pgAdmin

Перейти на: http://localhost:5050  
Логін: `admin@example.com` | Пароль: `admin`

Додати сервер:

- Host: `postgres`
- Port: `5432`
- Database: `ems_db`
- Username: `ems_user`
- Password: `ems_password`

---

## 10. REST API та Frontend (ЛР4)

Є два способи запуску: **локально** (для розробки) або **Docker** (для демонстрації).

---

### Варіант А — Локальний запуск (рекомендовано для розробки)

#### Крок 1 — Встановити додаткові залежності

```bash
pip install fastapi "uvicorn[standard]" python-multipart openpyxl httpx
```

#### Крок 2 — Запустити FastAPI backend

```bash
uvicorn backend.main:app --reload --port 8000
```

Після старту:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```
**Swagger UI:** http://localhost:8000/docs  

#### Крок 3 — Запустити React frontend (окремий термінал)

```bash
cd frontend
npm install       # перший раз
npm run dev
```

**Веб-інтерфейс:** http://localhost:3000

> Vite автоматично проксіює `/api/*` → `http://localhost:8000`

#### Крок 4 — Перевірка

```bash
# Перевірити що API працює:
curl http://localhost:8000/health
# → {"status": "ok", "version": "4.0.0"}

# Перевірити що новий forecast endpoint є:
curl http://localhost:8000/api/v1/forecast/test-predictions?n=3

# Перевірити прогноз:
curl http://localhost:8000/api/v1/forecast/summary
```

---

### Варіант Б — Docker Compose (усі сервіси разом)

```bash
# Повний стек: PostgreSQL + pgAdmin + FastAPI + React
docker-compose --profile full up -d
```

|     Сервіс      |             URL            |
|-----------------|----------------------------|
| React Frontend  | http://localhost:3000      |
| FastAPI Backend | http://localhost:8000      |
| Swagger UI      | http://localhost:8000/docs |
| pgAdmin         | http://localhost:5050      |
| PostgreSQL      | localhost:5432             |

## Структура проекту

```
PZ-main/
├── docker-compose.yml              # PostgreSQL + pgAdmin + (profile:full) API + Frontend
├── requirements.txt
├── .env.example
├── reports/                        # CSV + PNG звіти (автогенерація ЛР1–3)
├── models_saved/                   # .joblib моделі (ЛР2) ← потрібні для API
│   ├── gradient_boosting.joblib
│   └── metadata.json              # feature_columns, best_model
├── notebooks/
│   ├── lab2_forecasting.ipynb
│   └── lab3_ems_simulation.ipynb
│
├── backend/
│   ├── main.py                     # FastAPI application entry (ЛР4)
│   ├── config/
│   │   ├── settings.yaml           # ВСІ параметри системи
│   │   └── config.py               # Pydantic Settings (10 класів конфігурації)
│   └── app/
│       ├── database.py             # engine, session_scope, get_db, SessionLocal
│       ├── models/
│       │   ├── models.py           # 9 ORM-моделей (ЛР1)
│       │   └── simulation_models.py# simulation_runs, simulation_results (ЛР3)
│       ├── repositories/           # Generic CRUD (ЛР1)
│       ├── services/               # EnergyService, TariffService (ЛР1)
│       ├── analytics/              # SQL queries + charts (ЛР1)
│       │   ├── queries.py
│       │   └── charts.py
│       ├── forecasting/            # ЛР2
│       │   ├── feature_engineering.py  # 36 ознак, build_features()
│       │   ├── models.py               # 6 ML-моделей
│       │   ├── forecast_service.py     # ForecastService (головний сервіс)
│       │   └── model_loader.py         # збереження/завантаження .joblib
│       ├── simulation/             # ЛР3
│       │   ├── components/
│       │   │   ├── solar.py        # SolarPlant (NOCT модель)
│       │   │   ├── battery.py      # BatteryStorage (SOC, ефективність)
│       │   │   ├── grid.py         # GridConnection (тарифи)
│       │   │   └── load_profile.py # LoadProfile (ЛР1 + ЛР2)
│       │   ├── ems_controller.py   # EMSController + TariffOptimizer
│       │   ├── simulation_engine.py# SimulationEngine (7 діб, PostgreSQL)
│       │   ├── economics.py        # NPV, IRR, Payback, LCOE
│       │   └── simulation_service.py # SimulationService (API-ready)
│       ├── api/                    # ЛР4
│       │   ├── deps.py             # get_db() FastAPI dependency
│       │   ├── exceptions.py       # централізований exception handler
│       │   ├── schemas/__init__.py # всі Pydantic response schemas
│       │   └── routers/
│       │       ├── dashboard.py    # GET /dashboard/summary|kpi
│       │       ├── consumption.py  # GET /consumption/monthly|daily|hourly|tariff|specific
│       │       ├── weather.py      # GET /weather
│       │       ├── forecasts.py    # GET /forecast/summary|hourly|metrics|test-predictions
│       │       ├── ems.py          # GET+POST /ems/*
│       │       └── reports.py      # POST /reports/generate + GET download|preview
│       └── scripts/
│           ├── init_db.py          # ЛР1: ініціалізація схеми БД
│           ├── generate_data.py    # ЛР1: генерація синтетичних даних
│           ├── run_analytics.py    # ЛР1: аналітика та графіки
│           ├── train_models.py     # ЛР2: навчання та збереження моделей
│           ├── init_simulation_db.py # ЛР3: таблиці симуляції
│           └── run_simulation.py   # ЛР3: запуск EMS симуляції
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    ├── tsconfig.json
    ├── Dockerfile
    └── src/
        ├── main.tsx
        ├── App.tsx                 # React Router, 7 маршрутів
        ├── types/index.ts          # TypeScript типи
        ├── services/api.ts         # axios клієнт до FastAPI
        ├── components/
        │   ├── layout/Layout.tsx   # Sidebar + Header
        │   ├── ui/index.tsx        # KPICard, Card, Spinner, Badge, Empty
        │   └── charts/Gauges.tsx   # ArcGauge, BarGauge, DashboardGauges
        └── pages/
            ├── Dashboard.tsx       # 8 KPI + місячні графіки + гейджі
            ├── Consumption.tsx     # Рік/Тижні/Дні, baseline, фільтр легенди
            ├── ForecastPage.tsx    # Прогноз листопада + ДІ + Факт vs Прогноз
            ├── EmsPage.tsx         # SOC gauge, alerts, економіка (ЛР3)
            ├── EnergyBalance.tsx   # SVG flow diagram + добовий баланс
            ├── Analytics.tsx       # Heatmap + scatter temp/load
            └── Reports.tsx         # ZIP архів (CSV + summary.txt)
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

## ЛР3

### EMS Engine — компоненти

|         Клас        |             Файл             |              Призначення              |
|---------------------|------------------------------|---------------------------------------|
| `SolarPlant`        | `components/solar.py`        | Фізична модель СЕС (NOCT, деградація) |
| `BatteryStorage`    | `components/battery.py`      | BESS (ефективність, SOC, саморозряд)  |
| `GridConnection`    | `components/grid.py`         | Двозонний тариф, обмеження 95 кВт     |
| `LoadProfile`       | `components/load_profile.py` | ЛР1 дані + ЛР2 прогноз                |
| `EMSController`     | `ems_controller.py`          | Головна логіка кроку                  |
| `TariffOptimizer`   | `ems_controller.py`          | Нічна зарядка / денна розрядка        |
| `SimulationEngine`  | `simulation_engine.py`       | 7-добова симуляція, PostgreSQL        |
| `EconomicAnalyzer`  | `economics.py`               | NPV, IRR, Payback, LCOE               |
| `SimulationService` | `simulation_service.py`      | API-ready для ЛР4                     |

### Параметри BESS

|     Параметр      |  Значення  |
|-------------------|------------|
| Ємність           | 25 кВт·год |
| SOC min (операц.) | 20%        |
| SOC max (операц.) | 90%        |
| Початковий SOC    | 50%        |
| ККД заряду        | 95%        |
| ККД розряду       | 95%        |
| Саморозряд        | 0.1%/год   |
| Макс. потужність  | 12 кВт     |

### Алгоритм управління (кожна година)

```
1. Саморозряд батареї (0.1%/год)
2. Генерація СЕС = f(інсоляція, температура, деградація)
3. balance = solar − load
4. IF balance ≥ 0 (надлишок):
     → заряд батареї до SOC_max
     → залишок → експорт у мережу
5. IF balance < 0 (дефіцит):
     IF нічний тариф AND SOC < 85%:
       → нічна зарядка від мережі (12 кВт)
     IF денний тариф AND SOC > 20%:
       → розряд батареї для покриття
     Решта дефіциту → імпорт
```

### Результати симуляції (01–07.07.2025)

|       Показник       |        Значення       |
|----------------------|-----------------------|
| Загальне споживання  | 2 072.4 кВт·год       |
| Генерація СЕС        | 426.9 кВт·год         |
| Покриття навант. СЕС | 20.6%                 |
| Самоспоживання СЕС   | 100.0%                |
| Самодостатність      | 26.2%                 |
| Цикли батареї        | 4.98                  |
| Вартість з EMS       | 10 944 грн            |
| Вартість без EMS     | 13 936 грн            |
| **Економія**         | **2 992 грн (21.5%)** |
| Річна екстраполяція  | 155 996 грн/рік       |

### Інвестиційний аналіз

|         Показник        |     Значення      |
|-------------------------|-------------------|
| CAPEX (СЕС 35 кВт)      | 1 330 000 грн     |
| CAPEX (BESS 25 кВт·год) | 350 000 грн       |
| CAPEX загальний         | 1 680 000 грн     |
| Simple Payback Period   | 10.8 років        |
| NPV (r=12%, 20 р.)      | −315 434 грн      |
| IRR                     | 9.5%              |
| LCOE                    | 11.61 грн/кВт·год |

### Нові таблиці БД (ЛР3)

|        Таблиця       |            Призначення           |
|----------------------|----------------------------------|
| `simulation_runs`    | Метаінформація про кожний прогін |
| `simulation_results` | 168 погодинних записів на прогін |


## ЛР4
## API Endpoints

**Base URL:** `http://localhost:8000`  
**Swagger:** `http://localhost:8000/docs`

|           Endpoint           | Метод|                 Опис             |   ЛР  |
|------------------------------|------|----------------------------------|-------|
| `/health`                    | GET  | Перевірка стану API              |   —   |
| `/dashboard/summary`         | GET  | 8 KPI поточного стану            |  1+3  |
| `/dashboard/kpi`             | GET  | Місячні KPI за рік               |   1   |
| `/consumption/monthly`       | GET  | Місячне споживання (`?year=`)    |   1   |
| `/consumption/daily`         | GET  | Добове (`?start=&end=`)          |   1   |
| `/consumption/hourly`        | GET  | Погодинне з пагінацією           |   1   |
| `/consumption/tariff`        | GET  | Розбивка по тарифних зонах       |   1   |
| `/weather`                   | GET  | Метеодані (`?start=&end=`)       |   1   |
| `/forecast/summary`          | GET  | Прогноз листопада (GB model)     |   2   |
| `/forecast/hourly`           | GET  | Погодинний прогноз з ДІ          |   2   |
| `/forecast/metrics`          | GET  | R², RMSE, MAE, MAPE              |   2   |
| `/forecast/test-predictions` | GET  | Факт vs прогноз (тестовий набір) |   2   |
| `/ems/status`                | GET  | Статус останнього прогону        |   3   |
| `/ems/simulation`            | GET  | 168 погодинних кроків            |   3   |
| `/ems/metrics`               | GET  | Енергетичні KPI                  |   3   |
| `/ems/economics`             | GET  | NPV, IRR, Payback, LCOE          |   3   |
| `/ems/energy-flow`           | GET  | Потоки для Sankey                |   3   |
| `/ems/run`                   | POST | Запустити симуляцію              |   3   |
| `/reports/generate`          | POST | Отримати report_id               | 1+2+3 |
| `/reports/{id}/preview`      | GET  | Текстовий preview (summary.txt)  | 1+2+3 |
| `/reports/{id}/download`     | GET  | ZIP з CSV + summary.txt          | 1+2+3 |


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
