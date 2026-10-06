  // Подробный отчёт: отправка возможна только по нажатию пользователя.
  var REPORT_CSS = __REPORT_CSS__;
  var REPORT_LEVELS = ["Низкий уровень", "Умеренный уровень", "Повышенный уровень", "Высокий уровень"];

  function reportSections() {
    var out = [];
    for (var i = 0; i < DATA.length; i++) {
      if (!visible(i)) continue;
      var score = sectionScore(i);
      if (score.answered) out.push({ idx: i, score: score, level: level(score.pct) });
    }
    return out;
  }

  function reportAnswer(v) {
    if (v === undefined) return { label: "Не отвечено", level: "none" };
    for (var i = 0; i < SCALE.length; i++)
      if (SCALE[i].v === v) return { label: SCALE[i].label, level: i };
    return { label: "Не отвечено", level: "none" };
  }

  function reportQuestions(si, sub, questions) {
    var html = "";
    for (var i = 0; i < questions.length; i++) {
      var answer = reportAnswer(state.answers[key(si, sub, i)]);
      html += '<div class="chk-report__q">';
      html += '<span class="chk-report__qnum">' + (i + 1) + '.</span>';
      html += '<span class="chk-report__qtext">' + esc(questions[i]) + '</span>';
      html += '<span class="chk-report__answer" data-level="' + answer.level + '">' + answer.label + '</span>';
      html += '</div>';
    }
    return html;
  }

  function reportSubsection(si, sub) {
    var item = DATA[si].s[sub], score = subScore(si, sub);
    var lv = score.answered ? level(score.pct) : "none";
    var label = score.answered ? REPORT_LEVELS[lv] : "Не заполнено";
    var html = '<div class="chk-report__subsection">';
    html += '<div class="chk-report__subhead">';
    html += '<span class="chk-report__subscore" data-level="' + lv + '">' + score.sum + '</span>';
    html += '<div><div class="chk-report__subname">' + esc(item.t) + '</div>';
    html += '<div class="chk-report__submeta"><span class="chk-report__status" data-level="' + lv + '">' + label + '</span>';
    html += score.sum + ' из ' + (score.answered * 8) + ' баллов';
    if (score.answered < score.total) html += ' · отвечено ' + score.answered + ' из ' + score.total;
    html += '</div></div></div>';
    if (item.n) html += '<p class="chk-report__subnote">' + esc(item.n) + '</p>';
    html += reportQuestions(si, sub, item.q);
    return html + '</div>';
  }

  function reportSection(row, open) {
    var si = row.idx, item = DATA[si], score = row.score, lv = row.level;
    var html = '<details class="chk-report__section"' + (open ? ' open' : '') + '>';
    html += '<summary><span class="chk-report__section-name">' + (si + 1) + '. ' + esc(item.t) + '</span>';
    html += '<span class="chk-report__section-score" data-level="' + lv + '">' + score.sum + ' / ' + (score.answered * 8) + '</span>';
    html += '<span class="chk-report__chevron" aria-hidden="true">▼</span></summary>';
    html += '<div class="chk-report__body">';
    if (score.answered < score.total)
      html += '<p class="chk-report__partial">Отвечено ' + score.answered + ' из ' + score.total + ' вопросов. Цвет считается по отвеченным.</p>';
    if (item.n) html += '<p class="chk-report__subnote">' + esc(item.n) + '</p>';
    if (item.q) html += reportQuestions(si, null, item.q);
    if (item.s) for (var j = 0; j < item.s.length; j++) html += reportSubsection(si, j);
    return html + '</div></details>';
  }

  function resultHtml(forFile) {
    var list = reportSections(), total = totals(), counts = [0, 0, 0, 0];
    for (var i = 0; i < list.length; i++) counts[list[i].level]++;
    var html = '<div class="chk-report">';
    html += '<div class="chk-report__brand">ALINA ECOSIN</div>';
    html += '<p class="chk-report__eyebrow">Чек-ап организма · Персональный отчёт</p>';
    html += '<div class="chk-report__intro"><h2>Ваш персональный чек-ап организма</h2>';
    html += '<p>Подробные результаты по системам организма: баллы, цветовые уровни и каждый ответ в одном файле.</p>';
    html += '<div class="chk-report__benefits">';
    html += '<div class="chk-report__benefit"><b>Подробный анализ</b>Разделы и подразделы</div>';
    html += '<div class="chk-report__benefit"><b>Цветовая карта</b>Уровни видны сразу</div>';
    html += '<div class="chk-report__benefit"><b>Полный отчёт</b>Все ответы по вопросам</div>';
    html += '</div></div>';
    html += '<div class="chk-report__meta">';
    html += '<div class="chk-report__meta-name">' + (state.name ? esc(state.name) : 'Без имени') + '</div>';
    var meta = [];
    if (state.born) meta.push('Дата рождения: ' + esc(state.born.split('-').reverse().join('.')));
    if (state.gender) meta.push('Пол: ' + (state.gender === 'female' ? 'женский' : 'мужской'));
    if (state.contact) meta.push('Контакт: ' + esc(state.contact));
    meta.push('Отвечено ' + total.answered + ' из ' + total.total);
    html += '<div class="chk-report__meta-detail">' + meta.join(' · ') + '</div></div>';

    html += '<h2 class="chk-report__heading">Краткая сводка</h2>';
    html += '<div class="chk-report__summary"><h3>Распределение заполненных разделов</h3>';
    html += '<div class="chk-report__stats">';
    var labels = ['В норме', 'Умеренно', 'Повышено', 'Высоко'];
    for (i = 0; i < 4; i++)
      html += '<div class="chk-report__stat" data-level="' + i + '"><b>' + counts[i] + '</b><span>' + labels[i] + '</span></div>';
    html += '</div>';
    var priority = list.filter(function (r) { return r.level >= 2; })
      .sort(function (a, b) { return b.score.pct - a.score.pct; }).slice(0, 3);
    if (priority.length) {
      html += '<div class="chk-report__priority"><b>Куда смотреть в первую очередь:</b> ';
      html += priority.map(function (r) { return esc(DATA[r.idx].t); }).join(', ') + '.</div>';
    } else {
      html += '<div class="chk-report__priority">По заполненным разделам нет повышенных уровней.</div>';
    }
    html += '</div>';

    html += '<h2 class="chk-report__heading">Результаты по системам</h2>';
    if (list.length) {
      html += '<div class="chk-report__toolbar">';
      html += '<button type="button" class="chk-report__tool" data-expand-all>Развернуть всё</button>';
      html += '<button type="button" class="chk-report__tool" data-collapse-all>Свернуть всё</button>';
      html += '<button type="button" class="chk-report__tool" data-print>Распечатать / PDF</button>';
      html += '</div>';
      for (i = 0; i < list.length; i++) html += reportSection(list[i], i === 0);
    } else {
      html += '<p class="chk-report__empty">Пока нет ответов. Вернитесь к анкете и заполните хотя бы один раздел.</p>';
    }

    html += '<div class="chk-report__legend">';
    for (i = 0; i < 4; i++)
      html += '<span data-level="' + i + '"><i aria-hidden="true"></i>' + REPORT_LEVELS[i] + '</span>';
    html += '</div>';
    html += '<p class="chk-report__note">Цвет показывает уровень по отвеченным вопросам. Этот отчёт не является диагнозом.</p>';
    html += '<div class="chk-report__next">';
    html += '<div class="chk-report__offer chk-report__offer--consult"><div class="chk-report__offer-text">';
    html += '<h3>Обсудить результат</h3><p>Алина разберёт анкету вместе с вами и поможет составить план дальнейших действий.</p></div>';
    html += '<a href="https://alinaecosin.ru/consultation.html" target="_blank" rel="noopener">О консультации →</a></div>';
    html += '<div class="chk-report__offer chk-report__offer--analizy"><div class="chk-report__offer-text">';
    html += '<h3>Какие анализы сдать</h3><p>Посмотрите подборки анализов по жалобам и подготовку к сдаче.</p></div>';
    html += '<a href="https://alinaecosin.ru/analizy.html" target="_blank" rel="noopener">К анализам →</a></div>';
    html += '</div>';
    if (!forFile) {
      html += '<div class="chk-report__send"><h3>Отправить результат Алине</h3>';
      html += '<p>После нажатия полный отчёт уйдёт в личный Telegram Алины. Укажите контакт, чтобы она могла вам ответить.</p>';
      html += '<div class="chk-report__send-fields">';
      html += '<label>Ваше имя<input type="text" data-send-name class="ym-disable-keys ym-hide-content" value="' + esc(state.name || '') + '" autocomplete="name"></label>';
      html += '<label>Telegram или телефон<input type="text" data-send-contact class="ym-disable-keys ym-hide-content" value="' + esc(state.contact || '') + '" autocomplete="off"></label>';
      html += '</div><button type="button" data-send>Отправить результат Алине</button>';
      html += '<p class="chk-report__send-status" data-send-status role="status" aria-live="polite"></p></div>';
      html += '<div class="chk-report__actions">';
      html += '<button type="button" data-download>Скачать полный отчёт</button>';
      html += '<button type="button" data-back>Вернуться к анкете</button></div>';
      html += '<p class="chk-report__note">Если отправка недоступна, сохраните файл и пришлите его Алине самостоятельно.</p>';
    }
    html += '<div class="chk-report__footer">Ecosin · Алина Сингизова</div></div>';
    return html;
  }

  function reportActions(box) {
    box.onclick = function (e) {
      var button = e.target.closest('button');
      if (!button || !box.contains(button)) return;
      if (button.hasAttribute('data-expand-all')) {
        box.querySelectorAll('.chk-report__section').forEach(function (d) { d.open = true; });
      } else if (button.hasAttribute('data-collapse-all')) {
        box.querySelectorAll('.chk-report__section').forEach(function (d) { d.open = false; });
      } else if (button.hasAttribute('data-print')) {
        box.querySelectorAll('.chk-report__section').forEach(function (d) { d.open = true; });
        window.print();
      } else if (button.hasAttribute('data-download')) {
        downloadResult();
      } else if (button.hasAttribute('data-send')) {
        sendResult(box, button);
      } else if (button.hasAttribute('data-back')) {
        state.done = false; save(); showForm(false);
        window.scrollTo({ top: root.offsetTop - 80, behavior: 'smooth' });
      }
    };
  }

  function showResults() {
    var box = $("[data-screen='results']");
    box.innerHTML = resultHtml(false);
    state.done = true;
    save();
    screen('results');
    window.scrollTo({ top: root.offsetTop - 80, behavior: 'smooth' });
    reportActions(box);
    if (typeof window.ecosinGoal === 'function') window.ecosinGoal('checkup_done');
  }

  function reportDocument() {
    var title = 'Функциональная анкета' + (state.name ? ' — ' + state.name : '');
    var behavior = '<script>document.addEventListener("click",function(e){' +
      'var b=e.target.closest("[data-expand-all],[data-collapse-all],[data-print]");if(!b)return;' +
      'var ds=document.querySelectorAll(".chk-report__section");' +
      'if(b.hasAttribute("data-expand-all"))ds.forEach(function(d){d.open=true});' +
      'if(b.hasAttribute("data-collapse-all"))ds.forEach(function(d){d.open=false});' +
      'if(b.hasAttribute("data-print")){ds.forEach(function(d){d.open=true});window.print()}' +
      '});</scr' + 'ipt>';
    return '<!doctype html><html lang="ru"><head><meta charset="utf-8">' +
      '<meta name="viewport" content="width=device-width,initial-scale=1">' +
      '<title>' + esc(title) + '</title><style>' + REPORT_CSS + '</style></head>' +
      '<body class="chk-report-file">' + resultHtml(true) + behavior + '</body></html>';
  }

  function downloadResult() {
    downloadFile(reportDocument(), fileName('Анкета', 'html'), 'text/html');
  }

  function sendResult(box, button) {
    var status = box.querySelector('[data-send-status]');
    var name = box.querySelector('[data-send-name]').value.trim();
    var contact = box.querySelector('[data-send-contact]').value.trim();
    if (!name || !contact) {
      status.textContent = 'Укажите имя и Telegram или телефон для связи.';
      return;
    }
    state.name = name; state.contact = contact; save();
    button.disabled = true;
    button.textContent = 'Отправляю…';
    status.textContent = 'Отправляю полный отчёт Алине…';
    var payload = JSON.stringify({ name: name, contact: contact, html: reportDocument() });
    function send(url) {
      return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: payload })
        .then(function (r) { return r.json().catch(function () { return { ok: false }; }); });
    }
    send('https://api.alinaecosin.ru/shop-api/checkup')
      .catch(function () { return send('https://alinaecosin.store/shop-api/checkup'); })
      .then(function (res) {
        if (res && res.ok) {
          button.textContent = 'Отправлено Алине';
          status.textContent = 'Готово: полный отчёт доставлен Алине в Telegram.';
          if (typeof window.ecosinGoal === 'function') window.ecosinGoal('checkup_sent');
        } else {
          button.disabled = false;
          button.textContent = 'Отправить результат Алине';
          status.textContent = 'Не удалось отправить отчёт. Сохраните файл и пришлите его Алине в Telegram.';
        }
      })
      .catch(function () {
        button.disabled = false;
        button.textContent = 'Отправить результат Алине';
        status.textContent = 'Нет связи с сервером. Сохраните файл и пришлите его Алине в Telegram.';
      });
  }
