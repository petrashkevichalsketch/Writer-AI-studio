/* ── Редактор результата стадии на /pipeline (кнопка ✏) ─────────
   Механика — по образцу карточек персонажей: структурная форма,
   сохранение в сырой слой world_bible через
   POST /api/pipeline/{stage}/edit (сервер строго валидирует).

   Правило видимости: кнопка появляется ТОЛЬКО на последней
   выполненной стадии и уходит на новую, как только следующая
   стадия становится done. Правка более ранней стадии блокируется
   сервером (409): данные не должны противоречить сгенерированному
   лору, который на них опирается.

   Формы строятся из декларативных схем SPECS: типы полей —
   text/area/int/float/bool/enum/list/idlist/intlist/floatlist/
   obj/objlist. Редактируется рабочая копия content_json целиком:
   поля, которых нет в схеме, сохраняются как были. ──────────── */
(function () {
  'use strict';

  /* ── Справочники перечислений (синхронизированы с validator.py) ── */
  const ENUM = {
    rel_type: ['ally', 'enemy', 'family', 'lover', 'rival', 'mentor', 'stranger'],
    inst_type: ['corporation', 'government', 'army', 'religion',
                'crime_syndicate', 'research_lab', 'resistance_movement'],
    event_type: ['discovery', 'institutionalization', 'first_failure', 'war',
                 'treaty', 'catastrophe', 'breakthrough', 'scandal',
                 'migration', 'revolution'],
    beat_key: ['opening_image', 'theme_stated', 'setup', 'catalyst', 'debate',
               'break_into_two', 'b_story', 'fun_and_games', 'midpoint',
               'bad_guys_close_in', 'all_is_lost', 'dark_night',
               'break_into_three', 'finale', 'final_image'],
  };

  const STAGE_TITLES = {
    world_core: 'Ядро мира',
    world_rules: 'Правила мира',
    history: 'История',
    institutions: 'Институции',
    geography: 'География',
    economy: 'Экономика',
    society: 'Общество',
    culture: 'Культура',
    conflicts: 'Конфликты',
    secrets: 'Секреты',
    characters: 'Персонажи',
    relations: 'Отношения',
    story_structure: 'Структура истории',
    chapter_outline: 'План глав',
  };

  /* ── Схемы форм стадий ────────────────────────────────────────
     Ключи = ключи content_json стадии. ro: true — только чтение
     (id и связи, на которых держатся другие стадии). ─────────── */
  const SPECS = {
    world_core: {
      fields: {
        central_concept: { t: 'obj', label: 'Центральная концепция', fields: {
          name: { t: 'text', label: 'Название (2–4 слова)' },
          one_line: { t: 'area', label: 'Суть одним предложением' },
        }},
        immutable_rules: { t: 'objlist', label: 'Неизменяемые правила', item: {
          id: { t: 'text', label: 'ID', ro: true },
          statement: { t: 'area', label: 'Правило' },
          may_change: { t: 'bool', label: 'Может изменяться' },
        }, title: it => it.statement || it.id },
        central_paradox: { t: 'area', label: 'Центральный парадокс' },
        core_question: { t: 'text', label: 'Главный вопрос книги (ровно один «?»)' },
        tone_tags: { t: 'list', label: 'Теги тональности' },
      },
    },

    world_rules: {
      fields: {
        physics: { t: 'obj', label: 'Физика мира', fields: {
          space_travel: { t: 'area', label: 'Перемещение' },
          time: { t: 'area', label: 'Время' },
          biology: { t: 'area', label: 'Биология' },
        }},
        technology: { t: 'obj', label: 'Технологии', fields: {
          energy: { t: 'area', label: 'Энергия' },
          transport: { t: 'area', label: 'Транспорт' },
          communication: { t: 'area', label: 'Связь' },
          medicine: { t: 'area', label: 'Медицина' },
          weapons: { t: 'area', label: 'Оружие' },
        }},
        constraints: { t: 'objlist', label: 'Ограничения', item: {
          id: { t: 'text', label: 'ID', ro: true },
          statement: { t: 'area', label: 'Ограничение' },
          implications: { t: 'list', label: 'Следствия' },
        }, title: it => it.statement || it.id },
        forbidden_techs: { t: 'list', label: 'Запрещённые технологии' },
      },
    },

    history: {
      fields: {
        timeline_start_year: { t: 'int', label: 'Начальный год таймлайна' },
        events: { t: 'objlist', label: 'События (10–20)', item: {
          id: { t: 'text', label: 'ID', ro: true },
          year: { t: 'int', label: 'Год' },
          type: { t: 'enum', label: 'Тип', options: ENUM.event_type },
          description: { t: 'area', label: 'Описание' },
          causes: { t: 'idlist', label: 'Причины (id событий)' },
          consequences: { t: 'idlist', label: 'Следствия (id событий)' },
          immutable: { t: 'bool', label: 'Неизменяемое' },
        }, title: it => it.description || it.id },
      },
    },

    institutions: {
      fields: {
        institutions: { t: 'objlist', label: 'Институции (5–6)', item: {
          id: { t: 'text', label: 'ID', ro: true },
          name: { t: 'text', label: 'Название' },
          type: { t: 'enum', label: 'Тип', options: ENUM.inst_type },
          public_role: { t: 'area', label: 'Публичная роль' },
          real_role: { t: 'area', label: 'Настоящая роль' },
          resources: { t: 'list', label: 'Ресурсы' },
          weaknesses: { t: 'list', label: 'Слабости' },
          goals: { t: 'list', label: 'Цели' },
          methods: { t: 'list', label: 'Методы' },
        }, title: it => it.name || it.id },
      },
    },

    geography: {
      fields: {
        locations: { t: 'objlist', label: 'Локации (5–8)', item: {
          id: { t: 'text', label: 'ID', ro: true },
          name: { t: 'text', label: 'Название' },
          type: { t: 'text', label: 'Тип' },
          traits: { t: 'list', label: 'Черты' },
          controlled_by: { t: 'idlist', label: 'Контролируют (id институций)' },
          connected_to: { t: 'objlist', label: 'Связи с локациями', item: {
            location: { t: 'text', label: 'ID локации' },
          }, title: it => it.location },
        }, title: it => it.name || it.id },
      },
    },

    economy: {
      fields: {
        currency: { t: 'text', label: 'Валюта' },
        major_resources: { t: 'list', label: 'Основные ресурсы (≥3)' },
        scarce_resources: { t: 'list', label: 'Дефицитные ресурсы (≥2)' },
        power_centers: { t: 'idlist', label: 'Центры силы (id институций)' },
        wealth_distribution: { t: 'area', label: 'Распределение богатства' },
        black_markets: { t: 'list', label: 'Чёрные рынки' },
      },
    },

    society: {
      fields: {
        society: { t: 'obj', label: 'Общество', fields: {
          class_structure: { t: 'list', label: 'Классовая структура' },
          family_structure: { t: 'list', label: 'Формы семьи' },
          education: { t: 'obj', label: 'Образование', fields: {
            'кто_учит': { t: 'area', label: 'Кто учит' },
            'чему_учат': { t: 'area', label: 'Чему учат' },
            'доступ': { t: 'area', label: 'Доступ' },
          }},
          work: { t: 'obj', label: 'Труд', fields: {
            'типичная_занятость': { t: 'area', label: 'Типичная занятость' },
            'безработица': { t: 'area', label: 'Безработица' },
          }},
          crime: { t: 'obj', label: 'Преступность', fields: {
            'главные_виды': { t: 'list', label: 'Главные виды' },
            'наказание': { t: 'area', label: 'Наказание' },
          }},
          healthcare: { t: 'obj', label: 'Здравоохранение', fields: {
            'доступ': { t: 'area', label: 'Доступ' },
            'типичные_болезни': { t: 'list', label: 'Типичные болезни' },
          }},
          entertainment: { t: 'list', label: 'Развлечения' },
          social_norms: { t: 'list', label: 'Социальные нормы' },
          taboos: { t: 'list', label: 'Табу' },
          status_symbols: { t: 'list', label: 'Символы статуса' },
          common_fears: { t: 'list', label: 'Общие страхи' },
          common_desires: { t: 'list', label: 'Общие желания' },
        }},
      },
    },

    culture: {
      fields: {
        culture: { t: 'obj', label: 'Культура', fields: {
          values: { t: 'list', label: 'Ценности' },
          religions: { t: 'list', label: 'Религии' },
          philosophies: { t: 'list', label: 'Философии' },
          art: { t: 'list', label: 'Искусство' },
          fashion: { t: 'list', label: 'Мода' },
          language_changes: { t: 'list', label: 'Изменения языка' },
          customs: { t: 'list', label: 'Обычаи' },
          holidays: { t: 'list', label: 'Праздники (макс 3)' },
          popular_myths: { t: 'list', label: 'Популярные мифы (≥3)' },
        }},
      },
    },

    conflicts: {
      fields: {
        primary_conflict: { t: 'obj', label: 'Главный конфликт', fields: {
          factions: { t: 'idlist', label: 'Фракции (ровно 2, id институций)' },
          resource: { t: 'area', label: 'Из-за чего борьба' },
          stakes: { t: 'area', label: 'Что на карте' },
          irreconcilable_issue: { t: 'area', label: 'Почему неразрешим компромиссом' },
        }},
        secondary_conflicts: { t: 'objlist', label: 'Вторичные конфликты (2–4)', item: {
          id: { t: 'text', label: 'ID', ro: true },
          factions: { t: 'idlist', label: 'Фракции (id институций)' },
          resource: { t: 'area', label: 'Из-за чего борьба' },
          stakes: { t: 'area', label: 'Что на карте' },
        }, title: it => it.resource || it.id },
        latent_conflicts: { t: 'objlist', label: 'Латентные конфликты (≥2)', item: {
          id: { t: 'text', label: 'ID', ro: true },
          description: { t: 'area', label: 'Описание' },
          visibility: { t: 'text', label: 'Видимость (hidden)' },
          activation_conditions: { t: 'list', label: 'Условия активации' },
        }, title: it => it.description || it.id },
      },
    },

    secrets: {
      fields: {
        secrets: { t: 'objlist', label: 'Секреты (3–7)', item: {
          id: { t: 'text', label: 'ID', ro: true },
          truth: { t: 'area', label: 'Правда' },
          known_by: { t: 'idlist', label: 'Кто знает (id институций / public)' },
          reveal_rules: { t: 'obj', label: 'Правила раскрытия', fields: {
            earliest_chapter: { t: 'int', label: 'Раньше главы' },
            foreshadowing_required: { t: 'bool', label: 'Требуется форшадоуинг' },
            partial_revelation: { t: 'bool', label: 'Частичное раскрытие' },
          }},
          reveal_priority: { t: 'float', label: 'Приоритет раскрытия (0..1)' },
        }, title: it => it.truth || it.id },
      },
    },

    characters: {
      fields: {
        characters: { t: 'objlist', label: 'Персонажи (3–7)', item: {
          id: { t: 'text', label: 'ID', ro: true },
          name: { t: 'text', label: 'Имя' },
          age: { t: 'int', label: 'Возраст' },
          role_in_conflict: { t: 'text', label: 'Роль в конфликте' },
          side: { t: 'text', label: 'Сторона (id институции или neutral)' },
          personal_stake: { t: 'area', label: 'Личная ставка' },
          contradiction: { t: 'area', label: 'Противоречие' },
          goals: { t: 'list', label: 'Цели' },
          secrets: { t: 'idlist', label: 'Знает секреты (id)' },
          knowledge: { t: 'list', label: 'Знание' },
          skills: { t: 'list', label: 'Навыки' },
          flaws: { t: 'list', label: 'Изъяны' },
          backstory_wound: { t: 'area', label: 'Прошлая рана' },
          defense_mechanism: { t: 'area', label: 'Защитный механизм' },
          arc_potential: { t: 'text', label: 'Потенциал арки' },
          initial_abilities: { t: 'objlist', label: 'Стартовые способности (макс 3)', item: {
            name: { t: 'text', label: 'Название' },
            level: { t: 'int', label: 'Уровень (1..3)' },
            description: { t: 'area', label: 'Описание' },
          }, title: it => it.name },
        }, title: it => it.name || it.id },
      },
    },

    relations: {
      fields: {
        relations: { t: 'objlist', label: 'Связи', item: {
          from: { t: 'text', label: 'От (ID)', ro: true },
          to: { t: 'text', label: 'К (ID)', ro: true },
          type: { t: 'enum', label: 'Тип', options: ENUM.rel_type },
          history: { t: 'area', label: 'Предыстория отношений' },
          tension: { t: 'int', label: 'Напряжение (0..100)' },
          secret: { t: 'text', label: 'Общий секрет (id)' },
        }, title: it => (it.from && it.to) ? `${it.from} → ${it.to}` : '' },
      },
    },

    story_structure: {
      fields: {
        total_chapters: { t: 'int', label: 'Всего глав' },
        story_beats: { t: 'objlist', label: 'Биты (Save the Cat)', item: {
          key: { t: 'enum', label: 'Ключ', options: ENUM.beat_key },
          chapter: { t: 'int', label: 'Глава' },
          description: { t: 'area', label: 'Описание' },
        }, title: it => it.key },
        acts: { t: 'objlist', label: 'Акты', item: {
          num: { t: 'int', label: '№ акта' },
          purpose: { t: 'area', label: 'Задача акта' },
          chapters: { t: 'intlist', label: 'Главы акта' },
        }, title: it => (it.num != null) ? `${tr('Акт')} ${it.num}` : '' },
        pov_threads: { t: 'objlist', label: 'POV-нити', item: {
          id: { t: 'text', label: 'ID', ro: true },
          character: { t: 'text', label: 'Персонаж (ID)' },
          chapters: { t: 'intlist', label: 'Главы' },
          style_anchor: { t: 'area', label: 'Голос нити' },
        }, title: it => it.character || it.id },
        character_arcs: { t: 'objlist', label: 'Арки персонажей', item: {
          char: { t: 'text', label: 'Персонаж (ID)', ro: true },
          starts_at: { t: 'area', label: 'Исходная ложная вера' },
          turns_at: { t: 'obj', label: 'Перелом', fields: {
            chapter: { t: 'int', label: 'Глава' },
            event: { t: 'area', label: 'Событие' },
          }},
          ends_at: { t: 'obj', label: 'Финал арки', fields: {
            chapter: { t: 'int', label: 'Глава' },
            state: { t: 'area', label: 'Новое состояние' },
          }},
        }, title: it => it.char },
        reveal_schedule: { t: 'objlist', label: 'Расписание раскрытий', item: {
          secret_id: { t: 'text', label: 'Секрет (ID)', ro: true },
          reveal_at_chapter: { t: 'int', label: 'Раскрытие в главе' },
          foreshadow_from: { t: 'int', label: 'Форшадоуинг с главы' },
        }, title: it => it.secret_id },
        tension_curve: { t: 'floatlist', label: 'Кривая напряжения (0..1, по главе на значение)' },
      },
    },

    chapter_outline: {
      fields: {
        chapters: { t: 'objlist', label: 'Главы', item: {
          num: { t: 'int', label: '№ главы', ro: true },
          title: { t: 'text', label: 'Название' },
          pov: { t: 'text', label: 'POV (ID персонажа)' },
          act: { t: 'int', label: 'Акт' },
          purpose: { t: 'area', label: 'Драматургическая задача' },
          location: { t: 'text', label: 'Локация (ID)' },
          word_target: { t: 'int', label: 'Целевой объём' },
          tension_target: { t: 'float', label: 'Целевое напряжение (0..1)' },
          time_of_day: { t: 'text', label: 'Время суток' },
          mood: { t: 'text', label: 'Настроение' },
          key_objects: { t: 'list', label: 'Ключевые предметы' },
          characters_present: { t: 'idlist', label: 'Персонажи в главе (ID)' },
          events: { t: 'idlist', label: 'События (ID)' },
          secrets_touched: { t: 'list', label: 'Затронутые секреты (ID)' },
          new_events_expected: { t: 'int', label: 'Новых событий ожидается' },
          beats: { t: 'objlist', label: 'Сцены (ровно 5)', item: {
            scene: { t: 'int', label: '№ сцены', ro: true },
            word_target: { t: 'int', label: 'Объём сцены' },
            action_chain: { t: 'list', label: 'Цепочка действий (микрособытия)' },
            result: { t: 'area', label: 'Результат сцены' },
          }, title: it => `${tr('Сцена')} ${it.scene != null ? it.scene : '?'}` },
        }, title: it => `№${it.num != null ? it.num : '?'} — ${it.title || ''}` },
      },
    },
  };

  /* ── DOM-хелперы ───────────────────────────────────────────── */
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  /* Значение по умолчанию для поля, которого нет в рабочей копии:
     скаляры — null (валидатор стадии явно сообщит о проблеме),
     контейнеры — пустые (форма даёт их заполнить). */
  function defaultValue(spec) {
    switch (spec.t) {
      case 'obj': return {};
      case 'objlist': return [];
      case 'list': case 'idlist': case 'intlist': case 'floatlist': return [];
      default: return null;
    }
  }

  function parseScalar(spec, raw) {
    if (spec.t === 'int' || spec.t === 'float') {
      const s = String(raw == null ? '' : raw).trim();
      if (!s) return null;
      const n = spec.t === 'int' ? parseInt(s, 10) : parseFloat(s.replace(',', '.'));
      return Number.isFinite(n) ? n : null;
    }
    return raw;
  }

  function parseList(spec, raw) {
    const s = String(raw == null ? '' : raw);
    if (spec.t === 'list') {
      return s.split('\n').map(x => x.trim()).filter(Boolean);
    }
    // idlist / intlist / floatlist — значения через запятую
    const parts = s.split(',').map(x => x.trim()).filter(Boolean);
    if (spec.t === 'idlist') return parts;
    return parts
      .map(x => parseFloat(x.replace(',', '.')))
      .filter(x => Number.isFinite(x));
  }

  /* Построить контрол для spec и привязать его к obj[key] */
  function control(spec, obj, key) {
    // Поля, которых нет в рабочей копии, инициализируются по типу;
    // существующие null не трогаем — валидатор сообщит о пустом поле.
    if (obj[key] === undefined) obj[key] = defaultValue(spec);
    const cur = obj[key];
    const wrap = el('div', 'se-field');

    let input;
    switch (spec.t) {
      case 'obj':
        wrap.appendChild(el('div', 'se-obj-label', tr(spec.label)));
        const inner = el('div', 'se-obj');
        renderFields(inner, spec.fields, cur || (obj[key] = {}));
        wrap.appendChild(inner);
        return wrap;
      case 'objlist':
        wrap.appendChild(el('div', 'se-obj-label',
          tr(spec.label) + ` — ${(cur || []).length}`));
        wrap.appendChild(renderObjList(spec, obj, key));
        return wrap;
      case 'bool': {
        input = el('input');
        input.type = 'checkbox';
        input.checked = !!cur;
        input.addEventListener('change', () => { obj[key] = input.checked; });
        break;
      }
      case 'enum': {
        input = el('select');
        const opts = (spec.options || []).slice();
        if (cur != null && !opts.includes(cur)) opts.unshift(cur);
        if (!opts.length) opts.push('');
        opts.forEach(o => {
          const op = el('option', null, o);
          op.value = o;
          input.appendChild(op);
        });
        input.value = cur == null ? '' : cur;
        input.addEventListener('change', () => { obj[key] = input.value; });
        break;
      }
      case 'list':
        input = el('textarea');
        input.rows = Math.min(8, Math.max(2, (cur || []).length + 1));
        input.value = (cur || []).join('\n');
        input.addEventListener('input', () => { obj[key] = parseList(spec, input.value); });
        break;
      case 'idlist': case 'intlist': case 'floatlist':
        input = el('input');
        input.type = 'text';
        input.value = (cur || []).join(', ');
        input.addEventListener('input', () => { obj[key] = parseList(spec, input.value); });
        break;
      case 'area':
        input = el('textarea');
        input.rows = 2;
        input.value = cur == null ? '' : cur;
        input.addEventListener('input', () => { obj[key] = input.value; });
        break;
      case 'int': case 'float':
        input = el('input');
        input.type = 'text';
        input.inputMode = 'numeric';
        input.value = cur == null ? '' : cur;
        input.addEventListener('input', () => { obj[key] = parseScalar(spec, input.value); });
        break;
      default: // text
        input = el('input');
        input.type = 'text';
        input.value = cur == null ? '' : cur;
        input.addEventListener('input', () => { obj[key] = input.value; });
    }

    if (spec.ro) { input.readOnly = true; input.classList.add('se-ro'); }
    const lab = el('label', 'se-label', tr(spec.label || key));
    wrap.appendChild(lab);
    wrap.appendChild(input);
    return wrap;
  }

  function renderFields(container, fields, obj) {
    for (const [key, spec] of Object.entries(fields)) {
      container.appendChild(control(spec, obj, key));
    }
  }

  const TITLE_KEYS = ['name', 'title', 'truth', 'statement', 'key',
                      'description', 'char', 'resource', 'location'];

  function itemTitle(spec, it, i) {
    if (spec.title) {
      const t = spec.title(it);
      if (t) return t;
    }
    for (const k of TITLE_KEYS) {
      if (it && typeof it[k] === 'string' && it[k]) return it[k];
    }
    return `#${i + 1}`;
  }

  function renderObjList(spec, owner, key) {
    const box = el('div', 'se-objlist');
    const arr = owner[key];
    if (!Array.isArray(arr)) return box;

    arr.forEach((it, i) => {
      if (it == null || typeof it !== 'object') return;
      const card = el('details', 'se-card');
      const sum = el('summary', 'se-card-head');
      sum.appendChild(el('span', 'se-card-title',
        itemTitle(spec, it, i)));
      sum.appendChild(el('span', 'se-card-num', `#${i + 1}`));
      card.appendChild(sum);
      const body = el('div', 'se-card-body');
      renderFields(body, spec.item, it);
      card.appendChild(body);
      box.appendChild(card);
    });
    return box;
  }

  /* ── Модалка ────────────────────────────────────────────────── */
  const modal = document.getElementById('stage-edit-modal');
  const titleEl = document.getElementById('stage-edit-title');
  const formEl = document.getElementById('stage-edit-form');
  const errBox = document.getElementById('stage-edit-errors');
  const statusEl = document.getElementById('stage-edit-status');
  const saveBtn = document.getElementById('stage-edit-save');
  if (!modal || !formEl || !saveBtn) return;

  let work = null;      // рабочая копия content_json
  let curStage = null;  // редактируемая стадия
  let busy = false;

  function openModal() { modal.style.display = ''; }
  function closeModal() {
    modal.style.display = 'none';
    formEl.innerHTML = '';
    errBox.style.display = 'none';
    errBox.innerHTML = '';
    statusEl.textContent = '';
    work = null; curStage = null;
  }

  function showErrors(list) {
    errBox.innerHTML = '';
    (Array.isArray(list) ? list : [list]).forEach(x => {
      errBox.appendChild(el('div', 'se-err-line', '✗ ' + x));
    });
    errBox.style.display = '';
    errBox.scrollIntoView({ block: 'nearest' });
  }

  async function open(stage) {
    if (busy) return;
    const r = await fetch(`/api/pipeline/${encodeURIComponent(stage)}/edit`);
    if (r.status === 409) {
      const d = await r.json().catch(() => ({}));
      UI.toast(d.detail || tr('Стадия больше не редактируема'), 'error');
      refresh();
      return;
    }
    if (!r.ok) {
      UI.toast(`HTTP ${r.status}`, 'error');
      return;
    }
    const d = await r.json().catch(() => null);
    if (!d || !d.content) {
      UI.toast(tr('У стадии нет результата в базе'), 'error');
      return;
    }
    curStage = stage;
    work = JSON.parse(JSON.stringify(d.content));

    titleEl.textContent =
      `${tr('Редактирование')}: ${tr(STAGE_TITLES[stage] || stage)}`;
    formEl.innerHTML = '';
    renderFields(formEl, SPECS[stage].fields, work);
    errBox.style.display = 'none';
    statusEl.textContent = '';
    openModal();
  }

  async function save() {
    if (busy || !work || !curStage) return;
    busy = true;
    saveBtn.disabled = true;
    statusEl.textContent = '…';
    try {
      const r = await fetch(
        `/api/pipeline/${encodeURIComponent(curStage)}/edit`,
        { method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(work) });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        showErrors(d.detail || `HTTP ${r.status}`);
        statusEl.textContent = '';
        return;
      }
      UI.toast(tr('Стадия обновлена'), 'ok');
      closeModal();
    } catch (err) {
      showErrors(tr('Ошибка сети: {msg}', { msg: err.message }));
      statusEl.textContent = '';
    } finally {
      busy = false;
      saveBtn.disabled = false;
    }
  }

  saveBtn.addEventListener('click', save);

  /* ── Видимость кнопки ✏: только на последней выполненной стадии ── */
  function lastDoneStage() {
    let last = null;
    document.querySelectorAll(
      '#stages-phase1 li[data-stage], #stages-phase2 li[data-stage]')
      .forEach(li => {
        const st = li.querySelector('.status');
        if (st && st.textContent.trim() === 'done') last = li.dataset.stage;
      });
    return last;
  }

  function refresh() {
    const target = lastDoneStage();
    document.querySelectorAll('button.stage-edit').forEach(btn => {
      btn.style.visibility =
        (btn.dataset.stage === target) ? 'visible' : 'hidden';
    });
  }
  window.StageEditRefresh = refresh;

  document.querySelectorAll('button.stage-edit').forEach(btn => {
    btn.addEventListener('click', () => open(btn.dataset.stage));
  });

  // Первичная расстановка: по статусам, отрендеренным сервером.
  refresh();
})();
