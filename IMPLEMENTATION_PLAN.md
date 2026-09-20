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
* Telegram handlers отвечают за Telegram-взаимодействие.
* Services отвечают за бизнес-логику.
* Database отвечает за модели и работу с БД.
* Конфигурационные значения находятся в `core.py`.
* Не ломать существующие команды без причины.
* Все persistent-механики должны переживать перезапуск бота.
* Не использовать in-memory состояние там, где состояние должно храниться в БД.
* Не использовать фоновые бесконечные задачи для механик, которые можно рассчитывать по timestamp при обращении пользователя.
* `/purge` полностью исключён из проекта.
* Message tracking полностью исключён из проекта.
* Не добавлять отдельные таблицы или файлы для message tracking.
* Не добавлять `purge` обратно в commands/help/permissions/handlers.
* RP-сообщения не дают XP. XP начисляется обычным обработанным сообщениям.

---

# 1. Фактическая структура проекта

Проект сознательно оставлен компактным.

```text
angelok/
├── bot.py
├── core.py
├── database.py
├── services.py
├── handlers.py
├── requirements.txt
├── .env.example
├── README.md
└── IMPLEMENTATION_PLAN.md
```

Всего: **9 основных файлов**.

Новые `games.py`, `rp.py`, `inventory.py`, `moderation.py` не создаются.

Их ответственность распределена между:

* `handlers.py` — Telegram routing/UI;
* `services.py` — бизнес-логика;
* `database.py` — модели/БД;
* `core.py` — конфигурация/константы;
* `bot.py` — lifecycle.

---

# 2. bot.py

## Ответственность

Только lifecycle и запуск приложения.

### Должно быть

* загрузка `.env`;
* чтение конфигурации;
* инициализация приложения;
* инициализация БД;
* создание `Bot`;
* создание `Dispatcher`;
* регистрация handlers;
* настройка Telegram command menu;
* запуск background worker только там, где он действительно нужен;
* graceful shutdown;
* обработка ошибок верхнего уровня.

### Не должно быть

* игровой бизнес-логики;
* SQL-запросов;
* расчётов экономики;
* RP-механики;
* инвентарной логики;
* permission-логики.

### Giveaway worker

Разрешён один background worker для автоматического завершения giveaway.

Worker не хранит состояние механики в памяти.

Состояние giveaway всегда берётся из БД.

---

# 3. core.py

## Ответственность

Центральная конфигурация, постоянные значения и игровые правила.

### 3.1 Конфигурация

Использовать:

* `BOT_TOKEN`
* `OWNER_ID`
* `DATABASE_URL`
* `LOG_LEVEL`
* `MESSAGE_REWARD_MIN`
* `MESSAGE_REWARD_MAX`
* `MESSAGE_XP`
* `MESSAGE_REWARD_COOLDOWN`
* `DAILY_BONUS_MIN`
* `DAILY_BONUS_MAX`
* `MIN_BET`
* `MAX_BET`

### 3.2 XP

За каждое обычное обработанное сообщение:

```text
+1 XP
```

Без cooldown.

Антифлуд действует только на денежную награду за сообщение.

Нельзя:

```text
cooldown → блок XP
```

Правильно:

```text
message
→ +XP
→ +Battle Pass XP
→ отдельно проверка денежной награды
```

RP-команды не должны выдавать XP.

### 3.3 Battle Pass XP

Отдельная система:

```text
1 обычное сообщение = +1 Battle Pass XP
```

Без антифлуда.

---

# 4. Уровни

Сохраняется текущая формула уровней.

Текущие feature unlock:

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

Проверка unlock должна происходить в service layer.

Callback не может обходить unlock.

---

# 5. Battle Pass

## Состояние

Хранить в БД:

* `battle_pass_xp`;
* `battle_pass_level`;
* `battle_pass_season`.

## Прогресс

Текущая модель:

```text
1 сообщение = +1 BP XP
100 BP XP = +1 BP level
```

Максимальный уровень:

```text
30
```

## Типы наград

* арахис;
* XP;
* кейс;
* tag.

## Claim

Награда каждого уровня должна выдаваться только один раз.

Использовать `BattlePassRewardClaim`.

Повторная обработка сообщения или повторная попытка claim не должны повторно выдавать награду.

## UI

`/battlepass` должен показывать:

* текущий уровень;
* текущий BP XP;
* XP до следующего уровня;
* полученные награды;
* текущую/следующую награду;
* финальную награду.

## Финальная награда

Уникальный tag:

```text
ЖИВАЯ ЛЕГЕНДА
```

---

# 6. database.py

## Ответственность

Только SQLAlchemy-модели и работа с БД.

Никакого отдельного `models.py`.

## User

Хранит Telegram-пользователя.

## Chat

Хранит Telegram-chat.

## ChatMember

Хранит состояние пользователя внутри конкретного чата:

* balance;
* messages;
* xp;
* level;
* battle pass xp;
* battle pass level;
* battle pass season;
* penis size;
* disease;
* disease timestamps;
* child;
* child timestamps;
* robbery cooldown;
* message reward timestamp;
* RP cooldown;
* masturbation cooldown;
* daily bonus timestamp;
* выбранный tag;
* игровые statistics;
* profile nickname.

## StaffMember

Привязка:

```text
chat_id + user_id
```

Роли:

```text
OWNER
HEAD_ADMIN
ADMIN
MODERATOR
```

## ModPermission

Хранит permission конкретной moderation-команды.

Scopes:

```text
STAFF
ADMIN
HEAD_ADMIN
```

`PURGE` не существует.

## InventoryItem

Тип предмета и описание.

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

## UserItem

Связь пользователя и предмета.

Поддерживает:

* quantity;
* uses_left;
* stackable;
* max_quantity.

## Tag

Описание тега.

## UserTag

Принадлежность тега пользователю.

Установить можно только tag, который реально есть у пользователя.

## Game

Хранит историю завершённых игр.

## TicTacToeGame

Хранит состояние TTT:

* players;
* board;
* status;
* current player;
* bet;
* message id.

## Giveaway

Хранит:

* chat;
* creator;
* prize;
* prize type;
* end time;
* status;
* winner;
* completion timestamp.

## GiveawayParticipant

Участники giveaway.

Unique:

```text
giveaway_id + user_id
```

## BattlePassRewardClaim

Unique:

```text
chat_id + user_id + season + level
```

---

# 7. Миграция БД

`create_all()` недостаточно для существующей БД.

В `database.py` используется простой compatibility layer:

1. определить существующие таблицы;
2. определить существующие колонки;
3. добавить отсутствующие колонки;
4. создать отсутствующие таблицы;
5. выполнить безопасный startup.

Не создавать отдельный migration-файл.

SQLite должен работать локально.

PostgreSQL должен сохранять совместимость.

---

# 8. services.py

## Ответственность

Вся бизнес-логика проекта.

Handler не должен сам рассчитывать:

* экономику;
* XP;
* Battle Pass;
* RP;
* disease;
* child;
* item effects;
* game payouts;
* permissions.

---

# 9. Экономика

Поддержать:

* баланс;
* добавление арахиса;
* списание арахиса;
* перевод;
* проверку достаточности средств;
* сообщение reward;
* daily bonus;
* game payout;
* item compensation;
* disease support cost;
* child support;
* RP cost.

Все изменения баланса должны создавать `EconomyTransaction`.

Баланс не может становиться отрицательным.

---

# 10. Transaction safety

Денежные операции должны быть атомарными в рамках одной DB-транзакции.

Особенно:

* ставки;
* выигрыши;
* transfer;
* robbery;
* RP cost;
* medicine;
* venereologist;
* abortion;
* child support;
* case compensation;
* Battle Pass peanuts;
* daily bonus.

Не допускать:

```text
double payout
double charge
negative balance
```

Конкурентные операции должны повторно проверять баланс под общей economy lock.

---

# 11. XP

Каждое обычное сообщение:

```text
member.messages += 1
member.xp += MESSAGE_XP
member.battle_pass_xp += 1
```

Без XP cooldown.

При переходе уровня:

1. определить `old_level`;
2. определить `new_level`;
3. обработать каждый новый уровень;
4. выдать все положенные rewards;
5. применить size reward;
6. собрать unlocks;
7. сформировать уведомление.

---

# 12. Level rewards

При переходе через несколько уровней:

```text
old = 2
new = 5
```

обрабатываются:

```text
3
4
5
```

а не только уровень 5.

Награды должны быть idempotent.

---

# 13. Message economy

Экономическая награда за сообщение имеет отдельный cooldown.

```text
message XP
    ↓
всегда

message money reward
    ↓
через cooldown
```

Таким образом:

```text
cooldown не влияет на XP
```

---

# 14. Target resolver

Единый принцип для target-based механик:

1. reply;
2. username;
3. user id;
4. self, если команда допускает self.

Используется для:

```text
/profile
/stats
/rob
RP
```

Target должен существовать в текущем chat context для chat-specific действий.

---

# 15. Disease reconciliation

Не использовать отдельный scheduler.

При обращении к пользователю:

```text
reconcile_member_state()
```

внутри которой выполняются:

```text
reconcile_disease()
reconcile_child()
reconcile_rubber_pussy_daily()
```

## Disease

Если прошло несколько часов:

```text
for every missed hour:
    penis_size -= 0.5
    charge up to 500 peanuts
```

Если денег недостаточно:

* баланс не уходит в минус;
* size penalty всё равно применяется.

После tick timestamp сдвигается так, чтобы тот же tick не применился повторно.

---

# 16. Child reconciliation

При активном child:

```text
каждый прошедший час:
    charge up to 10000 peanuts
```

Баланс не уходит ниже нуля.

После:

```text
child_until <= now
```

состояние child очищается.

Пока child активен:

```text
18+ RP заблокирован
```

---

# 17. Robbery

Условия:

* actor != target;
* оба пользователя существуют в текущем chat;
* actor size > target size;
* target balance > 0;
* cooldown 24 часа.

Cooldown хранится в БД.

Сама операция должна быть защищена economy lock.

Проигрыш robbery тоже считается попыткой и обновляет cooldown согласно текущей логике.

---

# 18. Обычный RP

Цена:

```text
10 🥜
```

Команды:

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

Обычный RP:

* требует target;
* не разрешается на себя;
* списывает 10 🥜;
* не даёт XP;
* не даёт Battle Pass XP;
* не содержит графических описаний.

---

# 19. RP parser

Parser должен поддерживать longest-match.

Примеры:

```text
дать пять
дать подзатыльник
кинуть тапок
```

Нельзя разбирать только первый токен.

Порядок:

```text
сначала наиболее длинный alias
потом более короткий
```

---

# 20. 18+ RP

Цена:

```text
50 🥜
```

Cooldown:

```text
15 минут
```

При наличии Rubber Pussy:

```text
cooldown × 0.5
```

18+ RP остаётся не графическим.

Service отвечает только за игровые эффекты:

* size;
* cooldown;
* disease;
* child;
* items.

---

# 21. 18+ size modifiers

Размер actor:

```text
+random gain × action modifier
```

Размер target:

```text
-random loss × action modifier
```

Размер не может стать отрицательным.

Lubricant:

```text
+5% к росту
```

После применения lubricant расходуется.

---

# 22. Condom

Condom используется автоматически при 18+ RP.

Если есть condom:

```text
disease chance × (1 - 90%)
```

То есть заболевание становится значительно менее вероятным.

Condom расходуется на использование.

Предмет stackable.

---

# 23. Disease

Без condom:

```text
50% chance
```

При наличие condom:

```text
эффективный шанс значительно ниже
```

Болезнь:

```text
persistent
```

Каждый час:

```text
-0.5 см
-500 🥜 максимум
```

---

# 24. Medicine

Medicine очищает/смягчает состояние болезни согласно текущей механике.

Стоимость и остальные значения находятся в `core.py`.

---

# 25. Venereologist

Кнопка появляется в profile только при болезни:

```text
🩺 Сходить к венерологу
```

Стоимость:

```text
5000 🥜
```

Chance:

```text
20%
```

При успехе:

```text
disease = false
```

При провале:

```text
disease сохраняется
```

---

# 26. Child mechanic

При 18+ RP:

Без condom:

```text
15%
```

С condom:

```text
5%
```

При срабатывании:

```text
actor.has_child = true
actor.child_until = now + 18 hours
```

Второй child получить нельзя.

---

# 27. Child support

Каждый прошедший час:

```text
-10000 🥜
```

После 18 часов:

```text
child = false
```

Время поддержки хранится в БД.

---

# 28. Abortion

Кнопка:

```text
👶 Дать денег на аборт
```

Стоимость:

```text
30000 🥜
```

Chance:

```text
50%
```

Успех:

```text
child = false
```

Провал:

```text
child сохраняется
```

---

# 29. Masturbation

Команда:

```text
/masturbate
```

Основной cooldown:

```text
6 часов
```

Rubber Pussy:

```text
cooldown × 0.5
```

Gain:

```text
+0.05–0.20 см
```

При наличии Dildo:

* cooldown может быть обойдён согласно текущей механике;
* используется один charge;
* количество uses уменьшается;
* после исчерпания предмет удаляется.

Cooldown и расход Dildo должны быть защищены от double callback.

---

# 30. Dildo

Свойства:

```text
3–5 uses
max 1
```

Если выпадает повторно:

```text
+5000 🥜
```

Вместо второго Dildo.

---

# 31. Rubber Pussy

При получении:

```text
18+ RP cooldown × 0.5
masturbation cooldown × 0.5
```

Daily effect:

```text
20% chance +1 см в сутки
```

Должен применяться максимум один раз за сутки.

---

# 32. Silicone Implant

При выпадении:

```text
+1 см
```

Применяется автоматически.

Не хранится как обычный usable item.

---

# 33. Inventory

Кейсы и предметы должны храниться в БД.

Inventory UI показывает:

* предмет;
* quantity;
* uses_left, если применимо.

Не создавать отдельное in-memory состояние.

---

# 34. Cases

Кейс содержит weighted random reward.

Возможные типы:

```text
peanuts
lubricant
dildo
rubber_pussy
silicone_implant
condom
tag
```

Открытие:

```text
case consumed
reward granted
```

Один callback не должен выдавать награду повторно.

---

# 35. Tags

Пользовательский `/settag` полностью удалён.

Теги выдаются:

* через cases;
* через Battle Pass.

`/tag` показывает только теги текущего пользователя.

UI:

```text
[ 🏷 Tag 1 ]
[ 🏷 Tag 2 ]
[ 🏷 Tag 3 ]
```

Callback обязан дополнительно проверить принадлежность tag пользователю.

Чужой tag назначить нельзя.

---

# 36. Telegram native title

Не использовать Telegram custom title как основную систему обычных тегов.

Использовать bot-managed tags.

Формат:

```text
👤 Username [ЖИВАЯ ЛЕГЕНДА]
```

---

# 37. Games

Поддерживаются:

```text
coinflip
dice
slots
roulette
guess
football
basketball
tictactoe
blackjack
crash
```

Игровая бизнес-логика находится в `services.py`.

Игровой Telegram UI находится в `handlers.py`.

---

# 38. Game unlock

Перед запуском game service обязан проверить unlock.

При callback также нельзя доверять только кнопке.

Если уровень недостаточен:

```text
🔒 Игра открывается на X уровне.
```

---

# 39. Game transaction flow

Для каждой ставки:

```text
validate bet
↓
reconcile state
↓
check unlock
↓
check balance
↓
recheck balance under economy lock
↓
charge stake
↓
determine result
↓
payout
↓
write Game
↓
commit
```

Повторный callback не должен повторно выдавать payout.

---

# 40. Football

Unlock:

```text
level 5
```

Есть ставка.

Результат определяется случайно.

Win:

```text
payout according to FOOTBALL_MULTIPLIER
```

Loss:

```text
stake lost
```

---

# 41. Basketball

Unlock:

```text
level 7
```

Есть ставка.

Результат определяется случайно.

Win:

```text
payout according to BASKETBALL_MULTIPLIER
```

Loss:

```text
stake lost
```

---

# 42. Tic-Tac-Toe

Unlock:

```text
level 10
```

Минимальная ставка:

```text
10 🥜
```

Flow:

```text
start
↓
waiting
↓
join
↓
playing
↓
moves
↓
win/draw
```

Join callback:

```text
tttjoin:{game.id}
```

обязательно обрабатывается.

Проверять:

* game exists;
* waiting/playing status;
* participant;
* second player;
* balance;
* self-join;
* turn;
* cell ownership;
* cell availability;
* finished state.

Draw:

```text
stake refund
```

Оба игрока получают корректно записанную игровую статистику.

Win:

```text
winner payout
loser stake lost
```

---

# 43. Blackjack

Минимальная ставка:

```text
10 🥜
```

Win:

```text
2.0x
```

Natural:

```text
2.5x
```

Draw:

```text
refund
```

Все операции money должны быть атомарными.

---

# 44. Crash

Unlock:

```text
level 20
```

Min bet:

```text
10 🥜
```

Multiplier range:

```text
1.10x–10.00x
```

Текущая реализация — одношаговый симулятор:

```text
ставка
↓
выбор cashout multiplier
↓
генерация crash multiplier
↓
win/loss
```

Это не должно требовать in-memory game session.

---

# 45. Giveaways

Создание доступно разрешённым staff.

Типы призов:

```text
peanuts
inventory item
external/manual
```

Участие через inline button:

```text
🎁 Участвовать
```

Один пользователь:

```text
один giveaway → один participant
```

---

# 46. Giveaway completion

При завершении:

1. получить active giveaway;
2. получить participants;
3. выбрать winner;
4. сохранить winner;
5. выдать внутренний приз;
6. external prize пометить как manual;
7. изменить status;
8. сохранить completion timestamp.

Повторное завершение не должно выдавать приз повторно.

---

# 47. Giveaways persistence

Статус:

```text
active
finished
```

хранится в БД.

Автоматическое завершение выполняется worker'ом в `bot.py`.

Worker только находит просроченные записи и вызывает service.

---

# 48. Moderation

Роли:

```text
OWNER
HEAD_ADMIN
ADMIN
MODERATOR
```

Owner определяется через:

```text
OWNER_ID
```

Owner выше локальной staff hierarchy.

---

# 49. Moderation permissions

Scopes:

```text
STAFF
ADMIN
HEAD_ADMIN
```

Расшифровка:

```text
STAFF
→ moderator + admin + head admin

ADMIN
→ admin + head admin

HEAD_ADMIN
→ head admin
```

Owner всегда имеет доступ.

---

# 50. Moderation commands

Поддерживаются текущие:

```text
/warn
/unwarn
/warnings
/mute
/unmute
/ban
/unban
/kick
/setnick
/setrole
/delrole
/setperm
```

Также:

```text
/give
/take
/setbalance
/setlevel
```

для разрешённых staff.

`/settag` отсутствует.

`/purge` отсутствует.

---

# 51. Staff management

Поддержать текущую систему:

```text
/setrole
/delrole
```

или существующие aliases внутри текущей архитектуры.

Нельзя дать роль выше собственных полномочий.

---

# 52. Permission management

Head Admin может изменять permission moderation-команд.

Настройка сохраняется в БД.

Owner всегда выше permission system.

---

# 53. Command cleanup

В группах:

```text
command
↓
bot response
↓
temporary cleanup
```

Текущая политика:

```text
GROUP_COMMAND_TTL = 5 sec
GROUP_BOT_MESSAGE_TTL = 30 sec
PRIVATE_BOT_MESSAGE_TTL = 0
```

Ошибки удаления не должны падать в handler.

Использовать:

```text
safe_delete_message()
```

Message tracking отсутствует.

Callback messages с inline UI не должны удаляться так, чтобы ломать игровой flow.

---

# 54. Bottom ReplyKeyboard

Основная навигация должна использовать нижнюю ReplyKeyboard:

```text
👤 Профиль
📊 Стата
🥜 Баланс
🎒 Инвентарь
🎮 Игры
🏆 Топ
📏 Топ размера
🎁 Бонус
🏅 Battle Pass
🏷 Теги
```

Кнопки ведут к соответствующим разделам.

Основные игровые действия должны по возможности использовать inline keyboard.

---

# 55. Inline UI

Использовать inline buttons для:

* разделов профиля;
* disease/medicine;
* venereologist;
* child/abortion;
* Battle Pass;
* cases;
* tags;
* games;
* TTT;
* giveaways.

Основные интерактивные сценарии не должны требовать от пользователя ручного повторного ввода там, где можно использовать callback.

---

# 56. Profile

Команда:

```text
/profile
```

Поддержка:

```text
/profile
/profile @username
/profile USER_ID
```

и reply.

Показывать:

* username;
* nickname;
* tag;
* level;
* XP;
* balance;
* penis size;
* disease;
* child;
* Battle Pass;
* краткий inventory summary;
* cooldown information по необходимости.

Если disease:

```text
🩺 Сходить к венерологу
```

Если child:

```text
👶 Дать денег на аборт
```

Переходы выполняются через callbacks.

---

# 57. Stats

Показывать:

* messages;
* XP;
* level;
* games;
* wins/losses;
* total won/lost;
* size;
* Battle Pass progress.

---

# 58. Top

Поддержать:

```text
/top
/topsize
```

Размер сортируется по:

```text
penis_size DESC
```

Показывать:

```text
1. user — X.XX см
2. user — X.XX см
3. user — X.XX см
```

---

# 59. Error handling

Ожидаемые ошибки превращаются в ServiceResult:

* user not found;
* target not found;
* callback expired;
* insufficient balance;
* cooldown;
* locked game;
* missing item;
* finished game;
* finished giveaway;
* no permission.

Telegram API errors не должны ронять dispatcher.

---

# 60. Callback security

Каждый callback повторно проверяет необходимые условия.

Проверять:

* callback user id;
* target;
* game state;
* game participant;
* permissions;
* ownership;
* item ownership;
* giveaway status;
* cooldown;
* unlock;
* balance.

Inline button не считается доверенным источником состояния.

---

# 61. Idempotency

Ключевые системы не должны повторно выдавать reward:

* game payout;
* game stake;
* TTT win;
* TTT draw;
* blackjack refund;
* giveaway winner/prize;
* case opening;
* Battle Pass reward;
* item compensation;
* disease ticks;
* child support;
* daily bonus.

Использовать:

* DB state;
* unique constraints;
* timestamps;
* service-level locks;
* повторные проверки состояния.

---

# 62. Persistence

После restart должны сохраняться:

```text
XP
level
Battle Pass
inventory
tags
selected tag
size
disease
child
cooldowns
game history
giveaway state
staff roles
permissions
```

Никакая из этих механик не должна зависеть от runtime-only in-memory session.

---

# 63. Configurable constants

Все balance-related значения находятся в `core.py`.

Основные:

```text
NORMAL_RP_COST = 10
ADULT_RP_COST = 50

ADULT_RP_COOLDOWN = 15 min
MASTURBATION_COOLDOWN = 6 h

DISEASE_CHANCE = 50%
CONDOM_PROTECTION = 90%

DISEASE_SIZE_LOSS = 0.5
DISEASE_TICK_COST = 500
VENEREOLOGIST_COST = 5000
VENEREOLOGIST_CURE_CHANCE = 20%

PREGNANCY_CHANCE = 15%
PREGNANCY_CHANCE_WITH_CONDOM = 5%

CHILD_SUPPORT = 10000
CHILD_DURATION = 18 h

ABORTION_COST = 30000
ABORTION_SUCCESS_CHANCE = 50%

LUBRICANT_BONUS = 5%

SILICONE_IMPLANT_BONUS = 1.0

MASTURBATION_MIN_GAIN = 0.05
MASTURBATION_MAX_GAIN = 0.20

ROB_COOLDOWN = 24 h
```

---

# 64. Case balancing

Drop rates должны храниться в `core.py`.

Не размещать вероятности внутри handlers.

---

# 65. Final audit

После завершения основной реализации необходимо проверить связку:

```text
handlers.py
↔
services.py
↔
database.py
↔
core.py
```

Проверить:

* все imports;
* все service signatures;
* все callback prefixes;
* все команды;
* все model fields;
* все database aliases/synonyms;
* все permission scopes;
* все feature unlocks.

---

# 66. Static checks

Перед объявлением готовности выполнить минимум:

```text
python -m py_compile bot.py core.py database.py services.py handlers.py
```

Также проверить:

```text
python import checks
database initialization checks
```

при доступном окружении.

---

# 67. Database checks

Проверить:

## SQLite

* новая БД создаётся;
* существующая БД запускается;
* отсутствующие колонки добавляются;
* новые таблицы создаются.

## PostgreSQL

* URL корректно разбирается;
* async driver используется;
* модели создаются/совместимы;
* compatibility layer не содержит SQLite-only логики.

---

# 68. XP checks

Проверить:

```text
message #1 → +1 XP
message #2 → +1 XP
message #3 → +1 XP
```

Даже если денежный reward cooldown ещё не истёк.

Отдельно:

```text
message → +1 BP XP
```

RP:

```text
RP → no XP
```

---

# 69. Profile checks

Проверить:

```text
/profile
/profile @username
/profile reply
```

и callback-кнопки:

```text
medicine
venereologist
abortion
```

---

# 70. RP checks

Проверить все команды:

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

Отдельно:

```text
longest-match parser
```

---

# 71. 18+ checks

Проверить:

```text
cost = 50
cooldown = 15 min
Rubber Pussy = ×0.5
```

Также:

* lubricant;
* dildo;
* rubber pussy;
* silicone implant;
* condom;
* disease;
* child.

---

# 72. Disease checks

Проверить:

```text
infection
condom protection
missed hourly ticks
size loss
balance charge
insufficient balance
medicine
venereologist
```

Особенно:

```text
repeated reconciliation
```

не должна повторно применять один и тот же tick.

---

# 73. Child checks

Проверить:

```text
pregnancy chance
condom chance
child lock
hourly support
insufficient balance
18h expiration
abortion
```

---

# 74. Inventory checks

Проверить:

```text
case quantity
case open
lubricant consumption
dildo uses
dildo expiration
duplicate dildo compensation
rubber pussy
implant instant effect
condom consumption
tag ownership
```

---

# 75. Game checks

Проверить:

```text
coinflip
dice
slots
roulette
guess
football
basketball
tictactoe
blackjack
crash
```

Для каждой:

* unlock;
* min/max bet;
* balance;
* payout;
* Game record;
* repeated callback.

---

# 76. TTT checks

Отдельно проверить:

```text
start
join
self join
third player
wrong participant
wrong turn
occupied cell
win
draw
refund
stats
finished callback
```

---

# 77. Giveaway checks

Проверить:

```text
create
join
duplicate join
finish
random winner
automatic peanuts
automatic item
manual external prize
expired auto-finish
double finish
```

---

# 78. Moderation checks

Проверить:

```text
owner
head admin
admin
moderator
permissions
setrole
delrole
setperm
warn
unwarn
warnings
mute
unmute
ban
unban
kick
setnick
```

Проверить, что `purge` нигде не существует.

---

# 79. Purge exclusion check

Обязательный финальный grep/search:

```text
purge
message tracking
tracking model
```

Допускаются только исторические пояснения в git/старых документах, но в рабочем коде:

```text
нет purge handler
нет purge permission
нет purge command
нет tracking model
нет tracking service
```

---

# 80. UI finalization

После функционального аудита выполняется отдельный cosmetic pass.

Приоритет:

1. Profile;
2. Battle Pass;
3. Inventory;
4. Cases;
5. Games;
6. TTT;
7. Top/Stats;
8. navigation.

Цель:

* меньше лишнего текста;
* больше inline navigation;
* единый стиль;
* понятные кнопки;
* короткие ответы;
* отсутствие визуального мусора в групповых чатах.

---

# 81. Current implementation stages

## Этап 1 — handlers

Статус:

```text
DONE
```

Сделано:

* ReplyKeyboard;
* inline navigation;
* callback routing;
* profile actions;
* games UI;
* TTT join;
* case UI;
* tag UI;
* Battle Pass UI;
* command cleanup;
* удаление purge;
* удаление message tracking.

---

## Этап 2 — services

Статус:

```text
DONE
```

Сделано:

* economy;
* XP;
* Battle Pass;
* RP;
* 18+ RP;
* disease;
* child;
* items;
* cases;
* tags;
* games;
* TTT;
* giveaways;
* moderation;
* reconciliation.

Осталось пройти финальный race/idempotency audit.

---

## Этап 3 — bot

Статус:

```text
DONE
```

Сделано:

* startup;
* shutdown;
* DB initialization;
* Telegram command menu;
* giveaway worker;
* удаление purge из command menu.

---

## Этап 4 — final audit

Статус:

```text
IN PROGRESS
```

Нужно:

* проверить transaction safety;
* проверить concurrent economy operations;
* проверить repeated callbacks;
* проверить Battle Pass claim idempotency;
* проверить disease/child reconciliation;
* проверить полный callback routing;
* проверить database compatibility;
* провести syntax/import tests.

---

## Этап 5 — cosmetic pass

После финального audit:

* Battle Pass UI;
* profile UI;
* inventory UI;
* games UI;
* навигация;
* тексты;
* компактность ответов.

---

# 82. Definition of Done

Работа считается завершённой, когда:

* [ ] максимум 10 основных файлов;
* [ ] фактическая архитектура соответствует 9-файловой структуре;
* [ ] purge полностью удалён;
* [ ] message tracking полностью удалён;
* [ ] TTT работает;
* [ ] TTT join работает;
* [ ] TTT callbacks проверяют игрока и состояние;
* [ ] профиль другого пользователя работает;
* [ ] `/profile @username` работает;
* [ ] `/profile` reply работает;
* [ ] двухсловные RP работают;
* [ ] football работает;
* [ ] basketball работает;
* [ ] game unlock реально работает;
* [ ] callback не обходит unlock;
* [ ] Battle Pass работает;
* [ ] каждое обычное сообщение даёт XP;
* [ ] cooldown не блокирует XP;
* [ ] каждое обычное сообщение даёт BP XP;
* [ ] RP не даёт XP;
* [ ] награды Battle Pass idempotent;
* [ ] финальный tag выдаётся;
* [ ] `/settag` отсутствует;
* [ ] `/tag` показывает только собственные tags;
* [ ] cases работают;
* [ ] items работают;
* [ ] duplicate dildo даёт компенсацию;
* [ ] silicone implant применяется автоматически;
* [ ] size работает;
* [ ] top size работает;
* [ ] disease работает;
* [ ] disease reconciliation работает;
* [ ] medicine работает;
* [ ] venereologist работает;
* [ ] condom работает;
* [ ] child mechanic работает;
* [ ] child support работает;
* [ ] child expiration работает;
* [ ] abortion работает;
* [ ] robbery работает;
* [ ] robbery cooldown сохраняется;
* [ ] normal RP стоит 10;
* [ ] 18+ RP стоит 50;
* [ ] 18+ cooldown работает;
* [ ] masturbation cooldown работает;
* [ ] moderation roles работают;
* [ ] moderation permissions работают;
* [ ] purge отсутствует;
* [ ] giveaways работают;
* [ ] duplicate giveaway join запрещён;
* [ ] automatic prizes работают;
* [ ] manual prizes работают;
* [ ] balance не становится отрицательным;
* [ ] double payout невозможен;
* [ ] repeated callbacks безопасны;
* [ ] existing functionality не сломана;
* [ ] бот переживает restart;
* [ ] SQLite работает;
* [ ] PostgreSQL compatibility сохранена;
* [ ] syntax checks пройдены;
* [ ] import checks пройдены;
* [ ] final UI pass завершён.

---

# 83. Главное правило финального релиза

Новые механики после прохождения основного аудита не добавляются без отдельной причины.

Порядок работы:

```text
functional audit
↓
transaction/idempotency fixes
↓
tests
↓
cosmetic/UI pass
↓
final verification
```
