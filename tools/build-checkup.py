# -*- coding: utf-8 -*-
"""Собирает src/partials/tail-checkup.html из src/data/checkup-questions.json.

Зачем отдельный шаг: вопросов 595, и держать их прямо в partial означало бы
править девяносто килобайт разметки руками. Здесь данные лежат отдельным
JSON, а скрипт вклеивает их в готовую обёртку с логикой.

Что делает по дороге:
  — снимает нумерацию и капслок с заголовков разделов;
  — разбирает заголовки с переносом строки на заголовок и пояснение;
  — экранирует </ внутри данных, иначе строка закрыла бы <script> раньше времени.

Запуск (из корня репозитория):

    python tools/build-checkup.py
    python tools/build.py          собрать сайт

Источник вопросов — репозиторий a6340374-stack/oprosnik, где анкета жила
отдельной страницей на github.io. Тексты вопросов перенесены дословно.
"""
import json, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "partials" / "tail-checkup.html"
SRC = ROOT / "src" / "data" / "checkup-questions.json"

raw = json.loads(SRC.read_text(encoding="utf-8"))


def split_title(t):
    """«Заголовок\n(пояснение)» → заголовок + пояснение отдельно."""
    parts = [p.strip() for p in t.split("\n") if p.strip()]
    return parts[0], " ".join(parts[1:])


def clean_section_title(t):
    """«1. ЖЕЛУДОЧНО-КИШЕЧНЫЙ ТРАКТ» → «Желудочно-кишечный тракт».

    Номер выводится отдельным элементом, а капслок на 22 строки подряд
    в вёрстке сайта смотрится криком.
    """
    t = re.sub(r"^\s*\d+\.\s*", "", t).strip()
    return t[:1].upper() + t[1:].lower()


sections = []
for sec in raw["sections"]:
    title, note = split_title(sec["title"])
    item = {"t": clean_section_title(title), "n": note}
    subs = []
    for sub in sec.get("subsections", []):
        st, sn = split_title(sub["title"])
        subs.append({
            "t": st,
            "n": sn,
            "q": [q["text"].strip() for q in sub["questions"]],
        })
    if subs:
        item["s"] = subs
    direct = [q["text"].strip() for q in sec.get("questions", [])]
    if direct:
        item["q"] = direct
    sections.append(item)

total = sum(
    len(s.get("q", [])) + sum(len(x["q"]) for x in s.get("s", []))
    for s in sections
)
assert total == 595, total
assert len(sections) == 22, len(sections)

data_js = json.dumps(sections, ensure_ascii=False, separators=(",", ":"))
# Внутри <script> последовательность </ закрыла бы тег раньше времени.
data_js = data_js.replace("</", "<\\/")

APP = r"""
<!-- ===== Функциональная анкета =====

     595 вопросов, 22 раздела. Всё считается в браузере: ни ответы, ни имя
     никуда не отправляются, серверной части у страницы нет вообще.

     Почему не перерисовываем страницу целиком на каждый клик: 595 вопросов
     по четыре кнопки — 2380 узлов. Открыт всегда один раздел, в разметке
     живут только его вопросы, а клик по ответу трогает ровно три места —
     кнопки своего вопроса, счётчик раздела и полосу сверху.

     Прогресс лежит в localStorage. Он переживает закрытие вкладки, но
     привязан к браузеру: на другом устройстве будет пусто, а Safari
     на iOS сам чистит такое хранилище примерно через неделю без заходов.
     Поэтому рядом есть черновик файлом — он переносится куда угодно. -->
<script>
(function () {
  "use strict";

  var root = document.querySelector("[data-checkup]");
  if (!root) return;

  var DATA = __DATA__;

  var SCALE = [
    { label: "Нет или редко", v: 0 },
    { label: "Иногда",        v: 1 },
    { label: "Часто",         v: 4 },
    { label: "Очень часто",   v: 8 }
  ];

  // Разделы, которые показываются по полу. Индексы с нуля: 20 — простата,
  // 21 — женская репродуктивная система.
  var ONLY_MALE = 20, ONLY_FEMALE = 21;

  var LS = "ecosin_checkup_v1";
  var DRAFT_VERSION = 1;

  var state = {
    name: "", born: "", gender: "",
    answers: {},   // "секция-подраздел-вопрос" → 0|1|4|8
    open: null,    // индекс открытого раздела
    started: false,
    done: false
  };

  // ─────────────────────────── хранилище ───────────────────────────

  function save() {
    try { localStorage.setItem(LS, JSON.stringify(state)); } catch (e) {}
  }

  function load() {
    var saved;
    try { saved = localStorage.getItem(LS); } catch (e) { return false; }
    if (!saved) return false;
    try {
      var parsed = JSON.parse(saved);
      if (!parsed || typeof parsed !== "object") return false;
      for (var k in state) if (parsed[k] !== undefined) state[k] = parsed[k];
      return true;
    } catch (e) { return false; }
  }

  function wipe() {
    try { localStorage.removeItem(LS); } catch (e) {}
  }

  // ──────────────────────────── подсчёт ────────────────────────────

  function visible(i) {
    if (i === ONLY_MALE) return state.gender === "male";
    if (i === ONLY_FEMALE) return state.gender === "female";
    return true;
  }

  function key(si, sub, qi) {
    return si + "-" + (sub === null ? "_" : sub) + "-" + qi;
  }

  // Плоский список вопросов раздела: и прямые, и разложенные по подразделам.
  function questionsOf(si) {
    var sec = DATA[si], out = [], j, k;
    if (sec.q) for (j = 0; j < sec.q.length; j++) out.push({ sub: null, qi: j, text: sec.q[j] });
    if (sec.s) for (j = 0; j < sec.s.length; j++)
      for (k = 0; k < sec.s[j].q.length; k++) out.push({ sub: j, qi: k, text: sec.s[j].q[k] });
    return out;
  }

  // Процент считаем от отвеченного, а не от всех вопросов раздела.
  // Иначе наполовину заполненный раздел всегда выглядит благополучным.
  function score(list) {
    var sum = 0, answered = 0;
    for (var i = 0; i < list.length; i++) {
      var v = state.answers[list[i].k];
      if (v !== undefined) { sum += v; answered++; }
    }
    return {
      sum: sum, answered: answered, total: list.length,
      pct: answered ? (sum / (answered * 8)) * 100 : 0
    };
  }

  function sectionScore(si) {
    var qs = questionsOf(si), list = [], i;
    for (i = 0; i < qs.length; i++) list.push({ k: key(si, qs[i].sub, qs[i].qi) });
    return score(list);
  }

  function subScore(si, sub) {
    var arr = DATA[si].s[sub].q, list = [], i;
    for (i = 0; i < arr.length; i++) list.push({ k: key(si, sub, i) });
    return score(list);
  }

  function totals() {
    var answered = 0, total = 0;
    for (var i = 0; i < DATA.length; i++) {
      if (!visible(i)) continue;
      var s = sectionScore(i);
      answered += s.answered; total += s.total;
    }
    return { answered: answered, total: total, pct: total ? (answered / total) * 100 : 0 };
  }

  function level(pct) {
    if (pct <= 25) return 0;
    if (pct <= 50) return 1;
    if (pct <= 75) return 2;
    return 3;
  }

  var VERDICT = ["В пределах нормы", "Умеренно", "Повышено", "Высоко"];

  // ──────────────────────────── вспомогательное ────────────────────

  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function plural(n, one, few, many) {
    var d10 = n % 10, d100 = n % 100;
    if (d10 === 1 && d100 !== 11) return one;
    if (d10 >= 2 && d10 <= 4 && (d100 < 12 || d100 > 14)) return few;
    return many;
  }

  function $(sel) { return root.querySelector(sel); }

  function screen(name) {
    var all = root.querySelectorAll("[data-screen]");
    for (var i = 0; i < all.length; i++)
      all[i].hidden = all[i].getAttribute("data-screen") !== name;
  }

  // ───────────────────────────── экран старта ───────────────────────

  function bindStart() {
    var genderBox = $("[data-gender]");
    var startBtn = $("[data-start]");
    var hint = $("[data-start-hint]");
    var nameInput = $("#chk-name");
    var bornInput = $("#chk-born");

    nameInput.value = state.name || "";
    bornInput.value = state.born || "";

    function syncGender() {
      var btns = genderBox.querySelectorAll("button");
      for (var i = 0; i < btns.length; i++)
        btns[i].setAttribute("aria-pressed", String(btns[i].getAttribute("data-val") === state.gender));
      startBtn.disabled = !state.gender;
      if (state.gender) {
        hint.innerHTML = "<b>Можно начинать.</b> Имя и дата рождения остаются в вашем браузере и нужны только для подписи файла с результатом.";
      }
    }

    genderBox.addEventListener("click", function (e) {
      var btn = e.target.closest("button[data-val]");
      if (!btn) return;
      state.gender = btn.getAttribute("data-val");
      save();
      syncGender();
    });

    nameInput.addEventListener("input", function () { state.name = nameInput.value; save(); });
    bornInput.addEventListener("input", function () { state.born = bornInput.value; save(); });

    startBtn.addEventListener("click", function () {
      if (!state.gender) return;
      state.started = true;
      save();
      showForm();
      window.scrollTo({ top: root.offsetTop - 80, behavior: "smooth" });
    });

    $("[data-load-draft]").addEventListener("click", importDraft);
    syncGender();
  }

  // ───────────────────────────── оглавление ─────────────────────────

  function sectionStateText(si) {
    var s = sectionScore(si);
    if (s.answered === 0) return { text: "не начат", full: "no" };
    if (s.answered === s.total) return { text: "готово", full: "yes" };
    return { text: s.answered + " из " + s.total, full: "no" };
  }

  function renderToc() {
    var html = "", i;
    for (i = 0; i < DATA.length; i++) {
      if (!visible(i)) continue;
      var st = sectionStateText(i);
      var isOpen = state.open === i;
      html += '<div class="chk-sec" data-sec="' + i + '" data-open="' + (isOpen ? "yes" : "no") + '">';
      html += '<button type="button" class="chk-sec-head" aria-expanded="' + (isOpen ? "true" : "false") +
              '" aria-controls="chk-body-' + i + '">';
      html += '<span class="chk-sec-num">' + (i + 1) + '</span>';
      html += '<span class="chk-sec-name">' + esc(DATA[i].t) + '</span>';
      html += '<span class="chk-sec-state" data-full="' + st.full + '">' + esc(st.text) + '</span>';
      html += '</button>';
      html += '<div class="chk-sec-body" id="chk-body-' + i + '"' + (isOpen ? "" : " hidden") + '></div>';
      html += '</div>';
    }
    $("[data-toc]").innerHTML = html;
    if (state.open !== null && visible(state.open)) fillSection(state.open);
  }

  // Вопросы рисуем только у открытого раздела.
  function fillSection(si) {
    var box = root.querySelector('[data-sec="' + si + '"] .chk-sec-body');
    if (!box) return;
    var sec = DATA[si], html = "", j, k;

    if (sec.n) html += '<p class="chk-subnote">' + esc(sec.n) + '</p>';

    if (sec.q) html += questionsHtml(si, null, sec.q, 1);

    if (sec.s) for (j = 0; j < sec.s.length; j++) {
      html += '<h3 class="chk-subtitle">' + esc(sec.s[j].t) + '</h3>';
      if (sec.s[j].n) html += '<p class="chk-subnote">' + esc(sec.s[j].n) + '</p>';
      html += questionsHtml(si, j, sec.s[j].q, 1);
    }

    html += '<div class="chk-sec-next">';
    html += '<button type="button" class="btn btn-primary" data-next="' + si + '">Следующий раздел <span class="arrow">→</span></button>';
    html += '<span class="chk-sec-left" data-sec-left="' + si + '"></span>';
    html += '</div>';

    box.innerHTML = html;
    updateSectionLeft(si);
  }

  function questionsHtml(si, sub, arr, startNum) {
    var html = "", i, j, k, cur;
    for (i = 0; i < arr.length; i++) {
      k = key(si, sub, i);
      cur = state.answers[k];
      html += '<div class="chk-q" data-k="' + k + '">';
      html += '<div class="chk-q-text"><span class="chk-q-num">' + (startNum + i) + '.</span><span>' + esc(arr[i]) + '</span></div>';
      html += '<div class="chk-opts">';
      for (j = 0; j < SCALE.length; j++) {
        html += '<button type="button" data-v="' + SCALE[j].v + '" aria-pressed="' +
                (cur === SCALE[j].v ? "true" : "false") + '">' + SCALE[j].label + '</button>';
      }
      html += '</div></div>';
    }
    return html;
  }

  function updateSectionLeft(si) {
    var el = root.querySelector('[data-sec-left="' + si + '"]');
    if (!el) return;
    var s = sectionScore(si);
    var left = s.total - s.answered;
    el.textContent = left === 0
      ? "Раздел заполнен"
      : "Осталось " + left + " " + plural(left, "вопрос", "вопроса", "вопросов");
  }

  function updateSectionState(si) {
    var el = root.querySelector('[data-sec="' + si + '"] .chk-sec-state');
    if (!el) return;
    var st = sectionStateText(si);
    el.textContent = st.text;
    el.setAttribute("data-full", st.full);
  }

  function updateBar() {
    var t = totals();
    $("[data-progress]").parentNode.style.setProperty("--done", t.pct.toFixed(1) + "%");
    $("[data-count]").innerHTML = "Отвечено <b>" + t.answered + "</b> из " + t.total;
    var left = t.total - t.answered;
    $("[data-left]").textContent = left === 0
      ? "Анкета заполнена полностью"
      : "Не отвечено на " + left + " " + plural(left, "вопрос", "вопроса", "вопросов");
  }

  function openSection(si) {
    var prev = state.open;
    state.open = (prev === si) ? null : si;
    save();

    if (prev !== null && prev !== si) {
      var pbox = root.querySelector('[data-sec="' + prev + '"]');
      if (pbox) {
        pbox.setAttribute("data-open", "no");
        pbox.querySelector(".chk-sec-head").setAttribute("aria-expanded", "false");
        var pbody = pbox.querySelector(".chk-sec-body");
        pbody.hidden = true;
        pbody.innerHTML = "";   // освобождаем разметку закрытого раздела
      }
    }

    var box = root.querySelector('[data-sec="' + si + '"]');
    if (!box) return;
    var open = state.open === si;
    box.setAttribute("data-open", open ? "yes" : "no");
    box.querySelector(".chk-sec-head").setAttribute("aria-expanded", open ? "true" : "false");
    var body = box.querySelector(".chk-sec-body");
    body.hidden = !open;
    if (open) fillSection(si); else body.innerHTML = "";
  }

  function nextSection(si) {
    var i, order = [];
    for (i = 0; i < DATA.length; i++) if (visible(i)) order.push(i);
    var pos = order.indexOf(si);
    // Сначала ищем следующий незаполненный, после конца — с начала.
    for (i = pos + 1; i < order.length; i++) {
      var s = sectionScore(order[i]);
      if (s.answered < s.total) return order[i];
    }
    for (i = 0; i < pos; i++) {
      var s2 = sectionScore(order[i]);
      if (s2.answered < s2.total) return order[i];
    }
    return null;
  }

  function bindForm() {
    var toc = $("[data-toc]");

    toc.addEventListener("click", function (e) {
      var head = e.target.closest(".chk-sec-head");
      if (head) {
        openSection(+head.parentNode.getAttribute("data-sec"));
        var box = head.parentNode;
        if (box.getAttribute("data-open") === "yes") {
          var top = box.getBoundingClientRect().top + window.pageYOffset - 110;
          window.scrollTo({ top: top, behavior: "smooth" });
        }
        return;
      }

      var next = e.target.closest("[data-next]");
      if (next) {
        var from = +next.getAttribute("data-next");
        var to = nextSection(from);
        if (to === null) {
          openSection(from);
          $("[data-finish]").scrollIntoView({ behavior: "smooth", block: "center" });
        } else {
          openSection(to);
          var el = root.querySelector('[data-sec="' + to + '"]');
          window.scrollTo({ top: el.getBoundingClientRect().top + window.pageYOffset - 110, behavior: "smooth" });
        }
        return;
      }

      var opt = e.target.closest(".chk-opts button");
      if (!opt) return;

      var q = opt.closest(".chk-q");
      var k = q.getAttribute("data-k");
      var v = +opt.getAttribute("data-v");
      // Повторный клик по выбранному варианту снимает ответ.
      if (state.answers[k] === v) delete state.answers[k];
      else state.answers[k] = v;

      var btns = q.querySelectorAll(".chk-opts button");
      for (var i = 0; i < btns.length; i++)
        btns[i].setAttribute("aria-pressed", String(state.answers[k] === +btns[i].getAttribute("data-v")));

      var si = +k.split("-")[0];
      updateSectionState(si);
      updateSectionLeft(si);
      updateBar();
      save();
    });

    $("[data-finish]").addEventListener("click", showResults);
    $("[data-save-draft]").addEventListener("click", exportDraft);
    $("[data-reset]").addEventListener("click", function () {
      if (!window.confirm("Стереть все ответы и начать заново? Отменить это будет нельзя.")) return;
      wipe();
      state.answers = {}; state.open = null; state.started = false; state.done = false;
      screen("start");
      bindStartValues();
      window.scrollTo({ top: root.offsetTop - 80, behavior: "smooth" });
    });
  }

  function bindStartValues() {
    $("#chk-name").value = state.name || "";
    $("#chk-born").value = state.born || "";
    var btns = $("[data-gender]").querySelectorAll("button");
    for (var i = 0; i < btns.length; i++)
      btns[i].setAttribute("aria-pressed", String(btns[i].getAttribute("data-val") === state.gender));
    $("[data-start]").disabled = !state.gender;
  }

  function showForm(restored) {
    screen("form");
    renderToc();
    updateBar();
    var box = $("[data-restored]");
    var t = totals();
    if (restored && t.answered > 0) {
      box.hidden = false;
      box.className = "chk-restored";
      box.innerHTML = "Продолжаем с того же места: заполнено <b>" + Math.round(t.pct) + "%</b>, " +
        t.answered + " " + plural(t.answered, "ответ", "ответа", "ответов") + " из " + t.total +
        ". Прогресс хранится в этом браузере — если будете продолжать с другого устройства, " +
        "сохраните черновик файлом.";
    } else {
      box.hidden = true;
    }
  }

  // ───────────────────────────── результат ──────────────────────────

  function rows() {
    var out = [], i;
    for (i = 0; i < DATA.length; i++) {
      if (!visible(i)) continue;
      var s = sectionScore(i);
      if (s.answered === 0) continue;
      var subs = [];
      if (DATA[i].s) for (var j = 0; j < DATA[i].s.length; j++) {
        var ss = subScore(i, j);
        if (ss.answered === 0) continue;
        subs.push({ title: DATA[i].s[j].t, pct: ss.pct, answered: ss.answered, total: ss.total });
      }
      out.push({
        idx: i, title: DATA[i].t, pct: s.pct,
        answered: s.answered, total: s.total, subs: subs
      });
    }
    return out;
  }

  function resultHtml(forFile) {
    var list = rows();
    var t = totals();
    var top = list.slice().filter(function (r) { return r.pct > 50; })
      .sort(function (a, b) { return b.pct - a.pct; }).slice(0, 5);

    var html = "";
    html += '<div class="chk-res-head"><h2>Что получилось</h2>';

    if (list.length === 0) {
      html += '<p class="chk-res-lede">Пока ни одного ответа. Вернитесь к анкете и заполните хотя бы один раздел.</p></div>';
      return html;
    }

    var lede;
    if (top.length === 0) {
      lede = "Ни по одной системе сигналы не выходят за умеренный уровень. Это не значит, что всё идеально, — это значит, что по вашим ответам явных провалов не видно.";
    } else {
      var names = top.map(function (r) { return r.title.toLowerCase(); });
      lede = "Больше всего сигналов — " + names.slice(0, 3).join(", ") +
             ". С этого и начнём разбор.";
    }
    html += '<p class="chk-res-lede">' + esc(lede) + '</p>';

    var whoBits = [];
    if (state.name) whoBits.push(esc(state.name));
    if (state.born) whoBits.push("дата рождения " + esc(state.born.split("-").reverse().join(".")));
    whoBits.push("отвечено " + t.answered + " из " + t.total + " " + plural(t.total, "вопроса", "вопросов", "вопросов"));
    html += '<p class="chk-res-who">' + whoBits.join(" · ") + "</p>";
    html += "</div>";

    if (top.length) {
      html += '<div class="chk-top"><h3>Куда смотреть в первую очередь</h3></div>';
      html += rowsHtml(top);
      html += '<div class="chk-top"><h3>Все разделы</h3></div>';
    }

    html += rowsHtml(list);

    if (!forFile) {
      var tg = "https://t.me/alina_ecosin";
      html += '<div class="chk-res-actions">';
      html += '<button type="button" class="btn btn-primary" data-download>Скачать результат файлом</button>';
      html += '<a class="btn btn-ghost" href="' + tg + '" target="_blank" rel="noopener">Написать Алине</a>';
      html += '<button type="button" class="btn btn-ghost" data-back>Вернуться к анкете</button>';
      html += "</div>";
      html += '<p class="chk-res-note">Файл сохраняется к вам на устройство — я его не получаю. Чтобы я увидела результат, пришлите файл в Telegram. ' +
              'Проценты считаются от тех вопросов, на которые вы ответили: незаполненные разделы в подсчёт не попадают и в этом списке не показаны.</p>';
    } else {
      html += '<p class="chk-res-note">Проценты считаются от отвеченных вопросов. Незаполненные разделы в список не попали. ' +
              'Это не диагноз и не заменяет обследование — это структурированный рассказ о самочувствии.</p>';
    }
    return html;
  }

  function rowsHtml(list) {
    var html = "", i, j;
    for (i = 0; i < list.length; i++) {
      var r = list[i], lv = level(r.pct);
      html += '<div class="chk-row">';
      html += '<div class="chk-row-top"><span class="chk-row-name">' + esc(r.title) + "</span>";
      html += '<span class="chk-row-verdict" data-level="' + lv + '">' + VERDICT[lv] + "</span></div>";
      html += '<div class="chk-row-line"><i data-level="' + lv + '" style="--v:' + r.pct.toFixed(1) + '%"></i></div>';
      html += '<div class="chk-row-sub">' + Math.round(r.pct) + "% · отвечено " + r.answered + " из " + r.total + "</div>";
      if (r.subs && r.subs.length > 1) {
        html += '<div class="chk-row-subs">';
        for (j = 0; j < r.subs.length; j++)
          html += "<span>" + esc(r.subs[j].title) + " <b>" + Math.round(r.subs[j].pct) + "%</b></span>";
        html += "</div>";
      }
      html += "</div>";
    }
    return html;
  }

  function showResults() {
    var box = $("[data-screen='results']");
    box.innerHTML = resultHtml(false);
    state.done = true;
    save();
    screen("results");
    window.scrollTo({ top: root.offsetTop - 80, behavior: "smooth" });

    var dl = box.querySelector("[data-download]");
    if (dl) dl.addEventListener("click", downloadResult);
    var back = box.querySelector("[data-back]");
    if (back) back.addEventListener("click", function () {
      state.done = false; save();
      showForm(false);
      window.scrollTo({ top: root.offsetTop - 80, behavior: "smooth" });
    });

    // Номер счётчика знает только metrika.html — здесь берём его помощник,
    // чтобы номер не размножался по файлам.
    if (typeof window.ecosinGoal === "function") window.ecosinGoal("checkup_done");
  }

  // Результат файлом: самодостаточный HTML со своими стилями, чтобы
  // открывался откуда угодно и печатался как есть.
  function downloadResult() {
    var css = [
      "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;",
      "max-width:760px;margin:40px auto;padding:0 20px;color:#2a2418;line-height:1.55;background:#faf6ed;}",
      "h2{font-size:28px;margin:0 0 6px;font-weight:600;}h3{font-size:19px;margin:34px 0 0;}",
      ".chk-res-lede{font-size:17px;color:#4d4538;margin:14px 0 0;}",
      ".chk-res-who{font-size:13px;color:#b9a682;margin:10px 0 0;}",
      ".chk-res-head{border-top:2px solid #2a2418;padding-top:18px;}",
      ".chk-top{border-top:1px solid #2a2418;padding-top:14px;margin-top:34px;}",
      ".chk-row{margin-top:20px;padding-top:14px;border-top:1px solid rgba(42,36,24,.18);}",
      ".chk-row-top{display:flex;justify-content:space-between;gap:14px;align-items:baseline;}",
      ".chk-row-name{font-size:17px;}",
      ".chk-row-verdict{font-size:11px;letter-spacing:.14em;text-transform:uppercase;white-space:nowrap;}",
      '.chk-row-verdict[data-level="0"]{color:#6f7e4a;}.chk-row-verdict[data-level="1"]{color:#b9a682;}',
      '.chk-row-verdict[data-level="2"]{color:#b86b4a;}.chk-row-verdict[data-level="3"]{color:#a8402a;}',
      ".chk-row-line{margin-top:9px;height:4px;background:#ede2cf;}",
      ".chk-row-line i{display:block;height:100%;}",
      '.chk-row-line i[data-level="0"]{background:#6f7e4a;}.chk-row-line i[data-level="1"]{background:#b9a682;}',
      '.chk-row-line i[data-level="2"]{background:#b86b4a;}.chk-row-line i[data-level="3"]{background:#a8402a;}',
      ".chk-row-sub{margin-top:7px;font-size:13px;color:#4d4538;}",
      ".chk-row-subs{margin-top:9px;display:grid;gap:4px;}",
      ".chk-row-subs span{display:flex;justify-content:space-between;gap:12px;font-size:13px;color:#4d4538;}",
      ".chk-res-note{margin-top:28px;font-size:13px;color:#4d4538;border-top:1px solid rgba(42,36,24,.18);padding-top:14px;}"
    ].join("");

    var title = "Функциональная анкета" + (state.name ? " — " + state.name : "");
    var doc = '<!doctype html><html lang="ru"><head><meta charset="utf-8">' +
      '<meta name="viewport" content="width=device-width,initial-scale=1">' +
      "<title>" + esc(title) + "</title><style>" + css + "</style></head><body>" +
      resultHtml(true) +
      "</body></html>";

    downloadFile(doc, fileName("Анкета", "html"), "text/html");
  }

  // ───────────────────────── черновик файлом ────────────────────────
  //
  // localStorage привязан к браузеру и на iOS протухает примерно
  // за неделю. Черновик переносится между устройствами и не протухает.

  function exportDraft() {
    var payload = {
      kind: "ecosin-checkup-draft",
      version: DRAFT_VERSION,
      saved: new Date().toISOString(),
      state: state
    };
    downloadFile(JSON.stringify(payload), fileName("Черновик-анкеты", "json"), "application/json");
  }

  function importDraft() {
    var input = document.createElement("input");
    input.type = "file";
    input.accept = ".json,application/json";
    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function () {
        var parsed;
        try { parsed = JSON.parse(String(reader.result)); } catch (e) { parsed = null; }
        if (!parsed || parsed.kind !== "ecosin-checkup-draft" || !parsed.state) {
          showFileError("Это не похоже на черновик анкеты. Нужен файл, который страница сохранила кнопкой «Сохранить черновик файлом».");
          return;
        }
        for (var k in state) if (parsed.state[k] !== undefined) state[k] = parsed.state[k];
        state.done = false;
        save();
        bindStartValues();
        if (state.gender) { state.started = true; save(); showForm(true); }
      };
      reader.readAsText(file);
    });
    input.click();
  }

  function showFileError(text) {
    var hint = $("[data-start-hint]");
    if (hint) hint.innerHTML = "<b>Не получилось.</b> " + esc(text);
  }

  function fileName(prefix, ext) {
    var who = (state.name || "").replace(/[^\wа-яёА-ЯЁ\s-]/gi, "").trim().replace(/\s+/g, "_");
    var d = new Date();
    var stamp = d.getFullYear() + "-" +
      String(d.getMonth() + 1).padStart(2, "0") + "-" +
      String(d.getDate()).padStart(2, "0");
    return prefix + (who ? "_" + who : "") + "_" + stamp + "." + ext;
  }

  function downloadFile(text, name, mime) {
    var blob = new Blob([text], { type: mime + ";charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  // ─────────────────────────────── запуск ───────────────────────────

  var restored = load();

  bindStart();
  bindForm();

  if (state.started && state.gender) {
    if (state.done) {
      showForm(false);
      showResults();
    } else {
      showForm(restored);
    }
  } else {
    screen("start");
  }
})();
</script>
"""

APP = APP.replace("__DATA__", data_js)
OUT.write_text(APP.lstrip("\n"), encoding="utf-8")
print("записан", OUT)
print("вопросов:", total, "| разделов:", len(sections), "| размер:", OUT.stat().st_size, "байт")
