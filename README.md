# Nginx Technical Assessment

Цей README містить повний опис виконання практичного завдання: підготовка Ubuntu Server у VirtualBox, налаштування SSH, запуск Python application, встановлення та налаштування Nginx, балансування між двома екземплярами application, TLS, security headers, gzip, caching, rate limiting, JSON access logs, zero-downtime reload, тимчасове виведення backend з ротації та перевірка Docker Compose-версії.

Наведені нижче кроки зберігають фактичну послідовність виконання роботи, використані команди, результати перевірок і проблеми, з якими довелося зіткнутися.

## Зміст

- [1. Підготовка середовища](#1-підготовка-середовища)
- [2. Налаштування SSH](#2-налаштування-ssh)
- [3. Тестовий Python-сервер](#3-тестовий-python-сервер)
- [4. Чому перевірка в PowerShell виконується у віртуальній машині](#4-чому-перевірка-в-powershell-виконується-у-віртуальній-машині)
- [Task 1.1 — Installation and service status](#task-11--installation-and-service-status)
- [Task 1.2 — Configuration validation](#task-12--configuration-validation)
- [Task 1.3 — Static content](#task-13--static-content)
- [Task 1.4 — Theory](#task-14--theory)
- [Task 2.1 — Deploy the application](#task-21--deploy-the-application)
- [Task 2.3 — Common production configuration](#task-23--common-production-configuration)
- [Task 2.4 — Zero-downtime operations](#task-24--zero-downtime-operations)

Спочатку поставив VirtualBox для Windows з сайту virtualbox.org. Брав пакет Windows hosts і встановив його як звичайну програму.
Потім завантажив образ Ubuntu Server 24.04.5 LTS з ubuntu.com. Файл з розширенням `.iso`.

## 1. Підготовка середовища

Створив віртуальну машину, підключив iso і пройшов встановлення. Задав користувача `yaroslav` і ім’я машини `nginx-lab`.

Система встановилась.

Після входу з’явилось запрошення:
```bash
yaroslav@nginx-lab:~$
```

Після входу в систему було оновлено інформацію про доступні пакети:
```bash
sudo apt update
```
Команда apt update оновлює локальну інформацію про доступні пакети та їхні версії.

Після цього було оновлено встановлені пакети:
```bash
sudo apt upgrade -y
```
Параметр -y автоматично підтверджує встановлення оновлень.

### Встановлення необхідних інструментів

Для виконання завдання були встановлені Python 3, Git та curl:
```bash
sudo apt install -y python3 git curl
```
Python необхідний для запуску demo application, Git — для подальшого збереження конфігурацій та результатів роботи, а curl використовується для перевірки HTTP-запитів та відповідей сервера.
Встановлену версію Python було перевірено командою:
```bash
python3 --version
```

### Створення директорії demo application

Згідно із завданням application має знаходитися за адресою:
/opt/demo-app/app.py
Для цього було створено директорію:
```bash
sudo mkdir -p /opt/demo-app
```
Параметр -p дозволяє створити необхідні батьківські директорії, якщо вони ще не існують.
Після виконання команда не вивела жодного повідомлення про помилку, що означало успішне виконання.
Для перевірки було використано:
```bash
ls -ld /opt/demo-app
```
Директорія була успішно створена.

### Створення Python application
Файл application було відкрито за допомогою текстового редактора nano:
```bash
sudo nano /opt/demo-app/app.py
```

### Проблема з вставленням коду з завдання в nano
Під час першої спроби вставити код у nano було використано:
Ctrl + V
Текст не вставився, а курсор продовжив блимати.

#### Що пробував

- увімкнув двонаправлений буфер обміну в налаштуваннях VirtualBox;
- пробував клавішу Insert;

Причина: галочки в налаштуваннях VirtualBox недостатньо. Спільний буфер працює через Guest Additions, а на Ubuntu Server їх немає. У чистому терміналі без робочого столу вставка з Windows у чорне вікно майже не заводиться.

Вставку вирішив робити через SSH. Вікно VirtualBox після цього лише тримає машину увімкненою, а команди набираються з Windows.

## 2. Налаштування SSH

У терміналі Ubuntu спочатку оновив список пакетів:
```bash
sudo apt update
```
Ця команда пройшла нормально, інтернет у віртуалці працював.

Спроба встановити SSH пройшла успішно:
```bash
sudo apt install -y openssh-server
```

Пакет встановлювати наново не довелося. Система відповіла, що `openssh-server` уже встановлений.

Перевірка статусу через sudo systemctl status ssh спочатку виглядала як поломка:

```bash
Active: inactive (dead)
```

На Ubuntu це не поломка. Служба часто спить і прокидається через сокет, коли хтось справді підключається. Щоб не залежати від цього режиму, увімкнув її явно:
```bash
sudo systemctl enable --now ssh
```
Після цього статус став `active (running)`.
Далі була друга перешкода. З ноутбука адреса `10.0.2.15` недоступна, бо це внутрішня адреса NAT, її бачить лише сама віртуалка. Тому в налаштуваннях мережі VirtualBox додав переадресацію портів:

- адаптер 1, тип підключення NAT;
- протокол TCP;
- ім’я правила `ssh`;
- порт хоста `2222`;
- порт гостя `22`;
- обидва поля IP залишив порожніми.

Підключення з PowerShell на Windows:
```bash
ssh yaroslav@127.0.0.1 -p 2222
```

На питання про ключ відповів `yes`, потім ввів той самий пароль, що й в Ubuntu.

Тут важливо, що означає адреса. `127.0.0.1` у команді `ssh` — це сам ноутбук. VirtualBox приймає порт 2222 на Windows і віддає його на порт 22 Ubuntu. Після пароля запрошення знову стає `yaroslav@nginx-lab:~$`, але вже у вікні PowerShell. З цього моменту команди виконуються всередині віртуальної машини. PowerShell лише показує цей екран.

## 3. Тестовий Python-сервер

Спочатку в SSH-сесії відкрив редактор:
```bash
nano app.py
```
Вставив код Ctrl+V, зберіг файл через Ctrl+O і Enter, вийшов через Ctrl+X. Після цього скрипт лежав у файлі app.py.
У тій самій сесії запустив сервер:
```bash
python3 app.py
```
Запрошення зникло, вікно залишилось без нового рядка. Так і має бути: процес працює і чекає запити. Це вікно не закривав і нічого в ньому більше не набирав.
Відкрив другий PowerShell і зайшов тією самою командою ssh yaroslav@127.0.0.1 -p 2222 і перевірив:
```bash
curl http://127.0.0.1:8080/api/health
```
Відповідь прийшла:
```bash
JSON{"status": "ok", "port": 8080}
```
Друга сесія сама сервер не запускає. Вона лише дає ще один термінал у ту саму машину, тому бачить процес, який уже працює в першому вікні. Зупинити сервер можна через Ctrl+C у першій сесії, тоді запрошення повертається.

## 4. Чому перевірка в PowerShell виконується у віртуальній машині

PowerShell відкритий на моєму комп’ютері, не всередині вікна VirtualBox. Але після `ssh yaroslav@127.0.0.1 -p 2222` і пароля це вікно вже не виконує команди Windows. Воно показує термінал Ubuntu.

Це видно по запрошенню:

- `yaroslav@nginx-lab:~$` — уже користувач `yaroslav` на машині `nginx-lab`.

Після перевірки Python-додатка наступним кроком мав бути Nginx, а не одразу до зламаного конфіга з PDF. Папки /etc/nginx ще немає, доки пакет не встановлений, тому пункт 2 зі стартового набору раніше за встановлення зробити не можна.
Сам початок був правильний. Віртуалка, SSH і додаток на порту 8080 не залежать від Nginx. У завданні цей файл якраз перший. Task 1.1 потрібен перед конфігом, а не замість додатка.
Порт 8080 — це внутрішні двері лише для Python. Перевірка curl http://127.0.0.1:8080/api/health стукала прямо в додаток, Nginx у цьому запиті не брав участі. Пізніше Nginx сяде на звичайні двері сайту, порт 80, і запити на /api/ буде пересилати вже цьому додатку.

У систему я входив як `yaroslav`, а завдання далі очікує теку /home/candidate/site. Тому створив окремого користувача:
```bash
sudo adduser --disabled-password --gecos "" candidate
--disabled-password означає, що цим користувачем не можна увійти за паролем. Він потрібен лише як власник теки. --gecos "" залишає порожніми поля з повним ім’ям і телефоном, щоб команда не зупинялась і не ставила питань. Вхід у систему лишається під yaroslav.
```

## Task 1.1 — Installation and service status

1. Nginx встановлено з офіційного складу авторів, а не з пакета Ubuntu.
   Спочатку підключив інструменти для складу: curl, gnupg2, ca-certificates, lsb-release, ubuntu-keyring. Потім завантажив ключ підпису:
```bash
   curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null
```
   Команда нічого не надрукувала: ключ записався у файл. Перевірка відбитка показала 573BFD6B3D8FBC641079A6ABABF5BD827BD9BF62, це ключ nginx.org.
   Підключив стабільний склад. Система сама підставила ім’я випуску noble:
```bash
   echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] https://nginx.org/packages/ubuntu $(lsb_release -cs) nginx" | sudo tee /etc/apt/sources.list.d/nginx.list
```
   Щоб Ubuntu не підмінила пакет своїм, задав пріоритет 900:
```bash
   printf '%s\n' 'Package: \*' 'Pin: origin nginx.org' 'Pin: release o=nginx' 'Pin-Priority: 900' | sudo tee /etc/apt/preferences.d/99nginx
```
   Після `sudo apt update` встановив пакет: `sudo apt install -y nginx`.
```bash
   apt-cache policy nginx показав пакети з https://nginx.org/packages/ubuntu noble/nginx з пріоритетом 900. Пакет Ubuntu з archive.ubuntu.com був нижче, з пріоритетом 500. Отже, стоїть збірка авторів.
```
   Різниця між пакетами. Пакет дистрибутива збирає Ubuntu: він часто старіший, модулі обирає дистрибутив, оновлення приходять разом зі звичайними оновленнями системи. Пакет nginx.org збирають автори Nginx: версія новіша, шляхи і модулі такі, як у їхній документації, оновлення приходять з їхнього складу. Пріоритет 900 потрібен, щоб наступний apt upgrade не замінив цей пакет пакетом Ubuntu.

2. Версія і модулі збірки
   Команди:
```bash
   nginx -v
   nginx -V
```
   `nginx -v` показав nginx version: nginx/1.30.5.
   `nginx -V` показав ту саму версію і параметри збірки. Бінарник зібраний gcc 13.3.0, з OpenSSL 3.0.13 від 30 січня 2024, підтримка TLS SNI увімкнена. У configure arguments є модулі http_ssl, http_v2, http_v3, http_realip, http_stub_status, http_gunzip, http_gzip_static, stream, stream_ssl, mail, а також file-aio і threads. З цієї ж рядка видно службові шляхи: конфіг /etc/nginx/nginx.conf, журнал помилок /var/log/nginx/error.log, журнал запитів /var/log/nginx/access.log.

3. Чи працює служба, чи вмикається сама, які процеси і порт
   Команди:
```bash
   systemctl is-active nginx
   systemctl is-enabled nginx
   sudo ss -tlnp | grep ':80'
   ps -o pid,user,cmd -C nginx
```
   is-active повернув active: служба зараз працює. is-enabled повернув enabled: після перезавантаження віртуалки вона увімкнеться сама.
   Одразу після встановлення було інакше. systemctl status nginx --no-pager показав Active: inactive (dead) поруч із enabled: автозапуск увімкнений, але процес тоді не працював. Запустив вручну sudo systemctl start nginx. Після цього статус став active (running).
```bash
   ss показав, що порт 80 слухається на всіх адресах: 0.0.0.0:80, програма nginx, процеси 1895, 1896 і 1897. Черга з’єднань 511.
   ps показав три процеси. Майстер 1895 запущений від root і читає /etc/nginx/nginx.conf. Два робочі процеси, 1896 і 1897, запущені від користувача nginx. Запити обробляють вони, не майстер.
```

4. Головний конфіг і журнали
   Команда:
```bash
   nginx -V 2>&1 | tr ' ' '\n' | grep -E 'conf-path|error-log-path|http-log-path'
```
   Вона вирізає шляхи з параметрів збірки. Результат:
```bash
   --conf-path=/etc/nginx/nginx.conf
   --error-log-path=/var/log/nginx/error.log
   --http-log-path=/var/log/nginx/access.log
```
   Головний конфіг — /etc/nginx/nginx.conf. Журнал помилок — /var/log/nginx/error.log. Журнал запитів — /var/log/nginx/access.log.

## Task 1.2 — Configuration validation

1. Тест конфіга і виправлення помилки в demo.conf
   Заводський сайт пакета nginx.org лежить у /etc/nginx/conf.d/default.conf і теж слухає порт 80. Перед перевіркою відсунув його, не видаляючи:
```bash
   sudo mv /etc/nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf.bak
   ls /etc/nginx/conf.d показав лише default.conf.bak.
```
   Зламаний конфіг із завдання записав у /etc/nginx/conf.d/demo.conf. Після root /home/candidate/site навмисно не було крапки з комою. wc -l показав 19 рядків.
   Перевірка:
```bash
   sudo nginx -t
```
   Результат:
```bash
   nginx: [emerg] invalid number of arguments in "root" directive in /etc/nginx/conf.d/demo.conf:10
   nginx: configuration file /etc/nginx/nginx.conf test failed
```
   Команда лише читає файли і не перезапускає службу. Помилка на рядку 10: немає ; після root /home/candidate/site. Nginx не побачив кінця директиви і приєднав до неї наступний рядок index index.html, тому написав «невірна кількість аргументів у root», а не «пропущена крапка з комою».
   Відкрив файл через sudo nano /etc/nginx/conf.d/demo.conf і додав крапку з комою. Інше не чіпав, зокрема порт 8081: це не синтаксична помилка, nginx -t на неї не скаржиться. Повторна перевірка:
```bash
   nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
   nginx: configuration file /etc/nginx/nginx.conf test is successful
```

2. Різниця між reload і restart
```bash
   nginx -s reload надсилає сигнал майстру: перечитай конфіг. Старі робочі процеси доробляють уже відкриті запити і закриваються, нові беруть наступні. З’єднання не обриваються. Сигнал іде повз systemd, тому на сервері це запасний варіант: служба може не побачити, що конфіг уже перечитано.
   systemctl reload nginx робить те саме, але через службу. Після успішного nginx -t застосував конфіг саме так. Для звичайної правки конфіга беру його.
   systemctl restart nginx зупиняє процеси і запускає їх знову. Уже відкриті з’єднання можуть обірватися. Потрібен, якщо змінювався сам пакет, ліміти служби або reload не підхопив зміну. Звичайну правку demo.conf ним не роблю.
```

3. Повний підсумковий конфіг однією командою
```bash
   sudo nginx -T
```
   Велика -T знову перевіряє конфіг і друкує його цілком, разом із файлами, які головний конфіг підключає. У виводі були /etc/nginx/nginx.conf і /etc/nginx/conf.d/demo.conf уже з рядком root /home/candidate/site;. Заводського default.conf не було: файл перейменований у default.conf.bak, а Nginx читає лише .conf.
   Після цього конфіг застосований без зупинки служби: sudo systemctl reload nginx.

## Task 1.3 — Static content

1. Потрібно, щоб http://demo.local/ віддав /home/candidate/site/index.html з кодом 200.
   Спочатку перевірив службу: systemctl is-active nginx повернув active.
   Створив теку і сторінку:
```bash
   sudo mkdir -p /home/candidate/site
   sudo tee /home/candidate/site/index.html > /dev/null << 'EOF'
```
   hello from demo.local
```bash
   EOF
```

Перевірка без sudo впала:
ls: cannot access '/home/candidate/site/index.html': Permission denied
Причину подивився від адміністратора: sudo ls -ld /home/candidate /home/candidate/site. У /home/candidate були права drwxr-x--- і власник candidate. Останні три прочерки означають, що іншим користувачам у теку заходити не можна. Я увійшов як yaroslav, тому ls і зупинився. Робочий процес Nginx теж іде не від candidate, а від користувача nginx, тож без правки він не зміг би прочитати файл.
Відкрив вхід у теки і читання файлу:
```bash
sudo chmod 755 /home/candidate /home/candidate/site
sudo chmod 644 /home/candidate/site/index.html
chmod змінює, кому можна заходити в теку і читати файл. Три цифри — це власник, його група і всі інші. 4 означає читати, 2 змінювати, 1 заходити в теку або запускати файл. 7 — це 4+2+1, можна все. 5 — це 4+1, читати і заходити, але не змінювати. 6 — це 4+2, читати і змінювати.
```
755 на теці: власник може все, група й інші можуть зайти і подивитися список файлів, але не можуть нічого записати. Для /home/candidate це якраз відкрило двері користувачу nginx. Раніше там було 750: остання цифра 0, іншим вхід закритий, тому ls і отримав Permission denied.
644 на файлі: власник може читати і змінювати, група й інші можуть лише читати. Запускати файл нікому не потрібно, це звичайна сторінка, тому остання цифра 4, не 5.
Після цього ls -l /home/candidate/site/index.html уже показав файл, права -rw-r--r--.
Ім’я сайту прописав на цю ж машину:
```bash
echo '127.0.0.1 demo.local' | sudo tee -a /etc/hosts
```
Перевірка:
```bash
curl -i http://demo.local/
```
Відповідь: HTTP/1.1 200 OK, нижче текст hello from demo.local. Сторінку віддав Nginx, Python у цьому запиті не брав участі.

## Task 1.4 — Theory

1. Майстер і робочі процеси
   Nginx тримає один майстер-процес і кілька робочих. Майстер читає конфіг, відкриває порт 80 і стежить за робочими. Самі запити обробляють робочі процеси.
   Це видно на скриншоті Task 1.1. Команди там вставлені одним блоком, серед них є ps -o pid,user,cmd -C nginx. Її вивід нижче, після таблиці ss:
```bash
   1895 root nginx: master process /usr/sbin/nginx -c /etc/nginx/nginx.conf
   1896 nginx nginx: worker process
   1897 nginx nginx: worker process
```
   1895 від root — майстер. 1896 і 1897 від користувача nginx — робочі. Поруч ss показав, що порт 80 тримають ці самі три процеси. Після перезавантаження номери процесів змінюються, написи master process і worker process лишаються.
```nginx
   worker_processes задає, скільки робочих процесів запустити. Значення auto зазвичай означає по одному на ядро процесора. worker_connections задає, скільки з’єднань може тримати один робочий процес. Груба стеля — кількість робочих, помножена на worker_connections, але її ще обмежує ліміт відкритих файлів системи.
```

2. Контексти конфіга
   Директиви лежать у вкладених блоках: main, далі events і http, усередині http блок server, усередині нього location. Що загальніше блок, то ширше діє директива. Вужчий блок може багато з них перевизначити.
   На цій машині це вже видно у файлах. Головний конфіг /etc/nginx/nginx.conf знайдений у Task 1.1 через nginx -V. Блок server і два блоки location лежать у /etc/nginx/conf.d/demo.conf, його додавали в Task 1.2. Повний зліпок із підключеними файлами тоді ж друкувала команда nginx -T.
   Не кожна директива успадковується. Частина взагалі дозволена лише у своєму контексті: worker_connections живе в events, server_name у server. Окрема пастка — add_header. Якщо в location написаний хоч один свій add_header, заголовки з server у цей location уже не успадковуються. Пастку add_header пізніше відтворив. У Task 2.3 заголовок X-Cache-Status стоїть у location = /api/health, тому HSTS і решту довелося повторити в цьому блоці. У Task 2.4 заголовок X-Reload-Test із server у відповіді /api/health не з’явився з тієї самої причини.

3. Як обирається блок server
   Спочатку Nginx дивиться, на який адрес і порт прийшов запит, і бере лише блоки server з таким listen. Серед них шукає server_name, який збігається із заголовком Host. Точне ім’я важливіше за маску, маска важливіша за регулярний вираз. Якщо нічого не збіглося, береться default server цього порту.
   У Task 1.2 у demo.conf записаний блок listen 80 і server_name demo.local. У Task 1.3 запит curl -i http://demo.local/ пішов на порт 80 з іменем demo.local і отримав 200 та index.html. Тобто вибраний був цей блок, а не заводський сайт: його ще в Task 1.2 перейменували в default.conf.bak.

4. Модифікатори location і порядок вибору
   = означає точний збіг шляху. ^~ означає звичайний префікс, який у разі збігу зупиняє перевірку регулярних виразів. ~ — регулярний вираз із урахуванням регістру. ~_ — регулярний вираз без урахування регістру. Без модифікатора це звичайний префікс.
   Порядок такий. Спочатку перевіряються точні =. Потім шукається найдовший префікс із ^~: якщо він знайшовся, регулярні вирази уже не дивляться. Інакше запам’ятовується найдовший звичайний префікс, а потім перевіряються ~ і ~_ у тому порядку, як вони записані в конфігу. Перший регулярний вираз, що збігся, перемагає. Якщо жоден не збігся, лишається той найдовший звичайний префікс.
   У demo.conf з Task 1.2 обидва блоки без модифікатора: location / і location /api/. Запит http://demo.local/ з Task 1.3 потрапив у location / і віддав файл. Шлях /api/health за цими правилами має потрапити в location /api/, бо цей префікс довший.

## Task 2.1 — Deploy the application

1. Додаток має працювати не з відкритого вікна, а як служба: від звичайного користувача і з підйомом після падіння. Потрібні два екземпляри, порти 8080 і 8082.
   Файл уже лежав на місці: /opt/demo-app/app.py, права -rwxr-xr-x.
   Створив дві служби. Перша:
```bash
   sudo tee /etc/systemd/system/demo-app-8080.service > /dev/null << 'EOF'
```
   [Unit]
   Description=Demo app on port 8080
   After=network.target

[Service]
User=candidate
Group=candidate
ExecStart=/usr/bin/python3 /opt/demo-app/app.py 8080
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
```bash
EOF
```
Друга така сама, файл /etc/systemd/system/demo-app-8082.service, у Description і ExecStart порт 8082.
User=candidate запускає процес не від root. Restart=on-failure піднімає його знову, якщо він упав. WantedBy=multi-user.target вмикає автозапуск після завантаження віртуалки.
Systemd перечитав нові файли і одразу запустив обидві служби:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now demo-app-8080 demo-app-8082
```
У відповіді були два рядки Created symlink: автозапуск увімкнений.
Перевірка:
```bash
systemctl is-active demo-app-8080 demo-app-8082
curl -s http://127.0.0.1:8080/api/health
curl -s http://127.0.0.1:8082/api/health
```
Результат:
```bash
active
active
{"status": "ok", "port": 8080}
{"status": "ok", "port": 8082}
```

2.  Балансування через demo_backend
    Два екземпляри вже працювали на 8080 і 8082. У Nginx до цього був старий upstream на 127.0.0.1:8081, там ніхто не слухав. Замінив блок у /etc/nginx/conf.d/demo.conf:
```nginx
    upstream demo_backend {
```
    least_conn;
    keepalive 16;
```nginx
    server 127.0.0.1:8080 max_fails=2 fail_timeout=10s;
    server 127.0.0.1:8082 max_fails=2 fail_timeout=10s;
    }
```
    least_conn віддає запит туди, де зараз менше відкритих з’єднань. max_fails=2 і fail_timeout=10s — пасивна перевірка: два невдалі звернення, і цей порт на 10 секунд вибуває.
    Слеша в кінці `proxy_pass` прибрав. З ним Nginx відрізає префікс /api/, і додаток шукав би /health, якого в нього немає.

3.  Keepalive
    У upstream стоїть keepalive 16: Nginx тримає до 16 готових з’єднань до додатків, щоб не відкривати нове на кожен запит.
    Цього рядка мало. У location /api/ додані:
```nginx
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_http_version 1.1 вмикає протокол, який вміє не закривати з’єднання. proxy_set_header Connection "" прибирає заголовок close. Без цих двох клієнт просить закрити з’єднання, і запас не використовується.
```

4.  Доказ
    Перевірка і застосування:
```bash
    sudo nginx -t
    sudo systemctl reload nginx
    nginx -t дав syntax is ok і test is successful. Reload пройшов без виводу.
```
    Десять запитів уже через Nginx:
```bash
    for i in $(seq 1 10); do curl -s http://demo.local/api/health; echo; done
```
    У відповідях були і "port": 8080, і "port": 8082. Одна адреса `demo.local`, відповідають різні екземпляри.

## Task 2.3 — Common production configuration

1.  Потрібен захищений сайт: самопідписаний сертифікат, лише TLS 1.2 і 1.3, перехід зі звичайної адреси на захищену кодом 301, заголовок HSTS і HTTP/2.
    Сертифікат зробив на самій віртуалці, без зовнішнього центру. Пара живе рік і виписана на ім’я demo.local:
```bash
    sudo mkdir -p /etc/nginx/ssl
    sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
```
     -keyout /etc/nginx/ssl/demo.local.key \
     -out /etc/nginx/ssl/demo.local.crt \
     -subj "/CN=demo.local"
```bash
    mkdir створює теку для ключів. openssl req -x509 одразу виписує самопідписаний сертифікат, без запиту в центр. -nodes лишає ключ без пароля, інакше Nginx не зміг би прочитати його під час старту. -newkey rsa:2048 створює ключ. -subj "/CN=demo.local" підставляє ім’я сайту, щоб команда не зупинялась і не ставила питань. У звіті лише команда: сам файл ключа в репозиторій не кладу.
```
    Порт 80 більше не віддає сторінку. Окремий блок лише перенаправляє:
```nginx
    server {
    listen 80;
```
    server_name demo.local;
    return 301 https://$host$request_uri;
```nginx
    }
```
    301 означає постійний переїзд. $host бере ім’я з запиту, $request_uri лишає шлях, тож http://demo.local/api/health стане https://demo.local/api/health, а не просто коренем сайту.
    Сам сайт переїхав на 443:
```nginx
    server {
    listen 443 ssl;
```
    http2 on;
    server_name demo.local;

```nginx
        ssl_certificate /etc/nginx/ssl/demo.local.crt;
        ssl_certificate_key /etc/nginx/ssl/demo.local.key;
        ssl_protocols TLSv1.2 TLSv1.3;
```

```nginx
        add_header Strict-Transport-Security "max-age=31536000" always;
```

```nginx
    }
    listen 443 ssl вмикає шифрування. http2 on вмикає HTTP/2 на цьому порту. ssl_certificate і ssl_certificate_key вказують пару файлів. ssl_protocols лишає лише TLS 1.2 і 1.3, старіші версії клієнт не зможе домовитися про старішу версію. Strict-Transport-Security просить браузер рік ходити на цей сайт одразу по HTTPS, навіть якщо посилання було звичайним. always додає заголовок і на відповіді з помилкою, не лише на 200.
```
    Решту конфіга переніс у блок 443 без змін: два порти додатків, заголовки клієнта, ліміт 10 МБ лише для /api/upload, таймаут 120 с лише для /api/slow, свій JSON замість HTML на 502.
    Перевірка і застосування: sudo nginx -t дав syntax is ok і test is successful, далі sudo systemctl reload nginx.
    Звичайний адрес:
```bash
    curl -si http://demo.local/ | head -n 8
```
    Відповідь: HTTP/1.1 301 Moved Permanently і Location: https://demo.local/. Сторінка по порту 80 більше не віддається.
    Захищений адрес:
```bash
    curl -ski https://demo.local/ | head -n 12
```
    Відповідь: HTTP/2 200, заголовок strict-transport-security: max-age=31536000 і текст hello from demo.local. Прапорець -k потрібен, бо сертифікат самопідписаний: curl і браузер йому не довіряють, центру підпису немає. Для стенда це нормально.

2.  Версію сховав директивою server_tokens off у блоці server на порту 443. Після reload рядок став server: nginx, без /1.30.5.
    Поруч із уже наявним HSTS додав:
```nginx
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Content-Security-Policy "default-src 'self'" always;
```
    nosniff забороняє браузеру вгадувати тип файлу. DENY забороняє вставляти сайт у фрейм на чужій сторінці. default-src 'self' дозволяє вантажити ресурси лише зі своєї адреси. always додає заголовок і на відповіді з помилкою, не лише на 200.
    Пастка add_header: якщо в location написаний хоч один свій add_header, заголовки з server у цей шлях уже не успадковуються. Тому ці чотири рядки стоять у server, а не в окремому location. Інакше, наприклад, шлях /api/ міг би втратити HSTS.
    Перевірка: curl -ski https://demo.local/ дав HTTP/2 200, server: nginx і всі чотири заголовки.

3.  Потрібно стискати текст, JSON, JS і CSS, але не чіпати зовсім короткі відповіді: на них стиснення лише витрачає час процесора і майже не зменшує розмір.
    У блоці server на порту 443, поруч із server_tokens off, додав:
```nginx
    gzip on;
    gzip_min_length 256;
    gzip_types text/plain text/css text/javascript application/javascript application/json image/svg+xml;
    gzip_vary on;
    gzip on вмикає стиснення відповіді перед відправкою клієнту. text/html Nginx стискає сам, щойно gzip увімкнений, тому в списку його немає. JSON, CSS, JS і SVG самі в цей список не входять, їх треба назвати в gzip_types. Картинки JPEG і PNG уже стиснуті своїм форматом, їх сюди не клав.
    gzip_min_length 256 ставить поріг у байтах. Відповідь коротша за 256 байт іде як є. gzip_vary on додає заголовок Vary: Accept-Encoding. Так кеш не віддасть стиснуту відповідь клієнту, який gzip не вміє.
```
    Для перевірки сторінка index.html не годилась: у ній 22 байти, поріг вона не проходить. Створив довший файл стилів:
```bash
    sudo python3 -c 'open("/home/candidate/site/app.css","w").write("body{color:#222}\n"\*40)'
    ls -l показав 680 байт, це більше за 256. Після nginx -t і systemctl reload nginx зробив два запити.
```
    Коротка сторінка:
```bash
    curl -ski https://demo.local/ | head -n 12
```
    Відповідь HTTP/2 200, content-length: 22, рядка content-encoding немає. Поріг спрацював.
    Файл стилів, клієнт сам каже, що вміє gzip:
```bash
    curl -ski -H "Accept-Encoding: gzip" https://demo.local/app.css | head -n 12
```
    Відповідь HTTP/2 200, content-type: text/css, vary: Accept-Encoding і content-encoding: gzip. Тип у списку, розмір більший за поріг, клієнт погодився на стиснення, тому Nginx стиснув.

4.  CSS, JS і картинки можна тримати 30 днів. index.html не можна: інакше браузер не побачить нову сторінку.
    Заголовок кешу ставить expires, не add_header. Свій add_header усередині location стер би HSTS і решту заголовків із блока server.
    Перед location / додав:
```nginx
    location = /index.html {
    expires -1;
    }
```

```nginx
location ~_ \.(css|js|png|jpg|jpeg|gif|svg|ico|webp)$ {
expires 30d;
}
expires -1 для сторінки означає не кешувати. expires 30d для файлів за розширенням ставить строк 30 днів. ~_ порівнює без урахування регістру, тож ловить і .CSS, і .css.
```
Після nginx -t і reload curl -ski https://demo.local/index.html показав cache-control: no-cache. curl -ski https://demo.local/app.css показав cache-control: max-age=2592000 і expires на 4 листопада. Поруч на обох відповідях лишилися strict-transport-security і решта заголовків безпеки.

5.  Потрібно обмежити /api/: не більше 10 запитів на секунду з однієї адреси, запас 20 понад цю норму. Коли запас закінчується, відповідь має бути 429, а не заводська сторінка 503.
    Зону оголосив на самому початку /etc/nginx/conf.d/demo.conf, над upstream. Її не можна ховати всередині server: спочатку зона має існувати, і лише потім location може на неї послатися.
```nginx
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
```
$binary_remote_addr — адреса клієнта в короткому вигляді. На цьому стенді це 127.0.0.1, бо запити йдуть із самої віртуалки. zone=api_limit:10m дає зоні ім’я і 10 МБ пам’яті на таблицю адрес. rate=10r/s — середня норма, десять запитів на секунду.
    Саме обмеження стоїть у трьох місцях: у location /api/, у location = /api/upload і в location = /api/slow.
```nginx
    limit_req zone=api_limit burst=20 nodelay;
    limit_req_status 429;
```
    Точний шлях не бере директиви із сусіднього блока. Якби рядки були лише в location /api/, завантаження і повільний запит лишилися б без ліміту. burst=20 дозволяє ще 20 запитів понад норму, короткою чергою. nodelay віддає цей запас одразу, без штучної паузи між запитами. limit_req_status 429 міняє код відмови: без цього рядка Nginx відповів би 503.
    Після nginx -t і systemctl reload nginx прогнав сорок запитів:
```bash
    for i in $(seq 1 40); do curl -sk -o /dev/null -w "%{http_code}\n" https://demo.local/api/health; done
```
    -o /dev/null ховає тіло, -w друкує лише код. Спочатку йшли 200: десять за нормою плюс запас 20. Далі пішли 429. Окремі 200 серед 429 теж очікувані: поки цикл ще триває, норма 10 запитів на секунду встигає пропустити ще кілька.

6.  Шлях /api/headers показує заголовки, які дійшли до додатка, зокрема адресу клієнта. Його не можна лишати відкритим для всіх. Завдання дозволяє два входи: з самої машини, адреса 127.0.0.1, або за паролем. Достатньо однієї умови.
    Спочатку файл пароля. Команда htpasswd лежить у пакеті apache2-utils:
```bash
    sudo apt install -y apache2-utils
    sudo htpasswd -bc /etc/nginx/.htpasswd-api demo Secret123
```
    -c створює файл. demo — ім’я, Secret123 — пароль цього стенда. У файлі лежить не сам пароль, а його хеш. У звіт і в репозиторій файл не кладу, лише команду.
    Далі окремий блок у /etc/nginx/conf.d/demo.conf, перед location /api/. Точний шлях не бере рядки із сусіднього блока, тому проксі і ліміт повторені.
```nginx
    location = /api/headers {
    satisfy any;
    allow 127.0.0.1;
    deny all;
    auth_basic "api headers";
    auth_basic_user_file /etc/nginx/.htpasswd-api;
```

```nginx
        limit_req zone=api_limit burst=20 nodelay;
        limit_req_status 429;
```

```nginx
        proxy_pass http://demo_backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
```

```nginx
    }
    satisfy any означає: досить одного виконаного правила. allow 127.0.0.1 разом із deny all пускає лише локальну адресу. auth_basic просить пароль, якщо адреса чужа. auth_basic_user_file читає файл, створений вище. Ліміт 10 запитів на секунду лишився і тут, інакше цей точний шлях обходив би пункт 5.
```
    Після nginx -t і systemctl reload nginx три перевірки.
    З самої машини, без пароля. Запит іде на 127.0.0.1, його пускає allow:
```bash
    curl -ski https://demo.local/api/headers | head -n 12
```
    Відповідь HTTP/2 200 і JSON з Host: demo.local та X-Real-IP: 127.0.0.1.
    Чужа адреса, без пароля. --interface 10.0.2.15 бере мережеву адресу віртуалки, не локальну:
```bash
    curl -ski --interface 10.0.2.15 https://demo.local/api/headers | head -n 8
```
    Відповідь HTTP/2 401 і заголовок www-authenticate: Basic realm="api headers". Без пароля Nginx далі не пускає.
    Та сама чужа адреса, уже з паролем:
```bash
    curl -ski --interface 10.0.2.15 -u demo:Secret123 https://demo.local/api/headers | head -n 8
```
    Знову HTTP/2 200. Спрацювало одне з двох: своя адреса або пароль.

7.  Потрібен журнал запитів у JSON. У кожному рядку мають бути час запиту, час відповіді додатка, адреса додатка і код відповіді. Поруч ротація, щоб файл не ріс без кінця.
    Формат оголосив на початку /etc/nginx/conf.d/demo.conf, над limit_req_zone. Усередині server його оголошувати не можна.
```nginx
    log_format demo_json escape=json
    '{'
    '"time":"$time_iso8601",'
        '"status":$status,'
    '"request_time":$request_time,'
        '"upstream_response_time":"$upstream_response_time",'
    '"upstream_addr":"$upstream_addr",'
        '"request":"$request",'
    '"remote_addr":"$remote_addr"'
    '}';
```
    escape=json сам екранує лапки всередині значень. $request_time — скільки секунд зайняв увесь запит. $upstream_response_time — скільки з них Nginx чекав додаток. $upstream_addr — який порт відповів. $status — код відповіді.
    У блоці listen 443 ssl додав окремий файл, заводський журнал не чіпав:
```nginx
    access_log /var/log/nginx/demo.json.log demo_json;
```
    Після nginx -t і reload зробив один запит і подивився кінець файлу:
```bash
    curl -sk -o /dev/null https://demo.local/api/health
    sudo tail -n 1 /var/log/nginx/demo.json.log
```
    Рядок містив "status":200, "request_time":0.002, "upstream_response_time":"0.002" і "upstream_addr":"127.0.0.1:8080".
    Ротацію окремо не писав. Пакет уже має /etc/logrotate.d/nginx: шаблон /var/log/nginx/\*.log накриває і новий файл. daily міняє файл раз на день, rotate 52 тримає 52 архіви, compress стискає старі. У postrotate сигнал USR1 каже Nginx відкрити новий файл, інакше він писав би в уже перейменований.

8.  Відповідь GET /api/health треба тримати в кеші Nginx 10 секунд і показати клієнту, чи взята вона з кешу, чи Nginx щойно ходив у додаток.
    Зону оголосив на початку /etc/nginx/conf.d/demo.conf, поруч із форматом журналу. Усередині server її оголошувати не можна.
```nginx
    proxy_cache_path /var/cache/nginx/demo levels=1:2 keys_zone=health_cache:10m max_size=100m inactive=60s;
```
    /var/cache/nginx/demo — тека, куди лягають самі відповіді. Її створив окремо і віддав користувачу nginx:
```bash
    sudo mkdir -p /var/cache/nginx/demo
    sudo chown nginx:nginx /var/cache/nginx/demo
```
    Без цього робочий процес не зміг би туди писати. levels=1:2 розкладає файли по підтеках, щоб в одній теці їх не було занадто багато. keys_zone=health_cache:10m дає кешу ім’я і 10 МБ пам’яті на таблицю ключів. max_size=100m обмежує диск. inactive=60s викидає запис, до якого хвилину ніхто не звертався, навіть якщо 10 секунд свіжості ще не минули.
    Сам кеш увімкнув точним блоком location = /api/health. Він не бере рядки із сусіднього location /api/, тому проксі, заголовки клієнта і ліміт частоти повторені. Інакше цей шлях обійшов би пункт 5 і не передав би Host.
```nginx
    proxy_cache health_cache;
    proxy_cache_valid 200 10s;
    add_header X-Cache-Status $upstream_cache_status always;
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Content-Security-Policy "default-src 'self'" always;
    proxy_cache_valid 200 10s тримає лише успішну відповідь і лише 10 секунд. $upstream_cache_status показує, звідки вона взята: MISS означає, що в кеші порожньо і Nginx сходив у додаток, HIT означає, що віддав збережену копію. Це теж add_header. Один свій add_header у location стирає заголовки з server, тому HSTS і решту тут повторив. Інакше на /api/health вони зникли б.
```
    Перша перевірка заголовка не показала: правка ще не була збережена або не перечитана. Після повторного nginx -t і systemctl reload nginx два запити підряд:
```bash
    curl -ski https://demo.local/api/health | head -n 15
    curl -ski https://demo.local/api/health | head -n 15
```
    Перший запит дав `x-cache-status`: MISS і тіло з портом 8080: кеш був порожній, відповідь прийшла від додатка і збереглася. Другий запит одразу слідом дав x-cache-status: HIT: ті самі 10 секунд, у додаток Nginx уже не ходив. На обох відповідях лишилися strict-transport-security і решта заголовків безпеки.

## Task 2.4 — Zero-downtime operations

1. Конфіг застосував через systemctl reload nginx, не через restart. Reload просить майстер перечитати файли. Старі робочі процеси доробляють відкриті запити, нові беруть наступні. Restart процеси зупиняє, уже відкриті з’єднання можуть обірватися.
   Щоб було що застосовувати, у блок server додав add_header X-Reload-Test "ok" always. Під час reload гнав цикл із паузою 0,2 с, щоб не впертися в ліміт 10 запитів на секунду:
```bash
   for i in $(seq 1 40); do curl -sk -o /dev/null -w "%{http_code}\n" https://demo.local/api/health; sleep 0.2; done > /tmp/reload-loop.txt &
   sleep 1
   sudo systemctl reload nginx
```
   wait
```bash
   sort /tmp/reload-loop.txt | uniq -c
```
   Результат: 40 200. Кодів 000 немає, обривів не було. Заголовок X-Reload-Test у відповіді /api/health не з’явився: у цього location вже є свої add_header, і батьківські в цей шлях не успадковуються. Для пункту це не завадило, доказ — цикл.

2. Потрібно тимчасово прибрати один екземпляр із роздачі, не чіпаючи саме додаток. Зупинка служби systemctl stop тут не годиться: процес тоді справді вимкнеться. Потрібна правка лише в Nginx.
   У блоці upstream demo_backend до рядка порту 8082 додав параметр down:
```nginx
   server 127.0.0.1:8082 max_fails=2 fail_timeout=10s down;
```
   Рядок 8080 не змінював. down позначає сервер як постійно недоступний для нових запитів. З’єднання на нього Nginx більше не відкриває, пасивна перевірка max_fails тут уже ні до чого: порт вийнятий явно, а не після помилок. Служба demo-app-8082 при цьому лишається запущеною, systemctl is-active давав active.
   Перша спроба файл зламала. Рядок із down випадково потрапив у самий початок конфіга і злипся з proxy_cache_path. nginx -t відповів directive "server" has no opening "{" у першому рядку: директива server опинилася поза блоком. Reload зламаний файл не взяв, тож вісім однакових відповідей з портом 8080 нічого не доводили. Зайвий шматок із першого рядка прибрав, down лишив тільки всередині upstream. Після цього sudo nginx -T показав рядок server 127.0.0.1:8082 ... down уже в працюючому конфігу.
   Доказ знімав не з тіла відповіді, а з журналу. /api/health кешується на 10 секунд, швидкий цикл curl віддавав би одну й ту саму копію і ховав другий порт. Параметр на кшталт `?x=1` теж не підійшло: додаток порівнює шлях цілком, для нього це вже не /api/health, і він відповідав 404. Тому два, потім три запити рівно на /api/health з паузою 11 секунд, щоб кеш встиг протухнути, і tail файлу /var/log/nginx/demo.json.log.
   Поки стояв down, усі три рядки мали "status":200 і "upstream_addr":"127.0.0.1:8080". Порту 8082 серед них не було.
   Після доказу слово down прибрав, знову nginx -t і systemctl reload nginx. Наступні три рядки журналу вже з обома портами: перший 127.0.0.1:8082, два наступні 127.0.0.1:8080. Тобто порт повернувся в ротацію, додаток заради цього зупиняти не довелося.

3. Завдання дозволяє зібрати все рішення або в docker-compose.yml, або в роль Ansible. Взяв Compose: для цього стенда він коротший. Живу віртуалку не переносив. Поруч із нею зробив теку ~/nginx-lab, з якої те саме піднімається однією командою.
   У теці чотири частини. app/app.py — копія додатка. site/index.html — сторінка hello from demo.local. ssl/ — самопідписаний сертифікат на ім’я demo.local, команда та сама, що на віртуалці. nginx/demo.conf — конфіг для контейнера. Ключ у звіт не кладу.
   docker-compose.yml описує три сервіси. app8080 і app8082 беруть образ python:3.12-slim і запускають python /app/app.py зі своїм портом. nginx бере образ nginx:1.28, підключає конфіг, теку сайту і сертифікат. Зовні відкриті 8088 і 8443, не 80 і 443: на віртуалці ці порти вже займає встановлений Nginx, інакше контейнер не стартував би.
   Головна відмінність від стенда — адреси. На віртуалці додаток слухає 127.0.0.1, і Nginx ходить до нього по локальному порту. У Compose кожен сервіс у своєму контейнері, спільного 127.0.0.1 у них немає. Тому в upstream стоять імена сервісів:
   server app8080:8080 max_fails=2 fail_timeout=10s;
   server app8082:8082 max_fails=2 fail_timeout=10s;
   Compose сам підставляє ці імена в загальну мережу контейнерів.
   Перший запуск дав 502 і HTML-сторінку Nginx. Журнал показав причину: connect() failed (111: Connection refused) на 172.18.0.2:8080 і 172.18.0.3:8082. Nginx до контейнерів дійшов, але порт усередині був закритий: копія додатка, як і на віртуалці, слухала лише 127.0.0.1. Для сусіднього контейнера це чужа адреса.
   У копії ~/nginx-lab/app/app.py останній рядок замінив на ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever(). 0.0.0.0 означає слухати на всіх адресах контейнера. Файл на віртуалці, /opt/demo-app/app.py, не чіпав: там локальна адреса якраз правильна. Контейнери перестворив, інакше вони тримали старий процес:
```bash
   sudo docker compose up -d --force-recreate
   curl -ski https://127.0.0.1:8443/api/health
```
   Відповідь: HTTP/2 200, x-cache-status: MISS і {"status": "ok", "port": 8080}. Журнал app8080 показав GET /api/health з кодом 200, у журналі Nginx рядка Connection refused більше не було. Порожній вивід на попередніх спробах давав прапорець -s: він ховає і помилку, тому обрив виглядав як порожній екран.

Повний конфіг стенда — це /etc/nginx/conf.d/demo.conf: там завантаження до 10 МБ, повільний шлях на 120 секунд, пароль на /api/headers, свій JSON на 502 і JSON-журнал. Файл ~nginx/demo.conf коротший. Ним я перевірив, що упаковка взагалі піднімається: після виправлення адреси curl -ski https://127.0.0.1:8443/api/health дав HTTP/2 200 і порт додатка. Решта пунктів Level 2 доведена на віртуалці, не в контейнері.
