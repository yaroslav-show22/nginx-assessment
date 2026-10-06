#### Task 2.2 Troubleshooting

A. Симптом. curl -i http://demo.local/api/health не повертав JSON додатка.
Діагноз. Прямі запити на 127.0.0.1:8080 і :8082 давали 200 і "port". У стартовому demo.conf upstream дивився на 127.0.0.1:8081, там ніхто не слухав. У proxy_pass http://demo_backend/ в кінці був слеш: Nginx відрізав /api/, додаток отримував /health і відповідав 404.
Причина. Невірний порт і слеш у proxy_pass.
Виправлення. У upstream порти 8080 і 8082. proxy_pass http://demo_backend без слеша. Після nginx -t і reload десять запитів дали 200 і обидва порти. (Скріншот є з таски 2.1)

B. Заголовки
Симптом. curl -s http://demo.local/api/headers показував Host як demo_backend. Заголовків X-Real-IP, X-Forwarded-For і X-Forwarded-Proto не було.
Діагноз. Додаток лише повертає те, що до нього дійшло. Nginx без proxy_set_header підставляє ім’я upstream і не додає клієнтські заголовки.
Причина. У location /api/ не було передачі Host, адреси клієнта і схеми.
Виправлення. Додані чотири директиви: Host $host, X-Real-IP $remote_addr, X-Forwarded-For $proxy_add_x_forwarded_for, X-Forwarded-Proto $scheme. Після nginx -t і reload у JSON є demo.local, 127.0.0.1 і http.

С. Завантаження 5 МБ
Симптом. POST файлу на 5 МБ у /api/upload повернув 413 Request Entity Too Large і HTML-сторінку Nginx.
Діагноз. Файл створений командою head -c 5M /dev/urandom > f.bin, ls -l показав 5242880 байт. Відповідь прийшла від Nginx, не від додатка. Заводська межа client_max_body_size — 1 МБ.
Причина. Ліміт за замовчуванням менший за файл. Піднімати його на весь сервер не можна: до 10 МБ дозволено тільки для /api/upload.
Виправлення. Окремий location = /api/upload з client_max_body_size 10m і тими самими proxy_set_header, бо з сусіднього location вони не переходять. Після nginx -t і reload той самий файл дав 200 і {"received_bytes": 5242880}.

D. Повільний запит
Симптом. curl -i http://demo.local/api/slow повернув 504 Gateway Time-out і HTML-сторінку Nginx приблизно за 60 с.
Діагноз. Додаток на /api/slow навмисно спить 90 с і потім відповідає. Відповідь 504 прийшла від Nginx, не від додатка. Заводський proxy_read_timeout — 60 с.
Причина. Час очікування проксі менший за час роботи додатка. Збільшувати його на весь сервер не можна.
Виправлення. Окремий location = /api/slow з proxy_read_timeout 120s і proxy_send_timeout 120s. Інші location лишилися на 60 с. Після nginx -t і reload той самий запит дав 200 і {"status": "finally"}.

E. Обидва додатки зупинені
Симптом. Після зупинки обох додатків curl -i http://demo.local/api/health повертав 502 Bad Gateway і заводську HTML-сторінку Nginx. У тілі були <html> і nginx, Content-Type був text/html.
Діагноз. Зупинив служби:
sudo systemctl stop demo-app-8080 demo-app-8082
curl -i http://demo.local/api/health
Обидві були inactive. Відповідь прийшла від Nginx, не від додатка: достукатися до портів 8080 і 8082 він не зміг.
Причина. Своєї сторінки для 502 не було, тому Nginx віддав вбудовану HTML-сторінку.
Виправлення. У location /api/ додав дві директиви:
proxy_intercept_errors on;
error_page 502 503 504 = @api_down;
proxy_intercept_errors каже не віддавати помилку upstream клієнту як є. error_page відправляє коди 502, 503 і 504 в окремий блок.
Після location /api/ додав:
location @api_down {
default_type application/json;
return 502 '{"error":"backend unavailable"}';
}
@api_down — внутрішня назва, зовні по ній не ходять. return 502 лишає код 502 і віддає JSON замість HTML.
Перша вставка через tee обірвалася: рядок EOF потрапив раніше блоку, і return лишився на екрані, а не у файлі. grep тоді не бачив api_down. Записав файл ще раз цілком. Перевірка показала рядки в конфігу:
error_page 502 503 504 = @api_down;
location @api_down {
return 502 '{"error":"backend unavailable"}';
sudo nginx -t дав syntax is ok і test is successful. Після sudo systemctl reload nginx повторив зупинку і запит:
sudo systemctl stop demo-app-8080 demo-app-8082
curl -i http://demo.local/api/health; echo
Відповідь: HTTP/1.1 502 Bad Gateway, Content-Type: application/json, тіло {"error":"backend unavailable"}. Тега <html> немає.
Після перевірки служби повернув:
sudo systemctl start demo-app-8080 demo-app-8082
curl -s http://demo.local/api/health; echo
Відповідь знову {"status": "ok", "port": 8080}.

F. Слеш у proxy_pass
Симптом. У стартовому конфігу було proxy_pass http://demo_backend/;. Потрібно показати, що змінює слеш у кінці, і підтвердити це запитом.
Діагноз. Спочатку слеш уже лежав у файлі в location /api/, але curl усе ще давав 200. nginx -t лише перевіряє файл, працюючий процес його не перечитує. Після sudo systemctl reload nginx той самий запит змінився.
Перевірка зі слешем:
curl -i http://demo.local/api/health; echo
Відповідь: HTTP/1.1 404 Not Found і тіло {"error": "not found", "path": "/health"}.
Причина. Слеш у proxy_pass http://demo_backend/; замінює частину location на те, що стоїть після слеша. Для location /api/ після слеша порожньо, тому префікс /api/ відрізається. Запит /api/health доходить до додатка як /health. Такого шляху в додатка немає, він відповідає 404.
Без слеша шлях передається як є. Повернув рядок на proxy_pass http://demo_backend;, знову nginx -t і systemctl reload nginx.
curl -i http://demo.local/api/health; echo
Відповідь: HTTP/1.1 200 OK і {"status": "ok", "port": 8080}. /api/health лишився /api/health.
Виправлення. У робочому конфігу залишений варіант без слеша. Зі слешем той самий запит дає 404 і шлях /health, без слеша дає 200 і порт додатка.
