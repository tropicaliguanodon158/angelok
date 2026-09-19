# ANGELОK — Implementation Plan

## 0. Правила реализации

Этот файл является главным техническим планом проекта.

Перед каждой существенной правкой необходимо сверяться с ним.

### Ограничения

* Максимум 10 основных файлов проекта.
* Не создавать десятки маленьких модулей.
* Сохранять SQLAlchemy 2.x + asyncio.
* SQLite для локального запуска.
* PostgreSQL для VDS.
* Все игровые и RP-механики должны быть вынесены из `handlers.py`, насколько это возможно.
* Telegram handlers отвечают за Telegram-взаимодействие.
* Services отвечают за бизнес-логику.
* Database отвечает за модели и работу с БД.
* Конфигурационные значения должны находиться в `core.py`.
* Не ломать существующие команды без причины.
* Все новые механики должны переживать перезапуск бота.
* Не использовать in-memory состояние там, где состояние должно сохраняться в БД.
* Не использовать фоновые бесконечные задачи для механик, которые можно рассчитывать по timestamp при обращении пользователя.

---

# 1. Итоговая структура

```text
angelok/
├── bot.py
├── core.py
├── database.py
├── services.py
├── handlers.py
├── games.py
├── rp.py
├── inventory.py
├── moderation.py
├── requirements.txt
├── .env.example
├── README.md
└── IMPLEMENTATION_PLAN.md
```

Основной лимит: **10 файлов**, включая `requirements.txt`.

---

# 2. bot.py

## Ответственность

Только lifecycle и запуск приложения.

### Должно быть

* загрузка конфигурации;
* инициализация БД;
* создание Bot;
* создание Dispatcher/Router;
* регистрация handlers из:

  * `handlers.py`;
  * `games.py`;
  * `rp.py`;
  * `inventory.py`;
  * `moderation.py`;
* startup;
* shutdown;
* обработка ошибок верхнего уровня.

### Не должно быть

* игровой логики;
* SQL-запросов;
* расчётов экономики;
* RP-механики;
* логики модерации.

---

# 3. core.py

## Ответственность

Центральная конфигурация и константы.

### 3.1 Конфигурация

Существующие:

* BOT_TOKEN
* OWNER_ID
* DATABASE_URL
* LOG_LEVEL
* MESSAGE_REWARD_MIN
* MESSAGE_REWARD_MAX
* MESSAGE_XP
* MESSAGE_REWARD_COOLDOWN
* DAILY_BONUS_MIN
* DAILY_BONUS_MAX
* MIN_BET
* MAX_BET

### 3.2 XP

Оставить существующую систему уровней, но привести к единой логике.

Важно:

> За каждое сообщение пользователь получает XP.

Никакого cooldown для XP.

То есть:

```text
сообщение → +1 XP
сообщение → +1 XP
сообщение → +1 XP
```

Антифлуд может существовать отдельно для выдачи арахиса, но **не имеет права блокировать XP**.

### 3.3 Battle Pass XP

Отдельная система:

```text
1 сообщение = +1 Battle Pass XP
```

Также без антифлуда.

### 3.4 Уровневые разблокировки

Существующие:

```text
1  profile
1  stats
1  coinflip
1  dice
2  slots
3  roulette
5  football
7  basketball
10 tictactoe
15 blackjack
20 crash
```

Каждый игровой handler обязан проверять unlock.

---

# 4. Battle Pass

## Цель

Добавить сезонный Battle Pass.

### Состояние пользователя

Хранить:

* battle pass XP;
* battle pass level;
* season.

### Награды

Каждый уровень получает конкретную награду.

Типы:

* арахис;
* XP;
* кейс;
* тег.

### Финальная награда

Последний уровень:

```text
ЖИВАЯ ЛЕГЕНДА
```

Награда — уникальный тег.

### Команда

```text
/battlepass
```

Показывает:

* текущий уровень;
* XP;
* XP до следующего уровня;
* текущие/полученные награды;
* следующую награду;
* финальную награду.

---

# 5. database.py

## Ответственность

Все SQLAlchemy модели и работа с БД.

Не создавать отдельный `models.py`.

## Необходимые сущности

Использовать существующие модели, расширив их.

### User / Profile

Добавить необходимые поля:

* XP;
* battle pass XP;
* battle pass season;
* battle pass level;
* penis size;
* disease state;
* disease tick timestamp;
* child state;
* child expiration;
* child support timestamp;
* last robbery timestamp;
* выбранный tag;
* необходимые cooldown timestamps.

### StaffMember

Хранить:

```text
OWNER
HEAD_ADMIN
ADMIN
MODERATOR
```

Привязка:

```text
chat_id + user_id
```

### ModPermission

Хранить доступ к конкретной moderation-команде.

Пример:

```text
warn → STAFF
ban → ADMIN
purge → HEAD_ADMIN
```

Возможные scopes:

```text
STAFF
ADMIN
HEAD_ADMIN
```

### InventoryItem

Тип предмета.

Примеры:

```text
case
lubricant
dildo
rubber_pussy
silicone_implant
condom
tag
```

### UserItem

Инвентарь пользователя.

Нужна поддержка:

* quantity;
* uses_left;
* stackable;
* max_quantity.

### Tag

Постоянное описание тега.

### UserTag

Связь:

```text
user → earned tag
```

Тег нельзя установить, если он не принадлежит пользователю.

### Giveaway

Хранить:

* chat;
* creator;
* prize type;
* prize amount/item;
* duration/end time;
* status;
* winner.

### GiveawayParticipant

Участники розыгрыша.

### Game

Использовать существующую модель, если возможно.

---

# 6. Миграция БД

Главная задача:

Не сломать существующую БД.

`create_all()` недостаточно для добавления новых колонок в существующие таблицы.

В `database.py` реализовать максимально простой механизм совместимости:

* проверить существование нужных колонок;
* добавить отсутствующие колонки;
* создать отсутствующие новые таблицы.

Не создавать отдельный migration-файл.

Если для конкретной PostgreSQL-конструкции автоматическое добавление невозможно — сделать безопасный fallback и явно сообщить при запуске.

---

# 7. services.py

## Ответственность

Общая бизнес-логика.

### 7.1 Экономика

Функции:

* get balance;
* add peanuts;
* remove peanuts;
* transfer;
* проверка достаточности средств;
* начисление за сообщение;
* daily bonus.

### 7.2 XP

Отдельно:

```text
add_message_xp()
```

Каждое сообщение:

```text
+1 XP
```

Без cooldown.

При переходе уровня:

* определить новый уровень;
* выдать награду уровня;
* увеличить member size согласно настройке;
* сообщить о новом уровне.

### 7.3 Target resolver

Единый resolver для:

```text
/profile
/profile @username
/profile reply
/stats
/tag
/rob
RP
```

Приоритет:

1. reply;
2. username;
3. собственный пользователь.

### 7.4 Disease reconciliation

Не создавать отдельный scheduler.

При любом обращении к пользователю:

```text
если disease активна:
    определить сколько часов прошло
    применить все пропущенные ticks
```

Каждый tick:

```text
penis_size -= 0.5
charge 500 peanuts
```

Если денег недостаточно:

* баланс не уходит в минус;
* эффект болезни всё равно применяется.

### 7.5 Child reconciliation

Аналогично.

При наличии ребёнка:

```text
каждый прошедший час:
    charge 10000 peanuts
```

После истечения 18 часов:

```text
child = false
```

Пользователь снова получает возможность использовать 18+ RP.

### 7.6 Robbery

Условия:

* один раз в сутки;
* только пользователь из того же чата;
* размер жертвы меньше размера грабителя;
* нельзя ограбить себя.

Сумма ограбления — отдельная константа в `core.py`.

---

# 8. RP — rp.py

## Главное правило

Все RP-команды должны быть **не графическими**.

18+ RP работает по той же архитектуре, что и обычный RP:

```text
команда
→ target
→ проверка цены
→ проверка cooldown
→ применение эффекта
→ сообщение
```

Без описания сексуальных действий.

---

# 9. Обычный RP

Цена:

```text
10 🥜
```

Существующие команды:

```text
обнять
пожать
поцеловать
пнуть
ударить
погладить
подмигнуть
дать пять
поздравить
пожалеть
рассмешить
напугать
ткнуть
укусить
дать подзатыльник
кинуть тапок
```

---

# 10. RP parser

Исправить ошибку двухсловных команд.

Должны корректно распознаваться:

```text
дать пять
дать подзатыльник
кинуть тапок
```

Parser должен использовать longest-match.

Нельзя делать:

```python
parts = text.split(maxsplit=1)
action = parts[0]
```

для RP.

---

# 11. 18+ RP

Цена:

```text
50 🥜
```

Cooldown:

```text
15 минут
```

Команды регистрируются аналогично обычным RP.

Они не должны содержать графического текста.

Каждая команда может иметь modifiers:

* изменение размера;
* шанс болезни;
* шанс ребёнка;
* шанс других эффектов;
* использование предметов.

---

# 12. Member Size

Пользователь получает параметр:

```text
penis_size
```

Начальное значение:

```text
0.0
```

Размер:

* увеличивается от 18+ RP;
* может увеличиваться от уровня;
* уменьшается от болезни;
* изменяется предметами.

Показывать размер в профиле.

Добавить рейтинг:

```text
/top
```

или отдельный:

```text
/topsize
```

Сортировка по размеру.

---

# 13. Modifiers 18+ RP

### Обычный эффект

Каждая подходящая RP-команда имеет свой modifier.

### Lubricant

Эффект:

```text
+5% к увеличению размера
```

Одно использование.

Stackable.

Количество не ограничено.

### Dildo

* максимум 1 предмет;
* позволяет выполнить 3–5 дополнительных использований;
* после исчерпания исчезает;
* если выпадает повторно:

  * вместо предмета +5000 🥜.

### Rubber Pussy

При получении:

* уменьшает cooldown 18+ RP на 50%;
* уменьшает cooldown «дрочки» на 50%;
* 20% шанс +1 см в сутки;
* даёт автоматическую механику «дрочки».

«Дрочка»:

```text
+0.05–0.20 см
```

Cooldown:

```text
6 часов
```

### Silicone Implant

При выпадении:

```text
+1 см
```

Автоматически применяется.

Не хранится в инвентаре.

### Condom

Используется автоматически при 18+ RP.

Stackable.

---

# 14. Disease

При использовании 18+ RP на другого пользователя:

```text
50% chance disease
```

При наличии condom:

```text
90% protection
```

То есть шанс заболевания значительно снижается.

Болезнь:

```text
каждый час:
    -0.5 см
    -500 🥜
```

---

# 15. Venereologist

Если пользователь болен:

в профиле появляется кнопка:

```text
🩺 Сходить к венерологу
```

Стоимость:

```text
5000 🥜
```

Шанс лечения:

```text
20%
```

При успехе:

```text
disease = false
```

---

# 16. Child mechanic

При использовании 18+ RP на другого пользователя:

### Без condom

```text
15% chance
```

### С condom

```text
5% chance
```

При наступлении эффекта:

* actor получает child;
* 18+ RP блокируется;
* длительность — 18 часов;
* child support — 10000 🥜/час.

Нельзя получить второй child одновременно.

---

# 17. Abortion

Если есть child:

в профиле:

```text
👶 Дать денег на аборт
```

Стоимость:

```text
30000 🥜
```

Шанс:

```text
50%
```

Успех:

```text
child = false
```

Провал:

```text
child остаётся
```

---

# 18. Inventory — inventory.py

## Ответственность

* кейсы;
* предметы;
* теги;
* открытие кейсов;
* использование предметов;
* inline keyboards.

### Кейсы

Добавить:

```text
/open_case
/cases
```

или аналогичную понятную систему.

Кейс содержит случайную награду.

Возможные награды:

* арахис;
* Lubricant;
* Dildo;
* Rubber Pussy;
* Silicone Implant;
* Condom;
* Tag.

---

# 19. Tags

Убрать возможность пользователю самому назначать себе tag.

Полностью убрать пользовательский `/settag`.

Теги:

* получаются из кейсов;
* получаются из Battle Pass;
* хранятся в UserTag;
* нельзя выбрать чужой tag.

Команда:

```text
/tag
```

доступна всем.

Показывает inline buttons:

```text
[ 🏷 Tag 1 ]
[ 🏷 Tag 2 ]
[ 🏷 Tag 3 ]
```

Показываются только принадлежащие пользователю теги.

После выбора:

```text
selected_tag = tag
```

---

# 20. Telegram native title

Не пытаться выдавать обычным пользователям настоящий Telegram custom title через API.

Telegram custom title имеет ограничения и не является обычным пользовательским профилем.

Поэтому основная система:

```text
bot-managed tag
```

Tag показывается ботом:

```text
👤 Username [ЖИВАЯ ЛЕГЕНДА]
```

и в профиле.

---

# 21. Games — games.py

Все существующие игры перенести/собрать в одном файле.

### Существующие

* coinflip;
* dice;
* slots;
* roulette;
* tictactoe;
* blackjack;
* crash.

### Новые

* football;
* basketball.

---

# 22. Game unlock

Каждая игра перед запуском проверяет:

```text
is_feature_unlocked(user.level, feature)
```

Если нет:

```text
🔒 Игра открывается с X уровня.
```

Нельзя обойти unlock через callback.

Проверка должна выполняться и в callback handler.

---

# 23. Football

Unlock:

```text
level 5
```

Есть ставка.

Минимум/максимум ставки берутся из Config.

Результат определяется случайно.

После игры:

* проигрыш → ставка списана;
* выигрыш → приз начислен;
* ничья → отдельная логика.

---

# 24. Basketball

Unlock:

```text
level 7
```

Есть ставка.

Аналогичная безопасная транзакционная модель.

---

# 25. Tic-Tac-Toe

Исправить текущий баг.

Сейчас создаётся callback:

```text
tttjoin:{game.id}
```

но handler его не обрабатывает.

Добавить:

```text
tttjoin:
```

Проверить:

* существование игры;
* статус;
* первого игрока;
* второго игрока;
* ставку;
* нельзя присоединиться самому к себе;
* нельзя войти в уже начатую игру;
* нельзя сыграть в чужую завершённую игру.

---

# 26. Game transactions

Для игр со ставкой:

1. проверить баланс;
2. списать ставку;
3. создать game;
4. определить результат;
5. начислить выигрыш;
6. сохранить результат.

Не допускать повторного callback, который выдаёт награду несколько раз.

---

# 27. Giveaways

Добавить систему розыгрышей.

### Создание

Только разрешённые staff.

Параметры:

* приз;
* тип приза;
* время окончания.

### Призы

Поддержать:

```text
peanuts
inventory item
external/manual prize
```

### Участие

Inline button:

```text
🎁 Участвовать
```

Один пользователь — один участник.

### Завершение

Случайно выбрать одного участника.

Если приз внутренний:

```text
автоматически выдать
```

Если external:

```text
показать победителя + пометить приз как manual
```

---

# 28. Moderation — moderation.py

## Роли

```text
OWNER
HEAD_ADMIN
ADMIN
MODERATOR
```

### Owner

Задаётся через:

```text
OWNER_ID
```

Owner:

* назначает Head Admin.

### Head Admin

Может:

* назначать Admin;
* снимать Admin;
* назначать Moderator;
* снимать Moderator;
* менять доступ moderation-команд.

### Admin

Права определяются permission system.

### Moderator

Права определяются permission system.

---

# 29. Moderation permissions

Каждая moderation-команда имеет scope:

```text
STAFF
ADMIN
HEAD_ADMIN
```

### STAFF

Доступ:

```text
moderator + admin + head admin
```

### ADMIN

Доступ:

```text
admin + head admin
```

### HEAD_ADMIN

Доступ:

```text
head admin
```

Owner всегда выше системы.

---

# 30. Moderation commands

Сохранить/исправить:

```text
/warn
/unwarn
/mute
/unmute
/ban
/unban
/kick
/purge
/setnick
```

Убрать:

```text
/settag
```

---

# 31. Staff management

Добавить команды для управления ролями.

Например:

```text
/setheadadmin
/removeheadadmin

/setadmin
/removeadmin

/setmoderator
/removemoderator
```

Точные aliases можно определить при реализации.

---

# 32. Permission management

Head Admin должен иметь возможность изменить доступ каждой moderation-команды.

Например:

```text
/modpermission warn staff
/modpermission ban admin
/modpermission purge head_admin
```

После изменения сохранять в БД.

---

# 33. Purge

Текущий `/purge` фактически ничего не удаляет.

Исправить.

Например:

```text
/purge 20
```

Бот пытается удалить:

* команду;
* последние N сообщений.

Учитывать:

* права Telegram;
* невозможность удалить некоторые старые сообщения;
* ошибки Telegram API.

Удаление должно выполняться через реальные:

```python
bot.delete_message(...)
```

---

# 34. Command cleanup

По возможности после ответа бота пользовательские команды удаляются.

Например:

```text
/user command
       ↓
bot response
       ↓
delete command
```

Но удаление не должно ломать callback/game flow.

Все удаления — через безопасный helper:

```text
safe_delete_message()
```

Ошибки удаления не должны падать в handler.

---

# 35. Profile

Команда:

```text
/profile
```

Показывает собственный профиль.

Поддержать:

```text
/profile @username
```

и reply:

```text
/profile
```

ответом на сообщение пользователя.

Показывать:

* username;
* tag;
* level;
* XP;
* balance;
* penis size;
* disease;
* child status;
* cooldown-related information;
* Battle Pass;
* inventory-related summary.

Если есть disease:

```text
🩺 Сходить к венерологу
```

Если есть child:

```text
👶 Дать денег на аборт
```

---

# 36. Top

Добавить рейтинг размера:

```text
/topsize
```

или:

```text
/top
```

Показывать:

```text
1. user — X.XX см
2. user — X.XX см
3. user — X.XX см
```

---

# 37. Daily robbery

Команда:

```text
/rob @username
```

или reply.

Условия:

* один раз в 24 часа;
* размер нападающего строго больше размера цели;
* цель существует;
* нельзя rob самого себя.

Cooldown хранится в БД.

---

# 38. Message processing

Каждое обычное сообщение должно корректно проходить через:

```text
message
 ↓
find/create user
 ↓
+1 normal XP
 ↓
+1 Battle Pass XP
 ↓
level calculation
 ↓
level rewards if level increased
 ↓
economy reward separately
```

Главное:

**никакой cooldown не должен блокировать XP.**

---

# 39. Level rewards

При достижении уровня:

* проверить все новые уровни между old_level и new_level;
* выдать награды каждого уровня;
* увеличить member size согласно настройке;
* не выдавать одну награду повторно.

Награды должны быть idempotent.

---

# 40. Idempotency

Особенно важно для:

* games;
* giveaways;
* case opening;
* Battle Pass rewards;
* level rewards;
* callbacks;
* disease ticks;
* child support.

Повторный callback не должен повторно выдавать деньги/предмет.

---

# 41. Cooldowns

Все cooldown должны храниться по timestamp.

Основные:

```text
18+ RP       = 15 min
дрочка       = 6 hours
rob          = 24 hours
```

Модификаторы:

```text
Rubber Pussy:
18+ RP cooldown × 0.5
дрочка cooldown × 0.5
```

---

# 42. Item behavior

## Lubricant

```text
+5% к modifier увеличения размера
one-use
stackable
```

## Dildo

```text
3–5 дополнительных использований
max 1
после использования исчезает
duplicate → +5000 peanuts
```

## Rubber Pussy

```text
18+ cooldown × 0.5
дрочка cooldown × 0.5
20% daily +1 cm
автоматическая дрочка +0.05–0.20 cm
```

## Silicone Implant

```text
instant +1 cm
auto-consume
```

## Condom

```text
auto-use
90% protection from disease
stackable
```

---

# 43. Disease details

Disease is persistent.

Stored in database.

При каждом обращении:

```text
reconcile_disease()
```

Если прошло несколько часов:

```text
for every missed hour:
    size -= 0.5
    balance -= up to 500
```

Timestamp после обработки должен быть сдвинут корректно, чтобы эффект не применялся повторно.

---

# 44. Child details

Child state:

```text
child_until
last_child_support
```

При каждом обращении:

```text
reconcile_child()
```

Каждый прошедший час:

```text
-10000 peanuts
```

После 18 часов:

```text
child removed
```

Пока child активен:

```text
18+ RP запрещено
```

---

# 45. Error handling

Нельзя допускать падение бота из-за:

* отсутствующего пользователя;
* удалённого сообщения;
* старого callback;
* повторного callback;
* недостатка денег;
* отсутствующего предмета;
* Telegram permissions;
* неправильного username;
* уже завершённой игры.

Все ожидаемые ошибки должны превращаться в нормальный ответ пользователю.

---

# 46. Transaction safety

Денежные операции должны выполняться атомарно.

Особенно:

* ставки;
* выигрыши;
* rob;
* medicine;
* abortion;
* child support;
* case duplicate compensation;
* RP payment.

Нельзя допустить:

```text
деньги списались дважды
```

или:

```text
выигрыш выдан дважды
```

---

# 47. Configurable constants

В `core.py` вынести настройки:

```text
NORMAL_RP_COST = 10
ADULT_RP_COST = 50

ADULT_RP_COOLDOWN = 15 minutes
MASTURBATION_COOLDOWN = 6 hours

DISEASE_CHANCE = 50%
CONDOM_PROTECTION = 90%

DISEASE_SIZE_LOSS = 0.5
DISEASE_MEDICINE_TICK_COST = 500
VENEREOLOGIST_COST = 5000
VENEREOLOGIST_CURE_CHANCE = 20%

PREGNANCY_CHANCE = 15%
PREGNANCY_CHANCE_WITH_CONDOM = 5%

CHILD_SUPPORT = 10000
CHILD_DURATION = 18 hours

ABORTION_COST = 30000
ABORTION_SUCCESS_CHANCE = 50%

LUBRICANT_BONUS = 5%

SILICONE_IMPLANT_BONUS = 1.0

MASTURBATION_MIN_GAIN = 0.05
MASTURBATION_MAX_GAIN = 0.20

ROB_COOLDOWN = 24 hours
```

Все спорные балансные значения должны находиться в одном месте.

---

# 48. Case balancing

Все drop rates находятся в `core.py`.

Не размазывать вероятности по handlers.

Пример:

```text
peanuts
lubricant
dildo
rubber_pussy
silicone_implant
condom
tag
```

Точные вероятности можно балансировать без изменения бизнес-логики.

---

# 49. Telegram callback security

Каждый callback должен повторно проверять:

* user id;
* game ownership;
* item ownership;
* permissions;
* game state;
* giveaway state;
* target;
* cooldown.

Нельзя полагаться только на наличие inline button.

---

# 50. Проверка после реализации

После каждого этапа проверить:

## База

* запускается SQLite;
* подключается PostgreSQL;
* существующая база не ломается;
* новые таблицы создаются.

## XP

* каждое сообщение даёт XP;
* cooldown не блокирует XP;
* Battle Pass XP начисляется каждое сообщение.

## Profile

* свой профиль;
* профиль по username;
* профиль reply.

## RP

* обычный RP;
* двухсловные RP;
* цена 10;
* 18+ цена 50;
* cooldown;
* target;
* modifiers.

## Items

* case;
* lubricant;
* dildo;
* rubber pussy;
* implant;
* condom;
* tags.

## Disease

* заражение;
* condom protection;
* hourly tick;
* medicine;
* venereologist;
* cure chance.

## Child

* pregnancy;
* support;
* RP lock;
* abortion;
* expiration.

## Games

* unlock;
* ставки;
* payouts;
* TTT join;
* callbacks.

## Moderation

* owner;
* head admin;
* admin;
* moderator;
* permissions;
* purge.

## Giveaways

* join;
* duplicate join prevention;
* random winner;
* automatic prize;
* manual prize.

---

# 51. Этапы реализации

## Этап 1 — база и инфраструктура

Файлы:

```text
database.py
core.py
services.py
```

Сделать:

* новые поля;
* новые модели;
* migration compatibility;
* economy;
* XP;
* Battle Pass state;
* timestamps;
* target resolver.

---

## Этап 2 — RP

Файлы:

```text
rp.py
services.py
core.py
```

Сделать:

* parser;
* обычный RP;
* 18+ RP;
* цены;
* cooldown;
* size;
* disease;
* child;
* robbery;
* reconciliation.

---

## Этап 3 — Inventory / Cases / Tags

Файлы:

```text
inventory.py
database.py
core.py
handlers.py
```

Сделать:

* cases;
* drops;
* inventory;
* tags;
* `/tag`;
* использование предметов.

---

## Этап 4 — Games

Файлы:

```text
games.py
handlers.py
core.py
services.py
```

Сделать:

* unlock;
* football;
* basketball;
* TTT join;
* ставки;
* callback security.

---

## Этап 5 — Moderation

Файлы:

```text
moderation.py
database.py
handlers.py
```

Сделать:

* roles;
* permissions;
* role management;
* moderation;
* purge;
* setnick;
* убрать settag.

---

## Этап 6 — Battle Pass / Giveaways / Profile UI

Файлы:

```text
handlers.py
services.py
inventory.py
```

Сделать:

* Battle Pass;
* rewards;
* final tag;
* giveaways;
* profile buttons;
* disease button;
* abortion button;
* top.

---

## Этап 7 — Integration

Проверить:

* imports;
* circular dependencies;
* callback routing;
* command routing;
* database startup;
* existing functionality;
* configuration.

---

# 52. Финальная проверка

Перед объявлением работы завершённой:

### Commands

Проверить все существующие команды.

### Games

Проверить каждую игру.

### RP

Проверить каждую RP-команду.

### Database

Проверить существующую БД.

### Permissions

Проверить каждую moderation-команду.

### Callbacks

Проверить каждый callback prefix.

### Economy

Проверить каждую операцию с арахисом.

### Persistence

Перезапустить бота и убедиться, что:

* XP сохранён;
* level сохранён;
* Battle Pass сохранён;
* inventory сохранён;
* tags сохранены;
* disease сохранена;
* child сохранён;
* cooldown timestamps сохранены;
* games не могут быть использованы повторно;
* giveaway state сохранён.

---

# 53. Definition of Done

Работа считается завершённой только когда:

* [ ] максимум 10 основных файлов;
* [ ] TTT работает;
* [ ] профиль другого пользователя работает;
* [ ] двухсловные RP работают;
* [ ] football работает;
* [ ] basketball работает;
* [ ] game unlock реально работает;
* [ ] Battle Pass работает;
* [ ] каждое сообщение даёт XP;
* [ ] антифлуд не блокирует XP;
* [ ] награды Battle Pass работают;
* [ ] финальный tag выдаётся;
* [ ] `/settag` удалён;
* [ ] `/tag` показывает только собственные tags;
* [ ] cases работают;
* [ ] items работают;
* [ ] size работает;
* [ ] top size работает;
* [ ] disease работает;
* [ ] medicine работает;
* [ ] venereologist работает;
* [ ] condom работает;
* [ ] child mechanic работает;
* [ ] child support работает;
* [ ] abortion работает;
* [ ] robbery работает;
* [ ] normal RP стоит 10;
* [ ] 18+ RP стоит 50;
* [ ] 18+ cooldown работает;
* [ ] masturbation cooldown работает;
* [ ] moderation roles работают;
* [ ] moderation permissions работают;
* [ ] purge реально удаляет сообщения;
* [ ] giveaways работают;
* [ ] automatic prizes работают;
* [ ] manual prizes работают;
* [ ] существующие функции не сломаны;
* [ ] бот переживает restart;
* [ ] SQLite работает;
* [ ] PostgreSQL совместимость сохранена.
